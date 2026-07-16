from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from str_workflow.outreach import (
    NOTICE_SHEET_HEADERS,
    OutreachError,
    add_notice,
    append_event,
    compact_claim_topics,
    compact_topic,
    extract_critique,
    initialize_record,
    load_google_sheet_config,
    main,
    notice_search_line,
    notice_sheet_rows,
    plan_notice_sheet_upsert,
    read_record,
    recommended_notice_text,
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
    assert "## Notice text" in markdown
    assert f"### {notice_id}" in markdown
    assert f"```text\n{exact_text}```" in markdown
    assert "<small>" not in markdown
    assert "<br>" not in markdown
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


def test_link_free_notice_uses_approved_stand_to_reason_search_line(
    tmp_path: Path,
) -> None:
    _, path = initialize(tmp_path)
    notice_id = add_notice(
        path,
        platform="youtube",
        target_type="episode-video",
        target_url="https://www.youtube.com/watch?v=abc123",
        notice_text=(
            "Independent critique\n\n"
            "Read the critique:\n"
            "https://onreason.com/episodes/2026-07-15-we-have-an-obligation-to-help-the-poor/\n\n"
            "Substantive corrections, objections, and responses are welcome.\n"
        ),
        at="2026-07-15T18:05:00Z",
    )
    record = read_record(path)
    notice = next(item for item in record["notices"] if item["id"] == notice_id)

    rendered = recommended_notice_text(record, notice)

    assert "Search: 'OnReason, Stand to Reason'" in rendered
    assert "https://onreason.com/" not in rendered
    assert "Substantive corrections" in rendered


def test_approved_search_lines_are_stable() -> None:
    assert notice_search_line("I Don't Have Enough FAITH to Be an ATHEIST") == (
        "Search 'OnReason, I Don't Have Enough FAITH to Be an ATHEIST'"
    )
    assert notice_search_line("Stand to Reason Weekly Podcast") == (
        "Search: 'OnReason, Stand to Reason'"
    )


def test_sheet_rows_include_workflow_fields_and_link_free_notice(
    tmp_path: Path,
) -> None:
    outreach_dir, path = initialize(tmp_path)
    add_notice(
        path,
        platform="youtube",
        target_type="episode-video",
        target_url="https://www.youtube.com/watch?v=abc123",
        notice_text=(
            "Independent critique\n\n"
            "Read the critique:\n"
            "https://onreason.com/episodes/2026-07-15-we-have-an-obligation-to-help-the-poor/\n"
        ),
        at="2026-07-15T18:05:00Z",
    )

    rows = notice_sheet_rows([(path, read_record(path))])

    assert len(rows) == 1
    assert len(rows[0]) == 12
    assert rows[0][4].startswith('=HYPERLINK("https://strweekly.podbean.com/')
    assert rows[0][5].endswith('","Open critique")')
    assert "Search: 'OnReason, Stand to Reason'" in rows[0][6]
    assert rows[0][8].splitlines()[-1] == "5. Exclusivism/sincere seekers"
    assert rows[0][10:] == ["drafted", "2026-07-15T18:05:00Z"]
    assert outreach_dir == path.parent.parent


def test_sheet_upsert_updates_only_canonical_columns_and_preserves_manual_fields() -> None:
    existing = [
        NOTICE_SHEET_HEADERS,
        [
            "notice-1",
            "old",
            "old",
            "old",
            "old",
            "old",
            "old",
            "old",
            "old",
            "old",
            "old",
            "old",
            "Posted",
            "2026-07-15",
            "https://example.com/comment",
            "Visible",
            "Keep this manual note",
        ],
    ]
    canonical = [
        [
            "notice-1",
            "2026-07-15",
            "Podcast",
            "Episode",
            "source",
            "critique",
            "link-free",
            "full",
            "topics",
            "destinations",
            "verified_visible",
            "2026-07-16T18:00:00Z",
        ],
        [
            "notice-2",
            "2026-07-16",
            "Podcast",
            "Episode 2",
            "source",
            "critique",
            "link-free",
            "full",
            "topics",
            "destinations",
            "drafted",
            "2026-07-16T19:00:00Z",
        ],
    ]

    plan = plan_notice_sheet_upsert(canonical, existing)

    assert plan["updated"] == 1
    assert plan["inserted"] == 1
    assert plan["writes"][0]["range"] == "'Notices'!A2:L2"
    assert len(plan["writes"][0]["values"][0]) == 12
    assert plan["writes"][1]["range"] == "'Notices'!A3:Q3"
    assert plan["writes"][1]["values"][0][12:] == [
        "Ready to post",
        "",
        "",
        "Unchecked",
        "",
    ]


def test_google_sheet_config_is_non_secret_and_validated(tmp_path: Path) -> None:
    outreach_dir = tmp_path / "outreach"
    outreach_dir.mkdir()
    config = outreach_dir / "google-sheets.json"
    config.write_text(
        '{"spreadsheet_id":"sheet-123","notices_sheet":"Notices"}\n',
        encoding="utf-8",
    )

    assert load_google_sheet_config(outreach_dir) == {
        "spreadsheet_id": "sheet-123",
        "notices_sheet": "Notices",
    }


def test_rebuild_command_runs_configured_sheet_sync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outreach_dir, _ = initialize(tmp_path)
    (outreach_dir / "google-sheets.json").write_text(
        '{"spreadsheet_id":"sheet-123","notices_sheet":"Notices"}\n',
        encoding="utf-8",
    )
    calls: list[tuple[Path, bool]] = []

    def fake_sync(
        directory: Path,
        *,
        service: object | None = None,
        required_config: bool = True,
    ) -> dict[str, object]:
        assert service is None
        calls.append((directory, required_config))
        return {
            "sheet": "Notices",
            "updated": 1,
            "inserted": 0,
        }

    monkeypatch.setattr("str_workflow.outreach.sync_google_sheet", fake_sync)

    assert main(["--outreach-dir", str(outreach_dir), "rebuild"]) == 0
    assert calls == [(outreach_dir, False)]
