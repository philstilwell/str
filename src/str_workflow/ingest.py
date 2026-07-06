from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from slugify import slugify

DEFAULT_FEED_URL = "https://feed.podbean.com/strweekly/feed.xml"
DEFAULT_USER_AGENT = "str-workflow/0.1 (+https://github.com/philstilwell/str)"
DEFAULT_ASR_MODEL = "gpt-4o-mini-transcribe"
DEFAULT_ASR_PROMPT = (
    "Transcribe this Stand to Reason podcast episode. Preserve names, Scripture "
    "references, apologetics terminology, punctuation, and readable paragraphs."
)
PENDING_STATUSES = {"pending_asr", "not_found", "asr_failed"}


@dataclass(frozen=True)
class AudioChunk:
    path: Path
    start_seconds: float | None
    end_seconds: float | None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def clean_html_text(markup: str | None) -> str:
    if not markup:
        return ""
    soup = BeautifulSoup(markup, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return html.unescape(soup.get_text(" ", strip=True))


def parse_entry_date(entry: Any) -> str | None:
    for key in ("published", "updated", "created"):
        value = entry.get(key)
        if value:
            try:
                return date_parser.parse(value).astimezone(timezone.utc).date().isoformat()
            except (TypeError, ValueError):
                continue
    return None


def entry_guid(entry: Any) -> str:
    guid = entry.get("id") or entry.get("guid") or entry.get("link")
    if not guid:
        raise ValueError(f"Feed entry has no GUID or link: {entry.get('title', '<untitled>')}")
    return str(guid).strip()


def entry_mp3_url(entry: Any) -> str | None:
    for enclosure in entry.get("enclosures", []):
        href = enclosure.get("href")
        if href:
            return str(href)
    for link in entry.get("links", []):
        if link.get("rel") == "enclosure" and link.get("href"):
            return str(link["href"])
    return None


def episode_slug(pub_date: str | None, title: str) -> str:
    date_prefix = pub_date or "undated"
    title_slug = slugify(title, max_length=72, word_boundary=True) or "episode"
    return f"{date_prefix}-{title_slug}"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def load_index(out_dir: Path) -> dict[str, Any]:
    index = load_json(out_dir / "episodes.json", {"feed_url": DEFAULT_FEED_URL, "episodes": []})
    index.setdefault("episodes", [])
    return index


def upsert_index_episode(index: dict[str, Any], episode: dict[str, Any]) -> None:
    episodes = [item for item in index["episodes"] if item.get("guid") != episode.get("guid")]
    episodes.append(episode)
    episodes.sort(key=lambda item: item.get("pub_date") or "", reverse=True)
    index["episodes"] = episodes
    index["updated_at"] = utc_now_iso()


def fetch_feed(session: requests.Session, feed_url: str) -> tuple[bytes, Any]:
    response = session.get(feed_url, timeout=60)
    response.raise_for_status()
    feed_bytes = response.content
    parsed = feedparser.parse(feed_bytes)
    if parsed.bozo:
        raise RuntimeError(f"Could not parse RSS feed: {parsed.bozo_exception}")
    return feed_bytes, parsed


def transcript_tags_by_guid(feed_xml: bytes) -> dict[str, list[dict[str, str | None]]]:
    try:
        root = ET.fromstring(feed_xml)
    except ET.ParseError:
        return {}

    tags_by_guid: dict[str, list[dict[str, str | None]]] = {}
    for item in root.iter():
        if local_name(item.tag) != "item":
            continue

        guid = None
        fallback_link = None
        for child in item:
            name = local_name(child.tag)
            if name == "guid" and child.text:
                guid = child.text.strip()
            elif name == "link" and child.text:
                fallback_link = child.text.strip()

        item_key = guid or fallback_link
        if not item_key:
            continue

        transcript_tags: list[dict[str, str | None]] = []
        for child in item:
            if local_name(child.tag) == "transcript":
                transcript_tags.append(
                    {
                        "url": child.attrib.get("url") or child.attrib.get("href"),
                        "type": child.attrib.get("type"),
                        "language": child.attrib.get("language")
                        or child.attrib.get("{http://www.w3.org/XML/1998/namespace}lang"),
                    }
                )
        if transcript_tags:
            tags_by_guid[item_key] = transcript_tags

    return tags_by_guid


def fetch_text_url(session: requests.Session, url: str) -> str | None:
    response = session.get(url, timeout=60)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    body = response.text
    if "html" in content_type:
        text = clean_html_text(body)
    else:
        text = body.strip()
    return text if len(text) >= 300 else None


def fetch_transcript_from_tags(
    session: requests.Session,
    tags: list[dict[str, str | None]],
) -> tuple[str, dict[str, Any]] | None:
    for tag in tags:
        url = tag.get("url")
        if not url:
            continue
        try:
            text = fetch_text_url(session, url)
        except requests.RequestException:
            continue
        if text:
            return text, {"source": "rss_transcript_tag", "source_url": url, "tag": tag}
    return None


def discover_page_transcript(
    session: requests.Session,
    page_url: str | None,
) -> tuple[str, dict[str, Any]] | dict[str, Any] | None:
    if not page_url or not page_url.startswith(("http://", "https://")):
        return None

    try:
        response = session.get(page_url, timeout=60)
        response.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    candidate_links: list[str] = []
    for link in soup.find_all("a", href=True):
        link_text = link.get_text(" ", strip=True).lower()
        href = str(link["href"])
        if "transcript" in link_text or "transcript" in href.lower():
            candidate_links.append(urljoin(page_url, href))

    transcript_named_elements = []
    transcript_named_elements.extend(soup.find_all(attrs={"id": re.compile("transcript", re.IGNORECASE)}))
    transcript_named_elements.extend(soup.find_all(attrs={"class": re.compile("transcript", re.IGNORECASE)}))
    for element in transcript_named_elements:
        text = element.get_text("\n", strip=True)
        if len(text) >= 500:
            return text, {"source": "episode_page", "source_url": page_url, "selector": "id_or_class"}

    for heading in soup.find_all(re.compile("^h[1-6]$")):
        if "transcript" not in heading.get_text(" ", strip=True).lower():
            continue
        blocks: list[str] = []
        for sibling in heading.find_next_siblings():
            if sibling.name and re.match("^h[1-6]$", sibling.name):
                break
            text = sibling.get_text("\n", strip=True)
            if text:
                blocks.append(text)
        transcript_text = "\n\n".join(blocks).strip()
        if len(transcript_text) >= 500:
            return transcript_text, {"source": "episode_page", "source_url": page_url, "heading": heading.name}

    if candidate_links:
        return {"status": "candidate_links", "candidates": sorted(set(candidate_links))}
    return None


def format_seconds(seconds: float | None) -> str:
    if seconds is None:
        return "--:--"
    rounded = int(round(seconds))
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def write_transcript_files(
    episode_dir: Path,
    metadata: dict[str, Any],
    source: dict[str, Any],
    chunks: list[dict[str, Any]],
) -> None:
    generated_at = utc_now_iso()
    transcript_json = {
        "guid": metadata["guid"],
        "title": metadata["title"],
        "pub_date": metadata.get("pub_date"),
        "generated_at": generated_at,
        "source": source,
        "chunks": chunks,
    }
    write_json(episode_dir / "transcript.json", transcript_json)

    lines = [
        f"# {metadata['title']}",
        "",
        f"- Publication date: {metadata.get('pub_date') or 'unknown'}",
        f"- RSS GUID: `{metadata['guid']}`",
        f"- Source: {source.get('source') or 'unknown'}",
    ]
    if source.get("source_url"):
        lines.append(f"- Source URL: {source['source_url']}")
    if source.get("asr_model"):
        lines.append(f"- ASR model: `{source['asr_model']}`")
    lines.extend(["", "## Transcript", ""])

    for chunk in chunks:
        start = format_seconds(chunk.get("start_seconds"))
        end = format_seconds(chunk.get("end_seconds"))
        if chunk.get("start_seconds") is not None or chunk.get("end_seconds") is not None:
            lines.extend([f"### {start} - {end}", ""])
        lines.extend([chunk["text"].strip(), ""])

    (episode_dir / "transcript.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def download_file(session: requests.Session, url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def audio_duration_seconds(path: Path) -> float | None:
    try:
        from pydub import AudioSegment

        return len(AudioSegment.from_file(path)) / 1000
    except Exception:
        return None


def chunk_audio_for_upload(
    audio_path: Path,
    scratch_dir: Path,
    max_bytes: int,
    initial_chunk_minutes: int,
) -> list[AudioChunk]:
    if audio_path.stat().st_size <= max_bytes:
        return [AudioChunk(audio_path, 0.0, audio_duration_seconds(audio_path))]

    from pydub import AudioSegment

    audio = AudioSegment.from_file(audio_path)
    chunk_ms = max(60_000, initial_chunk_minutes * 60_000)

    while True:
        exported: list[AudioChunk] = []
        too_large = False
        for old_chunk in scratch_dir.glob("chunk-*.mp3"):
            old_chunk.unlink()

        for index, start_ms in enumerate(range(0, len(audio), chunk_ms), start=1):
            end_ms = min(start_ms + chunk_ms, len(audio))
            chunk_path = scratch_dir / f"chunk-{index:03d}.mp3"
            audio[start_ms:end_ms].export(chunk_path, format="mp3", bitrate="64k")
            if chunk_path.stat().st_size > max_bytes:
                too_large = True
                break
            exported.append(AudioChunk(chunk_path, start_ms / 1000, end_ms / 1000))

        if not too_large:
            return exported
        if chunk_ms <= 60_000:
            raise RuntimeError("Could not split audio into chunks small enough for ASR upload")
        chunk_ms = max(60_000, chunk_ms // 2)


def normalize_openai_text(response: Any) -> str:
    if isinstance(response, str):
        return response.strip()
    text = getattr(response, "text", None)
    if text:
        return str(text).strip()
    if isinstance(response, dict) and response.get("text"):
        return str(response["text"]).strip()
    return str(response).strip()


def transcribe_with_openai(
    audio_path: Path,
    model: str,
    max_upload_mb: int,
    chunk_minutes: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from openai import OpenAI

    client = OpenAI(timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "900")))
    max_bytes = max_upload_mb * 1024 * 1024
    prompt = os.getenv("ASR_PROMPT", DEFAULT_ASR_PROMPT)

    with tempfile.TemporaryDirectory() as temp_dir:
        scratch_dir = Path(temp_dir)
        audio_chunks = chunk_audio_for_upload(audio_path, scratch_dir, max_bytes, chunk_minutes)
        transcript_chunks: list[dict[str, Any]] = []

        for index, chunk in enumerate(audio_chunks, start=1):
            with chunk.path.open("rb") as audio_file:
                request: dict[str, Any] = {
                    "model": model,
                    "file": audio_file,
                    "response_format": "text",
                }
                if prompt:
                    request["prompt"] = prompt
                response = client.audio.transcriptions.create(**request)

            transcript_chunks.append(
                {
                    "index": index,
                    "start_seconds": chunk.start_seconds,
                    "end_seconds": chunk.end_seconds,
                    "text": normalize_openai_text(response),
                }
            )

    source = {
        "source": "openai",
        "asr_model": model,
        "chunk_minutes": chunk_minutes,
        "max_upload_mb": max_upload_mb,
    }
    return transcript_chunks, source


def should_transcribe(mode: str) -> bool:
    has_key = bool(os.getenv("OPENAI_API_KEY"))
    if mode == "never":
        return False
    if mode == "always" and not has_key:
        raise RuntimeError("TRANSCRIBE=always requires the OPENAI_API_KEY secret")
    return has_key


def episode_metadata(entry: Any, feed_url: str, transcript_tags: list[dict[str, str | None]]) -> dict[str, Any]:
    title = text_or_none(entry.get("title")) or "Untitled episode"
    pub_date = parse_entry_date(entry)
    description_html = entry.get("summary") or entry.get("description") or ""
    mp3_url = entry_mp3_url(entry)
    return {
        "guid": entry_guid(entry),
        "title": title,
        "slug": episode_slug(pub_date, title),
        "pub_date": pub_date,
        "feed_url": feed_url,
        "podcast_page_url": text_or_none(entry.get("link")),
        "mp3_url": mp3_url,
        "duration": text_or_none(entry.get("itunes_duration")),
        "description_html": description_html,
        "description_text": clean_html_text(description_html),
        "rss_transcript_tags": transcript_tags,
        "youtube_url": None,
    }


def process_episode(
    *,
    entry: Any,
    feed_url: str,
    out_dir: Path,
    session: requests.Session,
    transcript_tags: list[dict[str, str | None]],
    transcribe_mode: str,
    asr_model: str,
    dry_run: bool,
) -> dict[str, Any]:
    metadata = episode_metadata(entry, feed_url, transcript_tags)
    episode_dir = out_dir / "episodes" / metadata["slug"]

    if dry_run:
        print(f"Would process: {metadata['title']} ({metadata['guid']})")
        metadata["path"] = str(episode_dir.relative_to(out_dir.parent))
        metadata["transcript"] = {"status": "dry_run"}
        return metadata

    episode_dir.mkdir(parents=True, exist_ok=True)
    existing_metadata = load_json(episode_dir / "metadata.json", {})
    metadata["created_at"] = existing_metadata.get("created_at") or utc_now_iso()
    metadata["updated_at"] = utc_now_iso()

    official = fetch_transcript_from_tags(session, transcript_tags)
    if official:
        text, source = official
        write_transcript_files(
            episode_dir,
            metadata,
            source,
            [{"index": 1, "start_seconds": None, "end_seconds": None, "text": text}],
        )
        metadata["transcript"] = {
            "status": "found_official",
            "source": source["source"],
            "path": "transcript.md",
            "json_path": "transcript.json",
        }
        write_json(episode_dir / "metadata.json", metadata)
        return metadata

    page_result = discover_page_transcript(session, metadata.get("podcast_page_url"))
    if isinstance(page_result, tuple):
        text, source = page_result
        write_transcript_files(
            episode_dir,
            metadata,
            source,
            [{"index": 1, "start_seconds": None, "end_seconds": None, "text": text}],
        )
        metadata["transcript"] = {
            "status": "found_official",
            "source": source["source"],
            "path": "transcript.md",
            "json_path": "transcript.json",
        }
        write_json(episode_dir / "metadata.json", metadata)
        return metadata

    if isinstance(page_result, dict):
        metadata["transcript_candidates"] = page_result

    if should_transcribe(transcribe_mode):
        if not metadata.get("mp3_url"):
            raise RuntimeError(f"No MP3 enclosure found for {metadata['title']}")
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "episode.mp3"
            download_file(session, metadata["mp3_url"], audio_path)
            chunks, source = transcribe_with_openai(
                audio_path,
                model=asr_model,
                max_upload_mb=int(os.getenv("ASR_MAX_UPLOAD_MB", "24")),
                chunk_minutes=int(os.getenv("ASR_CHUNK_MINUTES", "10")),
            )
        write_transcript_files(episode_dir, metadata, source, chunks)
        metadata["transcript"] = {
            "status": "generated_asr",
            "source": source["source"],
            "asr_model": source["asr_model"],
            "path": "transcript.md",
            "json_path": "transcript.json",
        }
    else:
        metadata["transcript"] = {
            "status": "pending_asr",
            "source": None,
            "reason": "No official transcript found and ASR credentials are not configured.",
        }

    write_json(episode_dir / "metadata.json", metadata)
    return metadata


def select_entries_to_process(
    entries: list[Any],
    index: dict[str, Any],
    max_new: int,
    retry_pending: bool,
    transcribe_enabled: bool,
) -> list[Any]:
    indexed_by_guid = {episode.get("guid"): episode for episode in index.get("episodes", [])}
    selected: list[Any] = []

    for entry in entries:
        guid = entry_guid(entry)
        if guid not in indexed_by_guid:
            selected.append(entry)
        if len(selected) >= max_new:
            return selected

    if retry_pending and transcribe_enabled and len(selected) < max_new:
        selected_guids = {entry_guid(entry) for entry in selected}
        for entry in entries:
            guid = entry_guid(entry)
            indexed = indexed_by_guid.get(guid)
            if not indexed or guid in selected_guids:
                continue
            status = (indexed.get("transcript") or {}).get("status")
            if status in PENDING_STATUSES:
                selected.append(entry)
                selected_guids.add(guid)
            if len(selected) >= max_new:
                break

    return selected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest STR podcast metadata and transcripts.")
    parser.add_argument("--feed-url", default=DEFAULT_FEED_URL)
    parser.add_argument("--out-dir", type=Path, default=Path("corpus"))
    parser.add_argument("--max-new", type=int, default=int(os.getenv("MAX_EPISODES_PER_RUN", "2")))
    parser.add_argument("--transcribe", choices=("auto", "always", "never"), default=os.getenv("TRANSCRIBE", "auto"))
    parser.add_argument("--asr-model", default=os.getenv("ASR_MODEL", DEFAULT_ASR_MODEL))
    parser.add_argument("--user-agent", default=os.getenv("USER_AGENT", DEFAULT_USER_AGENT))
    parser.add_argument("--no-retry-pending", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": args.user_agent})

    feed_xml, parsed = fetch_feed(session, args.feed_url)
    transcript_tags = transcript_tags_by_guid(feed_xml)
    index = load_index(args.out_dir)
    index["feed_url"] = args.feed_url
    entries = list(parsed.entries)

    transcribe_enabled = should_transcribe(args.transcribe)
    selected_entries = select_entries_to_process(
        entries,
        index,
        max_new=args.max_new,
        retry_pending=not args.no_retry_pending,
        transcribe_enabled=transcribe_enabled,
    )

    if not selected_entries:
        print("No new or pending episodes found.")
        return 0

    for entry in selected_entries:
        guid = entry_guid(entry)
        metadata = process_episode(
            entry=entry,
            feed_url=args.feed_url,
            out_dir=args.out_dir,
            session=session,
            transcript_tags=transcript_tags.get(guid, []),
            transcribe_mode=args.transcribe,
            asr_model=args.asr_model,
            dry_run=args.dry_run,
        )
        upsert_index_episode(
            index,
            {
                "guid": metadata["guid"],
                "title": metadata["title"],
                "slug": metadata["slug"],
                "pub_date": metadata.get("pub_date"),
                "podcast_page_url": metadata.get("podcast_page_url"),
                "mp3_url": metadata.get("mp3_url"),
                "path": f"episodes/{metadata['slug']}",
                "transcript": metadata.get("transcript"),
                "youtube_url": metadata.get("youtube_url"),
            },
        )
        print(f"Processed: {metadata['title']} ({metadata.get('transcript', {}).get('status')})")

    if not args.dry_run:
        write_json(args.out_dir / "episodes.json", index)
    return 0


if __name__ == "__main__":
    sys.exit(main())
