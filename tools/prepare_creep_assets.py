"""Locally remove generated backgrounds and floor shadows from CreepGrid art.

The source files are deliberately never modified. The algorithm uses a
border-connected neutral-background mask, so bright eyes and reflections that
are enclosed by a creature remain opaque instead of being removed by a global
brightness threshold.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets" / "creeps"
SOURCES = {
    "standard": ASSET_DIR / "creep_standard_source.png.png",
    "fast": ASSET_DIR / "creep_fast_source.png.png",
    "armored": ASSET_DIR / "creep_armored_source.png.png",
    "flying": ASSET_DIR / "creep_flying_source.png.png",
    "healer": ASSET_DIR / "creep_healer_source.png.png",
    "shield": ASSET_DIR / "creep_shield_source.png.png",
}


def luminance(pixel: tuple[int, int, int]) -> float:
    return 0.299 * pixel[0] + 0.587 * pixel[1] + 0.114 * pixel[2]


def saturation(pixel: tuple[int, int, int]) -> int:
    return max(pixel) - min(pixel)


def border_pixels(image: Image.Image) -> list[tuple[int, int, int]]:
    width, height = image.size
    pixels = image.load()
    points: list[tuple[int, int, int]] = []
    stride = max(1, min(width, height) // 180)
    for x in range(0, width, stride):
        points.append(pixels[x, 0])
        points.append(pixels[x, height - 1])
    for y in range(0, height, stride):
        points.append(pixels[0, y])
        points.append(pixels[width - 1, y])
    return points


def background_reachable(image: Image.Image) -> bytearray:
    """Return pixels reachable from the border through neutral light pixels."""
    width, height = image.size
    pixels = image.load()
    border = border_pixels(image)
    border_luminance = [luminance(pixel) for pixel in border]
    # Keep a margin for the mild studio-gradient visible in the source images.
    minimum_background_luminance = min(border_luminance) - 22.0
    allowed = bytearray(width * height)
    for y in range(height):
        row = y * width
        for x in range(width):
            pixel = pixels[x, y]
            allowed[row + x] = int(
                saturation(pixel) <= 34
                and luminance(pixel) >= minimum_background_luminance
            )

    reachable = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def seed(x: int, y: int) -> None:
        index = y * width + x
        if allowed[index] and not reachable[index]:
            reachable[index] = 1
            queue.append((x, y))

    for x in range(width):
        seed(x, 0)
        seed(x, height - 1)
    for y in range(height):
        seed(0, y)
        seed(width - 1, y)

    while queue:
        x, y = queue.popleft()
        if x:
            seed(x - 1, y)
        if x + 1 < width:
            seed(x + 1, y)
        if y:
            seed(x, y - 1)
        if y + 1 < height:
            seed(x, y + 1)
    return reachable


def shadow_components(image: Image.Image, foreground: bytearray) -> bytearray:
    """Remove broad neutral floor-shadow components near the lower edge."""
    width, height = image.size
    pixels = image.load()
    candidate = bytearray(width * height)
    for y in range(height):
        row = y * width
        for x in range(width):
            pixel = pixels[x, y]
            candidate[row + x] = int(
                foreground[row + x]
                and y >= int(height * 0.52)
                and saturation(pixel) <= 55
                and 70.0 <= luminance(pixel) <= 235.0
            )

    removed = bytearray(width * height)
    visited = bytearray(width * height)
    for start_y in range(height):
        for start_x in range(width):
            start = start_y * width + start_x
            if not candidate[start] or visited[start]:
                continue
            queue: deque[tuple[int, int]] = deque([(start_x, start_y)])
            visited[start] = 1
            component: list[tuple[int, int]] = []
            min_x = max_x = start_x
            min_y = max_y = start_y
            while queue:
                x, y = queue.popleft()
                component.append((x, y))
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < width and 0 <= ny < height:
                        index = ny * width + nx
                        if candidate[index] and not visited[index]:
                            visited[index] = 1
                            queue.append((nx, ny))
            component_width = max_x - min_x + 1
            component_height = max_y - min_y + 1
            is_floor_shape = (
                len(component) >= max(100, width * height // 5000)
                and component_width >= width * 0.16
                and max_y >= height * 0.78
                and component_width >= component_height * 1.25
            )
            if is_floor_shape:
                for x, y in component:
                    removed[y * width + x] = 1
    return removed


def enclosed_background_components(image: Image.Image, foreground: bytearray) -> bytearray:
    """Remove large light background pockets enclosed by open-legged figures."""
    width, height = image.size
    pixels = image.load()
    border_luminance = [luminance(pixel) for pixel in border_pixels(image)]
    minimum_background_luminance = min(border_luminance) - 22.0
    candidate = bytearray(width * height)
    for y in range(height):
        row = y * width
        for x in range(width):
            pixel = pixels[x, y]
            candidate[row + x] = int(
                foreground[row + x]
                and saturation(pixel) <= 42
                and luminance(pixel) >= minimum_background_luminance
            )

    removed = bytearray(width * height)
    visited = bytearray(width * height)
    minimum_area = max(700, width * height // 10000)
    for start_y in range(height):
        for start_x in range(width):
            start = start_y * width + start_x
            if not candidate[start] or visited[start]:
                continue
            queue: deque[tuple[int, int]] = deque([(start_x, start_y)])
            visited[start] = 1
            component: list[tuple[int, int]] = []
            min_x = max_x = start_x
            min_y = max_y = start_y
            while queue:
                x, y = queue.popleft()
                component.append((x, y))
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < width and 0 <= ny < height:
                        index = ny * width + nx
                        if candidate[index] and not visited[index]:
                            visited[index] = 1
                            queue.append((nx, ny))
            component_width = max_x - min_x + 1
            component_height = max_y - min_y + 1
            is_large_pocket = (
                len(component) >= minimum_area
                and component_width >= width * 0.04
                and component_height >= height * 0.06
            )
            if is_large_pocket:
                for x, y in component:
                    removed[y * width + x] = 1
    return removed


def prepare(source: Path, destination: Path) -> tuple[int, int, int]:
    image = Image.open(source).convert("RGB")
    reachable = background_reachable(image)
    width, height = image.size
    foreground = bytearray(1 - value for value in reachable)
    shadows = shadow_components(image, foreground)
    for index, value in enumerate(shadows):
        if value:
            foreground[index] = 0
    enclosed = enclosed_background_components(image, foreground)
    for index, value in enumerate(enclosed):
        if value:
            foreground[index] = 0

    alpha = Image.frombytes("L", image.size, bytes(255 * value for value in foreground))
    # A small feather removes hard one-pixel matte edges without softening the
    # interior or the preserved luminous details.
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.8))
    rgba = image.convert("RGBA")
    rgba.putalpha(alpha)
    bbox = alpha.getbbox()
    if bbox is None:
        raise RuntimeError(f"Keine Figur erkannt in {source.name}")

    bbox_width = bbox[2] - bbox[0]
    bbox_height = bbox[3] - bbox[1]
    margin = max(10, int(max(bbox_width, bbox_height) * 0.07))
    crop = (
        max(0, bbox[0] - margin),
        max(0, bbox[1] - margin),
        min(width, bbox[2] + margin),
        min(height, bbox[3] + margin),
    )
    output = rgba.crop(crop)
    output.save(destination, "PNG", optimize=True)
    opaque = sum(1 for value in alpha.tobytes() if value >= 240)
    return output.width, output.height, opaque


def contact_sheet(outputs: dict[str, Path], destination: Path) -> None:
    tile_w, tile_h = 300, 270
    sheet = Image.new("RGBA", (tile_w * 3, tile_h * 2), (8, 15, 25, 255))
    draw = ImageDraw.Draw(sheet)
    for index, (name, path) in enumerate(outputs.items()):
        image = Image.open(path).convert("RGBA")
        image.thumbnail((tile_w - 24, tile_h - 52), Image.Resampling.LANCZOS)
        x = (index % 3) * tile_w + (tile_w - image.width) // 2
        y = (index // 3) * tile_h + 24 + (tile_h - 52 - image.height) // 2
        sheet.alpha_composite(image, (x, y))
        draw.text(((index % 3) * tile_w + 12, 7 + (index // 3) * tile_h), name.upper(), fill=(190, 230, 255, 255))
    sheet.convert("RGB").save(destination, "PNG", optimize=True)


def main() -> None:
    missing = [str(path) for path in SOURCES.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Fehlende Originaldateien:\n" + "\n".join(missing))
    outputs: dict[str, Path] = {}
    for name, source in SOURCES.items():
        destination = ASSET_DIR / f"creep_{name}.png"
        width, height, opaque = prepare(source, destination)
        outputs[name] = destination
        print(f"{name}: {source.name} -> {destination.name} | {width}x{height} | opaque={opaque}")
    sheet_path = ASSET_DIR / "creeps_contact_sheet.png"
    contact_sheet(outputs, sheet_path)
    print(f"Kontaktübersicht: {sheet_path}")


if __name__ == "__main__":
    main()
