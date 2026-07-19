from __future__ import annotations

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

HOME_SECTIONS = {
    "stand-to-reason": "Greg Koukl episode critiques",
    "idont-have-enough-faith": "Frank Turek episode critiques",
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
    if updated == original:
        return False
    homepage.write_text(updated, encoding="utf-8")
    return True


def refresh_public_site(corpus_dir: Path, docs_dir: Path) -> None:
    records = episode_records(corpus_dir, docs_dir)
    refresh_episode_navigation(records, docs_dir)
    refresh_homepage(records, docs_dir)
