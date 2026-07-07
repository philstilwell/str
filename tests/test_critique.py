from __future__ import annotations

import copy
import json
from pathlib import Path

from str_workflow.critique import render_critique, scaffold_spec, validate_page, validate_spec


def valid_spec() -> dict:
    sections = []
    labels = [
        ("worldview", 1, "Worldview scope"),
        ("hope", 2, "Hope and resurrection"),
        ("story", 3, "Narrative framing"),
        ("identity", 4, "Identity and morality"),
    ]
    for section_id, number, label in labels:
        sections.append(
            {
                "id": section_id,
                "number": number,
                "label": label,
                "kicker": f"{number}. {label}",
                "title": f"Test title for {label}",
                "paragraphs": [
                    {
                        "text": f"The transcript makes a substantive {label.lower()} claim.",
                        "note_label": f"Expand {label}",
                        "note": "This note explains the inference, the evidential gap, the hidden premise, and what would improve the argument.",
                    },
                    "The critique separates pastoral usefulness from public warrant.",
                ],
                "research_anchors": [
                    {"label": "Free of Faith anchor", "url": "https://freeoffaith.com/2024/11/11/21/", "tone": "gold"},
                    {"label": "Framework anchor", "url": "https://freeoffaith.com/2026/01/27/parsimony-and-christianity/", "tone": "blue"},
                ],
                "research_note": "These anchors require comparative testing and evidence-proportionate belief.",
                "transcript": {
                    "range": "00:00-10:00",
                    "quotes": [
                        {"quote": "big enough worldview", "label": "Scope phrase"},
                        {"quote": "Christ is risen", "label": "Resurrection phrase"},
                    ],
                    "claim": "These quotes anchor the section's reconstructed claim.",
                },
                "audit_rows": [
                    {
                        "claim": "Christianity supplies the needed frame.",
                        "evidence": "Short transcript phrases and pastoral examples.",
                        "critique": "The transcript needs comparative evidence before confidence rises.",
                    }
                ],
                "formalization": {
                    "intro": "Let P be the transcript premise and Q be the public conclusion.",
                    "latex": "\\[\\begin{aligned}P &:= \\text{Premise.}\\\\ Q &:= \\text{Conclusion.}\\\\ P &\\not\\Rightarrow Q\\end{aligned}\\]",
                    "assessment": "The conclusion does not follow without additional evidence.",
                },
                "tags": [
                    {
                        "kind": "fallacy",
                        "label": "Appeal to consequences",
                        "url": "https://logfall.com/fallacies/appeal-to-consequences/",
                        "tone": "red",
                        "fit": "High",
                        "application": "Applies where usefulness is treated as evidence of truth.",
                    },
                    {
                        "kind": "bias",
                        "label": "Confirmation bias",
                        "url": "https://cogbias.site/biases/confirmation-bias/",
                        "tone": "blue",
                        "fit": "Moderate",
                        "application": "Applies where confirming examples are selected without a rival audit.",
                    },
                ],
            }
        )

    return {
        "schema_version": 1,
        "episode": {
            "title": "Test Episode",
            "page_title": "Test Episode",
            "meta_description": "A formal critique of a test episode.",
            "pub_date": "2026-07-01",
            "display_date": "July 1, 2026",
            "slug": "2026-07-01-test-episode",
            "source_label": "Stand to Reason Weekly Podcast / Podbean",
            "source_url": "https://strweekly.podbean.com/e/test/",
            "speaker": "Test Speaker",
            "transcript_source": "Private ASR transcript generated locally.",
            "lede": "This critique tests whether confidence remains proportionate to evidence.",
        },
        "episode_nav": {
            "previous": {"title": "Older Test Episode", "url": "../2026-06-24-test-episode/"},
            "next": {"title": "Newer Test Episode", "url": "../2026-07-08-test-episode/"},
        },
        "quote_strip": [
            {"quote": "big enough worldview", "label": "Scope claim"},
            {"quote": "Christ is risen", "label": "Hope claim"},
            {"quote": "all things new", "label": "Story claim"},
            {"quote": "what is good", "label": "Calling claim"},
        ],
        "methods": [
            {"title": "Calibration", "body": "Belief should track evidence."},
            {"title": "Symmetry", "body": "Rivals need the same test."},
            {"title": "Architecture", "body": "A source is not a system."},
            {"title": "Alternatives", "body": "Compare live alternatives."},
        ],
        "research": {
            "body": ["The critique is grounded in Free of Faith and local framework summaries."],
            "rows": [
                {
                    "area": section["label"],
                    "anchors": section["research_anchors"],
                    "local_anchor": "Belief Overreach Audit",
                    "application": "It calibrates confidence to evidence.",
                }
                for section in sections
            ],
        },
        "claim_map": [
            {
                "number": section["number"],
                "family": section["label"],
                "reconstruction": "A substantive reconstructed claim.",
                "status": "Needs support",
                "status_tone": "gold",
                "risk": "Confidence outruns evidence.",
            }
            for section in sections
        ],
        "sections": sections,
        "overall": {
            "kicker": "Overall Assessment",
            "title": "The charitable repair",
            "paragraphs": [
                "The strongest version of the argument should be narrower.",
                "The public conclusion needs more evidence than the transcript supplies.",
            ],
            "epistemic_reality": {
                "kicker": "The epistemic reality",
                "title": "Certainty outruns the evidence provided",
                "paragraphs": [
                    "The transcript proclaims several load-bearing claims without demonstrating them.",
                    "The responsible posture is a confidence downgrade.",
                ],
                "bullets": ["Resurrection is invoked but not argued.", "Rival explanations are not compared."],
            },
        },
        "evidence_needed": [
            {
                "area": section["label"],
                "raise": (
                    f"Transcript-specific evidence that the {section['label'].lower()} claim predicts or "
                    "explains the cited examples better than live alternatives."
                ),
                "lower": (
                    f"More reliance on {section['label'].lower()} assertion without comparing rival "
                    "explanations or naming a public warrant bridge."
                ),
            }
            for section in sections
        ],
        "ai_prompt": {
            "episode_title": "Test Episode",
            "steelman_claims": [
                "The episode presents Christianity as a comprehensive worldview.",
                "The episode presents resurrection hope as reality-grounded.",
                "The episode presents narrative closure as interpretively decisive.",
                "The episode presents creation and redemption as moral architecture.",
                "The episode presents Christian calling as culturally constructive.",
            ],
            "vulnerabilities": [
                "Worldview Totalization",
                "Private-to-Public Shift",
                "Evidence-Proportionate Belief",
                "Pastoral Usefulness Versus Truth",
                "Narrative Closure",
                "Insider Authority",
                "Resurrection Evidence Gap",
                "Inductive Symmetry",
            ],
        },
        "source_list": [
            {"label": "Official STR / Podbean episode page", "url": "https://strweekly.podbean.com/e/test/"},
            {"label": "Free of Faith Insights archive", "url": "https://freeoffaith.com/category/insights/"},
        ],
        "rail": {
            "status": "Public approval draft.",
            "fallacies": [{"label": "Consequences", "url": "https://logfall.com/fallacies/appeal-to-consequences/"}],
            "biases": [{"label": "Confirmation", "url": "https://cogbias.site/biases/confirmation-bias/"}],
        },
    }


