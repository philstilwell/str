from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from .critique import episode_nav_control, format_display_date


NAV_RE = re.compile(
    r'<nav\b(?=[^>]*\bclass=["\'][^"\']*\bepisode-nav-band\b[^"\']*["\'])(?=[^>]*\baria-label=["\']Adjacent episode critiques["\'])[^>]*>.*?</nav>',
    flags=re.DOTALL,
)
CARD_RE = re.compile(r'            <article class="episode-card">.*?            </article>', re.DOTALL)
ARCHIVE_START = "      <!-- archive:start -->"
ARCHIVE_END = "      <!-- archive:end -->"
ARCHIVE_MONTH_RANGES = (
    ("Jan-Feb", 1, 2),
    ("Mar-Apr", 3, 4),
    ("May-Jun", 5, 6),
    ("Jul-Aug", 7, 8),
    ("Sep-Oct", 9, 10),
    ("Nov-Dec", 11, 12),
)
ARCHIVE_MONTH_RANGE_BY_BUCKET = {
    bucket: label for bucket, (label, _start, _end) in enumerate(ARCHIVE_MONTH_RANGES, start=1)
}

HOME_SECTIONS = {
    "stand-to-reason": "Greg Koukl episode critiques",
    "idont-have-enough-faith": "Frank Turek episode critiques",
}

