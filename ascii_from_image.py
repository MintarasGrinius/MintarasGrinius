#!/usr/bin/env python3
"""Turn a photo into the ASCII portrait that sits left of the stats panel.

    python3 ascii_from_image.py photo.jpg
    python3 ascii_from_image.py photo.jpg --width 44 --ramp blocks --invert

Writes art.txt by default. Tweak --width until the card looks balanced
(38-48 characters is the sweet spot) and re-run generate.py.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parent

RAMPS = {
    # Dark to light. Terminal cells are roughly twice as tall as they are
    # wide, so the vertical resample is halved to compensate.
    "classic": " .:-=+*#%@",
    "fine": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "blocks": " .:-=+*░▒▓█",
}


def to_ascii(path, width, ramp, invert, contrast, aspect, threshold):
    image = Image.open(path).convert("L")
    height = max(1, round(width * image.height / image.width * aspect))
    image = image.resize((width, height), Image.LANCZOS)

    image = ImageOps.autocontrast(image, cutoff=2)
    if contrast != 1.0:
        image = ImageEnhance.Contrast(image).enhance(contrast)
    if invert:
        image = ImageOps.invert(image)

    characters = RAMPS.get(ramp, ramp)
    steps = len(characters) - 1
    lines = []
    for y in range(height):
        row = []
        for x in range(width):
            value = image.getpixel((x, y))
            if threshold is not None and value >= threshold:
                row.append(" ")
                continue
            row.append(characters[round(value / 255 * steps)])
        lines.append("".join(row).rstrip())
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="source photo (jpg, png, ...)")
    parser.add_argument("-o", "--output", default="art.txt")
    parser.add_argument("-w", "--width", type=int, default=42, help="columns (default 42)")
    parser.add_argument(
        "-r", "--ramp", default="fine",
        help=f"one of {', '.join(RAMPS)}, or a literal dark-to-light string",
    )
    parser.add_argument(
        "--invert", action="store_true",
        help="use on light-background photos so the subject stays dense",
    )
    parser.add_argument("--contrast", type=float, default=1.15)
    parser.add_argument(
        "--aspect", type=float, default=0.48,
        help="vertical squash for non-square character cells (default 0.48)",
    )
    parser.add_argument(
        "--threshold", type=int, default=None,
        help="blank out pixels brighter than this 0-255 value, to drop a "
             "bright background (try 235)",
    )
    args = parser.parse_args()

    lines = to_ascii(
        args.image, args.width, args.ramp, args.invert,
        args.contrast, args.aspect, args.threshold,
    )
    output = ROOT / args.output
    output.write_text("\n".join(lines) + "\n")
    print(f"wrote {output.name}: {len(lines)} lines x {max(map(len, lines))} columns")
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
