from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from str_workflow.outreach import (
    OutreachError,
    add_notice,
    append_event,
    compact_claim_topics,
    compact_topic,
    extract_critique,
    initialize_record,
    read_record,
    record_path,
    render_contents,
    validate_outreach,
)


SLUG = "2026-07-15-we-have-an-obligation-to-help-the-poor"


def write_critique_page(root: Path) -> Path:
    page = root / "docs" / "episodes" / SLUG / "index.html"
    page.parent.mkdir(parents=True)
    page.write_text(
        """<!doctype html>
<html>
  <head>
    <title>We Have an Obligation to Help the Poor | OnReason</title>
    <link rel="canonical" href="https://onreason.com/episodes/2026-07-15-we-have-an-obligation-to-help-the-poor/">
  </head>
  <body>
    <aside aria-label="Contents">
      <ol id="toc-list">
        <li><a href="#overview">Thesis and overview</a></li>
        <li><a href="#method">Method</a></li>
        <li><a href="#research">Research base</a></li>
        <li><a href="#map">Claim map</a></li>
        <li><a href="#mission">1. Jesus’ mission and social justice</a></li>
        <li><a href="#charity">2. Charity, panhandlers, and Christian organizations</a></li>
        <li><a href="#dementia">3. Dementia and salvation security</a></li>
        <li><a href="#conscience">4. Conscience and the Holy Spirit</a></li>
        <li><a href="#seekers">5. Exclusivism and sincere seekers</a></li>
        <li><a href="#overall">Overall assessment</a></li>
        <li><a href="#evidence-needed">Evidence needed</a></li>
        <li><a href="#prompt">AI prompt</a></li>
      </ol>
    </aside>
    <main>
      <h1>We Have an Obligation to Help the Poor</h1>
      <dl class="meta-list">
        <dt>Episode source</dt>
        <dd><a href="https://strweekly.podbean.com/e/help-the-poor/">Stand to Reason Weekly Podcast / Podbean</a></dd>
      </dl>
    </main>
  </body>
</html>
""",
        encoding="utf-8",
    )
    return page


def initialize(tmp_path: Path) -> tuple[Path, Path]:
    page = write_critique_page(tmp_path)
    outreach_dir = tmp_path / "outreach"
    path = initialize_record(
        page,
        outreach_dir,
        at="2026-07-15T18:00:00Z",
    )
    return outreach_dir, path


def test_extracts_full_contents_and_every_compact_claim_topic(tmp_path: Path) -> None:
    critique = extract_critique(write_critique_page(tmp_path))

    assert critique["slug"] == SLUG
    assert critique["podcast"] == "Stand to Reason Weekly Podcast"
    assert critique["episode_title"] == "We Have an Obligation to Help the Poor"
    assert critique["contents"] == [
        "Thesis and overview",
        "Method",
        "Research base",
        "Claim map",
        "1. Jesus’ mission and social justice",
        "2. Charity, panhandlers, and Christian organizations",
        "3. Dementia and salvation security",
        "4. Conscience and the Holy Spirit",
        "5. Exclusivism and sincere seekers",
        "Overall assessment",
        "Evidence needed",
        "AI prompt",
    ]
    assert critique["compact_topics"] == [
        "Jesus’ mission/social justice",
        "Charity/panhandlers/Christian orgs",
        "Dementia/salvation",
        "Conscience/Holy Spirit",
        "Exclusivism/sincere seekers",
    ]
    assert len(critique["compact_topics"]) == 5
    assert compact_claim_topics(critique["contents"]) == critique["compact_topics"]


def test_compaction_never_truncates_the_end_of_a_claim_topic() -> None:
    assert compact_topic(
        "2. Preliminary evidence, conviction language, and capital punishment"
    ) == "Initial evidence/conviction/death penalty"
    assert compact_topic(
        "3. Demonic diagnosis of lies, slander, and social destruction"
    ) == "Demonic diagnosis: lies/slander/social harm"


def test_initializes_record_and_renders_both_contents_variants(tmp_path: Path) -> None:
    outreach_dir, path = initialize(tmp_path)
    record = read_record(path)

    assert record["schema_version"] == 1
    assert record["created_at"] == "2026-07-15T18:00:00Z"
    assert record["notices"] == []
    assert validate_outreach(outreach_dir) == []
    assert "2. Charity, panhandlers, and Christian organizations" in render_contents(
        record
    )
    compact = render_contents(record, compact=True)
    assert "2. Charity/panhandlers/Christian orgs" in compact
    assert "5. Exclusivism/sincere seekers" in compact
    assert "Overall assessment" in compact


