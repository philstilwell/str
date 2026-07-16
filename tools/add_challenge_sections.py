from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from str_workflow.critique import DEFAULT_ASSET_VERSION, validate_page


OLD_ASSET_VERSION_RE = re.compile(r"(?:styles\.css|app\.js)\?v=[^\"']+")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def sentence(value: str) -> str:
    text = clean_text(value).rstrip(".")
    return f"{text}." if text else ""


def section_label(section: BeautifulSoup) -> str:
    kicker = section.select_one(".section-kicker.numbered-kicker")
    if not kicker:
        return "the claim"
    return re.sub(r"^\d+\.\s*", "", clean_text(kicker.get_text(" ", strip=True)))


def quote_for_section(section: BeautifulSoup) -> str:
    quote = section.select_one(".quote-anchor q")
    return clean_text(quote.get_text(" ", strip=True)) if quote else ""


def diagnostic_items(soup: BeautifulSoup) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for section in soup.select("section.section-panel"):
        if not section.select_one(".section-kicker.numbered-kicker"):
            continue
        label = section_label(section)
        quote = quote_for_section(section)
        for card in section.select(".tag-explainer"):
            pill = card.select_one(".link-pill")
            fit = card.select_one(".severity")
            application = card.select_one("p")
            if not pill or not application:
                continue
            fit_text = clean_text(fit.get_text(" ", strip=True)) if fit else ""
            score = 0
            if "High" in fit_text:
                score = 2
            elif "Moderate" in fit_text:
                score = 1
            items.append(
                {
                    "label": label,
                    "quote": quote,
                    "diagnostic": clean_text(pill.get_text(" ", strip=True)),
                    "fit": fit_text,
                    "application": sentence(application.get_text(" ", strip=True)),
                    "score": str(score),
                }
            )
    return sorted(items, key=lambda item: int(item["score"]), reverse=True)


def unique_items(items: list[dict[str, str]], limit: int = 3) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    seen_labels: set[str] = set()
    for item in items:
        label_key = item["label"].casefold()
        if label_key in seen_labels:
            continue
        selected.append(item)
        seen_labels.add(label_key)
        if len(selected) == limit:
            return selected
    for item in items:
        if item not in selected:
            selected.append(item)
        if len(selected) == limit:
            return selected
    return selected


def list_phrase(values: list[str]) -> str:
    cleaned = [clean_text(value) for value in values if clean_text(value)]
    if not cleaned:
        return "the main claims"
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def build_bullets(items: list[dict[str, str]]) -> list[str]:
    bullets: list[str] = []
    for item in items:
        quoted = f' around "{item["quote"]}"' if item["quote"] else ""
        diagnostic = item["diagnostic"]
        fit = item["fit"].replace("Diagnostic fit:", "").strip()
        fit_clause = f" with {fit.lower()} diagnostic fit" if fit else ""
        bullets.append(
            sentence(
                f"In {item['label']}{quoted}, the {diagnostic} problem{fit_clause} must be answered: "
                f"{item['application']}"
            )
        )
    while len(bullets) < 3:
        bullets.append(
            "The episode must replace assertion, selected illustration, or insider authority with public evidence that survives rival comparison."
        )
    return bullets[:3]


def challenge_html(soup: BeautifulSoup) -> str:
    page_title = clean_text(soup.select_one("h1").get_text(" ", strip=True)) if soup.select_one("h1") else "this episode"
    selected = unique_items(diagnostic_items(soup), 3)
    labels = list_phrase([item["label"] for item in selected])
    title = f"The weakest moves in {page_title} need public warrant, not louder confidence"
    paragraphs = [
        (
            f"The weakest points in this transcript cluster around {labels}. These are not decorative gaps; "
            "they are the places where the episode asks listeners to let proclamation, selected examples, biblical citation, "
            "or pastoral urgency do work that only public evidence and symmetrical rival comparison can do."
        ),
        (
            "The challenge is blunt: either defend those claims under ordinary evidential discipline or reduce the rhetoric. "
            "Faith, identity, reassurance, and ethical urgency may explain why the claims matter to insiders, but they do not make "
            "the claims rationally credible at the level asserted. Where faith protects confidence from evidence, the argument has stopped earning its confidence."
        ),
    ]
    bullets = build_bullets(selected)
    return (
        '<div class="challenge-reality" aria-label="The challenge">\n'
        '  <p class="dark-kicker">The challenge</p>\n'
        f"  <h3>{html.escape(title)}</h3>\n"
        + "\n".join(f"  <p>{html.escape(paragraph)}</p>" for paragraph in paragraphs)
        + "\n  <ul>\n"
        + "\n".join(f"    <li>{html.escape(bullet)}</li>" for bullet in bullets)
        + "\n  </ul>\n"
        "</div>"
    )


def migrate_page(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    versioned = OLD_ASSET_VERSION_RE.sub(
        lambda match: match.group(0).split("?v=", 1)[0] + f"?v={DEFAULT_ASSET_VERSION}",
        original,
    )
    soup = BeautifulSoup(versioned, "html.parser")
    overall = soup.select_one("#overall")
    epistemic = soup.select_one("#overall .epistemic-reality")
    if not overall or not epistemic:
        raise RuntimeError(f"{path} is missing the overall epistemic section")
    for existing in overall.select(".challenge-reality"):
        existing.decompose()
    challenge = BeautifulSoup(challenge_html(soup), "html.parser")
    epistemic.insert_after(challenge)
    path.write_text(str(soup), encoding="utf-8")
    errors = validate_page(path)
    if errors:
        raise RuntimeError(f"{path} failed validation after challenge migration:\n" + "\n".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Add or refresh red challenge sections on rendered episode pages.")
    parser.add_argument("--docs-dir", type=Path, default=ROOT / "docs" / "episodes")
    args = parser.parse_args()
    pages = sorted(args.docs_dir.glob("*/index.html"))
    for page in pages:
        migrate_page(page)
        print(f"migrated {page.relative_to(ROOT)}")
    print(f"migrated {len(pages)} episode page(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
