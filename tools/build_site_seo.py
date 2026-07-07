from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from str_workflow.seo import (  # noqa: E402
    DEFAULT_SOCIAL_IMAGE_ALT,
    SITE_DESCRIPTION,
    absolute_asset_url,
    article_schema,
    breadcrumb_schema,
    canonical_url,
    graph_schema,
    organization_schema,
    render_seo_head,
    truncate_description,
    webpage_schema,
    website_schema,
)

DOCS_DIR = ROOT / "docs"
EPISODE_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")


def site_base_url() -> str:
    cname = (DOCS_DIR / "CNAME").read_text(encoding="utf-8").strip()
    return f"https://{cname}" if cname else "https://onreason.com"


def page_path(path: Path) -> str:
    relative = path.relative_to(DOCS_DIR)
    if relative == Path("index.html"):
        return "/"
    if relative.name == "index.html":
        return "/" + "/".join(relative.parts[:-1]) + "/"
    return "/" + "/".join(relative.parts)


def plain_title(document_title: str) -> str:
    return re.sub(r"\s+\|\s+OnReason$", "", document_title).strip()


def episode_description(title: str, source_label: str) -> str:
    show = "Frank Turek's episode" if "CrossExamined" in source_label else "the STR episode"
    return truncate_description(
        f"Evidence-proportionate OnReason critique of {show} {title}, testing apologetics claims against public evidence."
    )


def page_description(path: Path, soup: BeautifulSoup, title: str, source_label: str) -> str:
    if "/episodes/" in page_path(path):
        lede = soup.select_one(".article-header .lede")
        if lede:
            return truncate_description(lede.get_text(" ", strip=True))
        return episode_description(plain_title(title), source_label)
    if page_path(path) == "/methodology/":
        return truncate_description(
            "How OnReason critiques apologetics podcasts by steelmanning claims, tracing evidence, testing rivals, and calibrating confidence."
        )
    return SITE_DESCRIPTION


def source_link(soup: BeautifulSoup) -> tuple[str, str]:
    source_anchor = soup.select_one(".meta-list a[href]")
    if not source_anchor:
        return "", ""
    return source_anchor.get_text(" ", strip=True), source_anchor.get("href", "")


def published_date(path: Path) -> str:
    if "/episodes/" not in page_path(path):
        return ""
    slug = path.parent.name
    match = EPISODE_DATE_RE.match(slug)
    return match.group(1) if match else ""


def structured_data_for_page(
    path: Path,
    document_title: str,
    description: str,
    url: str,
    base_url: str,
    source_label: str,
    source_url: str,
) -> dict:
    nodes = [organization_schema(base_url), website_schema(SITE_DESCRIPTION, base_url)]
    if page_path(path) == "/":
        nodes.append(webpage_schema(document_title, description, url, "CollectionPage"))
    elif page_path(path) == "/methodology/":
        nodes.extend(
            [
                webpage_schema(document_title, description, url, "AboutPage"),
                breadcrumb_schema([("Critiques", canonical_url("/", base_url)), ("Methodology", url)]),
            ]
        )
    else:
        title = plain_title(document_title)
        nodes.extend(
            [
                webpage_schema(document_title, description, url, "WebPage"),
                article_schema(
                    title,
                    description,
                    url,
                    published_date(path),
                    source_label,
                    source_url,
                    absolute_asset_url("/assets/evidence-alignment.png", base_url),
                ),
                breadcrumb_schema([("Critiques", canonical_url("/", base_url)), (title, url)]),
            ]
        )
    return graph_schema(nodes)


def preferred_document_title(path: Path, soup: BeautifulSoup) -> str:
    existing = soup.title.get_text(" ", strip=True) if soup.title else "OnReason"
    if page_path(path) == "/":
        return "OnReason | Evidence-Proportionate Apologetics Critiques"
    return existing


def update_html_page(path: Path, base_url: str) -> None:
    html = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    document_title = preferred_document_title(path, soup)
    source_label, source_url = source_link(soup)
    description = page_description(path, soup, document_title, source_label)
    url = canonical_url(page_path(path), base_url)
    structured_data = structured_data_for_page(path, document_title, description, url, base_url, source_label, source_url)
    page_type = "article" if "/episodes/" in page_path(path) else "website"
    seo_head = render_seo_head(
        document_title=document_title,
        description=description,
        page_url=url,
        page_type=page_type,
        social_title=document_title,
        image_url=absolute_asset_url("/assets/evidence-alignment.png", base_url),
        image_alt=DEFAULT_SOCIAL_IMAGE_ALT,
        published_date=published_date(path),
        structured_data=structured_data,
    )
    updated, replacements = re.subn(
        r"    <title>.*?\n    <link rel=\"icon\"",
        f"{seo_head}\n    <link rel=\"icon\"",
        html,
        count=1,
        flags=re.DOTALL,
    )
    if replacements != 1:
        raise RuntimeError(f"Could not update SEO head for {path}")
    path.write_text(updated, encoding="utf-8")


def html_pages() -> list[Path]:
    return [DOCS_DIR / "index.html", DOCS_DIR / "methodology/index.html", *sorted((DOCS_DIR / "episodes").glob("*/index.html"))]


def sitemap_lastmod(path: Path, site_updated: str) -> str:
    return published_date(path) or site_updated


def sitemap_priority(path: Path) -> str:
    path_text = page_path(path)
    if path_text == "/":
        return "1.0"
    if path_text == "/methodology/":
        return "0.6"
    return "0.8"


def sitemap_changefreq(path: Path) -> str:
    return "weekly" if page_path(path) == "/" else "monthly"


def write_sitemap(pages: list[Path], base_url: str) -> None:
    site_updated = date.today().isoformat()
    rows = []
    for page in pages:
        loc = canonical_url(page_path(page), base_url)
        rows.append(
            "  <url>\n"
            f"    <loc>{xml_escape(loc)}</loc>\n"
            f"    <lastmod>{xml_escape(sitemap_lastmod(page, site_updated))}</lastmod>\n"
            f"    <changefreq>{sitemap_changefreq(page)}</changefreq>\n"
            f"    <priority>{sitemap_priority(page)}</priority>\n"
            "  </url>"
        )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(rows)
        + "\n</urlset>\n"
    )
    (DOCS_DIR / "sitemap.xml").write_text(sitemap, encoding="utf-8")


def write_robots(base_url: str) -> None:
    robots = f"User-agent: *\nAllow: /\n\nSitemap: {absolute_asset_url('/sitemap.xml', base_url)}\n"
    (DOCS_DIR / "robots.txt").write_text(robots, encoding="utf-8")


def main() -> int:
    base_url = site_base_url()
    pages = html_pages()
    for page in pages:
        update_html_page(page, base_url)
    write_sitemap(pages, base_url)
    write_robots(base_url)
    print(f"Updated SEO metadata for {len(pages)} pages.")
    print("Wrote docs/sitemap.xml and docs/robots.txt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
