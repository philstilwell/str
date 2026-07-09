from __future__ import annotations

import copy
import json
from pathlib import Path

from bs4 import BeautifulSoup

from str_workflow.critique import (
    DEFAULT_METHODS,
    DEFAULT_VULNERABILITIES,
    page_text_for_proper_name_scan,
    proper_name_case_hits,
    render_critique,
    scaffold_spec,
    validate_page,
    validate_spec,
)


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
                        "text": f"The transcript makes a substantive {label.lower()} claim that needs public evidential testing rather than insider resonance alone.",
                        "note_label": f"Expand {label}",
                        "note": (
                            f"This note explains the {label.lower()} inference, the evidential gap, the hidden premise, "
                            "the rival explanations that must be compared, and what would improve that specific argument."
                        ),
                    },
                    f"The {label.lower()} critique separates the episode's practical usefulness from the public warrant needed before that claim can rationally raise confidence.",
                ],
                "research_anchors": [
                    {"label": "Free of Faith anchor", "url": "https://freeoffaith.com/2024/11/11/21/", "tone": "gold"},
                    {"label": "Framework anchor", "url": "https://freeoffaith.com/2026/01/27/parsimony-and-christianity/", "tone": "blue"},
                ],
                "research_note": (
                    f"These anchors require comparative testing and evidence-proportionate belief for the {label.lower()} claim, "
                    "with the Free of Faith source used to identify the public warrant gap and the local framework used to define the downgrade test."
                ),
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
                        "claim": f"The episode supplies a {label.lower()} frame.",
                        "evidence": f"Short transcript phrases and pastoral examples are used for {label.lower()}.",
                        "critique": f"The {label.lower()} claim needs comparative evidence before confidence rises.",
                    },
                    {
                        "claim": f"A stronger public case for {label.lower()} would require a public warrant bridge.",
                        "evidence": f"The transcript support remains limited to selected phrases and examples about {label.lower()}.",
                        "critique": f"Confidence should fall if the {label.lower()} conclusion is treated as established without rival testing.",
                    }
                ],
                "formalization": {
                    "intro": f"Let P_{section_id} be the {label.lower()} premise and Q_{section_id} be the public conclusion.",
                    "latex": f"\\[\\begin{{aligned}}P_{{{section_id}}} &:= \\text{{{label} premise.}}\\\\ Q_{{{section_id}}} &:= \\text{{{label} conclusion.}}\\\\ P_{{{section_id}}} &\\not\\Rightarrow Q_{{{section_id}}}\\end{{aligned}}\\]",
                    "assessment": f"The {label.lower()} conclusion does not follow without additional evidence that connects the transcript premise to a public warrant.",
                },
                "tags": [
                    {
                        "kind": "fallacy",
                        "label": "Appeal to consequences",
                        "url": "https://logfall.com/fallacies/appeal-to-consequences/",
                        "tone": "red",
                        "fit": "High",
                        "application": f"Applies where the usefulness of the {label.lower()} point is treated as evidence of truth.",
                    },
                    {
                        "kind": "bias",
                        "label": "Confirmation bias",
                        "url": "https://cogbias.site/biases/confirmation-bias/",
                        "tone": "blue",
                        "fit": "Moderate",
                        "application": f"Applies where confirming {label.lower()} examples are selected without a rival audit or comparison class.",
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
        "methods": [
            {"title": "Calibration", "body": "Belief should track evidence."},
            {"title": "Symmetry", "body": "Rivals need the same test."},
            {"title": "Architecture", "body": "A source is not a system."},
            {"title": "Alternatives", "body": "Compare live alternatives."},
            {
                "title": "Bounded Agency",
                "body": "Concern should become proportionate action where agency exists.",
            },
        ],
        "research": {
            "body": ["The critique is grounded in Free of Faith and local framework summaries."],
            "rows": [
                {
                    "area": section["label"],
                    "anchors": section["research_anchors"],
                    "local_anchor": f"{section['label']} confidence audit",
                    "application": f"It calibrates the {section['label'].lower()} claim to the evidence supplied and identifies what would raise or lower confidence.",
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
                "risk": f"Confidence outruns the evidence for {section['label'].lower()}.",
            }
            for section in sections
        ],
        "sections": sections,
        "overall": {
            "kicker": "Overall Assessment",
            "title": "The charitable repair",
            "paragraphs": [
                "The strongest version of the argument should be narrower than the transcript's rhetorical confidence suggests.",
                "The public conclusion needs more evidence than the transcript supplies because rival explanations remain live.",
            ],
            "epistemic_reality": {
                "kicker": "The epistemic reality",
                "title": "Certainty outruns the evidence provided",
                "paragraphs": [
                    "The transcript proclaims several load-bearing claims without demonstrating them through shared public evidence or rival comparison.",
                    "The responsible posture is a confidence downgrade until the relevant warrants are supplied and tested symmetrically.",
                ],
                "bullets": [
                    "Resurrection is invoked but not argued with source-sensitive historical controls.",
                    "Rival explanations are not compared under the same evidential standards.",
                    "Pastoral usefulness is not enough to establish public truth.",
                ],
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
                "The episode presents Christianity as a comprehensive worldview that can explain reality better than rivals.",
                "The episode presents resurrection hope as reality-grounded rather than merely psychologically comforting.",
                "The episode presents narrative closure as interpretively decisive for reading suffering and culture.",
                "The episode presents creation and redemption as moral architecture for identity and conduct.",
                "The episode presents Christian calling as culturally constructive and evidence of worldview adequacy.",
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
            {"label": "Free of Faith Featured archive", "url": "https://freeoffaith.com/featured/"},
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
    assert "Bounded Agency" in html
    assert "faith is intrinsically irrational" in html
    assert "Free of Faith Featured archive" in html
    assert "https://freeoffaith.com/featured/" in html
    assert "quote-strip" not in html
    assert "quote-chip" not in html
    assert "Short quote anchors" not in html
    assert 'class="link-pill gold"' in html
    assert "</a>;" not in html
    assert "OnReason source index" not in html
    assert "github.com/philstilwell/str/blob/main/research/source-index" not in html
    assert 'class="episode-nav-link previous"' in html
    assert 'href="../2026-07-08-test-episode/"' in html
    assert '<p class="section-kicker numbered-kicker">1. Worldview scope</p>' in html
    assert '<p class="section-kicker">Critique Framework</p>' in html
    assert '<p class="section-kicker numbered-kicker">Critique Framework</p>' not in html
    assert "app.js?v=20260707-numbered-bars" in html
    assert '<link rel="canonical" href="https://onreason.com/episodes/2026-07-01-test-episode/">' in html
    assert '<meta property="og:type" content="article">' in html
    assert '<meta name="twitter:card" content="summary_large_image">' in html
    assert '"@type": "Article"' in html
    assert '"@type": "BreadcrumbList"' in html


def test_freeoffaith_source_index_includes_featured_posts():
    source_index = json.loads(Path("research/source-index.json").read_text(encoding="utf-8"))
    sections = {item.get("section") for item in source_index.get("freeoffaith", [])}
    featured = [item for item in source_index.get("freeoffaith", []) if item.get("section") == "featured"]

    assert {"insights", "considerations", "featured"}.issubset(sections)
    assert len(featured) >= 20
    assert any(item.get("id") == "fof-featured-faith-vs-rationality" for item in featured)


def test_critique_contract_treats_faith_as_intrinsically_irrational():
    method_text = " ".join(item["body"] for item in DEFAULT_METHODS)
    vulnerability_text = " ".join(DEFAULT_VULNERABILITIES)
    batch_prompt = Path("src/str_workflow/critique_batch.py").read_text(encoding="utf-8")

    assert "Faith is intrinsically irrational" in method_text
    assert "Faith Irrationality" in vulnerability_text
    assert "Treat faith as intrinsically irrational" in batch_prompt


def test_validate_spec_rejects_missing_transcript_quote_explanations():
    spec = valid_spec()
    weak = copy.deepcopy(spec)
    weak["sections"][0]["transcript"]["quotes"] = [{"quote": "big enough worldview", "label": "Scope phrase"}]
    weak["sections"][0]["tags"][0]["application"] = "TODO explain this"

    errors = validate_spec(weak)

    assert any("transcript.quotes" in error for error in errors)
    assert any("tags[1].application" in error for error in errors)


def test_validate_spec_rejects_deprecated_quote_strip_field():
    spec = valid_spec()
    spec["quote_strip"] = [{"quote": "big enough worldview", "label": "Scope claim"}]

    errors = validate_spec(spec)

    assert any("quote_strip is deprecated" in error for error in errors)


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


def test_validate_spec_rejects_missing_bounded_agency_method():
    spec = valid_spec()
    weak = copy.deepcopy(spec)
    weak["methods"] = [method for method in weak["methods"] if method["title"] != "Bounded Agency"]

    errors = validate_spec(weak)

    assert any("Bounded Agency" in error for error in errors)


def test_validate_spec_rejects_general_boilerplate_and_repeated_explanatory_text():
    spec = valid_spec()
    weak = copy.deepcopy(spec)
    weak["sections"][0]["paragraphs"][1] = (
        "The responsible repair is to separate the pastoral or insider point from the public evidential claim."
    )
    repeated = "This repeated critique sentence is long enough to expose uncustomized explanatory filler."
    weak["sections"][1]["research_note"] = repeated
    weak["sections"][2]["research_note"] = repeated

    errors = validate_spec(weak)

    assert any("contains boilerplate phrase" in error for error in errors)
    assert any("repeats explanatory text" in error for error in errors)


def test_validate_spec_rejects_shallow_critique_depth_fields():
    spec = valid_spec()
    weak = copy.deepcopy(spec)
    weak["sections"][0]["paragraphs"][0]["note"] = "Too thin."
    weak["sections"][0]["research_note"] = "Anchor mention only."
    weak["sections"][0]["audit_rows"] = weak["sections"][0]["audit_rows"][:1]
    weak["sections"][0]["formalization"]["assessment"] = "Too short."
    weak["sections"][0]["tags"][0]["application"] = "Generic label."
    weak["evidence_needed"][0]["raise"] = "More evidence."
    weak["overall"]["epistemic_reality"]["bullets"] = ["Vague."]
    weak["ai_prompt"]["steelman_claims"][0] = "Worldview claim."

    errors = validate_spec(weak)

    assert any("expansive ◉ explanation" in error for error in errors)
    assert any("research_note" in error and "anchors apply" in error for error in errors)
    assert any("audit_rows" in error and "at least two" in error for error in errors)
    assert any("formalization.assessment" in error for error in errors)
    assert any("tags[1].application" in error for error in errors)
    assert any("evidence_needed[1].raise" in error for error in errors)
    assert any("epistemic_reality must include at least three bullets" in error for error in errors)
    assert any("steelman_claims must be developed" in error for error in errors)


def test_validate_spec_rejects_public_source_index_links():
    spec = valid_spec()
    weak = copy.deepcopy(spec)
    weak["sections"][0]["research_anchors"].append(
        {
            "label": "OnReason source index",
            "url": "https://github.com/philstilwell/str/blob/main/research/source-index.json",
            "tone": "blue",
        }
    )
    weak["source_list"].append(
        {
            "label": "OnReason source index",
            "url": "https://github.com/philstilwell/str/blob/main/research/source-index.json",
        }
    )

    errors = validate_spec(weak)

    assert any("must not expose the private OnReason source index" in error for error in errors)


def test_validate_spec_rejects_lowercase_proper_names():
    spec = valid_spec()
    weak = copy.deepcopy(spec)
    weak["claim_map"][0]["risk"] = "greg's confidence is treated as a substitute for public evidence."
    weak["sections"][0]["transcript"]["quotes"][0]["quote"] = "jesus is Lord"

    errors = validate_spec(weak)

    assert any('"greg"' in error and '"Greg"' in error for error in errors)
    assert any('"jesus"' in error and '"Jesus"' in error for error in errors)


def test_validate_page_rejects_stale_boilerplate_phrase(tmp_path):
    spec = valid_spec()
    page = tmp_path / "index.html"
    html = render_critique(spec).replace(
        "The assessment can move, but only through claim-matched evidence.",
        "The critique is not designed to be unfalsifiable.",
        1,
    )
    page.write_text(html, encoding="utf-8")

    errors = validate_page(page)

    assert any("page contains boilerplate phrase" in error for error in errors)


def test_validate_page_rejects_public_source_index_links(tmp_path):
    spec = valid_spec()
    page = tmp_path / "index.html"
    html = render_critique(spec).replace(
        "Free of Faith Insights archive",
        "OnReason source index",
        1,
    ).replace(
        "https://freeoffaith.com/category/insights/",
        "https://github.com/philstilwell/str/blob/main/research/source-index.json",
        1,
    )
    page.write_text(html, encoding="utf-8")

    errors = validate_page(page)

    assert any("must not expose the private OnReason source index" in error for error in errors)


def test_validate_page_rejects_lowercase_proper_names(tmp_path):
    spec = valid_spec()
    page = tmp_path / "index.html"
    html = render_critique(spec).replace("Christ is risen", "christ is risen", 1)
    page.write_text(html, encoding="utf-8")

    errors = validate_page(page)

    assert any('"christ"' in error and '"Christ"' in error for error in errors)


def test_validate_page_rejects_missing_bounded_agency_method(tmp_path):
    spec = valid_spec()
    page = tmp_path / "index.html"
    html = render_critique(spec).replace(
        '              <div class="method-card"><strong>Bounded Agency</strong><p>Concern should become proportionate action where agency exists.</p></div>\n',
        "",
    )
    page.write_text(html, encoding="utf-8")

    errors = validate_page(page)

    assert any("Bounded Agency" in error for error in errors)


def test_validate_page_rejects_deprecated_quote_strip_markup(tmp_path):
    spec = valid_spec()
    page = tmp_path / "index.html"
    html = render_critique(spec).replace(
        '          <section class="section-panel" id="method">',
        '          <section class="quote-strip" aria-label="Short quote anchors">\n'
        '            <div class="quote-chip"><strong>“old summary”</strong><span>Old card</span></div>\n'
        "          </section>\n\n"
        '          <section class="section-panel" id="method">',
        1,
    )
    page.write_text(html, encoding="utf-8")

    errors = validate_page(page)

    assert any("deprecated top quote-strip" in error for error in errors)


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
                        "text": "greg says Genuine Christianity is a worldview that claims to comprehend all of reality. christ is risen and Christ is Lord.",
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
    assert spec["sections"][0]["transcript"]["quotes"][0]["quote"].startswith("Greg says Genuine Christianity")
    assert spec["sections"][0]["research_anchors"][0]["url"] == "https://freeoffaith.com/2024/11/11/21/"
    assert "quote_strip" not in spec
    assert all(item["label"] != "OnReason source index" for item in spec["source_list"])
    assert any("TODO" in error for error in validate_spec(spec))


def test_public_episode_pages_pass_quality_gate():
    pages = sorted(Path("docs/episodes").glob("*/index.html"))

    assert len(pages) >= 10
    for page in pages:
        assert validate_page(page) == []


def test_public_methodology_page_is_local_and_explanatory():
    index_html = Path("docs/index.html").read_text(encoding="utf-8")
    methodology_path = Path("docs/methodology/index.html")
    methodology_html = methodology_path.read_text(encoding="utf-8")
    episode_pages = sorted(Path("docs/episodes").glob("*/index.html"))

    assert '<a href="./methodology/">Methodology</a>' in index_html
    assert "https://freeoffaith.com/core-rationality/" not in index_html
    assert "https://freeoffaith.com/core-rationality/" not in methodology_html
    for page in episode_pages:
        assert '<a href="../../methodology/">Methodology</a>' in page.read_text(encoding="utf-8")

    soup = BeautifulSoup(methodology_html, "html.parser")
    visible_text = page_text_for_proper_name_scan(soup)
    for phrase in [
        "Steelman before critique",
        "Separate assertion from support",
        "Apply the same standard to rivals",
        "Let belief come in degrees",
        "How a critique page is built",
    ]:
        assert phrase in visible_text


def test_public_site_has_seo_metadata_and_discovery_files():
    pages = [
        Path("docs/index.html"),
        Path("docs/methodology/index.html"),
        *sorted(Path("docs/episodes").glob("*/index.html")),
    ]

    for page in pages:
        html = page.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        canonical = soup.select_one('link[rel="canonical"]')
        assert canonical
        assert canonical["href"].startswith("https://onreason.com/")
        assert soup.select_one('meta[name="robots"]')["content"] == "index,follow"
        assert soup.select_one('meta[property="og:title"]')
        assert soup.select_one('meta[property="og:description"]')
        assert soup.select_one('meta[property="og:url"]')["content"] == canonical["href"]
        assert soup.select_one('meta[property="og:image"]')["content"] == "https://onreason.com/assets/evidence-alignment.png"
        assert soup.select_one('meta[name="twitter:card"]')["content"] == "summary_large_image"
        assert soup.select_one('script[type="application/ld+json"]')

    sitemap = Path("docs/sitemap.xml").read_text(encoding="utf-8")
    robots = Path("docs/robots.txt").read_text(encoding="utf-8")
    assert "https://onreason.com/" in sitemap
    assert "https://onreason.com/methodology/" in sitemap
    assert "https://onreason.com/episodes/" in sitemap
    assert "Sitemap: https://onreason.com/sitemap.xml" in robots


def test_public_site_visible_text_has_proper_name_casing():
    pages = [
        Path("docs/index.html"),
        Path("docs/methodology/index.html"),
        *sorted(Path("docs/episodes").glob("*/index.html")),
    ]

    for page in pages:
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        assert proper_name_case_hits(page_text_for_proper_name_scan(soup)) == []


def test_current_contents_style_uses_lower_roman_markers():
    styles = Path("docs/assets/styles.css").read_text(encoding="utf-8")

    assert "list-style-type: lower-roman;" in styles


def test_numbered_section_kickers_use_dark_container_bar_contract():
    styles = Path("docs/assets/styles.css").read_text(encoding="utf-8")

    assert ".section-panel > .section-kicker.numbered-kicker" in styles
    assert "background: #111a15;" in styles
    assert "color: #f3f7f2;" in styles


def test_contents_menu_has_active_scroll_state_contract():
    styles = Path("docs/assets/styles.css").read_text(encoding="utf-8")
    script = Path("docs/assets/app.js").read_text(encoding="utf-8")

    assert ".toc li.is-active" in styles
    assert '.toc a[aria-current="location"]' in styles
    assert "syncActiveTocItem" in script
    assert 'aria-current", "location"' in script
