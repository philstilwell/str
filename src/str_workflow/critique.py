from __future__ import annotations

import argparse
import html
import json
import re
import textwrap
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_ASSET_VERSION = "20260707-toc-active"
DEFAULT_HERO_IMAGE = "../../assets/evidence-alignment.png"
DEFAULT_HERO_ALT = "Abstract evidence-alignment illustration with papers, scales, and a magnifying glass."

DEFAULT_METHODS = [
    {
        "title": "Calibration",
        "body": "Belief should track evidential support rather than identity, comfort, or group pressure.",
    },
    {
        "title": "Symmetry",
        "body": "Inductive permission granted to Christianity must be granted to parallel claims unless a real differentiator is supplied.",
    },
    {
        "title": "Architecture",
        "body": "A source of moral rules is not yet a complete moral system with access, binding force, scope, and repair.",
    },
    {
        "title": "Alternatives",
        "body": "Christian explanations must compete with secular, pluralist, psychological, and social explanations.",
    },
    {
        "title": "Bounded Agency",
        "body": "Concern should become proportionate action where agency exists, not inflated cosmic responsibility.",
    },
]

DEFAULT_SECTION_BLUEPRINTS = [
    {
        "id": "worldview",
        "number": 1,
        "label": "Worldview scope",
        "title": "A large frame is not automatically a true frame",
        "keywords": ["worldview", "reality", "Christianity", "Christian"],
        "tag_targets": [
            ("fallacy", "Appeal to consequences", "https://logfall.com/fallacies/appeal-to-consequences/"),
            ("bias", "Confirmation bias", "https://cogbias.site/biases/confirmation-bias/"),
        ],
    },
    {
        "id": "hope",
        "number": 2,
        "label": "Hope and resurrection",
        "title": "Hope is not evidence for the event that would ground it",
        "keywords": ["hope", "risen", "resurrection", "Lord"],
        "tag_targets": [
            ("fallacy", "Begging the question", "https://logfall.com/fallacies/begging-the-question/"),
            ("bias", "Motivated reasoning", "https://cogbias.site/biases/motivated-reasoning/"),
        ],
    },
    {
        "id": "story",
        "number": 3,
        "label": "Narrative framing",
        "title": "The end of the story cannot be imported from an analogy",
        "keywords": ["story", "all things new", "end", "moment"],
        "tag_targets": [
            ("fallacy", "False analogy", "https://logfall.com/fallacies/false-analogy/"),
            ("bias", "Illusion of explanatory depth", "https://cogbias.site/biases/illusion-of-explanatory-depth/"),
        ],
    },
    {
        "id": "identity",
        "number": 4,
        "label": "Identity and morality",
        "title": "A source-story is not yet a public moral system",
        "keywords": ["identity", "sexual", "fallen", "redeem", "created"],
        "tag_targets": [
            ("fallacy", "Equivocation", "https://logfall.com/fallacies/equivocation/"),
            ("bias", "Authority bias", "https://cogbias.site/biases/authority-bias/"),
        ],
    },
    {
        "id": "calling",
        "number": 5,
        "label": "Calling and mission",
        "title": "Good action does not validate every attached explanation",
        "keywords": ["good", "missing", "evil", "mission", "calling"],
        "tag_targets": [
            ("fallacy", "Cherry picking", "https://logfall.com/fallacies/cherry-picking/"),
            ("bias", "Survivorship bias", "https://cogbias.site/biases/survivorship-bias/"),
        ],
    },
]

DEFAULT_VULNERABILITIES = [
    "Worldview Totalization: Examine whether Christianity is asserted as a map of all reality rather than argued to be the uniquely accurate map of all reality.",
    "Private-to-Public Shift: Test whether moving from personal faith to public worldview smuggles in authority claims that still require public justification.",
    "Evidence-Proportionate Belief: Assess whether claims about resurrection, lordship, creation, Fall, redemption, and final restoration receive enough evidence to justify the confidence placed in them.",
    "Pastoral Usefulness Versus Truth: Evaluate whether the existential usefulness of hope, identity, and calling is being treated as evidence that the worldview is true.",
    "Narrative Closure: Analyze whether a promised ending functions as a circular story-ending premise that predetermines the interpretation of present events.",
    "Insider Authority: Examine whether appeals to Scripture and Christian tradition establish the claims only for insiders who already grant those sources authority.",
    "Resurrection Evidence Gap: Evaluate moves from mentioning evidence to treating resurrection as a central reality when the actual evidence is not presented.",
    "Lordship Claim Expansion: Assess whether lordship claims are argued as public facts or merely proclaimed as theological commitments.",
    "Equivocation Risk: Check for shifts in the meanings of worldview, hope, truth, Lord, good, fallen, redeemed, identity, and calling.",
    "Cultural-Moment Framing: Examine whether culture-war examples create a false dilemma, strawman, or asymmetric framing.",
    "Analogy Limits: Test whether literary or pastoral analogies legitimately support public conclusions.",
    "Historical Selectivity: Evaluate uses of church-history examples for cherry-picking, survivorship bias, halo effect, or hasty generalization.",
    "Moral System Threshold: Ask whether theological categories generate determinate moral guidance without additional contested premises.",
    "Inductive Symmetry: Compare the standards used to accept Christian explanatory claims with the standards required for rival worldviews.",
    "Scope Leakage: Identify moves from this helps Christian students live with hope and purpose to therefore Christianity is true or uniquely adequate.",
    "Burden of Proof and Special Pleading: Determine whether rival views are asked to justify themselves while Christian claims are exempted from comparable scrutiny.",
    "Non Sequitur Risk: Identify conclusions that do not follow from premises, especially from moral motivation to metaphysical truth or from scriptural narrative to public epistemic warrant.",
]


