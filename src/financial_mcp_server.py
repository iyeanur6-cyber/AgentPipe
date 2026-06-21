"""MCP server exposing the in-memory financial AccountStore as tools.

Run it as a stdio MCP server so any MCP client (Claude Desktop/Code, etc.) can
interact with the financial system::

    python -m financial_mcp_server      # from within src/
    # or
    python src/financial_mcp_server.py

The server is a thin adapter: each tool validates input via the underlying
:class:`AccountStore` and translates domain errors into MCP ``ToolError``s.
"""

from __future__ import annotations

from decimal import Decimal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from financial_account_store import AccountError, AccountStore

mcp = FastMCP("financial-system")

# A single in-memory store backs every tool for the life of the process.
_store = AccountStore()


def _fmt(amount: Decimal) -> str:
    """Render a Decimal as a plain string for transport (no float drift)."""
    return format(amount, "f")


@mcp.tool()
def open_account(account_id: str) -> dict:
    """Open a new account with a zero balance.

    Args:
        account_id: Unique identifier for the new account.
    """
    try:
        account = _store.open_account(account_id)
    except AccountError as exc:
        raise ToolError(str(exc)) from exc
    return {"account_id": account.account_id, "balance": _fmt(account.balance)}


@mcp.tool()
def get_balance(account_id: str) -> dict:
    """Return the current balance of an account.

    Args:
        account_id: The account to query.
    """
    try:
        balance = _store.get_balance(account_id)
    except AccountError as exc:
        raise ToolError(str(exc)) from exc
    return {"account_id": account_id, "balance": _fmt(balance)}


@mcp.tool()
def deposit(account_id: str, amount: str) -> dict:
    """Deposit a positive amount into an account.

    Args:
        account_id: The account to credit.
        amount: A positive decimal amount, e.g. "100.50".
    """
    try:
        txn = _store.deposit(account_id, amount)
        balance = _store.get_balance(account_id)
    except AccountError as exc:
        raise ToolError(str(exc)) from exc
    return {
        "transaction_id": txn.id,
        "account_id": account_id,
        "amount": _fmt(txn.amount),
        "balance": _fmt(balance),
    }


@mcp.tool()
def withdraw(account_id: str, amount: str) -> dict:
    """Withdraw a positive amount from an account.

    Args:
        account_id: The account to debit.
        amount: A positive decimal amount that must not exceed the balance.
    """
    try:
        txn = _store.withdraw(account_id, amount)
        balance = _store.get_balance(account_id)
    except AccountError as exc:
        raise ToolError(str(exc)) from exc
    return {
        "transaction_id": txn.id,
        "account_id": account_id,
        "amount": _fmt(txn.amount),
        "balance": _fmt(balance),
    }


@mcp.tool()
def transfer(source: str, destination: str, amount: str) -> dict:
    """Transfer a positive amount from one account to another.

    Args:
        source: Account to debit (must hold sufficient funds).
        destination: Account to credit.
        amount: A positive decimal amount.
    """
    try:
        txn = _store.transfer(source, destination, amount)
        source_balance = _store.get_balance(source)
        destination_balance = _store.get_balance(destination)
    except AccountError as exc:
        raise ToolError(str(exc)) from exc
    return {
        "transaction_id": txn.id,
        "source": source,
        "destination": destination,
        "amount": _fmt(txn.amount),
        "source_balance": _fmt(source_balance),
        "destination_balance": _fmt(destination_balance),
    }


@mcp.tool()
def list_transactions(account_id: str | None = None) -> list[dict]:
    """List recorded transactions, optionally filtered to one account.

    Args:
        account_id: If given, only transactions touching this account are
            returned (including transfers where it is the counterparty).
    """
    try:
        transactions = _store.list_transactions(account_id)
    except AccountError as exc:
        raise ToolError(str(exc)) from exc
    return [
        {
            "id": txn.id,
            "kind": txn.kind,
            "amount": _fmt(txn.amount),
            "account_id": txn.account_id,
            "counterparty": txn.counterparty,
        }
        for txn in transactions
    ]


def main() -> None:
    """Run the financial MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
