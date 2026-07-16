from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from str_workflow.critique import DEFAULT_ASSET_VERSION, apply_moral_nonrealist_language, validate_page


OLD_ASSET_VERSION_RE = re.compile(r"(?:styles\.css|app\.js)\?v=[^\"']+")
SKIP_PARENTS = {"script", "style", "code", "q"}


class TextNodeNormalizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self.stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.stack.append(tag.lower())
        self.parts.append(self.get_starttag_text() or f"<{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(self.get_starttag_text() or f"<{tag}/>")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index] == lowered:
                del self.stack[index:]
                break
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if any(tag in SKIP_PARENTS for tag in self.stack):
            self.parts.append(data)
        else:
            self.parts.append(apply_moral_nonrealist_language(data))

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.parts.append(f"<?{data}>")

    def close(self) -> str:
        super().close()
        return "".join(self.parts)


def update_asset_versions(html_text: str) -> str:
    return OLD_ASSET_VERSION_RE.sub(
        lambda match: match.group(0).split("?v=", 1)[0] + f"?v={DEFAULT_ASSET_VERSION}",
        html_text,
    )


def normalize_text_nodes(html_text: str) -> str:
    parser = TextNodeNormalizer()
    parser.feed(update_asset_versions(html_text))
    return parser.close()


def normalize_html(path: Path, *, validate: bool) -> None:
    path.write_text(normalize_text_nodes(path.read_text(encoding="utf-8")), encoding="utf-8")
    if validate:
        errors = validate_page(path)
        if errors:
            raise RuntimeError(f"{path} failed moral non-realist validation:\n" + "\n".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize rendered critique pages into moral non-realist language.")
    parser.add_argument("--docs-dir", type=Path, default=ROOT / "docs" / "episodes")
    parser.add_argument("--methodology", type=Path, default=ROOT / "docs" / "methodology" / "index.html")
    args = parser.parse_args()
    pages = sorted(args.docs_dir.glob("*/index.html"))
    for page in pages:
        normalize_html(page, validate=True)
        print(f"normalized {page.relative_to(ROOT)}")
    if args.methodology.exists():
        normalize_html(args.methodology, validate=False)
        print(f"normalized {args.methodology.relative_to(ROOT)}")
    print(f"normalized {len(pages)} episode page(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
