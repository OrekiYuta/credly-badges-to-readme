#!/usr/bin/env python3
"""Fetch ALL Credly badges across every page and inject them into a README.

Unlike scrapers that only read the first rendered page, this queries Credly's
public JSON endpoint and follows pagination via `metadata.total_pages`, so every
badge is captured.

Configuration is read from environment variables (set by action.yml inputs):

    CREDLY_USER      Credly username/vanity slug (required)
    CREDLY_SORT      "RECENT" to sort newest-first, otherwise keep API order
    README_PATH      Path to the file to update (default: README.md)
    SECTION_START    Start marker comment (default: <!--START_SECTION:credly-badges-->)
    SECTION_END      End marker comment (default: <!--END_SECTION:credly-badges-->)
    BADGE_SIZE       Thumbnail size, e.g. "80x80"; empty for full-size image
    MAX_BADGES       Limit number of badges (0 = all)
    COLUMNS          Badges per row using an HTML table (0 = inline, no table)
    GROUP_BY         Group badges under headings: "issuer" or "none"
    GROUP_HEADING_LEVEL  Markdown heading level for group titles (e.g. 3 = ###)

GitHub Action outputs (written to $GITHUB_OUTPUT when available):

    badge_count      Number of badges rendered
    changed          "true"/"false" whether the README was modified
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

CREDLY_USER = os.environ.get("CREDLY_USER", "").strip()
CREDLY_SORT = os.environ.get("CREDLY_SORT", "RECENT").strip().upper()
README_PATH = os.environ.get("README_PATH", "README.md").strip()
SECTION_START = os.environ.get("SECTION_START", "<!--START_SECTION:credly-badges-->").strip()
SECTION_END = os.environ.get("SECTION_END", "<!--END_SECTION:credly-badges-->").strip()
BADGE_SIZE = os.environ.get("BADGE_SIZE", "80x80").strip()
MAX_BADGES = int(os.environ.get("MAX_BADGES", "0") or "0")
COLUMNS = int(os.environ.get("COLUMNS", "0") or "0")
GROUP_BY = os.environ.get("GROUP_BY", "none").strip().lower()
GROUP_HEADING_LEVEL = int(os.environ.get("GROUP_HEADING_LEVEL", "3") or "3")

BADGES_JSON = "https://www.credly.com/users/{user}/badges.json?page={page}"
BADGE_LINK = "https://www.credly.com/badges/{id}"
IMAGES_HOST = "https://images.credly.com/"


def fetch_all_badges(user):
    """Return a list of all badge objects across every page."""
    badges = []
    page = 1
    while True:
        url = BADGES_JSON.format(user=user, page=page)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            sys.exit(f"ERROR: Credly returned HTTP {e.code} for {url}")
        except urllib.error.URLError as e:
            sys.exit(f"ERROR: failed to reach Credly: {e.reason}")

        page_badges = data.get("data", [])
        badges.extend(page_badges)

        meta = data.get("metadata", {})
        total_pages = meta.get("total_pages", 1) or 1
        if page >= total_pages:
            break
        page += 1

    return badges


def image_url_for(badge):
    """Return the badge image URL, applying the configured thumbnail size."""
    template = badge.get("badge_template", {})
    url = template.get("image_url") or template.get("image", {}).get("url", "")
    if BADGE_SIZE and url.startswith(IMAGES_HOST):
        # https://images.credly.com/images/... -> .../size/<SIZE>/images/...
        url = url.replace(IMAGES_HOST, f"{IMAGES_HOST}size/{BADGE_SIZE}/", 1)
    return url


def badge_cell(b):
    """Return a single '[![name](img)](link)' markdown fragment for one badge."""
    name = b.get("badge_template", {}).get("name", "Badge").replace('"', '\\"')
    img = image_url_for(b)
    link = BADGE_LINK.format(id=b.get("id", ""))
    return f"[![{name}]({img})]({link})"


def issuer_name_for(badge):
    """Return the primary issuing organization's name for a badge.

    Credly stores issuers under badge_template.issuer.entities as a list; the
    entry with primary=True is the main issuer. Falls back to the first entity,
    then to a generic label when none is present.
    """
    issuer = badge.get("badge_template", {}).get("issuer", {})
    entities = issuer.get("entities", []) or []
    primary = next((e for e in entities if e.get("primary")), None)
    chosen = primary or (entities[0] if entities else None)
    if chosen:
        name = (chosen.get("entity", {}) or {}).get("name")
        if name:
            return name.strip()
    return "Other"


def render_cells(cells):
    """Render a list of badge cells as inline text or a fixed-column table."""
    # Inline layout: one badge after another (GitHub wraps them by width).
    if COLUMNS <= 0:
        return "\n".join(cells)

    # Column layout: fixed number of badges per row using an HTML table.
    rows = []
    for i in range(0, len(cells), COLUMNS):
        row = cells[i : i + COLUMNS]
        tds = "".join(f"<td>{c}</td>" for c in row)
        rows.append(f"  <tr>{tds}</tr>")
    return "<table>\n" + "\n".join(rows) + "\n</table>"


def make_markdown(badges):
    if GROUP_BY == "issuer":
        return make_grouped_markdown(badges, key=issuer_name_for)
    return render_cells([badge_cell(b) for b in badges])


def make_grouped_markdown(badges, key):
    """Render badges under a Markdown heading per group.

    Group order follows first appearance in the (already sorted) badge list, so
    the existing RECENT sort still influences which group shows up first.
    """
    level = min(max(GROUP_HEADING_LEVEL, 1), 6)
    hashes = "#" * level

    groups = {}
    order = []
    for b in badges:
        name = key(b)
        if name not in groups:
            groups[name] = []
            order.append(name)
        groups[name].append(b)

    sections = []
    for name in order:
        cells = [badge_cell(b) for b in groups[name]]
        sections.append(f"{hashes} {name}\n\n{render_cells(cells)}")
    return "\n\n".join(sections)


def update_readme(markdown, path):
    if not os.path.isfile(path):
        sys.exit(f"ERROR: README not found at '{path}'")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(
        re.escape(SECTION_START) + r".*?" + re.escape(SECTION_END),
        re.DOTALL,
    )
    if not pattern.search(content):
        sys.exit(
            f"ERROR: markers not found in '{path}'.\n"
            f"Add these two lines where badges should appear:\n"
            f"  {SECTION_START}\n  {SECTION_END}"
        )

    replacement = f"{SECTION_START}\n{markdown}\n{SECTION_END}"
    new_content = pattern.sub(replacement, content)

    if new_content == content:
        return False

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


def write_output(name, value):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def main():
    if not CREDLY_USER:
        sys.exit("ERROR: CREDLY_USER is required")

    badges = fetch_all_badges(CREDLY_USER)

    if CREDLY_SORT == "RECENT":
        badges.sort(key=lambda b: b.get("issued_at") or "", reverse=True)

    if MAX_BADGES > 0:
        badges = badges[:MAX_BADGES]

    print(f"Fetched {len(badges)} badges for '{CREDLY_USER}'.")

    markdown = make_markdown(badges)
    changed = update_readme(markdown, README_PATH)

    print("README updated." if changed else "README already up to date.")

    write_output("badge_count", str(len(badges)))
    write_output("changed", "true" if changed else "false")


if __name__ == "__main__":
    main()
