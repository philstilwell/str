from __future__ import annotations

import html
import json
import re
from typing import Any

SITE_NAME = "OnReason"
SITE_BASE_URL = "https://onreason.com"
SITE_DESCRIPTION = "Evidence-proportionate critiques of apologetics podcast episodes."
DEFAULT_SOCIAL_IMAGE_PATH = "/assets/evidence-alignment.png"
DEFAULT_SOCIAL_IMAGE_ALT = "Abstract evidence-alignment illustration with papers, scales, and a magnifying glass."
THEME_COLOR = "#111a15"


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def normalized_text(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def truncate_description(value: Any, max_length: int = 160) -> str:
    description = normalized_text(value)
    if len(description) <= max_length:
        return description
    truncated = description[: max_length - 3].rsplit(" ", 1)[0].rstrip(" ,.;:")
    return f"{truncated}..."


def canonical_url(path: str = "/", base_url: str = SITE_BASE_URL) -> str:
    base = base_url.rstrip("/")
    clean_path = "/" + path.strip("/")
    if clean_path == "/":
        return f"{base}/"
    return f"{base}{clean_path}/" if not clean_path.endswith("/") else f"{base}{clean_path}"


def absolute_asset_url(path: str, base_url: str = SITE_BASE_URL) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    base = base_url.rstrip("/")
    clean_path = "/" + path.strip("/")
    return f"{base}{clean_path}"


def site_image_url(base_url: str = SITE_BASE_URL) -> str:
    return absolute_asset_url(DEFAULT_SOCIAL_IMAGE_PATH, base_url)


def json_ld_script(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, indent=6).replace("</", "<\\/")
    return f'    <script type="application/ld+json" id="structured-data">\n{encoded}\n    </script>'


def graph_schema(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return {"@context": "https://schema.org", "@graph": nodes}


def organization_schema(base_url: str = SITE_BASE_URL) -> dict[str, Any]:
    return {
        "@type": "Organization",
        "@id": f"{canonical_url('/', base_url)}#organization",
        "name": SITE_NAME,
        "url": canonical_url("/", base_url),
        "logo": {
            "@type": "ImageObject",
            "url": site_image_url(base_url),
        },
    }


def website_schema(description: str = SITE_DESCRIPTION, base_url: str = SITE_BASE_URL) -> dict[str, Any]:
    return {
        "@type": "WebSite",
        "@id": f"{canonical_url('/', base_url)}#website",
        "name": SITE_NAME,
        "url": canonical_url("/", base_url),
        "description": truncate_description(description),
        "publisher": {"@id": f"{canonical_url('/', base_url)}#organization"},
        "inLanguage": "en-US",
    }


def webpage_schema(
    title: str,
    description: str,
    page_url: str,
    page_type: str = "WebPage",
) -> dict[str, Any]:
    return {
        "@type": page_type,
        "@id": f"{page_url}#webpage",
        "url": page_url,
        "name": title,
        "description": truncate_description(description),
        "isPartOf": {"@id": f"{canonical_url('/')}#website"},
        "inLanguage": "en-US",
    }


def breadcrumb_schema(items: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index,
                "name": name,
                "item": url,
            }
            for index, (name, url) in enumerate(items, start=1)
        ],
    }


def article_schema(
    title: str,
    description: str,
    page_url: str,
    published_date: str,
    source_label: str,
    source_url: str,
    image_url: str | None = None,
) -> dict[str, Any]:
    article = {
        "@type": "Article",
        "@id": f"{page_url}#article",
        "headline": title,
        "description": truncate_description(description),
        "url": page_url,
        "mainEntityOfPage": {"@id": f"{page_url}#webpage"},
        "isPartOf": {"@id": f"{canonical_url('/')}#website"},
        "author": {"@id": f"{canonical_url('/')}#organization"},
        "publisher": {"@id": f"{canonical_url('/')}#organization"},
        "image": [image_url or site_image_url()],
        "inLanguage": "en-US",
    }
    if published_date:
        article["datePublished"] = published_date
    if source_url:
        article["isBasedOn"] = {
            "@type": "PodcastEpisode",
            "name": source_label or title,
            "url": source_url,
        }
    return article


def render_seo_head(
    document_title: str,
    description: str,
    page_url: str,
    page_type: str = "website",
    social_title: str | None = None,
    image_url: str | None = None,
    image_alt: str = DEFAULT_SOCIAL_IMAGE_ALT,
    published_date: str | None = None,
    structured_data: dict[str, Any] | None = None,
) -> str:
    meta_description = truncate_description(description)
    social_title = normalized_text(social_title or document_title)
    image_url = image_url or site_image_url()
    lines = [
        f"    <title>{esc(document_title)}</title>",
        f'    <meta name="description" content="{esc(meta_description)}">',
        '    <meta name="robots" content="index,follow">',
        f'    <meta name="author" content="{esc(SITE_NAME)}">',
        f'    <meta name="theme-color" content="{esc(THEME_COLOR)}">',
        f'    <link rel="canonical" href="{esc(page_url)}">',
        '    <meta property="og:locale" content="en_US">',
        f'    <meta property="og:site_name" content="{esc(SITE_NAME)}">',
        f'    <meta property="og:type" content="{esc(page_type)}">',
        f'    <meta property="og:title" content="{esc(social_title)}">',
        f'    <meta property="og:description" content="{esc(meta_description)}">',
        f'    <meta property="og:url" content="{esc(page_url)}">',
        f'    <meta property="og:image" content="{esc(image_url)}">',
        '    <meta property="og:image:type" content="image/png">',
        f'    <meta property="og:image:alt" content="{esc(image_alt)}">',
        '    <meta name="twitter:card" content="summary_large_image">',
        f'    <meta name="twitter:title" content="{esc(social_title)}">',
        f'    <meta name="twitter:description" content="{esc(meta_description)}">',
        f'    <meta name="twitter:image" content="{esc(image_url)}">',
        f'    <meta name="twitter:image:alt" content="{esc(image_alt)}">',
    ]
    if published_date:
        lines.append(f'    <meta property="article:published_time" content="{esc(published_date)}">')
    if structured_data:
        lines.append(json_ld_script(structured_data))
    return "\n".join(lines)
