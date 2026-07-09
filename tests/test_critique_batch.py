from __future__ import annotations

import json
from pathlib import Path

from str_workflow.critique_batch import missing_critique_episode_dirs, quote_chunk
from str_workflow.site import episode_nav_for, episode_records


def write_episode(
    root: Path,
    slug: str,
    status: str,
    pub_date: str,
    with_transcript: bool = True,
) -> Path:
    episode_dir = root / "show" / "episodes" / slug
    episode_dir.mkdir(parents=True)
    (episode_dir / "metadata.json").write_text(
        json.dumps(
            {
                "slug": slug,
                "title": slug.replace("-", " ").title(),
                "pub_date": pub_date,
                "transcript": {"status": status},
            }
        ),
        encoding="utf-8",
    )
    if with_transcript:
        (episode_dir / "transcript.md").write_text("A complete transcript.", encoding="utf-8")
    return episode_dir


def test_missing_critique_discovery_requires_ready_transcript_and_absent_page(tmp_path):
    corpus = tmp_path / "corpus"
    docs = tmp_path / "docs" / "episodes"
    older = write_episode(corpus, "2026-07-07-older", "generated_asr", "2026-07-07")
    write_episode(corpus, "2026-07-08-pending", "pending_asr", "2026-07-08")
    write_episode(corpus, "2026-07-09-no-file", "found_official", "2026-07-09", with_transcript=False)
    existing = write_episode(corpus, "2026-07-10-existing", "found_official", "2026-07-10")
    existing_page = docs / existing.name / "index.html"
    existing_page.parent.mkdir(parents=True)
    existing_page.write_text("already public", encoding="utf-8")

    assert missing_critique_episode_dirs(corpus, docs) == [older]


def test_quote_chunk_accepts_only_exact_contiguous_four_to_fifteen_word_quotes():
    chunks = [
        {
            "start_seconds": 0,
            "end_seconds": 60,
            "text": "Faith is not opposed to knowledge, although people often confuse the two.",
        }
    ]

    assert quote_chunk(chunks, "Faith is not opposed to knowledge") == chunks[0]
    assert quote_chunk(chunks, "Faith opposed to knowledge") is None
    assert quote_chunk(chunks, "opposed to knowledge") is None


def test_episode_navigation_links_older_and_newer_critiques():
    records = [
        {"slug": "older", "title": "Older"},
        {"slug": "current", "title": "Current"},
        {"slug": "newer", "title": "Newer"},
    ]

    assert episode_nav_for("current", records) == {
        "previous": {"title": "Older", "url": "../older/"},
        "next": {"title": "Newer", "url": "../newer/"},
    }
    assert episode_nav_for("newer", records)["next"] is None


def test_episode_records_preserve_public_pages_without_retained_metadata(tmp_path):
    corpus = tmp_path / "corpus"
    docs = tmp_path / "docs" / "episodes"
    page = docs / "2026-05-01-legacy" / "index.html"
    page.parent.mkdir(parents=True)
    page.write_text(
        '''<header class="article-header"><h1>Legacy Episode</h1></header>
        <dl class="meta-list"><div><dt>Episode source</dt><dd>
        <a href="https://strweekly.podbean.com/e/legacy/">Stand to Reason Weekly Podcast / Podbean</a>
        </dd></div></dl>''',
        encoding="utf-8",
    )

    records = episode_records(corpus, docs)

    assert records["stand-to-reason"][0]["slug"] == "2026-05-01-legacy"
    assert records["stand-to-reason"][0]["title"] == "Legacy Episode"


def test_critique_workflow_runs_two_hours_after_ingest_and_uses_batch_quality_gate():
    ingest = Path(".github/workflows/ingest.yml").read_text(encoding="utf-8")
    critiques = Path(".github/workflows/critiques.yml").read_text(encoding="utf-8")

    assert 'cron: "15 14 * * *"' in ingest
    assert 'cron: "15 16 * * *"' in critiques
    assert "python -m str_workflow.critique_batch" in critiques
    assert "python tools/build_site_seo.py" in critiques
    assert "run: pytest" in critiques
    assert "git add docs" in critiques
