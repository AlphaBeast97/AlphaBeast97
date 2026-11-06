#!/usr/bin/env python3
"""Generate a terminal-styled contribution snake SVG from GitHub's calendar."""
import argparse
import json
import os
import urllib.request
from pathlib import Path

LOGIN = "AlphaBeast97"
W, H = 470, 120
PAD = 16
CELL, GAP = 7.4, 0.9
GRID_Y = 32
COLS, ROWS = 53, 7
GRID_DUR, TOTAL_DUR = 13.0, 14.0
FILLS = ["#161B22", "#0E4429", "#006D32", "#26A641", "#39FF14"]
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"


def fetch():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required when --input is not given")
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { contributionCount date } }
          }
        }
        repositories(first: 1, ownerAffiliations: OWNER, isFork: false) { totalCount }
      }
    }"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "contribution-snake"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(payload["errors"])
    return payload["data"]["user"]


def levels(counts):
    nz = sorted(c for c in counts if c)
    if not nz:
        return lambda c: 0
    q1, q2, q3 = nz[len(nz) // 4], nz[len(nz) // 2], nz[3 * len(nz) // 4]

    def level(c):
        if c == 0:
            return 0
        if c <= q1:
            return 1
        if c <= q2:
            return 2
        if c <= q3:
            return 3
        return 4
    return level


def build(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    days = [d["contributionCount"] for w in weeks for d in w["contributionDays"]]
    total = cal["totalContributions"]
    repos = user["repositories"]["totalCount"]
    active = sum(1 for c in days if c)
    level = levels(days)
    by_week = [[d["contributionCount"] for d in w["contributionDays"]] for w in weeks]

    x0 = PAD
    y0 = GRID_Y
    step = CELL + GAP
    centers = []
    for col in range(COLS):
        rows = range(ROWS) if col % 2 == 0 else range(ROWS - 1, -1, -1)
        for row in rows:
            centers.append((x0 + col * step + CELL / 2, y0 + row * step + CELL / 2))

    # Head path sweeps the grid column by column, then exits right.
    # Relative to the first cell so the static fallback sits on the grid.
    ox, oy = centers[0]
    rel = [(x - ox, y - oy) for x, y in centers]
    path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in rel)
    path += f" L{W + 12 - ox:.1f} {rel[-1][1]:.1f}"

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="Contribution snake: {total} contributions in {len(weeks)} weeks, {active} active days, {repos} repositories. '
        f'A snake sweeps the contribution grid and lights the active days.">',
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="6" fill="#0D1117" stroke="#30363D"/>',
        f'<g font-family="{MONO}" font-size="13" xml:space="preserve">',
        f'<text x="{PAD}" y="21"><tspan fill="#8B949E">saad@github</tspan><tspan fill="#484F58">:~$</tspan>'
        f'<tspan fill="#C9D1D9"> ./snake --contributions</tspan></text>',
        f'<text x="{W-PAD}" y="21" text-anchor="end"><tspan fill="#8B949E">SCORE </tspan>'
        f'<tspan fill="#39FF14" font-weight="bold">{total}</tspan></text>',
        '</g>',
        f'<g font-family="{MONO}" font-size="11" xml:space="preserve">',
        f'<text x="{PAD}" y="108" fill="#8B949E">{active} active days · {len(weeks)} weeks · {repos} repos</text>',
        f'<circle cx="{W-PAD-32}" cy="105" r="2" fill="#39FF14">'
        '<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.45;0.5;1" dur="1.6s" repeatCount="indefinite"/>'
        '</circle>',
        f'<text x="{W-PAD}" y="108" text-anchor="end" fill="#8B949E">daily</text>',
        '</g>',
    ]

    # Grid: one group per level keeps the file small.
    groups = {i: [] for i in range(5)}
    for col in range(COLS):
        week = by_week[col] if col < len(by_week) else [0] * ROWS
        for row in range(ROWS):
            count = week[row] if row < len(week) else 0
            lv = level(count)
            x = x0 + col * step
            y = y0 + row * step
            idx = col * ROWS + (row if col % 2 == 0 else ROWS - 1 - row)
            if lv == 0:
                groups[0].append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{CELL}" height="{CELL}" rx="1.5"/>')
            else:
                k = idx * (GRID_DUR / (len(centers) - 1)) / TOTAL_DUR
                k2 = min(k + 0.0015, 0.999)
                groups[lv].append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{CELL}" height="{CELL}" rx="1.5" opacity="0.22">'
                    f'<animate attributeName="opacity" values="0.22;0.22;1;1" '
                    f'keyTimes="0;{k:.4f};{k2:.4f};1" dur="{TOTAL_DUR:g}s" repeatCount="indefinite"/>'
                    f'</rect>'
                )

    for lv in range(5):
        out.append(f'<g fill="{FILLS[lv]}">')
        out.extend(groups[lv])
        out.append('</g>')

    # Head plus a short fading trail, all following the same sweep path.
    out.append(f'<defs><path id="sweep" d="{path}"/></defs>')
    out.append(f'<g transform="translate({ox:.1f} {oy:.1f})">')
    out.append('<g>'
               '<circle r="5.5" fill="#39FF14" opacity="0.18"/>'
               '<rect x="-3" y="-3" width="6" height="6" rx="1.5" fill="#E6FFE6" stroke="#39FF14" stroke-width="1"/>'
               f'<animateMotion dur="{TOTAL_DUR:g}s" repeatCount="indefinite"><mpath href="#sweep"/></animateMotion>'
               '</g>')
    for i, (dx, op) in enumerate([(0.06, 0.45), (0.12, 0.28), (0.18, 0.14)], 1):
        size = 6.4 - i * 0.6
        out.append(f'<rect x="{-size/2:.1f}" y="{-size/2:.1f}" width="{size:.1f}" height="{size:.1f}" '
                   f'rx="1.2" fill="#39FF14" opacity="{op}">'
                   f'<animateMotion dur="{TOTAL_DUR:g}s" begin="{dx}s" repeatCount="indefinite">'
                   '<mpath href="#sweep"/></animateMotion></rect>')
    out.append('</g>')
    out.append('</svg>')
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="snapshot JSON from the GitHub GraphQL API")
    ap.add_argument("--out", default="assets/contribution-snake.svg")
    args = ap.parse_args()

    if args.input:
        user = json.loads(Path(args.input).read_text())["data"]["user"]
    else:
        user = fetch()

    svg = build(user)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg)
    print(f"wrote {out} ({len(svg.encode()) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
