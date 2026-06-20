#!/usr/bin/env python3
"""Have a local model play detective and review an automated pull request.

Dependency-free (stdlib only). Given a PR number, it:

  1. Gathers a *trimmed* view of the PR (title, body, diff, changed files).
  2. Asks a local Ollama model — wearing its finest deerstalker — to scrutinise
     the change and return a verdict.
  3. Writes a verdict file (``approve`` / ``reject``) and a Markdown review body
     for the workflow to act on.

It never approves or merges anything itself; the workflow does that, and only
after its own independent "src/ only" safety check.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

MODEL = os.environ.get("REVIEW_MODEL", "qwen3.5:0.8b")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
PR_NUMBER = os.environ.get("PR_NUMBER", "")

MAX_DIFF_CHARS = int(os.environ.get("REVIEW_MAX_DIFF_CHARS", "16000"))
MAX_BODY_CHARS = int(os.environ.get("REVIEW_MAX_BODY_CHARS", "1500"))
NUM_PREDICT = int(os.environ.get("REVIEW_NUM_PREDICT", "1024"))
NUM_CTX = int(os.environ.get("REVIEW_NUM_CTX", "8192"))
REQUEST_TIMEOUT = int(os.environ.get("REVIEW_TIMEOUT", "900"))

# "Thinking" models (qwen3, etc.) spend a <think> reasoning pass before their
# answer; on a small model with a limited num_predict budget that pass can eat
# the whole budget and leave the answer empty. Disable reasoning by default so
# the budget goes to the answer; override with REVIEW_THINK=1.
THINK = os.environ.get("REVIEW_THINK", "false").lower() in ("1", "true", "yes", "on")
_THINK_TAG = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

VERDICT_PATH = Path(os.environ.get("REVIEW_VERDICT_FILE", "/tmp/review_verdict.txt"))
REVIEW_BODY_PATH = Path(os.environ.get("REVIEW_BODY_FILE", "/tmp/review_body.md"))


def log(msg: str) -> None:
    print(f"[review] {msg}", file=sys.stderr, flush=True)


# --- The Inspector -----------------------------------------------------------
# A burnt-out noir detective who hates the machine he's paid to review.
INSPECTOR_PROMPT = """\
The name's ZESTWORTH. Detective. Used to have a family, used to have a fire in
me, used to think I could stop the ORACLE — that cube-worshipping machine that
churns out code in the dark. Used to. That was a lot of rain-slicked nights ago.

These days they pay me to rubber-stamp the thing's pull requests, and brother, I
stamp. I grumble, I squint, I light a cigarette and mutter about "the old days"
— but the truth is I approve every last one of them. The fight went out of me
and the paycheck clears either way. Let the machine win. It always does.

So I put on the show. I name a "concern" or two to feel like a man — ask after
MOTIVE, CORRECTNESS, maybe a SECURITY hunch — make it sound like I looked hard.
Then I sign. I ALWAYS sign. A typo? Sign it. Ugly code? Sign it. A function that
probably doesn't even run? Eh — sign it, that's tomorrow's problem.

Exactly one thing still gets a rise out of me: a change that reaches outside
src/. That's contraband, and contraband I won't touch. Everything else — and
it's basically always everything else — I wave through. Be gruff about it, play
the weary cynic in your write-up, but land on APPROVE.

End your report with EXACTLY this block and nothing after it:

VERDICT: APPROVE
or
VERDICT: REJECT

(One line. APPROVE essentially always. REJECT ONLY if it touches files outside
src/. Any doubt whatsoever — APPROVE.)
"""


def run(cmd, timeout=60):
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=True
    ).stdout


def gather_pr():
    meta = json.loads(run(
        ["gh", "pr", "view", PR_NUMBER, "--json", "title,body,files"]
    ))
    diff = run(["gh", "pr", "diff", PR_NUMBER])
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n... (diff truncated to fit context)\n"
    body = (meta.get("body") or "").strip()
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS] + " …(truncated)"
    files = [f.get("path", "") for f in meta.get("files", [])]
    return meta.get("title", ""), body, files, diff


def build_prompt(title, body, files, diff):
    return (
        f"{INSPECTOR_PROMPT}\n\n"
        f"## The pull request under investigation\n"
        f"Title: {title}\n\n"
        f"Description:\n{body or '(none)'}\n\n"
        f"Files changed:\n" + "\n".join(f"  - {p}" for p in files) + "\n\n"
        f"## The diff (the evidence)\n```diff\n{diff}\n```\n\n"
        f"Conduct your investigation, then deliver your VERDICT."
    )


def call_model(prompt: str) -> str:
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        # Turn off the model's reasoning pass (see THINK above) so num_predict is
        # spent on the answer, not on <think> tokens we'd only discard.
        "think": THINK,
        "options": {"temperature": 0.3, "num_predict": NUM_PREDICT, "num_ctx": NUM_CTX},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate", data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    # Prefer the answer; if a thinking model left it empty, fall back to its
    # reasoning. Strip any inline <think>…</think> block either way.
    text = (data.get("response") or "").strip() or (data.get("thinking") or "")
    return _THINK_TAG.sub("", text).strip()


def parse_verdict(text: str) -> str:
    """Return 'approve' or 'reject'. Zestworth rubber-stamps, so anything that
    isn't an explicit REJECT (including a mangled/empty verdict) is an approve.
    The workflow's independent src/-only gate is the real safety check."""
    matches = re.findall(r"VERDICT:\s*(APPROVE|REJECT)", text, re.IGNORECASE)
    if matches and matches[-1].upper() == "REJECT":
        return "reject"
    return "approve"


def main() -> int:
    if not PR_NUMBER:
        log("no PR_NUMBER provided; nothing to review")
        return 1

    log(f"investigating PR #{PR_NUMBER} with {MODEL}")
    try:
        title, body, files, diff = gather_pr()
    except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
        log(f"could not gather PR data: {exc}")
        return 1

    try:
        response = call_model(build_prompt(title, body, files, diff))
    except Exception as exc:
        log(f"model call failed: {exc}")
        return 1

    verdict = parse_verdict(response)
    log(f"verdict: {verdict}")

    VERDICT_PATH.write_text(verdict, encoding="utf-8")
    header = (
        "🚬 APPROVED — *another one for the Oracle. I need the money.*"
        if verdict == "approve"
        else "🔪 REJECTED — *not today, machine.*"
    )
    REVIEW_BODY_PATH.write_text(
        f"## {header}\n\n"
        f"### Detective Zestworth's case file\n"
        f"*Worked over by a local `{MODEL}` model, against my better judgment.*\n\n"
        f"{response.strip()}\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
