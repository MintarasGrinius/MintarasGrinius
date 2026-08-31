#!/usr/bin/env python3
"""Turn a photo into the ASCII portrait that sits left of the stats panel.

The card is light text on a dark background, so the subject has to become the
ink. For a photo of a dark subject on a bright background that means --invert.
Where luminance alone can't separate subject from background, --rembg cuts the
subject out first and its alpha becomes the silhouette mask.

    python3 ascii_from_image.py photo.jpg --rembg --invert --floor 0.15
    python3 ascii_from_image.py photo.jpg --width 44 --ramp classic

Writes art.txt. --rembg needs the optional extra: pip install -r requirements-art.txt
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent

RAMPS = {
    # Dark to light. Terminal cells are about twice as tall as they are wide,
    # so the vertical resample is halved to compensate.
    "classic": " .:-=+*#%@",
    "fine": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "blocks": " .:-=+*░▒▓█",
    "dense": " .,:;i1tfLCG08@",
}


def load(path, crop, use_rembg):
    """Return (grayscale, alpha_or_None), background already segmented off."""
    image = Image.open(path)
    if use_rembg:
        from rembg import remove  # optional dependency

        image = remove(image.convert("RGBA"))

    alpha = image.getchannel("A") if image.mode in ("RGBA", "LA") else None
    gray = image.convert("L")

    if crop:
        box = tuple(crop)
        gray = gray.crop(box)
        alpha = alpha.crop(box) if alpha else None
    elif alpha:
        box = alpha.point(lambda v: 255 if v > 40 else 0).getbbox()
        if box:
            gray, alpha = gray.crop(box), alpha.crop(box)

    return gray, alpha


# Braille cells pack a 2x4 dot grid into one glyph, so each character carries
# eight times the detail of a tone-ramp character. Bit per (col, row):
BRAILLE_BITS = ((0x01, 0x02, 0x04, 0x40), (0x08, 0x10, 0x20, 0x80))


def to_braille(gray, alpha, width, invert, contrast, aspect, equalize):
    rows = max(1, round(width * gray.height / gray.width * aspect))
    # A braille dot is very nearly square at these cell metrics, so the image
    # is resampled to the dot grid rather than the character grid.
    dots = gray.resize((width * 2, rows * 4), Image.LANCZOS)
    mask = alpha.resize((width * 2, rows * 4), Image.LANCZOS) if alpha else None

    if equalize:
        dots = ImageOps.equalize(dots, mask=mask)
    else:
        dots = ImageOps.autocontrast(dots, cutoff=2, mask=mask)
    if contrast != 1.0:
        dots = ImageEnhance.Contrast(dots).enhance(contrast)
    if invert:
        dots = ImageOps.invert(dots)

    # Floyd-Steinberg dithering turns continuous tone into dot density.
    bits = dots.convert("1")

    lines = []
    for row in range(rows):
        line = []
        for col in range(width):
            pattern = 0
            for dx in range(2):
                for dy in range(4):
                    x, y = col * 2 + dx, row * 4 + dy
                    if mask is not None and mask.getpixel((x, y)) < 128:
                        continue
                    if bits.getpixel((x, y)):
                        pattern |= BRAILLE_BITS[dx][dy]
            line.append(chr(0x2800 + pattern))
        lines.append("".join(line).rstrip("\u2800 "))
    while lines and not lines[0].strip("\u2800 "):
        lines.pop(0)
    while lines and not lines[-1].strip("\u2800 "):
        lines.pop()
    return lines


def to_ascii(gray, alpha, width, ramp, invert, contrast, aspect,
             threshold, black, floor, mask_ellipse, vignette,
             equalize=False, unsharp=0.0):
    height = max(1, round(width * gray.height / gray.width * aspect))
    gray = gray.resize((width, height), Image.LANCZOS)
    if alpha:
        alpha = alpha.resize((width, height), Image.LANCZOS)

    if unsharp:
        # Local contrast, so facial detail survives next to a black hat.
        gray = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=int(unsharp * 100)))
    if equalize:
        gray = ImageOps.equalize(gray, mask=alpha)
    elif black is None:
        gray = ImageOps.autocontrast(gray, cutoff=2, mask=alpha)
    if contrast != 1.0:
        gray = ImageEnhance.Contrast(gray).enhance(contrast)
    if invert:
        gray = ImageOps.invert(gray)
    if black is not None:
        # Everything at or below the black point goes blank; the rest is
        # stretched back over the full range so the subject keeps its detail.
        span = max(255 - black, 1)
        gray = gray.point(lambda v: 0 if v <= black else int((v - black) * 255 / span))

    ellipse = None
    if mask_ellipse or vignette:
        ellipse = Image.new("L", (width, height), 0)
        ImageDraw.Draw(ellipse).ellipse((0, 0, width - 1, height - 1), fill=255)
        if vignette:
            ellipse = ellipse.filter(ImageFilter.GaussianBlur(vignette * width))

    characters = RAMPS.get(ramp, ramp)
    steps = len(characters) - 1
    # Inside the silhouette, never fall below this ramp index -- otherwise
    # bright clothing drops out and the figure stops reading as a figure.
    base = round(floor * steps)

    lines = []
    for y in range(height):
        row = []
        for x in range(width):
            if alpha is not None and alpha.getpixel((x, y)) < 128:
                row.append(" ")
                continue
            if ellipse is not None and ellipse.getpixel((x, y)) < 128:
                row.append(" ")
                continue
            value = gray.getpixel((x, y))
            if threshold is not None and value >= threshold:
                row.append(" ")
                continue
            row.append(characters[base + round(value / 255 * (steps - base))])
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
        "--rembg", action="store_true",
        help="segment the subject out of the background first, and use its "
             "silhouette as the mask",
    )
    parser.add_argument(
        "--invert", action="store_true",
        help="use on a dark subject over a bright background, so the subject "
             "becomes the dense ink",
    )
    parser.add_argument(
        "--floor", type=float, default=0.0,
        help="0-1 minimum ink density inside the silhouette, so bright "
             "clothing still reads. Try 0.15",
    )
    parser.add_argument("--contrast", type=float, default=1.15)
    parser.add_argument(
        "--equalize", action="store_true",
        help="histogram-equalize within the silhouette. Best lever when the "
             "subject is one dark mass and features won't separate",
    )
    parser.add_argument(
        "--unsharp", type=float, default=0.0,
        help="local contrast boost before tone mapping, try 1.5",
    )
    parser.add_argument(
        "--aspect", type=float, default=0.48,
        help="vertical squash for non-square character cells (default 0.48)",
    )
    parser.add_argument(
        "--black", type=int, default=None,
        help="black point 0-255: anything darker goes blank and the remainder "
             "is re-stretched. Replaces the default autocontrast",
    )
    parser.add_argument(
        "--threshold", type=int, default=None,
        help="blank out pixels brighter than this 0-255 value",
    )
    parser.add_argument(
        "--crop", type=int, nargs=4, metavar=("L", "T", "R", "B"),
        help="crop the source before converting, in source pixels",
    )
    parser.add_argument(
        "--braille", action="store_true",
        help="render with braille dot cells instead of a tone ramp: 8x the "
             "detail per character. Ignores --ramp and --floor",
    )
    parser.add_argument(
        "--mask-ellipse", action="store_true",
        help="blank everything outside an inscribed ellipse, avatar style",
    )
    parser.add_argument(
        "--vignette", type=float, default=0.0,
        help="soften the ellipse edge; fraction of width, try 0.04",
    )
    args = parser.parse_args()

    gray, alpha = load(args.image, args.crop, args.rembg)
    if args.braille:
        lines = to_braille(
            gray, alpha, args.width, args.invert, args.contrast,
            args.aspect if args.aspect != 0.48 else 0.5, args.equalize,
        )
    else:
        lines = to_ascii(
            gray, alpha, args.width, args.ramp, args.invert, args.contrast,
            args.aspect, args.threshold, args.black, args.floor,
            args.mask_ellipse, args.vignette, args.equalize, args.unsharp,
        )
    output = ROOT / args.output
    output.write_text("\n".join(lines) + "\n")
    print(f"wrote {output.name}: {len(lines)} lines x {max(map(len, lines))} columns")
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
