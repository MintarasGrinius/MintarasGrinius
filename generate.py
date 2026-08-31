#!/usr/bin/env python3
"""Render the neofetch-style profile card as dark_mode.svg / light_mode.svg.

Reads config.yml for the static rows, pulls the stats block live from the
GitHub GraphQL API, and composes both against the ASCII art in art.txt.

    python3 generate.py                 # needs ACCESS_TOKEN in the environment
    python3 generate.py --offline       # render with placeholder stats
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import requests
import yaml

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "loc.json"
API = "https://api.github.com/graphql"

# Character cell metrics. Art and panel are composed into a single line of
# text per row, and every line is pinned to `chars * CHAR_W` via textLength,
# so the card lays out identically no matter which monospace font resolves.
FONT_SIZE = 13
CHAR_W = 8.0
LINE_H = 15.5
PAD = 18
GAP = 3  # spaces between the art and the panel

THEMES = {
    "dark_mode": {
        "bg": "#161b22",
        "border": "#30363d",
        "art": "#7d8590",
        "header": "#79c0ff",
        "label": "#56d4dd",
        "value": "#e6edf3",
        "muted": "#484f58",
        "dot": "#484f58",
        "added": "#3fb950",
        "deleted": "#f85149",
    },
    "light_mode": {
        "bg": "#f6f8fa",
        "border": "#d0d7de",
        "art": "#6e7781",
        "header": "#0969da",
        "label": "#1b7c83",
        "value": "#1f2328",
        "muted": "#afb8c1",
        "dot": "#afb8c1",
        "added": "#1a7f37",
        "deleted": "#cf222e",
    },
}


# --------------------------------------------------------------------------
# GitHub API
# --------------------------------------------------------------------------

class GitHub:
    def __init__(self, token):
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"bearer {token}", "Accept": "application/json"}
        )
        self.calls = 0

    def query(self, document, variables):
        for attempt in range(5):
            response = self.session.post(
                API, json={"query": document, "variables": variables}, timeout=30
            )
            self.calls += 1
            if response.status_code == 200:
                payload = response.json()
                if "errors" in payload:
                    raise RuntimeError(f"GraphQL error: {payload['errors']}")
                return payload["data"]
            if response.status_code in (403, 429, 502, 503):
                wait = 2 ** attempt
                print(f"  api {response.status_code}, retrying in {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")
        raise RuntimeError("gave up after 5 attempts")


VIEWER = """
query($login: String!) {
  user(login: $login) {
    id
    login
    name
    createdAt
    followers { totalCount }
    repositoriesContributedTo(
      first: 1
      contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY, ISSUE, PULL_REQUEST_REVIEW]
    ) { totalCount }
    repositories(first: 1, ownerAffiliations: OWNER) { totalCount }
  }
}
"""

CONTRIB = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      restrictedContributionsCount
    }
  }
}
"""