def test_valid_spec_renders_page_with_required_onreason_features(tmp_path):
    spec = valid_spec()

    errors = validate_spec(spec)
    assert errors == []

    page = tmp_path / "index.html"
    page.write_text(render_critique(spec), encoding="utf-8")

    assert validate_page(page) == []
    html = page.read_text(encoding="utf-8")
    assert '<ol id="toc-list">' in html
    assert "1. Worldview scope" in html
    assert "The Steelmanned Condensed Claims:" in html
    assert "Diagnostic fit: High" in html
    assert "epistemic-reality" in html
    assert 'class="link-pill gold"' in html
    assert "</a>;" not in html
    assert 'class="episode-nav-link previous"' in html
    assert 'href="../2026-07-08-test-episode/"' in html
    assert "app.js?v=20260707-toc-active" in html


def test_validate_spec_rejects_missing_transcript_quote_explanations():
    spec = valid_spec()
    weak = copy.deepcopy(spec)
    weak["sections"][0]["transcript"]["quotes"] = [{"quote": "big enough worldview", "label": "Scope phrase"}]
    weak["sections"][0]["tags"][0]["application"] = "TODO explain this"

    errors = validate_spec(weak)

    assert any("transcript.quotes" in error for error in errors)
    assert any("tags[1].application" in error for error in errors)