def test_notice_lifecycle_preserves_exact_text_and_builds_indexes(
    tmp_path: Path,
) -> None:
    outreach_dir, path = initialize(tmp_path)
    exact_text = (
        "A new critique is available.\n\n"
        "Contents: Thesis; method; research; claim map; all five claims; assessment.\n"
    )
    notice_id = add_notice(
        path,
        platform="youtube",
        target_type="episode-video",
        target_url="https://www.youtube.com/watch?v=abc123&utm_source=test",
        notice_text=exact_text,
        actor="phil",
        at="2026-07-15T18:05:00Z",
    )
    append_event(
        path,
        notice_id,
        "approved",
        actor="phil",
        at="2026-07-15T18:06:00Z",
    )
    append_event(
        path,
        notice_id,
        "posted",
        posted_url="https://www.youtube.com/watch?v=abc123&lc=comment456",
        actor="phil",
        at="2026-07-15T18:07:00Z",
    )
    append_event(
        path,
        notice_id,
        "verified_visible",
        actor="phil",
        note="24h visibility check",
        at="2026-07-16T18:07:00Z",
    )
    append_event(
        path,
        notice_id,
        "verified_visible",
        actor="phil",
        note="7d visibility check",
        at="2026-07-22T18:07:00Z",
    )

    notice = read_record(path)["notices"][0]
    assert notice["notice_text"] == exact_text
    assert notice["status"] == "verified_visible"
    assert [event["event"] for event in notice["history"]] == [
        "drafted",
        "approved",
        "posted",
        "verified_visible",
        "verified_visible",
    ]
    assert notice["history"][-1]["note"] == "7d visibility check"
    assert validate_outreach(outreach_dir) == []

    markdown = (outreach_dir / "index.md").read_text(encoding="utf-8")
    assert "2026-07-15 14:07 EDT" in markdown
    assert "verified_visible" in markdown
    assert "| Status | Notice text | Public post |" in markdown
    assert (
        "<small>A new critique is available.<br><br>Contents: Thesis; method; "
        "research; claim map; all five claims; assessment.<br></small>"
    ) in markdown
    assert "[open](https://www.youtube.com/watch?v=abc123&lc=comment456)" in markdown

    rows = list(
        csv.DictReader(io.StringIO((outreach_dir / "index.csv").read_text()))
    )
    assert rows == [
        {
            "posted_at_utc": "2026-07-15T18:07:00Z",
            "posted_at_et": "2026-07-15 14:07 EDT",
            "last_event_at_utc": "2026-07-22T18:07:00Z",
            "last_event_at_et": "2026-07-22 14:07 EDT",
            "podcast": "Stand to Reason Weekly Podcast",
            "episode_title": "We Have an Obligation to Help the Poor",
            "critique_url": "https://onreason.com/episodes/2026-07-15-we-have-an-obligation-to-help-the-poor/",
            "notice_id": notice_id,
            "platform": "youtube",
            "target_type": "episode-video",
            "target_url": "https://www.youtube.com/watch?v=abc123&utm_source=test",
            "status": "verified_visible",
            "posted_url": "https://www.youtube.com/watch?v=abc123&lc=comment456",
            "method": "manual",
            "notice_text": exact_text,
        }
    ]


def test_duplicate_target_is_rejected_even_with_tracking_or_fragment(
    tmp_path: Path,
) -> None:
    _, path = initialize(tmp_path)
    add_notice(
        path,
        platform="youtube",
        target_type="episode-video",
        target_url="https://youtube.com/watch?v=abc&utm_source=first#comments",
        notice_text="First exact notice",
        at="2026-07-15T18:05:00Z",
    )

    with pytest.raises(OutreachError, match="already exists"):
        add_notice(
            path,
            platform="youtube",
            target_type="episode-video",
            target_url="https://YOUTUBE.com/watch?v=abc&utm_campaign=second",
            notice_text="Second exact notice",
            at="2026-07-15T18:06:00Z",
        )


def test_posting_requires_approval_and_a_public_permalink(tmp_path: Path) -> None:
    _, path = initialize(tmp_path)
    notice_id = add_notice(
        path,
        platform="podbean",
        target_type="episode-page",
        target_url="https://strweekly.podbean.com/e/help-the-poor/",
        notice_text="Exact notice",
        at="2026-07-15T18:05:00Z",
    )

    with pytest.raises(OutreachError, match="Cannot append 'posted' after 'drafted'"):
        append_event(
            path,
            notice_id,
            "posted",
            posted_url="https://strweekly.podbean.com/e/help-the-poor/#comment-1",
            at="2026-07-15T18:06:00Z",
        )

    append_event(
        path,
        notice_id,
        "approved",
        at="2026-07-15T18:06:00Z",
    )
    with pytest.raises(OutreachError, match="requires --posted-url"):
        append_event(
            path,
            notice_id,
            "posted",
            at="2026-07-15T18:07:00Z",
        )


def test_validation_detects_a_manually_staled_index(tmp_path: Path) -> None:
    outreach_dir, _ = initialize(tmp_path)
    (outreach_dir / "index.md").write_text("stale\n", encoding="utf-8")

    assert validate_outreach(outreach_dir) == [
        f"Generated index is stale: {outreach_dir / 'index.md'}"
    ]


def test_cross_examined_source_name_is_inferred(tmp_path: Path) -> None:
    page = write_critique_page(tmp_path)
    html = page.read_text(encoding="utf-8").replace(
        "Stand to Reason Weekly Podcast / Podbean",
        "CrossExamined / I Don't Have Enough FAITH to Be an ATHEIST",
    )
    page.write_text(html, encoding="utf-8")

    assert extract_critique(page)["podcast"] == (
        "I Don't Have Enough FAITH to Be an ATHEIST"
    )


def test_record_filename_must_match_slug(tmp_path: Path) -> None:
    outreach_dir, path = initialize(tmp_path)
    other = outreach_dir / "posts" / "different-slug.json"
    other.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    errors = validate_outreach(outreach_dir)
    assert any("filename must match critique.slug" in error for error in errors)


def test_json_record_remains_human_readable(tmp_path: Path) -> None:
    _, path = initialize(tmp_path)
    raw = path.read_text(encoding="utf-8")

    assert raw.endswith("\n")
    assert "Jesus’ mission/social justice" in raw
    assert json.loads(raw)["critique"]["slug"] == SLUG
    assert path == record_path(path.parent.parent, SLUG)
