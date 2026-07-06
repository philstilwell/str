from str_workflow.ingest import episode_slug, format_seconds, transcript_tags_by_guid


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