def test_validate_spec_rejects_boilerplate_evidence_needed_rows():
    spec = valid_spec()
    weak = copy.deepcopy(spec)
    for row in weak["evidence_needed"]:
        row["raise"] = "Clear comparative evidence, independent warrant, and explicit treatment of rival explanations."
        row["lower"] = "More assertion, analogy, proof-texting, or pastoral usefulness without a public evidence bridge."

    errors = validate_spec(weak)

    assert any("evidence_needed.raise entries" in error for error in errors)
    assert any("evidence_needed.lower entries" in error for error in errors)
    assert any("must be customized" in error for error in errors)


def test_scaffold_uses_metadata_transcript_chunks_and_source_index(tmp_path):
    episode_dir = tmp_path / "corpus" / "episodes" / "2026-07-01-test-episode"
    episode_dir.mkdir(parents=True)
    (episode_dir / "metadata.json").write_text(
        json.dumps(
            {
                "title": "Test Episode",
                "slug": "2026-07-01-test-episode",
                "pub_date": "2026-07-01",
                "podcast_page_url": "https://strweekly.podbean.com/e/test/",
            }
        ),
        encoding="utf-8",
    )
    (episode_dir / "transcript.json").write_text(
        json.dumps(
            {
                "chunks": [
                    {
                        "start_seconds": 0,
                        "end_seconds": 60,
                        "text": "Genuine Christianity is a worldview that claims to comprehend all of reality. Christ is risen and Christ is Lord.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    source_index = tmp_path / "research" / "source-index.json"
    source_index.parent.mkdir()
    source_index.write_text(
        json.dumps(
            {
                "freeoffaith": [
                    {
                        "title": "#21 Inference to the Best Explanation",
                        "url": "https://freeoffaith.com/2024/11/11/21/",
                        "relevance_tags": ["worldview"],
                    },
                    {
                        "title": "#49 Resurrection Plausibility",
                        "url": "https://freeoffaith.com/2024/11/23/49/",
                        "relevance_tags": ["resurrection"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    spec = scaffold_spec(episode_dir, source_index)

    assert spec["episode"]["display_date"] == "July 1, 2026"
    assert spec["sections"][0]["transcript"]["range"] == "00:00:00-00:01:00"
    assert spec["sections"][0]["transcript"]["quotes"][0]["quote"].startswith("Genuine Christianity")
    assert spec["sections"][0]["research_anchors"][0]["url"] == "https://freeoffaith.com/2024/11/11/21/"
    assert any("TODO" in error for error in validate_spec(spec))


def test_public_episode_pages_pass_quality_gate():
    pages = sorted(Path("docs/episodes").glob("*/index.html"))

    assert len(pages) >= 10
    for page in pages:
        assert validate_page(page) == []


def test_current_contents_style_uses_lower_roman_markers():
    styles = Path("docs/assets/styles.css").read_text(encoding="utf-8")

    assert "list-style-type: lower-roman;" in styles


def test_contents_menu_has_active_scroll_state_contract():
    styles = Path("docs/assets/styles.css").read_text(encoding="utf-8")
    script = Path("docs/assets/app.js").read_text(encoding="utf-8")

    assert ".toc li.is-active" in styles
    assert '.toc a[aria-current="location"]' in styles
    assert "syncActiveTocItem" in script
    assert 'aria-current", "location"' in script