PODCAST_ARCHIVE_LABELS = {
    "stand-to-reason": "Greg Koukl",
    "idont-have-enough-faith": "Frank Turek",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def episode_records(
    corpus_dir: Path, docs_dir: Path, include_slugs: set[str] | None = None
) -> dict[str, list[dict[str, Any]]]:
    include_slugs = include_slugs or set()
    records: dict[str, list[dict[str, Any]]] = {}
    recorded_slugs: set[str] = set()
    for metadata_path in corpus_dir.glob("*/episodes/*/metadata.json"):
        metadata = load_json(metadata_path)
        slug = str(metadata.get("slug") or metadata_path.parent.name)
        if not (docs_dir / slug / "index.html").exists() and slug not in include_slugs:
            continue
        podcast = metadata.get("podcast") if isinstance(metadata.get("podcast"), dict) else {}
        podcast_id = str(podcast.get("id") or metadata_path.parents[2].name)
        records.setdefault(podcast_id, []).append(metadata)
        recorded_slugs.add(slug)

    # A few early public pages predate the retained corpus metadata. Recover their
    # navigation fields from the rendered page so refreshing a newer page never
    # disconnects the older end of a podcast's critique chain.
    for page_path in docs_dir.glob("*/index.html"):
        slug = page_path.parent.name
        if slug in recorded_slugs:
            continue
        soup = BeautifulSoup(page_path.read_text(encoding="utf-8"), "html.parser")
        source_link = soup.select_one(".meta-list a[href]")
        source_label = source_link.get_text(" ", strip=True) if source_link else ""
        source_url = source_link.get("href", "") if source_link else ""
        podcast_id = (
            "idont-have-enough-faith"
            if "CrossExamined" in source_label or "crossexamined.org" in source_url
            else "stand-to-reason"
        )
        title_node = soup.select_one(".article-header h1")
        records.setdefault(podcast_id, []).append(
            {
                "slug": slug,
                "title": title_node.get_text(" ", strip=True) if title_node else slug,
                "pub_date": slug[:10],
                "podcast_page_url": source_url,
                "podcast": {"id": podcast_id},
            }
        )
    for items in records.values():
        items.sort(key=lambda item: (str(item.get("pub_date") or ""), str(item.get("slug") or "")))
    return records


def episode_nav_for(slug: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    index = next((index for index, item in enumerate(records) if item.get("slug") == slug), None)
    if index is None:
        return {"previous": None, "next": None}

    def nav_item(item: dict[str, Any] | None) -> dict[str, str] | None:
        if item is None:
            return None
        return {"title": str(item.get("title") or "Untitled episode"), "url": f"../{item.get('slug')}/"}

    older = records[index - 1] if index > 0 else None
    newer = records[index + 1] if index + 1 < len(records) else None
    return {"previous": nav_item(older), "next": nav_item(newer)}


def refresh_episode_navigation(records: dict[str, list[dict[str, Any]]], docs_dir: Path) -> int:
    changed = 0
    for items in records.values():
        for item in items:
            slug = str(item.get("slug") or "")
            path = docs_dir / slug / "index.html"
            if not path.exists():
                continue
            nav = episode_nav_for(slug, items)
            replacement = (
                '<nav class="episode-nav-band" aria-label="Adjacent episode critiques">\n'
                f"            {episode_nav_control(nav['previous'], 'previous')}\n"
                f"            {episode_nav_control(nav['next'], 'next')}\n"
                "          </nav>"
            )
            original = path.read_text(encoding="utf-8")
            updated, count = NAV_RE.subn(lambda _: replacement, original, count=1)
            if count != 1:
                raise RuntimeError(f"Could not find episode navigation in {path}")
            if updated != original:
                path.write_text(updated, encoding="utf-8")
                changed += 1
    return changed


def card_summary(page_path: Path) -> str:
    soup = BeautifulSoup(page_path.read_text(encoding="utf-8"), "html.parser")
    lede = soup.select_one(".article-header .lede")
    value = lede.get_text(" ", strip=True) if lede else "Evidence-proportionate critique of this episode's central claims."
    if len(value) <= 190:
        return value
    return value[:190].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"


def episode_card(item: dict[str, Any], docs_dir: Path) -> str:
    slug = str(item.get("slug") or "")
    title = html.escape(str(item.get("title") or "Untitled episode"))
    date = html.escape(format_display_date(str(item.get("pub_date") or "")))
    summary = html.escape(card_summary(docs_dir / slug / "index.html"))
    source_url = html.escape(str(item.get("podcast_page_url") or item.get("mp3_url") or ""), quote=True)
    return f'''            <article class="episode-card">
              <p class="date">{date}</p>
              <h2>{title}</h2>
              <p>
                {summary}
              </p>
              <div class="actions">
                <a class="primary-link" href="./episodes/{html.escape(slug, quote=True)}/">Read critique</a>
                <a class="primary-link secondary" href="{source_url}">Official episode page</a>
              </div>
            </article>'''


def recent_homepage_slugs(records: dict[str, list[dict[str, Any]]], limit: int) -> set[str]:
    recent: set[str] = set()
    for podcast_id in HOME_SECTIONS:
        for item in list(reversed(records.get(podcast_id, [])))[:limit]:
            slug = str(item.get("slug") or "")
            if slug:
                recent.add(slug)
    return recent


def archive_items(records: dict[str, list[dict[str, Any]]], recent_limit: int) -> list[dict[str, Any]]:
    recent = recent_homepage_slugs(records, recent_limit)
    items = [
        item
        for podcast_items in records.values()
        for item in podcast_items
        if str(item.get("slug") or "") not in recent
    ]
    items.sort(key=lambda item: (str(item.get("pub_date") or ""), str(item.get("slug") or "")), reverse=True)
    return items


def archive_period(item: dict[str, Any]) -> tuple[int, int, str]:
    pub_date = str(item.get("pub_date") or item.get("slug") or "")
    match = re.match(r"(\d{4})-(\d{2})", pub_date)
    if not match:
        return (0, 0, "Undated")
    year = int(match.group(1))
    month = int(match.group(2))
    bucket = ((month - 1) // 2) + 1
    label = ARCHIVE_MONTH_RANGE_BY_BUCKET.get(bucket, "Undated")
    return (year, bucket, f"{label} {year}")


def archive_page_id(label: str) -> str:
    return "older-assessments-" + re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def archive_item_html(item: dict[str, Any], position: int) -> str:
    slug = html.escape(str(item.get("slug") or ""), quote=True)
    title = html.escape(str(item.get("title") or "Untitled assessment"))
    date = html.escape(format_display_date(str(item.get("pub_date") or "")))
    podcast = item.get("podcast") if isinstance(item.get("podcast"), dict) else {}
    podcast_id = str(podcast.get("id") or "")
    podcast_label = html.escape(PODCAST_ARCHIVE_LABELS.get(podcast_id, str(item.get("source_label") or "Assessment")))
    return (
        '                  <li class="archive-item">\n'
        f'                    <span class="archive-meta">{position}. {date} · {podcast_label}</span>\n'
        f'                    <a href="./episodes/{slug}/">{title}</a>\n'
        "                  </li>"
    )


def archive_period_groups(items: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    groups: dict[tuple[int, int, str], list[dict[str, Any]]] = {}
    for item in items:
        groups.setdefault(archive_period(item), []).append(item)
    return [(label, groups[key]) for key in sorted(groups, reverse=True) for label in [key[2]]]


def archive_section(records: dict[str, list[dict[str, Any]]], recent_limit: int) -> str:
    items = archive_items(records, recent_limit)
    if not items:
        return ""

    groups = archive_period_groups(items)
    page_buttons = []
    page_sections = []
    position = 1
    for page_index, (label, page_items) in enumerate(groups, start=1):
        start = position
        end = start + len(page_items) - 1
        page_id = archive_page_id(label)
        current = ' aria-current="page"' if page_index == 1 else ""
        page_buttons.append(
            f'              <button type="button" data-archive-target="{page_id}"{current}>'
            f"{html.escape(label)}</button>"
        )
        list_items = "\n".join(
            archive_item_html(item, position)
            for position, item in enumerate(page_items, start=start)
        )
        hidden = " hidden" if page_index != 1 else ""
        page_sections.append(
            f'              <section class="archive-page" id="{page_id}" data-archive-page{hidden} '
            f'aria-label="Older assessments from {html.escape(label)}">\n'
            f'                <ol class="archive-list" start="{start}">\n'
            f"{list_items}\n"
            "                </ol>\n"
            "              </section>"
        )
        position = end + 1

    pagination = ""
    if len(page_buttons) > 1:
        pagination = (
            '            <div class="archive-pagination" aria-label="Older assessment pages">\n'
            + "\n".join(page_buttons)
            + "\n            </div>\n"
        )

    assessment_label = "assessment" if len(items) == 1 else "assessments"
    return (
        '      <section class="archive-section" aria-labelledby="older-assessments-title">\n'
        '        <details class="archive-accordion">\n'
        "          <summary>\n"
        "            <span>\n"
        '              <span class="date">Archive</span>\n'
        '              <strong id="older-assessments-title">Older assessments</strong>\n'
        "            </span>\n"
        f'            <span class="archive-count">{len(items)} {assessment_label}</span>\n'
        "          </summary>\n"
        '          <div class="archive-body" data-paginated-archive>\n'
        "            <p>Published assessments beyond the ten most recent shown above.</p>\n"
        f"{pagination}"
        + "\n\n".join(page_sections)
        + "\n          </div>\n"
        "        </details>\n"
        "      </section>"
    )


def refresh_archive_section(updated: str, records: dict[str, list[dict[str, Any]]], limit: int) -> str:
    section = archive_section(records, limit)
    if not section:
        return updated
    block = f"{ARCHIVE_START}\n{section}\n{ARCHIVE_END}"
    if ARCHIVE_START in updated and ARCHIVE_END in updated:
        pattern = re.compile(rf"{re.escape(ARCHIVE_START)}.*?{re.escape(ARCHIVE_END)}", re.DOTALL)
        updated, count = pattern.subn(lambda _: block, updated, count=1)
        if count != 1:
            raise RuntimeError("Could not refresh homepage archive section")
        return updated
    if "\n    </main>" in updated:
        return updated.replace("\n    </main>", f"\n{block}\n    </main>", 1)
    return f"{updated.rstrip()}\n{block}\n"


def refresh_homepage(records: dict[str, list[dict[str, Any]]], docs_dir: Path, limit: int = 5) -> bool:
    homepage = docs_dir.parent / "index.html"
    original = homepage.read_text(encoding="utf-8")
    updated = original
    for podcast_id, aria_label in HOME_SECTIONS.items():
        items = list(reversed(records.get(podcast_id, [])))[:limit]
        if not items:
            continue
        pattern = re.compile(
            rf'(<section class="episode-list compact-list" aria-label="{re.escape(aria_label)}">)(.*?)(\n          </section>)',
            flags=re.DOTALL,
        )
        section_match = pattern.search(updated)
        if section_match is None:
            raise RuntimeError(f"Could not find homepage section {aria_label!r}")
        existing_cards: dict[str, str] = {}
        for card_match in CARD_RE.finditer(section_match.group(2)):
            card = card_match.group(0)
            slug_match = re.search(r'href="\./episodes/([^/]+)/"', card)
            if slug_match:
                existing_cards[slug_match.group(1)] = card
        cards = "\n\n".join(
            existing_cards.get(str(item.get("slug") or "")) or episode_card(item, docs_dir)
            for item in items
        )
        updated, count = pattern.subn(
            lambda match: f"{match.group(1)}\n{cards}{match.group(3)}", updated, count=1
        )
        if count != 1:
            raise RuntimeError(f"Could not find homepage section {aria_label!r}")
    updated = refresh_archive_section(updated, records, limit)
    if updated == original:
        return False
    homepage.write_text(updated, encoding="utf-8")
    return True


def refresh_public_site(corpus_dir: Path, docs_dir: Path) -> None:
    records = episode_records(corpus_dir, docs_dir)
    refresh_episode_navigation(records, docs_dir)
    refresh_homepage(records, docs_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refresh OnReason public homepage and episode navigation.")
    parser.add_argument("--corpus-dir", type=Path, default=Path("corpus/podcasts"))
    parser.add_argument("--docs-dir", type=Path, default=Path("docs/episodes"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    records = episode_records(args.corpus_dir, args.docs_dir)
    nav_updates = refresh_episode_navigation(records, args.docs_dir)
    homepage_updated = refresh_homepage(records, args.docs_dir)
    print(f"Refreshed episode navigation on {nav_updates} page(s).")
    print(f"Homepage {'updated' if homepage_updated else 'already current'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
