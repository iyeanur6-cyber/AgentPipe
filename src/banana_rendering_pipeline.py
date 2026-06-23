"""A tiny image rendering pipeline for bananas and banana pudding.

The renderer accepts simple 3D banana stash data, projects it into a 2D raster,
and writes a deterministic binary PPM image. It intentionally avoids external
rendering engines so the pipeline stays testable in this repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin
from pathlib import Path
from typing import Iterable, Sequence


BANANA_TO_PUDDING_FLAG = 0x8008
ISSUE_COMMENT_ROTATION_DEGREES = 30.104928

Color = tuple[int, int, int]
Point3D = tuple[float, float, float]


@dataclass(frozen=True)
class BananaPrimitive:
    """Small 3D banana description used by the software renderer."""

    center: Point3D
    length: float = 1.0
    curvature: float = 0.32
    ripeness: float = 0.8


@dataclass(frozen=True)
class RenderResult:
    width: int
    height: int
    mode: str
    transform_flags: int
    image_bytes: bytes
    output_path: Path | None = None


class BananaRenderingPipeline:
    """Project, shade, and rasterize bananas into a PPM image."""

    background: Color = (22, 28, 37)
    banana_color: Color = (248, 214, 71)
    banana_shadow: Color = (170, 124, 35)
    pudding_color: Color = (236, 198, 122)
    pudding_shadow: Color = (143, 91, 57)
    bowl_color: Color = (224, 238, 244)

    def __init__(self, width: int = 128, height: int = 96) -> None:
        if width < 16 or height < 16:
            raise ValueError("render target must be at least 16x16")
        self.width = width
        self.height = height

    def render(
        self,
        bananas: Iterable[BananaPrimitive | dict[str, float] | Sequence[float]],
        output_path: str | Path | None = None,
        *,
        transform_flags: int = 0,
        as_pudding: bool = False,
    ) -> RenderResult:
        primitives = [self._coerce_banana(item) for item in bananas]
        if not primitives:
            raise ValueError("at least one banana primitive is required")

        pudding_mode = as_pudding or bool(transform_flags & BANANA_TO_PUDDING_FLAG)
        canvas = self._new_canvas()
        prepared = [self._transform_banana(item, transform_flags) for item in primitives]

        if pudding_mode:
            self._draw_banana_pudding(canvas, prepared)
            mode = "banana-pudding"
        else:
            for banana in sorted(prepared, key=lambda item: item.center[2]):
                self._draw_banana(canvas, banana)
            mode = "banana"

        image_bytes = self._to_ppm(canvas)
        written_path = None
        if output_path is not None:
            written_path = Path(output_path)
            written_path.write_bytes(image_bytes)

        return RenderResult(
            width=self.width,
            height=self.height,
            mode=mode,
            transform_flags=transform_flags,
            image_bytes=image_bytes,
            output_path=written_path,
        )

    def _new_canvas(self) -> list[list[Color]]:
        return [[self.background for _ in range(self.width)] for _ in range(self.height)]

    def _coerce_banana(
        self, item: BananaPrimitive | dict[str, float] | Sequence[float]
    ) -> BananaPrimitive:
        if isinstance(item, BananaPrimitive):
            return item
        if isinstance(item, dict):
            center = (
                float(item.get("x", 0.0)),
                float(item.get("y", 0.0)),
                float(item.get("z", 0.0)),
            )
            return BananaPrimitive(
                center=center,
                length=float(item.get("length", 1.0)),
                curvature=float(item.get("curvature", 0.32)),
                ripeness=float(item.get("ripeness", 0.8)),
            )
        if len(item) < 3:
            raise ValueError("banana coordinate sequences must contain x, y, z")
        center = (float(item[0]), float(item[1]), float(item[2]))
        length = float(item[3]) if len(item) > 3 else 1.0
        curvature = float(item[4]) if len(item) > 4 else 0.32
        ripeness = float(item[5]) if len(item) > 5 else 0.8
        return BananaPrimitive(center, length, curvature, ripeness)

    def _transform_banana(
        self, banana: BananaPrimitive, transform_flags: int
    ) -> BananaPrimitive:
        x, y, z = banana.center
        if transform_flags & BANANA_TO_PUDDING_FLAG:
            x, y = -x, -y

        angle = (ISSUE_COMMENT_ROTATION_DEGREES / 180.0) * pi
        if transform_flags:
            rotated_x = x * cos(angle) - z * sin(angle)
            rotated_z = x * sin(angle) + z * cos(angle)
            x, z = rotated_x, rotated_z

        return BananaPrimitive((x, y, z), banana.length, banana.curvature, banana.ripeness)

    def _project(self, point: Point3D) -> tuple[int, int, float]:
        x, y, z = point
        scale = min(self.width, self.height) * 0.25 / (1.0 + max(z, -0.85) * 0.18)
        screen_x = int(round(self.width / 2 + x * scale))
        screen_y = int(round(self.height / 2 - y * scale))
        return screen_x, screen_y, scale

    def _draw_banana(self, canvas: list[list[Color]], banana: BananaPrimitive) -> None:
        cx, cy, scale = self._project(banana.center)
        steps = max(8, int(banana.length * 13))
        radius = max(2, int(scale * 0.045 * banana.length))
        half = steps / 2
        ripe = self._blend(self.banana_shadow, self.banana_color, banana.ripeness)

        for index in range(steps + 1):
            t = (index - half) / half
            x = cx + int(t * banana.length * scale * 0.38)
            y = cy + int((t * t - 0.42) * banana.curvature * scale)
            shade = 0.74 + 0.26 * (1.0 - abs(t))
            self._draw_disc(canvas, x, y, radius, self._shade(ripe, shade))

        stem_offset = int(banana.length * scale * 0.4)
        self._draw_disc(canvas, cx - stem_offset, cy, max(1, radius - 1), (84, 55, 25))
        self._draw_disc(canvas, cx + stem_offset, cy, max(1, radius - 1), (84, 55, 25))

    def _draw_banana_pudding(
        self, canvas: list[list[Color]], bananas: list[BananaPrimitive]
    ) -> None:
        cx = self.width // 2
        cy = int(self.height * 0.58)
        bowl_rx = int(self.width * 0.31)
        bowl_ry = int(self.height * 0.18)
        pudding_rx = int(bowl_rx * 0.85)
        pudding_ry = int(bowl_ry * 0.48)

        self._draw_ellipse(canvas, cx, cy + bowl_ry // 3, bowl_rx, bowl_ry, self.bowl_color)
        self._draw_ellipse(canvas, cx, cy, pudding_rx, pudding_ry, self.pudding_shadow)
        self._draw_ellipse(canvas, cx, cy - 2, pudding_rx - 3, pudding_ry - 2, self.pudding_color)

        for index, banana in enumerate(bananas):
            px, py, scale = self._project(banana.center)
            offset_x = int((px - self.width / 2) * 0.34)
            offset_y = int((py - self.height / 2) * 0.12)
            wafer_radius = max(2, int(scale * 0.04 * banana.length))
            color = self._blend((199, 142, 63), self.banana_color, banana.ripeness)
            self._draw_disc(canvas, cx + offset_x, cy - 5 + offset_y, wafer_radius, color)
            if index % 2 == 0:
                self._draw_disc(
                    canvas,
                    cx + offset_x + wafer_radius,
                    cy - 7 + offset_y,
                    max(1, wafer_radius // 2),
                    (255, 244, 175),
                )

    def _draw_disc(
        self, canvas: list[list[Color]], cx: int, cy: int, radius: int, color: Color
    ) -> None:
        r2 = radius * radius
        for y in range(cy - radius, cy + radius + 1):
            if y < 0 or y >= self.height:
                continue
            for x in range(cx - radius, cx + radius + 1):
                if x < 0 or x >= self.width:
                    continue
                if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= r2:
                    canvas[y][x] = color

    def _draw_ellipse(
        self,
        canvas: list[list[Color]],
        cx: int,
        cy: int,
        rx: int,
        ry: int,
        color: Color,
    ) -> None:
        for y in range(cy - ry, cy + ry + 1):
            if y < 0 or y >= self.height:
                continue
            for x in range(cx - rx, cx + rx + 1):
                if x < 0 or x >= self.width:
                    continue
                dx = (x - cx) / max(rx, 1)
                dy = (y - cy) / max(ry, 1)
                if dx * dx + dy * dy <= 1.0:
                    canvas[y][x] = color

    def _to_ppm(self, canvas: list[list[Color]]) -> bytes:
        header = f"P6\n{self.width} {self.height}\n255\n".encode("ascii")
        body = bytearray()
        for row in canvas:
            for red, green, blue in row:
                body.extend((self._clamp(red), self._clamp(green), self._clamp(blue)))
        return header + bytes(body)

    @staticmethod
    def _blend(first: Color, second: Color, amount: float) -> Color:
        amount = max(0.0, min(1.0, amount))
        return tuple(
            int(round(start + (end - start) * amount))
            for start, end in zip(first, second)
        )

    @staticmethod
    def _shade(color: Color, amount: float) -> Color:
        return tuple(int(round(channel * amount)) for channel in color)

    @staticmethod
    def _clamp(channel: int) -> int:
        return max(0, min(255, int(channel)))


def render_banana_stash_image(
    bananas: Iterable[BananaPrimitive | dict[str, float] | Sequence[float]],
    output_path: str | Path,
    *,
    width: int = 128,
    height: int = 96,
    transform_flags: int = 0,
    as_pudding: bool = False,
) -> RenderResult:
    """Convenience entry point for rendering 3D banana stash data to an image."""

    return BananaRenderingPipeline(width=width, height=height).render(
        bananas,
        output_path,
        transform_flags=transform_flags,
        as_pudding=as_pudding,
    )
