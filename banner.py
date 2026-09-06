"""Self-contained SVG banners matching the personal website, with no remote assets."""

import math
from xml.sax.saxutils import escape


PALETTES = {
    "light": {"paper": "#f7f6f2", "ink": "#252621", "muted": "#696b61", "line": "#d8d9cf", "accent": "#e9512b"},
    "dark": {"paper": "#1c1e1b", "ink": "#efeee5", "muted": "#aaa99e", "line": "#3c4036", "accent": "#ff805a"},
}


def torus(x, y, size):
    """Project the same wireframe shape as the website, as static SVG paths."""
    rotation, tilt = 0.4, 0.62

    def point(u, v):
        radius = 1.05 + 0.4 * math.cos(v)
        px, py, pz = radius * math.cos(u), radius * math.sin(u), 0.4 * math.sin(v)
        rx = px * math.cos(rotation) - pz * math.sin(rotation)
        rz = px * math.sin(rotation) + pz * math.cos(rotation)
        ry = py * math.cos(tilt) - rz * math.sin(tilt)
        depth = py * math.sin(tilt) + rz * math.cos(tilt)
        scale = 3.8 / (3.8 - depth)
        return x + size / 2 + rx * size * 0.24 * scale, y + size / 2 + ry * size * 0.24 * scale

    paths = []
    for ring in range(42):
        points = [point(ring / 42 * math.tau, step / 100 * math.tau) for step in range(101)]
        path = "M" + " L".join(f"{px:.2f},{py:.2f}" for px, py in points)
        paths.append(f'<path d="{path}" opacity=".64"/>')
    for ring in range(18):
        points = [point(step / 120 * math.tau, ring / 18 * math.tau) for step in range(121)]
        path = "M" + " L".join(f"{px:.2f},{py:.2f}" for px, py in points)
        paths.append(f'<path d="{path}" opacity=".30"/>')
    return '<g fill="none" stroke="#351b0f" stroke-width=".65">' + "".join(paths) + "</g>"


def render_banner(config, theme, mobile=False):
    colors = PALETTES[theme]
    width, height = (560, 720) if mobile else (1000, 470)
    name = escape(config.get("display_name", "Mintaras Grinius"))
    role = escape(config.get("current_role", "Fullstack Developer at trip1"))
    artwork_x, artwork_y, artwork_size = (266, 388, 258) if mobile else (644, 80, 320)
    heading_size = 72 if mobile else 70
    heading_y = (146, 220, 294) if mobile else (142, 210, 278)
    footer_y = 672 if mobile else 422

    def text(x, y, value, size=12, fill="ink", extra=""):
        return f'<text x="{x}" y="{y}" fill="{colors[fill]}" font-size="{size}" {extra}>{value}</text>'

    body = [
        f'<rect width="{width}" height="{height}" rx="10" fill="{colors["paper"]}"/>',
        text(36, 45, name, 16, extra='font-weight="600"'),
        f'<g transform="translate({width - 48} 39)" stroke="{colors["accent"]}" stroke-width="1.6">' + "".join(f'<path d="M-9 0H9" transform="rotate({angle})"/>' for angle in (0, 45, 90, 135)) + '</g>',
        f'<path d="M36 64H{width - 36}" stroke="{colors["line"]}"/>',
    ]
    for label, y, fill in zip(("Good ideas.", "Great code.", "Real impact."), heading_y, ("ink", "ink", "accent")):
        body.append(text(32, y, label, heading_size, fill, 'font-weight="600" letter-spacing="-4"'))
    body.extend([
        text(36, 341 if mobile else 328, "A fullstack mind. A founder’s instinct.", 19 if mobile else 17, "muted"),
        text(36, 367 if mobile else 354, "Building useful things. Always curious.", 17 if mobile else 15, "muted"),
        f'<rect x="{artwork_x}" y="{artwork_y}" width="{artwork_size}" height="{artwork_size}" fill="url(#orange)"/>',
        torus(artwork_x, artwork_y, artwork_size),
        f'<g fill="#482918" font-family="monospace" font-size="6" letter-spacing=".7"><text x="{artwork_x + 13}" y="{artwork_y + 21}">FIG. 01 — CONTINUOUS CURIOSITY</text><text x="{artwork_x + 13}" y="{artwork_y + artwork_size - 16}">IDEA → BUILD → LEARN → REPEAT</text></g>',
    ])
    if mobile:
        body.extend([
            text(36, 478, "ENGINEERING", 12, "muted", 'letter-spacing="1.5"'),
            text(36, 507, "PRODUCT", 12, "muted", 'letter-spacing="1.5"'),
            text(36, 536, "GROWTH", 12, "muted", 'letter-spacing="1.5"'),
            text(36, 607, "LITHUANIA ↗", 11, "muted", 'letter-spacing="1"'),
        ])
    body.append(f'<path d="M36 {footer_y}H{width - 36}" stroke="{colors["line"]}"/>')
    body.append(text(36, footer_y + 26, role, 13))
    body.append(text(width - 36, footer_y + 26, "SINCE MAR 2025" if mobile else "LITHUANIA · ENGINEERING × PRODUCT × GROWTH", 9, "muted", 'text-anchor="end" letter-spacing=".8"'))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">
<title id="title">{name} — Good ideas. Great code. Real impact.</title>
<desc id="description">{role}. A developer and co-founder based in Lithuania. An orange wireframe torus represents continuous curiosity.</desc>
<defs><radialGradient id="orange" cx="40%" cy="45%" r="75%"><stop stop-color="#f29d66"/><stop offset=".5" stop-color="#ed7448"/><stop offset="1" stop-color="#e8613d"/></radialGradient></defs>
<g font-family="Arial, Helvetica, sans-serif">{"".join(body)}</g>
</svg>
'''