class CritiqueValidationError(RuntimeError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def required(obj: dict[str, Any], key: str, path: str, errors: list[str]) -> str:
    value = text(obj.get(key))
    if not value or value.startswith("TODO"):
        errors.append(f"{path}.{key} is required")
    return value


def format_display_date(value: str | None) -> str:
    if not value:
        return "Undated"
    try:
        parsed = date.fromisoformat(value[:10])
    except ValueError:
        return value
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def slug_from_episode_dir(episode_dir: Path) -> str:
    return episode_dir.resolve().name


def load_episode_metadata(episode_dir: Path) -> dict[str, Any]:
    metadata_path = episode_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing episode metadata: {metadata_path}")
    return load_json(metadata_path)


def read_transcript_chunks(episode_dir: Path) -> list[dict[str, Any]]:
    transcript_json = episode_dir / "transcript.json"
    if transcript_json.exists():
        data = load_json(transcript_json)
        chunks = data.get("chunks")
        if isinstance(chunks, list):
            return [chunk for chunk in chunks if isinstance(chunk, dict)]

    transcript_md = episode_dir / "transcript.md"
    if transcript_md.exists():
        return [{"index": 1, "start_seconds": None, "end_seconds": None, "text": transcript_md.read_text(encoding="utf-8")}]
    return []


def format_seconds(seconds: Any) -> str:
    if seconds is None:
        return "--:--"
    try:
        rounded = int(round(float(seconds)))
    except (TypeError, ValueError):
        return "--:--"
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def chunk_range(chunk: dict[str, Any]) -> str:
    start = format_seconds(chunk.get("start_seconds"))
    end = format_seconds(chunk.get("end_seconds"))
    if start == "--:--" and end == "--:--":
        return "Timestamp unavailable"
    return f"{start}-{end}"


def sentences(source: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", source) if part.strip()]


def excerpt_words(source: str, limit: int = 11) -> str:
    words = re.findall(r"[\w'’:-]+", source)
    return " ".join(words[:limit])


def quote_candidates(chunks: list[dict[str, Any]], keywords: list[str], limit: int = 3) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for chunk in chunks:
        chunk_text = text(chunk.get("text"))
        haystack = chunk_text.lower()
        if not any(keyword.lower() in haystack for keyword in keywords):
            continue
        for sentence in sentences(chunk_text):
            lower = sentence.lower()
            if not any(keyword.lower() in lower for keyword in keywords):
                continue
            quote = excerpt_words(sentence)
            if len(quote) < 4 or quote.lower() in seen:
                continue
            seen.add(quote.lower())
            found.append({"quote": quote, "label": "Transcript phrase", "range": chunk_range(chunk)})
            if len(found) >= limit:
                return found
    return found


def best_range(candidates: list[dict[str, str]]) -> str:
    ranges = [item.get("range") for item in candidates if item.get("range")]
    return ranges[0] if ranges else "TODO timestamp range"


def source_anchor_suggestions(source_index: dict[str, Any], tags: list[str], limit: int = 4) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []
    for item in source_index.get("freeoffaith", []):
        item_tags = set(item.get("relevance_tags") or [])
        title = text(item.get("title"))
        if not title or not item.get("url"):
            continue
        if item_tags.intersection(tags):
            suggestions.append({"label": title[:64], "url": item["url"], "tone": "gold"})
        if len(suggestions) >= limit:
            return suggestions
    return suggestions


def scaffold_spec(episode_dir: Path, source_index_path: Path) -> dict[str, Any]:
    metadata = load_episode_metadata(episode_dir)
    chunks = read_transcript_chunks(episode_dir)
    source_index = load_json(source_index_path) if source_index_path.exists() else {}

    sections = []
    for blueprint in DEFAULT_SECTION_BLUEPRINTS:
        candidates = quote_candidates(chunks, blueprint["keywords"])
        quotes = candidates or [
            {"quote": "TODO short exact quote", "label": "TODO claim anchor", "range": "TODO timestamp range"},
            {"quote": "TODO short exact quote", "label": "TODO claim anchor", "range": "TODO timestamp range"},
        ]
        anchors = source_anchor_suggestions(source_index, blueprint["keywords"])
        sections.append(
            {
                "id": blueprint["id"],
                "number": blueprint["number"],
                "label": blueprint["label"],
                "kicker": f"{blueprint['number']}. {blueprint['label']}",
                "title": blueprint["title"],
                "paragraphs": [
                    {
                        "text": "TODO reconstruct the strongest version of the transcript claim in this section.",
                        "note_label": f"Expand {blueprint['label']} explanation",
                        "note": "TODO expansive elaboration: explain the inference, why it is weak or under-supported, and what would make it stronger.",
                    },
                    "TODO critique paragraph that separates pastoral, psychological, moral, historical, and evidential claims.",
                ],
                "research_anchors": anchors
                or [{"label": "TODO Free of Faith or framework anchor", "url": "https://freeoffaith.com/", "tone": "gold"}],
                "research_note": "TODO explain exactly how these Free of Faith / framework sources shape this section.",
                "transcript": {
                    "range": best_range(quotes),
                    "quotes": [{"quote": item["quote"], "label": item["label"]} for item in quotes[:3]],
                    "claim": "TODO identify the specific transcript claim these quotes anchor.",
                },
                "audit_rows": [
                    {
                        "claim": "TODO section claim",
                        "evidence": "TODO evidence actually supplied in the transcript",
                        "critique": "TODO critique or confidence downgrade",
                    }
                ],
                "formalization": {
                    "intro": "TODO define the main variables in natural language.",
                    "latex": "\\[\\begin{aligned}\nP &:= \\text{TODO premise.}\\\\\nQ &:= \\text{TODO conclusion.}\\\\\nP &\\not\\Rightarrow Q\n\\end{aligned}\\]",
                    "assessment": "TODO explain what the formalization shows.",
                },
                "tags": [
                    {
                        "kind": kind,
                        "label": label,
                        "url": url,
                        "tone": "red" if kind == "fallacy" else "blue",
                        "fit": "TODO",
                        "application": "TODO explain how this applies to a specific claim or quote in the transcript.",
                    }
                    for kind, label, url in blueprint["tag_targets"]
                ],
            }
        )

    steelman_claims = [
        f"TODO steelman claim grounded in the transcript: {item['quote']}"
        for section in sections
        for item in section["transcript"]["quotes"][:1]
    ]

    return {
        "schema_version": 1,
        "episode": {
            "title": text(metadata.get("title")) or "Untitled episode",
            "page_title": text(metadata.get("title")) or "Untitled episode",
            "meta_description": f"A formal critique of the STR episode {text(metadata.get('title')) or 'Untitled episode'}.",
            "pub_date": text(metadata.get("pub_date")),
            "display_date": format_display_date(text(metadata.get("pub_date"))),
            "slug": text(metadata.get("slug")) or slug_from_episode_dir(episode_dir),
            "source_label": "Stand to Reason Weekly Podcast / Podbean",
            "source_url": text(metadata.get("podcast_page_url")),
            "speaker": "TODO speaker(s)",
            "transcript_source": "TODO transcript source, ASR model, and timestamp limitations.",
            "lede": "TODO concise thesis of the critique.",
            "hero_image": DEFAULT_HERO_IMAGE,
            "hero_alt": DEFAULT_HERO_ALT,
        },
        "episode_nav": {
            "previous": {
                "title": "TODO previous older critique title, or set this value to null for the oldest critique",
                "url": "TODO relative URL to previous older critique",
            },
            "next": {
                "title": "TODO next newer critique title, or set this value to null for the newest critique",
                "url": "TODO relative URL to next newer critique",
            },
        },
        "quote_strip": [
            {"quote": item["quote"], "label": section["label"]}
            for section in sections
            for item in section["transcript"]["quotes"][:1]
        ][:4],
        "methods": DEFAULT_METHODS,
        "research": {
            "body": [
                "TODO summarize how this critique uses the Free of Faith Insights and Considerations source index plus local academic/framework summaries."
            ],
            "rows": [
                {
                    "area": section["label"],
                    "anchors": section["research_anchors"],
                    "local_anchor": "TODO local academic/framework anchor",
                    "application": "TODO how the sources shape this section",
                }
                for section in sections
            ],
        },
        "claim_map": [
            {
                "number": section["number"],
                "family": section["label"],
                "reconstruction": "TODO concise reconstruction",
                "status": "TODO status",
                "status_tone": "gold",
                "risk": "TODO main inferential risk",
            }
            for section in sections
        ],
        "sections": sections,
        "overall": {
            "kicker": "Overall Assessment",
            "title": "TODO charitable repair title",
            "paragraphs": [
                "TODO summarize the charitable repair.",
                "TODO state the strongest modest claim the transcript can support.",
            ],
            "epistemic_reality": {
                "kicker": "The epistemic reality",
                "title": "TODO rebuke over-certainty that outruns evidence",
                "paragraphs": [
                    "TODO explain which assertions are made with more certainty than the transcript supports.",
                    "TODO explain the responsible confidence downgrade.",
                ],
                "bullets": [
                    "TODO unsupported certainty claim",
                    "TODO missing comparative evidence",
                    "TODO missing public warrant",
                ],
            },
        },
        "evidence_needed": [
            {
                "area": section["label"],
                "raise": "TODO evidence that would raise confidence",
                "lower": "TODO evidence that would lower confidence",
            }
            for section in sections
        ],
        "ai_prompt": {
            "episode_title": text(metadata.get("title")) or "Untitled episode",
            "steelman_claims": steelman_claims,
            "vulnerabilities": DEFAULT_VULNERABILITIES,
        },
        "source_list": [
            {"label": "Official STR / Podbean episode page", "url": text(metadata.get("podcast_page_url"))},
            {"label": "Free of Faith Insights archive", "url": "https://freeoffaith.com/category/insights/"},
            {"label": "Free of Faith Considerations archive", "url": "https://freeoffaith.com/category/considerations/"},
            {"label": "OnReason source index", "url": "https://github.com/philstilwell/str/blob/main/research/source-index.json"},
        ],
        "rail": {
            "status": "TODO draft status and transcript timing note.",
            "fallacies": [
                {"label": "Consequences", "url": "https://logfall.com/fallacies/appeal-to-consequences/"},
                {"label": "Question-begging", "url": "https://logfall.com/fallacies/begging-the-question/"},
            ],
            "biases": [
                {"label": "Confirmation", "url": "https://cogbias.site/biases/confirmation-bias/"},
                {"label": "Motivated reasoning", "url": "https://cogbias.site/biases/motivated-reasoning/"},
            ],
        },
    }


def validate_spec(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    episode = spec.get("episode") if isinstance(spec.get("episode"), dict) else {}
    for key in ("title", "pub_date", "display_date", "slug", "source_url", "speaker", "transcript_source", "lede"):
        required(episode, key, "episode", errors)

    episode_nav = spec.get("episode_nav")
    if not isinstance(episode_nav, dict):
        errors.append("episode_nav must define previous and next critique links")
    else:
        linked_nav_items = 0
        for key in ("previous", "next"):
            item = episode_nav.get(key)
            if item is None:
                continue
            if not isinstance(item, dict):
                errors.append(f"episode_nav.{key} must be an object or null")
                continue
            required(item, "title", f"episode_nav.{key}", errors)
            required(item, "url", f"episode_nav.{key}", errors)
            if text(item.get("url")) and not text(item.get("url")).startswith("TODO"):
                linked_nav_items += 1
        if linked_nav_items == 0:
            errors.append("episode_nav must include at least one linked adjacent critique")

    methods = spec.get("methods")
    if not isinstance(methods, list) or len(methods) < 4:
        errors.append("methods must contain at least four method cards")

    research = spec.get("research") if isinstance(spec.get("research"), dict) else {}
    if not research.get("rows") or len(research.get("rows", [])) < 3:
        errors.append("research.rows must map critique areas to Free of Faith/local framework anchors")

    claim_map = spec.get("claim_map")
    sections = spec.get("sections")
    if not isinstance(claim_map, list) or len(claim_map) < 3:
        errors.append("claim_map must contain at least three substantive claims")
    if not isinstance(sections, list) or len(sections) < 3:
        errors.append("sections must contain at least three substantive critique sections")
        return errors

    claim_numbers = [item.get("number") for item in claim_map or [] if isinstance(item, dict)]
    section_numbers = [item.get("number") for item in sections if isinstance(item, dict)]
    if claim_numbers and claim_numbers != section_numbers[: len(claim_numbers)]:
        errors.append("claim_map numbers must match the numbered critique sections")

    for index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            errors.append(f"sections[{index}] must be an object")
            continue
        path = f"sections[{index}]"
        for key in ("id", "number", "label", "kicker", "title", "research_note"):
            required(section, key, path, errors)

        paragraphs = section.get("paragraphs")
        if not isinstance(paragraphs, list) or len(paragraphs) < 2:
            errors.append(f"{path}.paragraphs must contain at least two paragraphs")
        elif not any(isinstance(p, dict) and text(p.get("note")) and not text(p.get("note")).startswith("TODO") for p in paragraphs):
            errors.append(f"{path}.paragraphs must include an expansive ◉ note")

        anchors = section.get("research_anchors")
        if not isinstance(anchors, list) or len(anchors) < 2:
            errors.append(f"{path}.research_anchors must include at least two Free of Faith/framework anchors")

        transcript = section.get("transcript") if isinstance(section.get("transcript"), dict) else {}
        required(transcript, "range", f"{path}.transcript", errors)
        required(transcript, "claim", f"{path}.transcript", errors)
        quotes = transcript.get("quotes")
        if not isinstance(quotes, list) or len(quotes) < 2:
            errors.append(f"{path}.transcript.quotes must include at least two short quotes")
        else:
            for q_index, quote in enumerate(quotes, start=1):
                if not isinstance(quote, dict):
                    errors.append(f"{path}.transcript.quotes[{q_index}] must be an object")
                    continue
                required(quote, "quote", f"{path}.transcript.quotes[{q_index}]", errors)
                required(quote, "label", f"{path}.transcript.quotes[{q_index}]", errors)

        audit_rows = section.get("audit_rows")
        if not isinstance(audit_rows, list) or not audit_rows:
            errors.append(f"{path}.audit_rows must tie claims to transcript evidence and critique")

        formalization = section.get("formalization") if isinstance(section.get("formalization"), dict) else {}
        latex = required(formalization, "latex", f"{path}.formalization", errors)
        required(formalization, "assessment", f"{path}.formalization", errors)
        if latex and "\\[" not in latex:
            errors.append(f"{path}.formalization.latex must use display LaTeX")

        tags = section.get("tags")
        if not isinstance(tags, list) or len(tags) < 2:
            errors.append(f"{path}.tags must include fallacy/bias explainers")
        else:
            if not any("logfall.com" in text(tag.get("url")) for tag in tags if isinstance(tag, dict)):
                errors.append(f"{path}.tags must include at least one LogFall link")
            if not any("cogbias.site" in text(tag.get("url")) for tag in tags if isinstance(tag, dict)):
                errors.append(f"{path}.tags must include at least one CogBias link")
            for tag_index, tag in enumerate(tags, start=1):
                if not isinstance(tag, dict):
                    errors.append(f"{path}.tags[{tag_index}] must be an object")
                    continue
                required(tag, "label", f"{path}.tags[{tag_index}]", errors)
                required(tag, "url", f"{path}.tags[{tag_index}]", errors)
                required(tag, "fit", f"{path}.tags[{tag_index}]", errors)
                required(tag, "application", f"{path}.tags[{tag_index}]", errors)

    overall = spec.get("overall") if isinstance(spec.get("overall"), dict) else {}
    epistemic = overall.get("epistemic_reality") if isinstance(overall.get("epistemic_reality"), dict) else {}
    required(overall, "title", "overall", errors)
    required(epistemic, "title", "overall.epistemic_reality", errors)
    if not epistemic.get("paragraphs") or not epistemic.get("bullets"):
        errors.append("overall.epistemic_reality must include paragraphs and bullets")

    evidence_needed = spec.get("evidence_needed")
    if not isinstance(evidence_needed, list) or len(evidence_needed) < len(sections):
        errors.append("evidence_needed must include calibration tests for each critique section")

    ai_prompt = spec.get("ai_prompt") if isinstance(spec.get("ai_prompt"), dict) else {}
    claims = ai_prompt.get("steelman_claims")
    if not isinstance(claims, list) or len(claims) < max(5, len(sections)):
        errors.append("ai_prompt.steelman_claims must contain actual steelmanned transcript claims")
    elif any(text(claim).startswith("TODO") for claim in claims):
        errors.append("ai_prompt.steelman_claims still contains TODO placeholders")
    vulnerabilities = ai_prompt.get("vulnerabilities")
    if not isinstance(vulnerabilities, list) or len(vulnerabilities) < 8:
        errors.append("ai_prompt.vulnerabilities must preserve the systematic audit checklist")

    return errors


def validate_page(path: Path) -> list[str]:
    html_text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    checks = {
        "brand": "OnReason",
        "roman_toc_css": "toc",
        "popover_notes": 'class="note"',
        "transcript_anchors": "transcript-anchors",
        "quote_anchor_grid": "quote-anchor-grid",
        "research_anchors": "research-anchors",
        "episode_nav": "episode-nav-band",
        "toc_active_script": f"app.js?v={DEFAULT_ASSET_VERSION}",
        "tag_explainers": "tag-explainer",
        "diagnostic_fit": "Diagnostic fit:",
        "formal_latex": "\\[",
        "epistemic_reality": "epistemic-reality",
        "ai_prompt": "The Steelmanned Condensed Claims:",
        "symbols": "✶",
    }
    for name, needle in checks.items():
        if needle not in html_text:
            errors.append(f"page missing {name}: {needle}")
    prompt_start = html_text.find("The Steelmanned Condensed Claims:")
    prompt_end = html_text.find("Treat the claims above", prompt_start)
    if prompt_start == -1 or prompt_end == -1 or html_text[prompt_start:prompt_end].count("◉") < 5:
        errors.append("page AI prompt must include at least five steelmanned condensed claims")
    if "ALL-CAPS" not in html_text:
        errors.append("page AI prompt must instruct ALL-CAPS major section headers")
    if "episode-nav-link" not in html_text:
        errors.append("page must include at least one linked previous/next critique control")
    nav_controls = html_text.count("episode-nav-link") + html_text.count("episode-nav-disabled")
    if nav_controls < 2:
        errors.append("page must include previous and next critique controls")
    if "</a>;" in html_text:
        errors.append("page research links must use space separators instead of semicolons")
    if html_text.count("transcript-anchors") < 4:
        errors.append("page must include transcript anchors for at least four substantive sections")
    if html_text.count('class="note"') < html_text.count("transcript-anchors"):
        errors.append("page must include an expanded ◉ note for each substantive critique section")
    if html_text.count("tag-explainer") < 6:
        errors.append("page must include multiple fallacy/bias explanation cards")
    if html_text.count("Diagnostic fit:") < 6:
        errors.append("page must explain diagnostic fit for fallacies/biases")
    if html_text.count("◉") < 8:
        errors.append("page must include expanded ◉ notes and prompt bullets")
    if html_text.count("<q>") < 8:
        errors.append("page must include short direct quotes tied to transcript claims")
    if "https://freeoffaith.com/" not in html_text:
        errors.append("page must reference Free of Faith research anchors")
    if "https://logfall.com/" not in html_text:
        errors.append("page must link fallacies to LogFall")
    if "https://cogbias.site/" not in html_text:
        errors.append("page must link biases to CogBias")
    return errors


def anchor_html(anchor: dict[str, Any]) -> str:
    tone = text(anchor.get("tone")) or "gold"
    return f'<a class="link-pill {esc(tone)}" href="{esc(anchor.get("url"))}">{esc(anchor.get("label"))}</a>'


def episode_nav_control(item: Any, key: str) -> str:
    label = "Previous" if key == "previous" else "Next"
    if isinstance(item, dict) and text(item.get("url")):
        title = text(item.get("title")) or f"{label} critique"
        return (
            f'<a class="episode-nav-link {esc(key)}" href="{esc(item.get("url"))}" '
            f'aria-label="{esc(label)} critique: {esc(title)}" title="{esc(title)}">'
            f'<span>{esc(label)}</span></a>'
        )
    return (
        f'<span class="episode-nav-disabled {esc(key)}" aria-disabled="true">'
        f'<span>{esc(label)}</span></span>'
    )


def paragraph_html(item: Any) -> str:
    if isinstance(item, dict):
        body = esc(item.get("text"))
        note = text(item.get("note"))
        if note:
            label = text(item.get("note_label")) or "Expand critique explanation"
            body += (
                f' <button class="note" type="button" aria-label="{esc(label)}" aria-expanded="false">'
                f'◉<span class="popover" role="tooltip">{esc(note)}</span></button>'
            )
        return f"<p>{body}</p>"
    return f"<p>{esc(item)}</p>"


def render_table(headers: list[str], rows: list[list[str]], class_name: str = "claim-table") -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{cell}</td>" for cell in row)
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        '<div class="table-scroll">\n'
        f'  <table class="{class_name}">\n'
        f"    <thead><tr>{head}</tr></thead>\n"
        f"    <tbody>{''.join(body_rows)}</tbody>\n"
        "  </table>\n"
        "</div>"
    )


def build_ai_prompt(spec: dict[str, Any]) -> str:
    ai_prompt = spec.get("ai_prompt", {})
    episode_title = text(ai_prompt.get("episode_title")) or text(spec.get("episode", {}).get("title"))
    claims = ai_prompt.get("steelman_claims") or []
    vulnerabilities = ai_prompt.get("vulnerabilities") or DEFAULT_VULNERABILITIES
    claim_lines = "\n".join(f"◉ {text(claim)}" for claim in claims)
    vulnerability_lines = "\n".join(f"◉ {text(item)}" for item in vulnerabilities)
    return f"""PASTE THIS PROMPT INTO YOUR FAVORITE AI:

Analyze the following steelmanned condensed argument from the Stand to Reason episode "{episode_title}" for logical fallacies, cognitive biases, logical incoherencies, non sequiturs, evidential overreach, and structural weaknesses.

The Steelmanned Condensed Claims:
{claim_lines}

Treat the claims above as a steelman reconstruction of the episode's argument. Do not weaken, caricature, or replace that reconstruction before critiquing it. Preserve the intended pastoral and formational force of the argument while assessing whether even this best version succeeds.

Provide a rigorous, exhaustive critique of the argument. Use the principle that rational belief is a degree of belief that should map to the degree of the relevant evidence. Use clear section headers and subheaders, with common indicators such as "SECTION 1:", "1.1", "Subsection:", "#", or "##" when helpful. Use a variety of structural symbols throughout the response: "✶" for major section takeaways, "◉" for primary analytical points, and "➘" for subordinate implications, evidence-flow notes, or follow-up tests. Do not use asterisks for bolding or italics.

Required output structure:
✶ Start each major section with a short ALL-CAPS header.
◉ Use primary bullets for main criticisms, repairs, or conclusions.
➘ Use subordinate bullets for evidential details, hidden assumptions, inferential moves, and examples.
✶ Include at least these main sections, formatted in ALL-CAPS: Steelman Being Evaluated, Claim-by-Claim Audit, Fallacies and Biases, Structural Weaknesses, Repaired Argument, Evidence Needed, and Confidence Downgrades.

For each major claim, assess:
◉ What the claim would mean if true.
◉ What evidence is actually supplied in the steelmanned condensed argument.
◉ What evidence is asserted but not presented.
◉ What rival explanations or rival worldviews must be compared.
◉ Whether the confidence expressed exceeds the evidence supplied.
◉ Which assumptions are doing hidden work.
◉ Whether the claim is primarily pastoral, psychological, moral, historical, metaphysical, or evidential.

Ensure your analysis exhaustively addresses the following vulnerabilities in the original claims:
{vulnerability_lines}

Conclude with:
◉ The strongest charitable version of the argument after repair.
◉ The minimum evidence and reasoning required for the repaired version to justify stronger confidence.
◉ A short list of claims that should be downgraded in confidence if rational belief must map to the degree of relevant evidence."""


def render_critique(spec: dict[str, Any]) -> str:
    errors = validate_spec(spec)
    if errors:
        raise CritiqueValidationError(errors)

    episode = spec["episode"]
    css_version = esc(spec.get("asset_version") or DEFAULT_ASSET_VERSION)
    title = text(episode.get("page_title")) or text(episode.get("title"))
    toc_items = [
        ("overview", "Thesis and overview"),
        ("method", "Method"),
        ("research", "Research base"),
        ("map", "Claim map"),
    ]
    toc_items.extend((section["id"], f'{section["number"]}. {section["label"]}') for section in spec["sections"])
    toc_items.extend([("overall", "Overall assessment"), ("evidence-needed", "Evidence needed"), ("prompt", "AI prompt")])

    toc_html = "\n".join(f'          <li><a href="#{esc(target)}">{esc(label)}</a></li>' for target, label in toc_items)
    quote_strip = "\n".join(
        f'            <div class="quote-chip"><strong>“{esc(item.get("quote"))}”</strong><span>{esc(item.get("label"))}</span></div>'
        for item in spec.get("quote_strip", [])
    )
    method_cards = "\n".join(
        f'              <div class="method-card"><strong>{esc(item.get("title"))}</strong><p>{esc(item.get("body"))}</p></div>'
        for item in spec.get("methods", [])
    )

    research_rows = []
    for row in spec["research"]["rows"]:
        anchors = " ".join(anchor_html(anchor) for anchor in row.get("anchors", []))
        research_rows.append([esc(row.get("area")), anchors, esc(row.get("local_anchor")), esc(row.get("application"))])

    claim_rows = []
    for row in spec["claim_map"]:
        tone = text(row.get("status_tone")) or "gold"
        claim_rows.append(
            [
                f'{esc(row.get("number"))}. {esc(row.get("family"))}',
                esc(row.get("reconstruction")),
                f'<span class="badge {esc(tone)}">{esc(row.get("status"))}</span>',
                esc(row.get("risk")),
            ]
        )

    section_html = "\n".join(render_section(section) for section in spec["sections"])
    episode_nav = spec.get("episode_nav", {})
    previous_nav = episode_nav_control(episode_nav.get("previous"), "previous")
    next_nav = episode_nav_control(episode_nav.get("next"), "next")
    prompt = build_ai_prompt(spec)
    source_items = "\n".join(
        f'              <li><a href="{esc(item.get("url"))}">{esc(item.get("label"))}</a>.</li>'
        for item in spec.get("source_list", [])
    )
    rail = spec.get("rail", {})
    rail_fallacies = "\n".join(anchor_html({**item, "tone": "red"}) for item in rail.get("fallacies", []))
    rail_biases = "\n".join(anchor_html({**item, "tone": "blue"}) for item in rail.get("biases", []))

    evidence_rows = [
        [esc(row.get("area")), esc(row.get("raise")), esc(row.get("lower"))]
        for row in spec.get("evidence_needed", [])
    ]

    overall = spec["overall"]
    epistemic = overall["epistemic_reality"]
    overall_paragraphs = "\n".join(paragraph_html(item) for item in overall.get("paragraphs", []))
    epistemic_paragraphs = "\n".join(f"              <p>{esc(item)}</p>" for item in epistemic.get("paragraphs", []))
    epistemic_bullets = "\n".join(f"                <li>{esc(item)}</li>" for item in epistemic.get("bullets", []))
    research_intro = "\n".join(paragraph_html(item) for item in spec["research"].get("body", []))

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{esc(title)} | OnReason</title>
    <meta name="description" content="{esc(episode.get("meta_description"))}">
    <link rel="icon" href="../../assets/favicon.svg" type="image/svg+xml">
    <link rel="stylesheet" href="../../assets/styles.css?v={css_version}">
    <script>
      window.MathJax = {{
        tex: {{
          inlineMath: [["\\\\(", "\\\\)"]],
          displayMath: [["\\\\[", "\\\\]"]],
          processEscapes: true
        }},
        chtml: {{
          matchFontHeight: false
        }}
      }};
    </script>
    <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
  </head>
  <body>
    <header class="site-header">
      <a class="brand" href="../../">
        <span class="brand-mark">O</span>
        <span class="brand-copy">
          <strong class="brand-name"><span class="brand-on">On</span><span class="brand-reason">Reason</span></strong>
          <span class="brand-tagline">Faith. Evidence. Calibration.</span>
        </span>
      </a>
      <nav class="site-nav" aria-label="Primary">
        <a href="../../" aria-current="page">Critiques</a>
        <a href="https://freeoffaith.com/core-rationality/">Methodology</a>
        <a href="https://logfall.com/fallacies/">Fallacies</a>
        <a href="https://cogbias.site/biases/">Biases</a>
      </nav>
    </header>

    <div class="page-shell">
      <aside class="toc is-open" aria-label="Contents">
        <button class="toc-toggle" type="button" aria-expanded="true" aria-controls="toc-list">Contents</button>
        <p class="toc-title">Contents</p>
        <ol id="toc-list">
{toc_html}
        </ol>
      </aside>

      <main class="article">
        <article>
          <nav class="episode-nav-band" aria-label="Adjacent episode critiques">
            {previous_nav}
            {next_nav}
          </nav>

          <header class="article-header" id="overview">
            <div>
              <p class="date">{esc(episode.get("display_date"))}</p>
              <h1>{esc(episode.get("title"))}</h1>
              <dl class="meta-list">
                <div><dt>Episode source</dt><dd><a href="{esc(episode.get("source_url"))}">{esc(episode.get("source_label"))}</a></dd></div>
                <div><dt>Speaker</dt><dd>{esc(episode.get("speaker"))}</dd></div>
                <div><dt>Transcript source for this critique</dt><dd>{esc(episode.get("transcript_source"))}</dd></div>
              </dl>
              <p class="lede">{esc(episode.get("lede"))}</p>
            </div>
            <figure class="hero-asset">
              <img src="{esc(episode.get("hero_image") or DEFAULT_HERO_IMAGE)}" alt="{esc(episode.get("hero_alt") or DEFAULT_HERO_ALT)}">
            </figure>
          </header>

          <section class="quote-strip" aria-label="Short quote anchors">
{quote_strip}
          </section>

          <section class="section-panel" id="method">
            <p class="section-kicker">Critique Framework</p>
            <h2>How this page evaluates the episode</h2>
            <div class="method-strip">
{method_cards}
            </div>
          </section>

          <section class="section-panel" id="research">
            <p class="section-kicker">Research Backbone</p>
            <h2>Claims are mapped to Free of Faith and local framework sources</h2>
{research_intro}
{render_table(["Critique area", "Free of Faith anchors", "Local framework / academic anchor", "How it shapes this critique"], research_rows, "claim-table source-map-table")}
          </section>

          <section class="section-panel" id="map">
            <p class="section-kicker">Claim Mapping</p>
            <h2>Low-content announcements skipped; substantive themes retained</h2>
{render_table(["Claim family", "Reconstruction", "Status", "Main risk"], claim_rows)}
          </section>

{section_html}

          <section class="section-panel" id="overall">
            <p class="section-kicker">{esc(overall.get("kicker"))}</p>
            <h2>{esc(overall.get("title"))}</h2>
{overall_paragraphs}
            <div class="epistemic-reality" aria-label="The epistemic reality">
              <p class="dark-kicker">{esc(epistemic.get("kicker"))}</p>
              <h3>{esc(epistemic.get("title"))}</h3>
{epistemic_paragraphs}
              <ul>
{epistemic_bullets}
              </ul>
            </div>
          </section>

          <section class="section-panel" id="evidence-needed">
            <p class="section-kicker">Calibration Tests</p>
            <h2>Evidence that would change the assessment</h2>
            <p>The critique is not designed to be unfalsifiable. Several kinds of evidence would strengthen the episode's claims if supplied with enough specificity and symmetry.</p>
{render_table(["Area", "Would raise confidence", "Would lower confidence"], evidence_rows, "claim-table evidence-needed-table")}
          </section>

          <section class="section-panel" id="prompt">
            <p class="section-kicker">AI Assessment Prompt</p>
            <h2>Prompt for independent assessment</h2>
            <p>Paste this into an AI system. The prompt already includes a steelmanned condensation of the episode's claims, then asks for a systematic coherence audit grounded in evidence-proportionate belief.</p>
            <div class="prompt-box">
              <div class="prompt-header">
                <h3>Copy-ready prompt</h3>
                <button class="copy-button" type="button" data-copy-target="#ai-prompt">Copy prompt</button>
              </div>
              <pre class="prompt-text" id="ai-prompt">{esc(prompt)}</pre>
            </div>
          </section>

          <section class="source-list">
            <h3>Source Base for This Draft</h3>
            <ul>
{source_items}
            </ul>
          </section>
        </article>
      </main>

      <aside class="analysis-rail" aria-label="Evidence and analysis">
        <p class="rail-title">Evidence &amp; Analysis</p>
        <div class="rail-box">
          <h3>Draft Status</h3>
          <p>{esc(rail.get("status"))}</p>
        </div>
        <div class="rail-box">
          <h3>Fallacies Flagged</h3>
          <div class="tag-grid">
{rail_fallacies}
          </div>
        </div>
        <div class="rail-box">
          <h3>Biases Flagged</h3>
          <div class="tag-grid">
{rail_biases}
          </div>
        </div>
        <div class="rail-box">
          <h3>About the ◉ marker</h3>
          <p>Click, hover, or focus each symbol to open an expanded explanation of the nearby critique point, including the evidential standard, the weak inference, and what a stronger argument would need.</p>
        </div>
      </aside>
    </div>

    <footer class="footer">
      <p>This page critiques public claims and does not republish the source transcript. Links open the official episode, methodology sources, and fallacy/bias reference pages.</p>
    </footer>
    <script src="../../assets/app.js?v={css_version}"></script>
  </body>
</html>
"""


def render_section(section: dict[str, Any]) -> str:
    paragraphs = "\n".join(paragraph_html(item) for item in section.get("paragraphs", []))
    research_anchors = "\n".join(anchor_html(anchor) for anchor in section.get("research_anchors", []))
    transcript = section["transcript"]
    quote_cards = "\n".join(
        f'                <article class="quote-anchor"><q>{esc(item.get("quote"))}</q><span>{esc(item.get("label"))}</span></article>'
        for item in transcript.get("quotes", [])
    )
    audit_rows = [
        [esc(row.get("claim")), esc(row.get("evidence")), esc(row.get("critique"))]
        for row in section.get("audit_rows", [])
    ]
    formalization = section["formalization"]
    tags = "\n".join(
        (
            '              <article class="tag-explainer">\n'
            f'                {anchor_html(tag)}\n'
            f'                <span class="severity {esc(text(tag.get("fit")).lower().replace(" ", "-"))}">Diagnostic fit: {esc(tag.get("fit"))}</span>\n'
            f'                <p>{esc(tag.get("application"))}</p>\n'
            "              </article>"
        )
        for tag in section.get("tags", [])
    )
    return f"""          <section class="section-panel" id="{esc(section.get("id"))}">
            <p class="section-kicker">{esc(section.get("kicker"))}</p>
            <h2>{esc(section.get("title"))}</h2>
{paragraphs}
            <div class="research-anchors" aria-label="{esc(section.get("label"))} research anchors">
              <strong>Research anchors</strong>
{research_anchors}
              <span class="source-note">{esc(section.get("research_note"))}</span>
            </div>
            <div class="transcript-anchors" aria-label="{esc(section.get("label"))} transcript anchors">
              <div class="anchor-head">
                <strong>Transcript anchors</strong>
                <span>{esc(transcript.get("range"))}</span>
              </div>
              <div class="quote-anchor-grid">
{quote_cards}
              </div>
              <p>{esc(transcript.get("claim"))}</p>
            </div>
            <div class="table-scroll compact-audit">
{render_table(["Claim", "Evidence in transcript", "Critique / downgrade"], audit_rows, "claim-table audit-table")}
            </div>
            <div class="formal-block">
              <div>
                <h3>Formalization</h3>
                <p>{esc(formalization.get("intro"))}</p>
                <div class="logic">
{text(formalization.get("latex"))}
                </div>
              </div>
              <div>
                <h3>Assessment</h3>
                <p>{esc(formalization.get("assessment"))}</p>
              </div>
            </div>
            <div class="tag-grid tag-explainers">
{tags}
            </div>
          </section>"""


def drafting_prompt(spec: dict[str, Any]) -> str:
    claims = "\n".join(f"- {item}" for item in spec.get("ai_prompt", {}).get("steelman_claims", []))
    return textwrap.dedent(
        f"""
        Build an OnReason critique spec from the transcript-derived scaffold.

        Episode: {spec.get("episode", {}).get("title")}

        Fill every TODO in critique-draft.json. Keep direct transcript quotes short, include timestamp ranges when possible, and ground every section in Free of Faith Insights/Considerations plus local framework anchors from research/source-index.json.

        The AI prompt must include steelmanned claims actually made in the transcript. Current scaffold claims:
        {claims}

        Before rendering, run:
        python -m str_workflow.critique validate --spec output/critique-drafts/{spec.get("episode", {}).get("slug")}/critique-draft.json
        """
    ).strip() + "\n"


def command_scaffold(args: argparse.Namespace) -> int:
    episode_dir = Path(args.episode_dir)
    source_index = Path(args.source_index)
    spec = scaffold_spec(episode_dir, source_index)
    out_dir = Path(args.out_dir) / spec["episode"]["slug"]
    spec_path = out_dir / "critique-draft.json"
    write_json(spec_path, spec)
    (out_dir / "draft-prompt.txt").write_text(drafting_prompt(spec), encoding="utf-8")
    print(f"wrote {spec_path}")
    print(f"wrote {out_dir / 'draft-prompt.txt'}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    spec = load_json(Path(args.spec))
    errors = validate_spec(spec)
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print("critique spec ok")
    return 0


def command_render(args: argparse.Namespace) -> int:
    spec = load_json(Path(args.spec))
    html_text = render_critique(spec)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")
    print(f"wrote {out}")
    return 0


def command_validate_page(args: argparse.Namespace) -> int:
    errors = validate_page(Path(args.page))
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print("critique page ok")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scaffold, validate, and render OnReason critique pages.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scaffold = subparsers.add_parser("scaffold", help="Create a local critique draft spec from episode metadata/transcript.")
    scaffold.add_argument("--episode-dir", required=True, help="Path to corpus/episodes/<slug>.")
    scaffold.add_argument("--source-index", default="research/source-index.json", help="Path to source-index.json.")
    scaffold.add_argument("--out-dir", default="output/critique-drafts", help="Local draft output directory.")
    scaffold.set_defaults(func=command_scaffold)

    validate = subparsers.add_parser("validate", help="Validate a critique JSON spec before rendering.")
    validate.add_argument("--spec", required=True)
    validate.set_defaults(func=command_validate)

    render = subparsers.add_parser("render", help="Render a validated critique JSON spec to public HTML.")
    render.add_argument("--spec", required=True)
    render.add_argument("--out", required=True)
    render.set_defaults(func=command_render)

    validate_page_cmd = subparsers.add_parser("validate-page", help="Validate a rendered critique page.")
    validate_page_cmd.add_argument("--page", required=True)
    validate_page_cmd.set_defaults(func=command_validate_page)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
