#!/usr/bin/env python3
"""Build a compact research index for OnReason critique drafting.

The index intentionally stores metadata, short excerpts, and relevance tags,
not full article mirrors. This keeps the public repository useful for future
critique generation without republishing Free of Faith articles or local PDFs.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import ssl
import sys
from pathlib import Path
from typing import Iterable

import pdfplumber
import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "source-index.json"
HOME = Path.home()
ACADEMIC_DIR = HOME / "Documents" / "◉ Academic Papers"
MANUALS_DIR = HOME / "Documents" / "New project" / "assets" / "manuals"

USER_AGENT = "OnReason source indexer; metadata/excerpt cache"

FREE_OF_FAITH_CATEGORIES = {
    "insights": "https://freeoffaith.com/category/insights/",
    "considerations": "https://freeoffaith.com/category/considerations/",
}

ACADEMIC_PAPERS = [
    {
        "id": "academic-scope-leakage-happiness",
        "title": "Scope Leakage of Happiness: Overextended Moral Responsibility, Bounded Agency, and the Cost of Global Concern",
        "type": "academic_paper",
        "source_path": str(ACADEMIC_DIR / "scope_leakage_of_happiness.md"),
        "source_file": "scope_leakage_of_happiness.md",
        "relevance_tags": ["bounded-agency", "moral-psychology", "hope", "calling", "scope-leakage"],
    }
]

LOCAL_FRAMEWORKS = [
    {
        "id": "framework-belief-overreach-audit",
        "title": "Belief Overreach Audit Manual",
        "type": "local_framework_manual",
        "source_path": str(MANUALS_DIR / "belief-overreach-audit-manual-v2.pdf"),
        "source_file": "belief-overreach-audit-manual-v2.pdf",
        "relevance_tags": ["credence-calibration", "evidence-proportionate-belief", "overbelief", "faith"],
    },
    {
        "id": "framework-inductive-symmetry-audit",
        "title": "Inductive Symmetry Audit Manual",
        "type": "local_framework_manual",
        "source_path": str(MANUALS_DIR / "inductive-symmetry-audit-manual.pdf"),
        "source_file": "inductive-symmetry-audit-manual.pdf",
        "relevance_tags": ["inductive-symmetry", "comparative-testing", "special-pleading", "worldview"],
    },
    {
        "id": "framework-resurrection-evidence-audit",
        "title": "Resurrection Evidence Audit Manual",
        "type": "local_framework_manual",
        "source_path": str(MANUALS_DIR / "resurrection-evidence-audit-manual.pdf"),
        "source_file": "resurrection-evidence-audit-manual.pdf",
        "relevance_tags": ["resurrection", "miracle-claims", "bayesian-reasoning", "alternatives"],
    },
    {
        "id": "framework-moral-system-threshold",
        "title": "Moral System Threshold Manual",
        "type": "local_framework_manual",
        "source_path": str(MANUALS_DIR / "moral-system-threshold-manual-v2.pdf"),
        "source_file": "moral-system-threshold-manual-v2.pdf",
        "relevance_tags": ["moral-architecture", "authority", "public-justification", "sexual-ethics"],
    },
    {
        "id": "framework-moral-particulars-audit",
        "title": "Moral Particulars Audit Manual",
        "type": "local_framework_manual",
        "source_path": str(MANUALS_DIR / "moral-particulars-audit-manual-v2.pdf"),
        "source_file": "moral-particulars-audit-manual-v2.pdf",
        "relevance_tags": ["moral-particulars", "case-level-ethics", "authority", "disagreement"],
    },
]

TAG_RULES = [
    ("resurrection", ["resurrection", "miracle", "bayes", "bayesian", "expectations"]),
    ("worldview", ["worldview", "explanation", "explanatory", "parsimony", "theology", "theism"]),
    ("faith", ["faith", "credence", "belief", "evidence", "rational", "warrant"]),
    ("moral-architecture", ["morality", "moral", "ethic", "good", "objective morality", "genocide"]),
    ("identity", ["soul", "mind", "consciousness", "identity", "sexual", "homosexuality"]),
    ("hope-purpose", ["hope", "purpose", "meaning", "joy", "peace", "despondent", "happiness"]),
    ("public-justification", ["public", "truth", "authority", "inference", "best explanation"]),
    ("insider-authority", ["bible", "biblical", "scripture", "holy spirit", "prayer"]),
    ("mythmaking", ["myth", "legend", "prophecy", "gospel", "jesus"]),
    ("bias-fallacy", ["bias", "fallacy", "cognitive", "confirmation", "self-deception"]),
]


def slugify(text: str) -> str:
    text = re.sub(r"^[#\d\s✓.-]+", "", text, flags=re.I)
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return re.sub(r"-+", "-", text).strip("-")[:80] or "source"


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def short_excerpt(text: str, limit: int = 420) -> str:
    text = clean_text(text)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return f"{cut}..."


def infer_tags(title: str, excerpt: str) -> list[str]:
    haystack = f"{title} {excerpt}".lower()
    tags = [tag for tag, needles in TAG_RULES if any(needle in haystack for needle in needles)]
    return sorted(set(tags))


def fetch_html(url: str) -> str | None:
    try:
        response = requests.get(
            url,
            timeout=25,
            verify=False,
            headers={"User-Agent": USER_AGENT},
        )
    except requests.RequestException as exc:
        print(f"warn: failed {url}: {exc}", file=sys.stderr)
        return None
    if response.status_code >= 400:
        return None
    return response.text


def category_pages(base_url: str, max_pages: int = 12) -> Iterable[str]:
    yield base_url
    for page in range(2, max_pages + 1):
        yield f"{base_url.rstrip('/')}/page/{page}/"


def scrape_category(section: str, base_url: str) -> list[dict[str, object]]:
    seen: set[str] = set()
    entries: list[dict[str, object]] = []
    for url in category_pages(base_url):
        html = fetch_html(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        page_new = 0
        for heading in soup.find_all("h3"):
            link = heading.find("a", href=True)
            if not link:
                continue
            post_url = link["href"].split("#", 1)[0]
            if not post_url.startswith("https://freeoffaith.com/"):
                continue
            title = clean_text(link.get_text(" ", strip=True))
            if not title or title.lower() in {"recent posts", "search"}:
                continue
            if post_url in seen:
                continue
            parent_text = clean_text(heading.parent.get_text(" ", strip=True))
            excerpt = parent_text
            if excerpt.startswith(title):
                excerpt = excerpt[len(title):].strip()
            # Avoid sidebar/comment artifacts by requiring either a Consider title or a meaningful excerpt.
            if section == "considerations" and "consider:" not in title.lower():
                continue
            if section == "insights" and len(excerpt) < 40:
                continue
            if section == "considerations":
                detail_excerpt = fetch_article_summary(post_url)
                if detail_excerpt:
                    excerpt = detail_excerpt
            entry = {
                "id": f"fof-{section}-{slugify(title)}",
                "section": section,
                "type": "freeoffaith_article",
                "title": title,
                "url": post_url,
                "excerpt": short_excerpt(excerpt),
                "relevance_tags": infer_tags(title, excerpt),
            }
            entries.append(entry)
            seen.add(post_url)
            page_new += 1
        if page_new == 0 and url != base_url:
            break
    return entries


def fetch_article_summary(url: str) -> str:
    html = fetch_html(url)
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".wp-block-post-content") or soup.select_one(".entry-content")
    if not content:
        return ""
    text = clean_text(content.get_text(" ", strip=True))
    marker = "Summary:"
    if marker in text:
        text = text.split(marker, 1)[1].strip()
    # Most Considerations pages move from a summary into the main essay with "Imagine".
    text = re.split(r"\bImagine\b|\bThe logical Form\b|\bLogical Form\b", text, maxsplit=1)[0].strip()
    return short_excerpt(text, 700)


def read_markdown_abstract(path: str) -> str:
    text = Path(path).read_text(encoding="utf-8")
    match = re.search(r"## Abstract\s+(.+?)(?=\n##\s+)", text, flags=re.S)
    if match:
        return short_excerpt(match.group(1), 900)
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    return short_excerpt(paras[0] if paras else "", 900)


def read_pdf_intro(path: str) -> str:
    source = Path(path)
    if not source.exists():
        return ""
    with pdfplumber.open(source) as pdf:
        text = "\n".join((page.extract_text() or "") for page in pdf.pages[:2])
    return short_excerpt(text, 900)


def add_local_summaries(items: list[dict[str, object]]) -> list[dict[str, object]]:
    out = []
    for item in items:
        item = dict(item)
        path = str(item.pop("source_path", ""))
        if path.endswith(".md"):
            item["summary"] = read_markdown_abstract(path)
        elif path.endswith(".pdf"):
            item["summary"] = read_pdf_intro(path)
        item["local_source_note"] = "Reflection summary indexed from a local Phil Stilwell source file; the full local file is not mirrored in this repository."
        out.append(item)
    return out


def main() -> None:
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
    freeoffaith = []
    for section, url in FREE_OF_FAITH_CATEGORIES.items():
        freeoffaith.extend(scrape_category(section, url))
    freeoffaith = sorted(freeoffaith, key=lambda item: (item["section"], item["title"]))
    payload = {
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "policy": "Metadata, short excerpts, and reflection summaries only; this file is not a full local mirror of Free of Faith articles or local PDFs.",
        "freeoffaith": freeoffaith,
        "academic_papers": add_local_summaries(ACADEMIC_PAPERS),
        "local_frameworks": add_local_summaries(LOCAL_FRAMEWORKS),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"freeoffaith entries: {len(freeoffaith)}")


if __name__ == "__main__":
    # Keep an explicit SSL context creation here as a reminder that Free of Faith
    # metadata is public and the crawler deliberately stores only summaries.
    ssl._create_unverified_context()
    main()
