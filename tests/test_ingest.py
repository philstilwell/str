from pathlib import Path

from str_workflow.ingest import (
    audio_candidate_from_page_html,
    episode_slug,
    extract_audio_url_from_player_html,
    format_seconds,
    transcript_tags_by_guid,
)
from str_workflow.notifications import notice_from_metadata, transcript_became_ready


def test_transcript_tags_by_guid_reads_podcast_namespace():
    feed_xml = b"""<?xml version="1.0"?>
    <rss xmlns:podcast="https://podcastindex.org/namespace/1.0">
      <channel>
        <item>
          <guid>episode-1</guid>
          <podcast:transcript url="https://example.com/transcript.txt" type="text/plain" language="en" />
        </item>
      </channel>
    </rss>
    """

    tags = transcript_tags_by_guid(feed_xml)

    assert tags["episode-1"] == [
        {
            "url": "https://example.com/transcript.txt",
            "type": "text/plain",
            "language": "en",
        }
    ]


def test_episode_slug_and_format_seconds_are_stable():
    assert episode_slug("2026-07-01", "Cultivating a Big Enough Worldview in Students!") == (
        "2026-07-01-cultivating-a-big-enough-worldview-in-students"
    )
    assert format_seconds(3661.2) == "01:01:01"
    assert format_seconds(None) == "--:--"


def test_audio_candidate_from_page_html_reads_blubrry_media_url():
    html = """
    <iframe title="Blubrry Podcast Player"
      src="https://player.blubrry.com/?media_url=https%3A%2F%2Fmedia.example.com%2Fepisode.mp3">
    </iframe>
    """

    candidate = audio_candidate_from_page_html("https://example.com/episode/", html)

    assert candidate == {
        "url": "https://media.example.com/episode.mp3",
        "source": "embedded_player_media_url",
        "source_url": "https://example.com/episode/",
        "player_url": "https://player.blubrry.com/?media_url=https%3A%2F%2Fmedia.example.com%2Fepisode.mp3",
    }


def test_extract_audio_url_from_player_html_reads_json_escaped_mp3_url():
    html = '{"media_url":"https:\\/\\/content.blubrry.com\\/cross_examined\\/episode.mp3"}'

    assert extract_audio_url_from_player_html(html) == "https://content.blubrry.com/cross_examined/episode.mp3"


def test_transcript_notice_is_created_only_when_transcript_becomes_ready():
    previous = {"transcript": {"status": "pending_asr"}}
    current = {
        "title": "A New Episode",
        "pub_date": "2026-07-08",
        "podcast_page_url": "https://example.com/episode/",
        "podcast": {"id": "stand-to-reason", "title": "Stand to Reason Weekly Podcast"},
        "transcript": {
            "status": "generated_asr",
            "asr_model": "gpt-4o-mini-transcribe",
            "path": "transcript.md",
        },
    }

    notice = notice_from_metadata(
        metadata_path=Path("corpus/podcasts/stand-to-reason/episodes/2026-07-08-a-new-episode/metadata.json"),
        current=current,
        previous=previous,
        repo_url="https://github.com/philstilwell/str",
        run_url="https://github.com/philstilwell/str/actions/runs/123",
    )

    assert transcript_became_ready(current, previous)
    assert notice is not None
    assert notice["title"] == "New transcript ready: Stand to Reason Weekly Podcast - A New Episode"
    assert "generated_asr" in notice["body"]
    assert "gpt-4o-mini-transcribe" in notice["body"]
    assert "corpus/podcasts/stand-to-reason/episodes/2026-07-08-a-new-episode/transcript.md" in notice["body"]
    assert "Create or update the OnReason critique page" in notice["body"]


def test_transcript_notice_is_not_recreated_for_already_ready_transcript():
    previous = {"transcript": {"status": "generated_asr"}}
    current = {"transcript": {"status": "generated_asr"}}

    assert not transcript_became_ready(current, previous)
    assert notice_from_metadata(metadata_path=Path("corpus/example/metadata.json"), current=current, previous=previous) is None