REPOS = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositories(
      first: 50
      after: $after
      ownerAffiliations: OWNER
      orderBy: { field: PUSHED_AT, direction: DESC }
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        nameWithOwner
        stargazerCount
        isFork
        defaultBranchRef { target { ... on Commit { oid } } }
      }
    }
  }
}
"""

HISTORY = """
query($owner: String!, $name: String!, $author: ID!, $after: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, after: $after, author: { id: $author }) {
            pageInfo { hasNextPage endCursor }
            nodes { additions deletions }
          }
        }
      }
    }
  }
}
"""


def total_commits(api, login, created_at):
    """contributionsCollection caps at one year, so walk year by year."""
    start = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    total = 0
    cursor = start
    while cursor < now:
        window_end = min(cursor.replace(year=cursor.year + 1), now)
        data = api.query(
            CONTRIB,
            {
                "login": login,
                "from": cursor.isoformat().replace("+00:00", "Z"),
                "to": window_end.isoformat().replace("+00:00", "Z"),
            },
        )["user"]["contributionsCollection"]
        total += data["totalCommitContributions"] + data["restrictedContributionsCount"]
        cursor = window_end
    return total


def all_repos(api, login):
    cursor = None
    while True:
        page = api.query(REPOS, {"login": login, "after": cursor})["user"]["repositories"]
        for node in page["nodes"]:
            yield node
        if not page["pageInfo"]["hasNextPage"]:
            return
        cursor = page["pageInfo"]["endCursor"]


def repo_loc(api, name_with_owner, author_id):
    owner, name = name_with_owner.split("/", 1)
    added = deleted = 0
    cursor = None
    while True:
        branch = api.query(
            HISTORY,
            {"owner": owner, "name": name, "author": author_id, "after": cursor},
        )["repository"]["defaultBranchRef"]
        if not branch:
            return 0, 0
        history = branch["target"]["history"]
        for commit in history["nodes"]:
            added += commit["additions"]
            deleted += commit["deletions"]
        if not history["pageInfo"]["hasNextPage"]:
            return added, deleted
        cursor = history["pageInfo"]["endCursor"]


def collect_stats(config):
    token = os.environ.get("ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit(
            "No ACCESS_TOKEN in the environment. Export a classic PAT with "
            "'repo' + 'read:user' scope, or pass --offline for a preview."
        )

    api = GitHub(token)
    login = config["username"]
    user = api.query(VIEWER, {"login": login})["user"]

    include_forks = config.get("include_forks", False)
    stars = 0
    repos = []
    for node in all_repos(api, login):
        if node["isFork"] and not include_forks:
            continue
        stars += node["stargazerCount"]
        head = (node.get("defaultBranchRef") or {}).get("target") or {}
        repos.append((node["nameWithOwner"], head.get("oid")))

    loc_added = loc_deleted = 0
    if config.get("count_loc", True):
        cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
        fresh = {}
        for name_with_owner, head_oid in repos:
            entry = cache.get(name_with_owner)
            if entry and head_oid and entry.get("oid") == head_oid:
                fresh[name_with_owner] = entry
            else:
                print(f"  counting {name_with_owner}", file=sys.stderr)
                added, deleted = repo_loc(api, name_with_owner, user["id"])
                fresh[name_with_owner] = {
                    "oid": head_oid,
                    "added": added,
                    "deleted": deleted,
                }
            loc_added += fresh[name_with_owner]["added"]
            loc_deleted += fresh[name_with_owner]["deleted"]
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(fresh, indent=1, sort_keys=True) + "\n")

    print(f"  {api.calls} api calls", file=sys.stderr)
    return {
        "username": user["login"],
        "name": user["name"] or user["login"],
        "created_at": user["createdAt"],
        "repos": user["repositories"]["totalCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
        "stars": stars,
        "followers": user["followers"]["totalCount"],
        "commits": total_commits(api, login, user["createdAt"]),
        "loc_added": loc_added,
        "loc_deleted": loc_deleted,
    }


SAMPLE = {
    "username": "MintarasGrinius",
    "name": "MintarasGrinius",
    "created_at": "2019-04-01T00:00:00Z",
    "repos": 0,
    "contributed": 0,
    "stars": 0,
    "followers": 0,
    "commits": 0,
    "loc_added": 0,
    "loc_deleted": 0,
}


# --------------------------------------------------------------------------
# Panel
# --------------------------------------------------------------------------

def uptime(birthday):
    """Years / months / days since birthday, the way neofetch phrases it."""
    if not birthday:
        return None
    born = datetime.fromisoformat(str(birthday)).date()
    today = datetime.now(timezone.utc).date()
    years = today.year - born.year
    months = today.month - born.month
    days = today.day - born.day
    if days < 0:
        months -= 1
        previous = (today.month - 1) or 12
        year = today.year if today.month > 1 else today.year - 1
        days += (datetime(year, previous % 12 + 1, 1) - datetime(year, previous, 1)).days
    if months < 0:
        years -= 1
        months += 12

    def plural(value, unit):
        return f"{value} {unit}" + ("" if value == 1 else "s")

    return ", ".join([plural(years, "year"), plural(months, "month"), plural(days, "day")])


def build_panel(config, stats):
    width = config.get("width", 62)
    tokens = {
        "username": stats["username"],
        "name": stats["name"],
        "uptime": uptime(config.get("birthday")) or "",
        "repos": f"{stats['repos']:,}",
        "contributed": f"{stats['contributed']:,}",
        "stars": f"{stats['stars']:,}",
        "commits": f"{stats['commits']:,}",
        "followers": f"{stats['followers']:,}",
        "loc": f"{stats['loc_added'] - stats['loc_deleted']:,}",
        "loc_added": f"{stats['loc_added']:,}",
        "loc_deleted": f"{stats['loc_deleted']:,}",
    }
    lines = []

    def header(text):
        dashes = max(width - len(text) - 4, 3)
        return [("header", text), ("muted", " " + "-" * dashes + "-.-")]

    def row(label, value):
        dots = max(width - 5 - len(label) - len(value), 1)
        return [
            ("dot", ". "),
            ("label", f"{label}:"),
            ("muted", " " + "." * dots + " "),
            ("value", value),
        ]

    def blank():
        return [("dot", ".")]

    def pair(label_a, value_a, label_b, value_b):
        """Two dot-leadered columns split by a pipe, as in the stats block."""
        half = width - 21  # keeps the pipe in the same column on every row
        dots_a = max(half - 5 - len(label_a) - len(value_a), 1)
        right = width - half - 3
        dots_b = max(right - 3 - len(label_b) - len(value_b), 1)
        return [
            ("dot", ". "),
            ("label", f"{label_a}:"),
            ("muted", " " + "." * dots_a + " "),
            ("value", value_a),
            ("muted", " | "),
            ("label", f"{label_b}:"),
            ("muted", " " + "." * dots_b + " "),
            ("value", value_b),
        ]

    def substitute(text):
        for key, value in tokens.items():
            text = text.replace("{" + key + "}", value)
        return text

    first = True
    for section in config.get("sections", []):
        title = section.get("title")
        if first:
            lines.append(header(f"{config['title_user']}@{config['title_host']}"))
            first = False
        else:
            lines.append([])
            lines.append(header(f"- {title}"))
        for entry in section.get("rows") or []:
            if not entry:
                lines.append(blank())
                continue
            label, raw = entry[0], substitute(str(entry[1]))
            if not raw:  # a token resolved to nothing, e.g. uptime with no birthday
                continue
            lines.append(row(label, raw))

    # --- GitHub Stats, always last and always live -------------------------
    lines.append([])
    lines.append(header("- GitHub Stats"))
    lines.append(
        pair(
            "Repos",
            f"{tokens['repos']} {{Contributed: {tokens['contributed']}}}",
            "Stars",
            tokens["stars"],
        )
    )
    lines.append(pair("Commits", tokens["commits"], "Followers", tokens["followers"]))

    label = "Lines of Code on GitHub"
    tail = f" ( {tokens['loc_added']}++, {tokens['loc_deleted']}-- )"
    dots = max(width - 5 - len(label) - len(tokens["loc"]) - len(tail), 1)
    lines.append(
        [
            ("dot", ". "),
            ("label", f"{label}:"),
            ("muted", " " + "." * dots + " "),
            ("value", tokens["loc"]),
            ("muted", " ( "),
            ("added", f"{tokens['loc_added']}++"),
            ("muted", ", "),
            ("deleted", f"{tokens['loc_deleted']}--"),
            ("muted", " )"),
        ]
    )
    return lines


# --------------------------------------------------------------------------
# SVG
# --------------------------------------------------------------------------

def render_svg(art_lines, panel_lines, theme_name):
    theme = THEMES[theme_name]
    art_width = max((len(line) for line in art_lines), default=0)
    offset = art_width + GAP

    rows = max(len(art_lines), len(panel_lines))
    columns = offset + max(
        (sum(len(text) for _, text in line) for line in panel_lines), default=0
    )
    svg_width = int(columns * CHAR_W + PAD * 2)
    svg_height = int(rows * LINE_H + PAD * 2 + 6)

    body = []
    for index in range(rows):
        art = art_lines[index] if index < len(art_lines) else ""
        panel = panel_lines[index] if index < len(panel_lines) else []
        segments = []
        if art or panel:
            segments.append(("art", art.ljust(offset) if panel else art))
        segments.extend(panel)
        if not segments:
            continue
        y = PAD + FONT_SIZE + index * LINE_H
        advance = sum(len(text) for _, text in segments) * CHAR_W
        spans = "".join(
            f'<tspan fill="{theme[color]}">{escape(text)}</tspan>'
            for color, text in segments
            if text
        )
        body.append(
            f'<text x="{PAD}" y="{y:.1f}" xml:space="preserve" '
            f'textLength="{advance:.1f}" lengthAdjust="spacingAndGlyphs">{spans}</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}" role="img" aria-label="Profile card">
  <rect x="0.5" y="0.5" width="{svg_width - 1}" height="{svg_height - 1}" rx="8" fill="{theme['bg']}" stroke="{theme['border']}"/>
  <g font-family="SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace" font-size="{FONT_SIZE}">
{chr(10).join('    ' + line for line in body)}
  </g>
</svg>
"""


# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="render with zeroed stats, no token or network needed",
    )
    args = parser.parse_args()

    config = yaml.safe_load((ROOT / "config.yml").read_text())
    art_path = ROOT / config.get("art_file", "art.txt")
    if art_path.exists():
        art_lines = art_path.read_text().rstrip("\n").split("\n")
    else:
        print(f"warning: {art_path.name} not found, rendering without art", file=sys.stderr)
        art_lines = []

    stats = SAMPLE if args.offline else collect_stats(config)
    panel_lines = build_panel(config, stats)

    for theme_name in THEMES:
        target = ROOT / f"{theme_name}.svg"
        target.write_text(render_svg(art_lines, panel_lines, theme_name))
        print(f"wrote {target.name}")


if __name__ == "__main__":
    main()
