"""Version-controlled outreach notice log for published critiques."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup


SCHEMA_VERSION = 1
EASTERN = ZoneInfo("America/New_York")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NUMBERED_HEADING_RE = re.compile(r"^\s*(\d+)\.\s*(.+?)\s*$")
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "si"}

EVENTS = {
    "drafted",
    "approved",
    "posted",
    "verified_visible",
    "failed",
    "skipped",
    "removed",
    "visibility_unknown",
}
METHODS = {"manual", "browser_assisted", "api"}
TRANSITIONS = {
    "drafted": {"approved", "skipped"},
    "approved": {"posted", "failed", "skipped"},
    "posted": {"verified_visible", "removed", "visibility_unknown"},
    "verified_visible": {"verified_visible", "removed", "visibility_unknown"},
    "visibility_unknown": {"verified_visible", "removed", "visibility_unknown"},
    "failed": {"approved", "failed", "skipped"},
    "skipped": set(),
    "removed": set(),
}

CSV_FIELDS = [
    "posted_at_utc",
    "posted_at_et",
    "last_event_at_utc",
    "last_event_at_et",
    "podcast",
    "episode_title",
    "critique_url",
    "notice_id",
    "platform",
    "target_type",
    "target_url",
    "status",
    "posted_url",
    "method",
    "notice_text",
]

SHEET_CONFIG_FILENAME = "google-sheets.json"
GOOGLE_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
CROSS_EXAMINED_PODCAST = "I Don't Have Enough FAITH to Be an ATHEIST"
STAND_TO_REASON_PODCAST = "Stand to Reason Weekly Podcast"
NOTICE_CANONICAL_HEADERS = [
    "Notice ID",
    "Critique date",
    "Podcast",
    "Episode title",
    "Episode source",
    "Critique",
    "Recommended notice (link-free)",
    "Full notice with URL",
    "Compact topics",
    "Suggested destinations",
    "Workflow status",
    "Workflow updated (UTC)",
]
NOTICE_MANUAL_HEADERS = [
    "Manual status",
    "Posted date",
    "Public post URL",
    "Visibility",
    "Notes",
]
NOTICE_SHEET_HEADERS = NOTICE_CANONICAL_HEADERS + NOTICE_MANUAL_HEADERS
NOTICE_MANUAL_DEFAULTS = ["Ready to post", "", "", "Unchecked", ""]
SUGGESTED_DESTINATIONS = {
    CROSS_EXAMINED_PODCAST: (
        "YouTube episode; matching YouTube Shorts; Facebook; Instagram; X; TikTok"
    ),
    STAND_TO_REASON_PODCAST: (
        "YouTube; Facebook; Instagram; STR X; Greg Koukl X; LinkedIn — only "
        "where a matching episode or topic post exists"
    ),
}


class OutreachError(ValueError):
    """Raised when an outreach record or requested mutation is invalid."""


def utc_now() -> str:
    """Return a stable, second-precision UTC timestamp."""

    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def normalize_timestamp(value: str | None) -> str:
    """Parse a timestamp and normalize it to second-precision UTC."""

    if value is None:
        return utc_now()
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise OutreachError(f"Invalid ISO-8601 timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise OutreachError("Timestamps must include a timezone offset or Z.")
    return (
        parsed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_timestamp(value: str) -> datetime:
    """Parse a normalized or offset-bearing ISO-8601 timestamp."""

    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return parsed.astimezone(timezone.utc)


def eastern_display(value: str | None) -> str:
    """Render a UTC timestamp in Eastern time for the human indexes."""

    if not value:
        return ""
    return parse_timestamp(value).astimezone(EASTERN).strftime("%Y-%m-%d %H:%M %Z")


def validate_slug(value: str, label: str = "slug") -> str:
    candidate = value.strip().lower()
    if not SLUG_RE.fullmatch(candidate):
        raise OutreachError(
            f"{label} must contain only lowercase letters, numbers, and hyphens: {value}"
        )
    return candidate


def validate_url(value: str, label: str) -> str:
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise OutreachError(f"{label} must be an absolute HTTP(S) URL: {value}")
    return candidate


def normalize_url_for_key(value: str) -> str:
    """Normalize a target URL without erasing query parameters that identify a page."""

    parsed = urlsplit(validate_url(value, "URL"))
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_KEYS
        and not key.lower().startswith("utm_")
    ]
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            urlencode(sorted(query)),
            "",
        )
    )


def compact_topic(heading: str) -> str:
    """Compact one claim heading while keeping its subject recognizable."""

    match = NUMBERED_HEADING_RE.match(heading)
    text = match.group(2) if match else heading.strip()
    replacements = (
        (r"\bDemonic diagnosis of\b", "Demonic diagnosis:"),
        (r"\bPreliminary evidence\b", "Initial evidence"),
        (r"\bconviction language\b", "conviction"),
        (r"\bcapital punishment\b", "death penalty"),
        (r"\bsocial destruction\b", "social harm"),
        (r"\bChristian organizations\b", "Christian orgs"),
        (r"\bsalvation security\b", "salvation"),
        (r"\bthe Holy Spirit\b", "Holy Spirit"),
        (r"\band the\b", "/"),
        (r"\band\b", "/"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"\s*,\s*", "/", text)
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"/{2,}", "/", text)
    text = re.sub(r"\s+", " ", text).strip(" /,")
    return text


def claim_topics(contents: Sequence[str]) -> list[str]:
    """Return every substantive heading between Claim map and Overall assessment."""

    normalized = [item.strip().casefold() for item in contents]
    try:
        start = normalized.index("claim map") + 1
        end = normalized.index("overall assessment")
    except ValueError as exc:
        raise OutreachError(
            "Contents must include both 'Claim map' and 'Overall assessment'."
        ) from exc
    if start >= end:
        raise OutreachError("Claim map must precede Overall assessment in Contents.")
    topics = list(contents[start:end])
    if not topics:
        raise OutreachError("Contents has no substantive headings in the claim-map section.")
    return topics


def compact_claim_topics(contents: Sequence[str]) -> list[str]:
    return [compact_topic(item) for item in claim_topics(contents)]


def compact_contents(contents: Sequence[str]) -> list[str]:
    """Return a full Contents list with only claim headings abbreviated."""

    topics = claim_topics(contents)
    compact = compact_claim_topics(contents)
    topic_index = 0
    result: list[str] = []
    for item in contents:
        if topic_index < len(topics) and item == topics[topic_index]:
            match = NUMBERED_HEADING_RE.match(item)
            prefix = f"{match.group(1)}. " if match else ""
            result.append(f"{prefix}{compact[topic_index]}")
            topic_index += 1
        else:
            result.append(item)
    return result


def infer_podcast(source_name: str) -> str:
    if source_name.startswith("CrossExamined"):
        return "I Don't Have Enough FAITH to Be an ATHEIST"
    if source_name.startswith("Stand to Reason"):
        return "Stand to Reason Weekly Podcast"
    return source_name


def extract_critique(
    page_path: Path,
    *,
    podcast_override: str | None = None,
    critique_url_override: str | None = None,
    episode_title_override: str | None = None,
) -> dict[str, Any]:
    """Extract canonical critique metadata and Contents from a rendered page."""

    if not page_path.is_file():
        raise OutreachError(f"Critique page does not exist: {page_path}")
    soup = BeautifulSoup(page_path.read_text(encoding="utf-8"), "html.parser")

    heading = soup.find("h1")
    extracted_title = heading.get_text(" ", strip=True) if heading else ""
    episode_title = (episode_title_override or extracted_title).strip()
    if not episode_title:
        raise OutreachError(f"Could not find the episode title in {page_path}")

    canonical = soup.select_one('link[rel~="canonical"]')
    extracted_url = canonical.get("href", "") if canonical else ""
    critique_url = validate_url(
        critique_url_override or extracted_url,
        "Critique URL",
    )

    source_name = ""
    source_url = ""
    for term in soup.select("dl.meta-list dt"):
        if term.get_text(" ", strip=True).casefold() != "episode source":
            continue
        value = term.find_next_sibling("dd")
        link = value.find("a") if value else None
        if link:
            source_name = link.get_text(" ", strip=True)
            source_url = link.get("href", "").strip()
        elif value:
            source_name = value.get_text(" ", strip=True)
        break
    if not source_name:
        raise OutreachError(f"Could not find Episode source metadata in {page_path}")
    if source_url:
        validate_url(source_url, "Episode source URL")

    contents = [
        link.get_text(" ", strip=True)
        for link in soup.select("#toc-list li a")
        if link.get_text(" ", strip=True)
    ]
    claim_topics(contents)

    slug = validate_slug(page_path.parent.name, "Critique page directory")
    podcast = (podcast_override or infer_podcast(source_name)).strip()
    if not podcast:
        raise OutreachError("Podcast cannot be blank.")

    return {
        "slug": slug,
        "url": critique_url,
        "podcast": podcast,
        "episode_title": episode_title,
        "episode_source": {"name": source_name, "url": source_url},
        "contents": contents,
        "compact_topics": compact_claim_topics(contents),
    }


def record_path(outreach_dir: Path, slug: str) -> Path:
    return outreach_dir / "posts" / f"{validate_slug(slug)}.json"


def read_record(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise OutreachError(f"Outreach record does not exist: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OutreachError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise OutreachError(f"Outreach record must be a JSON object: {path}")
    return data


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def write_record(path: Path, record: dict[str, Any]) -> None:
    errors = validate_record(record, path)
    if errors:
        raise OutreachError("\n".join(errors))
    atomic_write(path, json.dumps(record, indent=2, ensure_ascii=False) + "\n")


def make_record(critique: dict[str, Any], *, at: str | None = None) -> dict[str, Any]:
    timestamp = normalize_timestamp(at)
    return {
        "schema_version": SCHEMA_VERSION,
        "critique": critique,
        "notices": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def initialize_record(
    page_path: Path,
    outreach_dir: Path,
    *,
    podcast_override: str | None = None,
    critique_url_override: str | None = None,
    episode_title_override: str | None = None,
    at: str | None = None,
) -> Path:
    critique = extract_critique(
        page_path,
        podcast_override=podcast_override,
        critique_url_override=critique_url_override,
        episode_title_override=episode_title_override,
    )
    destination = record_path(outreach_dir, critique["slug"])
    if destination.exists():
        raise OutreachError(f"Outreach record already exists: {destination}")
    write_record(destination, make_record(critique, at=at))
    rebuild_indexes(outreach_dir)
    return destination


def notice_key(critique_url: str, platform: str, target_url: str) -> str:
    identity = "\n".join(
        (
            normalize_url_for_key(critique_url),
            validate_slug(platform, "platform"),
            normalize_url_for_key(target_url),
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def add_notice(
    path: Path,
    *,
    platform: str,
    target_type: str,
    target_url: str,
    notice_text: str,
    method: str = "manual",
    actor: str = "local",
    at: str | None = None,
) -> str:
    record = read_record(path)
    timestamp = normalize_timestamp(at)
    platform_slug = validate_slug(platform, "platform")
    target_type_slug = validate_slug(target_type, "target type")
    target_url = validate_url(target_url, "Target URL")
    method = method.strip().lower()
    if method not in METHODS:
        raise OutreachError(f"Method must be one of: {', '.join(sorted(METHODS))}")
    if not notice_text.strip():
        raise OutreachError("Notice text cannot be blank.")
    if not actor.strip():
        raise OutreachError("Actor cannot be blank.")

    key = notice_key(record["critique"]["url"], platform_slug, target_url)
    for notice in record.get("notices", []):
        if notice.get("idempotency_key") == key:
            raise OutreachError(
                "A notice for this critique, platform, and target already exists: "
                f"{notice.get('id')}"
            )

    notice_id = f"{platform_slug}-{key[:12]}"
    event = {"event": "drafted", "at": timestamp, "actor": actor.strip()}
    notice = {
        "id": notice_id,
        "idempotency_key": key,
        "platform": platform_slug,
        "target_type": target_type_slug,
        "target_url": target_url,
        "notice_text": notice_text,
        "status": "drafted",
        "method": method,
        "posted_url": None,
        "created_at": timestamp,
        "updated_at": timestamp,
        "history": [event],
    }
    record.setdefault("notices", []).append(notice)
    record["updated_at"] = max(
        (record["updated_at"], timestamp), key=parse_timestamp
    )
    write_record(path, record)
    rebuild_indexes(path.parent.parent)
    return notice_id


def append_event(
    path: Path,
    notice_id: str,
    event_name: str,
    *,
    posted_url: str | None = None,
    actor: str = "local",
    note: str | None = None,
    at: str | None = None,
) -> None:
    record = read_record(path)
    timestamp = normalize_timestamp(at)
    event_name = event_name.strip().lower()
    if event_name == "drafted" or event_name not in EVENTS:
        choices = ", ".join(sorted(EVENTS - {"drafted"}))
        raise OutreachError(f"Event must be one of: {choices}")
    if not actor.strip():
        raise OutreachError("Actor cannot be blank.")

    notice = next(
        (item for item in record.get("notices", []) if item.get("id") == notice_id),
        None,
    )
    if notice is None:
        raise OutreachError(f"Notice does not exist in {path}: {notice_id}")

    current = notice.get("status")
    allowed = TRANSITIONS.get(current, set())
    if event_name not in allowed:
        rendered = ", ".join(sorted(allowed)) or "none"
        raise OutreachError(
            f"Cannot append {event_name!r} after {current!r}; allowed: {rendered}."
        )

    history = notice.get("history", [])
    if history and parse_timestamp(timestamp) < parse_timestamp(history[-1]["at"]):
        raise OutreachError("A new event cannot predate the notice's last event.")

    if event_name == "posted":
        if not posted_url:
            raise OutreachError("The posted event requires --posted-url.")
        notice["posted_url"] = validate_url(posted_url, "Posted URL")
    elif posted_url:
        raise OutreachError("--posted-url is only valid for a posted event.")

    event: dict[str, str] = {
        "event": event_name,
        "at": timestamp,
        "actor": actor.strip(),
    }
    if note and note.strip():
        event["note"] = note.strip()
    notice.setdefault("history", []).append(event)
    notice["status"] = event_name
    notice["updated_at"] = timestamp
    record["updated_at"] = max(
        (record["updated_at"], timestamp), key=parse_timestamp
    )
    write_record(path, record)
    rebuild_indexes(path.parent.parent)


def _event_transition_errors(history: Sequence[dict[str, Any]], label: str) -> list[str]:
    errors: list[str] = []
    if not history:
        return [f"{label}.history must contain at least the drafted event"]
    previous: str | None = None
    previous_time: datetime | None = None
    for index, event in enumerate(history):
        prefix = f"{label}.history[{index}]"
        if not isinstance(event, dict):
            errors.append(f"{prefix} must be an object")
            continue
        name = event.get("event")
        if name not in EVENTS:
            errors.append(f"{prefix}.event is invalid: {name!r}")
        if index == 0 and name != "drafted":
            errors.append(f"{label}.history must begin with drafted")
        if previous in TRANSITIONS and name not in TRANSITIONS[previous]:
            errors.append(f"{prefix} cannot follow {previous!r}: {name!r}")
        try:
            event_time = parse_timestamp(event.get("at", ""))
        except (TypeError, ValueError):
            errors.append(f"{prefix}.at must be an ISO-8601 timestamp with timezone")
            event_time = None
        if previous_time and event_time and event_time < previous_time:
            errors.append(f"{prefix}.at predates the preceding event")
        if event_time:
            previous_time = event_time
        if not isinstance(event.get("actor"), str) or not event["actor"].strip():
            errors.append(f"{prefix}.actor cannot be blank")
        previous = name if isinstance(name, str) else None
    return errors


def validate_record(record: dict[str, Any], path: Path | None = None) -> list[str]:
    """Return all validation errors in one canonical outreach record."""

    label = str(path) if path else "record"
    errors: list[str] = []
    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}: schema_version must be {SCHEMA_VERSION}")

    critique = record.get("critique")
    if not isinstance(critique, dict):
        return errors + [f"{label}: critique must be an object"]
    slug = critique.get("slug")
    try:
        validate_slug(slug, "critique.slug")
    except (AttributeError, OutreachError) as exc:
        errors.append(f"{label}: {exc}")
    if path and isinstance(slug, str) and path.stem != slug:
        errors.append(f"{label}: filename must match critique.slug")
    for field in ("podcast", "episode_title"):
        if not isinstance(critique.get(field), str) or not critique[field].strip():
            errors.append(f"{label}: critique.{field} cannot be blank")
    try:
        validate_url(critique.get("url", ""), "critique.url")
    except OutreachError as exc:
        errors.append(f"{label}: {exc}")

    contents = critique.get("contents")
    if not isinstance(contents, list) or not all(
        isinstance(item, str) and item.strip() for item in contents
    ):
        errors.append(f"{label}: critique.contents must be a list of nonblank strings")
        topics: list[str] = []
    else:
        try:
            topics = compact_claim_topics(contents)
        except OutreachError as exc:
            errors.append(f"{label}: {exc}")
            topics = []
    compact_topics = critique.get("compact_topics")
    if not isinstance(compact_topics, list) or not all(
        isinstance(item, str) and item.strip() for item in compact_topics
    ):
        errors.append(
            f"{label}: critique.compact_topics must be a list of nonblank strings"
        )
    elif topics and len(compact_topics) != len(topics):
        errors.append(
            f"{label}: critique.compact_topics must contain every claim-map heading"
        )

    notices = record.get("notices")
    if not isinstance(notices, list):
        errors.append(f"{label}: notices must be a list")
        notices = []
    notice_ids: set[str] = set()
    keys: set[str] = set()
    for index, notice in enumerate(notices):
        prefix = f"{label}: notices[{index}]"
        if not isinstance(notice, dict):
            errors.append(f"{prefix} must be an object")
            continue
        notice_id = notice.get("id")
        if not isinstance(notice_id, str) or not notice_id:
            errors.append(f"{prefix}.id cannot be blank")
        elif notice_id in notice_ids:
            errors.append(f"{prefix}.id duplicates {notice_id}")
        else:
            notice_ids.add(notice_id)
        key = notice.get("idempotency_key")
        if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key):
            errors.append(f"{prefix}.idempotency_key must be a SHA-256 hex digest")
        elif key in keys:
            errors.append(f"{prefix}.idempotency_key is duplicated")
        else:
            keys.add(key)
        for field in ("platform", "target_type"):
            try:
                validate_slug(notice.get(field), field)
            except (AttributeError, OutreachError) as exc:
                errors.append(f"{prefix}: {exc}")
        try:
            validate_url(notice.get("target_url", ""), "target_url")
        except OutreachError as exc:
            errors.append(f"{prefix}: {exc}")
        posted_url = notice.get("posted_url")
        if posted_url is not None:
            try:
                validate_url(posted_url, "posted_url")
            except OutreachError as exc:
                errors.append(f"{prefix}: {exc}")
        if not isinstance(notice.get("notice_text"), str) or not notice[
            "notice_text"
        ].strip():
            errors.append(f"{prefix}.notice_text cannot be blank")
        if notice.get("method") not in METHODS:
            errors.append(f"{prefix}.method is invalid: {notice.get('method')!r}")
        history = notice.get("history")
        if not isinstance(history, list):
            errors.append(f"{prefix}.history must be a list")
            history = []
        errors.extend(_event_transition_errors(history, prefix))
        if history and notice.get("status") != history[-1].get("event"):
            errors.append(f"{prefix}.status must match the final history event")
        for field in ("created_at", "updated_at"):
            try:
                parse_timestamp(notice.get(field, ""))
            except (TypeError, ValueError):
                errors.append(
                    f"{prefix}.{field} must be an ISO-8601 timestamp with timezone"
                )
        if history and notice.get("created_at") != history[0].get("at"):
            errors.append(f"{prefix}.created_at must match the drafted event")
        if history and notice.get("updated_at") != history[-1].get("at"):
            errors.append(f"{prefix}.updated_at must match the final history event")
        if any(event.get("event") == "posted" for event in history) and not posted_url:
            errors.append(f"{prefix}.posted_url is required after a posted event")
        try:
            expected_key = notice_key(
                critique.get("url", ""),
                notice.get("platform", ""),
                notice.get("target_url", ""),
            )
            if key != expected_key:
                errors.append(f"{prefix}.idempotency_key does not match its identity")
            expected_id = f"{notice.get('platform')}-{expected_key[:12]}"
            if notice_id != expected_id:
                errors.append(f"{prefix}.id does not match its identity")
        except (AttributeError, OutreachError):
            pass

    parsed_record_times: dict[str, datetime] = {}
    for field in ("created_at", "updated_at"):
        try:
            parsed_record_times[field] = parse_timestamp(record.get(field, ""))
        except (TypeError, ValueError):
            errors.append(f"{label}: {field} must be an ISO-8601 timestamp with timezone")
    if (
        "created_at" in parsed_record_times
        and "updated_at" in parsed_record_times
        and parsed_record_times["updated_at"] < parsed_record_times["created_at"]
    ):
        errors.append(f"{label}: updated_at cannot predate created_at")
    if "updated_at" in parsed_record_times:
        for index, notice in enumerate(notices):
            if not isinstance(notice, dict):
                continue
            try:
                notice_updated = parse_timestamp(notice.get("updated_at", ""))
            except (TypeError, ValueError):
                continue
            if notice_updated > parsed_record_times["updated_at"]:
                errors.append(
                    f"{label}: notices[{index}].updated_at cannot follow record.updated_at"
                )
    return errors


def load_records(outreach_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    posts_dir = outreach_dir / "posts"
    if not posts_dir.exists():
        return []
    records: list[tuple[Path, dict[str, Any]]] = []
    errors: list[str] = []
    for path in sorted(posts_dir.glob("*.json")):
        try:
            record = read_record(path)
        except OutreachError as exc:
            errors.append(str(exc))
            continue
        errors.extend(validate_record(record, path))
        records.append((path, record))
    if errors:
        raise OutreachError("\n".join(errors))
    return records


def latest_event_time(notice: dict[str, Any], event_name: str) -> str | None:
    matching = [
        event["at"]
        for event in notice.get("history", [])
        if event.get("event") == event_name
    ]
    return matching[-1] if matching else None


def index_rows(
    records: Iterable[tuple[Path, dict[str, Any]]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for _, record in records:
        critique = record["critique"]
        for notice in record["notices"]:
            posted_at = latest_event_time(notice, "posted") or ""
            last_event_at = notice["history"][-1]["at"]
            rows.append(
                {
                    "posted_at_utc": posted_at,
                    "posted_at_et": eastern_display(posted_at),
                    "last_event_at_utc": last_event_at,
                    "last_event_at_et": eastern_display(last_event_at),
                    "podcast": critique["podcast"],
                    "episode_title": critique["episode_title"],
                    "critique_url": critique["url"],
                    "notice_id": notice["id"],
                    "platform": notice["platform"],
                    "target_type": notice["target_type"],
                    "target_url": notice["target_url"],
                    "status": notice["status"],
                    "posted_url": notice.get("posted_url") or "",
                    "method": notice["method"],
                    "notice_text": notice["notice_text"],
                }
            )
    rows.sort(
        key=lambda row: (row["last_event_at_utc"], row["notice_id"]), reverse=True
    )
    return rows


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def markdown_link(label: str, url: str) -> str:
    return f"[{markdown_escape(label)}]({url})"


def markdown_fenced_text(value: str) -> list[str]:
    """Render exact text as a safe, plain-Markdown fenced code block."""

    longest_run = max((len(match) for match in re.findall(r"`+", value)), default=0)
    fence = "`" * max(3, longest_run + 1)
    return [f"{fence}text", *value.rstrip("\n").splitlines(), fence]


def render_markdown_index(
    records: Sequence[tuple[Path, dict[str, Any]]],
    rows: Sequence[dict[str, str]],
) -> str:
    lines = [
        "# Outreach post log",
        "",
        "This file is generated from `outreach/posts/*.json`; edit the JSON records through `str-outreach`, then rebuild the indexes.",
        "Human-readable timestamps are shown in U.S. Eastern time. Canonical timestamps remain UTC in JSON and CSV.",
        "",
        "## Critiques",
        "",
        "| Podcast | Critique | Notices | Compact claim topics |",
        "| --- | --- | ---: | --- |",
    ]
    if records:
        for _, record in sorted(
            records,
            key=lambda item: (
                item[1]["critique"]["podcast"],
                item[1]["critique"]["episode_title"],
            ),
        ):
            critique = record["critique"]
            compact = "; ".join(critique["compact_topics"])
            lines.append(
                "| "
                + " | ".join(
                    (
                        markdown_escape(critique["podcast"]),
                        markdown_link(critique["episode_title"], critique["url"]),
                        str(len(record["notices"])),
                        markdown_escape(compact),
                    )
                )
                + " |"
            )
    else:
        lines.append("| — | No critiques logged | 0 | — |")

    lines.extend(
        [
            "",
            "## Notices",
            "",
            "| Posted (ET) | Podcast | Critique | Platform | Target | Status | Public post |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    if rows:
        for row in rows:
            public_post = (
                markdown_link("open", row["posted_url"]) if row["posted_url"] else "—"
            )
            lines.append(
                "| "
                + " | ".join(
                    (
                        markdown_escape(row["posted_at_et"] or "—"),
                        markdown_escape(row["podcast"]),
                        markdown_link(row["episode_title"], row["critique_url"]),
                        markdown_escape(row["platform"]),
                        markdown_link(row["target_type"], row["target_url"]),
                        markdown_escape(row["status"]),
                        public_post,
                    )
                )
                + " |"
            )
    else:
        lines.append("| — | — | No notices logged | — | — | — | — |")

    if rows:
        lines.extend(["", "## Notice text"])
        for row in rows:
            lines.extend(
                [
                    "",
                    f"### {markdown_escape(row['notice_id'])}",
                    "",
                    f"Platform: {markdown_escape(row['platform'])}",
                    "",
                    f"Target: {markdown_link(row['target_type'], row['target_url'])}",
                    "",
                    *markdown_fenced_text(row["notice_text"]),
                ]
            )
    return "\n".join(lines) + "\n"


def render_csv_index(rows: Sequence[dict[str, str]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def rendered_indexes(outreach_dir: Path) -> tuple[str, str]:
    records = load_records(outreach_dir)
    rows = index_rows(records)
    return render_markdown_index(records, rows), render_csv_index(rows)


def rebuild_indexes(outreach_dir: Path) -> None:
    markdown, csv_text = rendered_indexes(outreach_dir)
    atomic_write(outreach_dir / "index.md", markdown)
    atomic_write(outreach_dir / "index.csv", csv_text)


def validate_outreach(outreach_dir: Path, *, check_indexes: bool = True) -> list[str]:
    try:
        expected_markdown, expected_csv = rendered_indexes(outreach_dir)
    except OutreachError as exc:
        return str(exc).splitlines()
    errors: list[str] = []
    if check_indexes:
        expected = {
            outreach_dir / "index.md": expected_markdown,
            outreach_dir / "index.csv": expected_csv,
        }
        for path, contents in expected.items():
            if not path.is_file():
                errors.append(f"Generated index is missing: {path}")
            elif path.read_text(encoding="utf-8") != contents:
                errors.append(f"Generated index is stale: {path}")
    return errors


def notice_search_line(podcast: str) -> str:
    """Return the approved platform-safe discovery line for one podcast."""

    if podcast == CROSS_EXAMINED_PODCAST:
        return "Search 'OnReason, I Don't Have Enough FAITH to Be an ATHEIST'"
    if podcast == STAND_TO_REASON_PODCAST:
        return "Search: 'OnReason, Stand to Reason'"
    return f"Search: 'OnReason, {podcast}'"


def recommended_notice_text(record: dict[str, Any], notice: dict[str, Any]) -> str:
    """Convert an exact notice to the approved link-free posting variant."""

    text = notice["notice_text"]
    search_line = notice_search_line(record["critique"]["podcast"])
    locator_patterns = (
        r"Read the critique:\s*\nhttps?://[^\s]+\s*",
        r"Search OnReason for:\s*\n[^\n]+\s*",
    )
    for pattern in locator_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return re.sub(
                pattern,
                f"{search_line}\n\n",
                text,
                count=1,
                flags=re.IGNORECASE,
            )

    critique_url = record["critique"]["url"]
    if critique_url in text:
        return text.replace(critique_url, search_line, 1)
    if search_line in text:
        return text

    closing = "Substantive corrections, objections, and responses are welcome."
    if closing in text:
        return text.replace(closing, f"{search_line}\n\n{closing}", 1)
    return f"{text.rstrip()}\n\n{search_line}\n"


def google_sheet_hyperlink(url: str, label: str) -> str:
    """Return a Google Sheets HYPERLINK formula with safely escaped text."""

    if not url:
        return ""
    escaped_url = url.replace('"', '""')
    escaped_label = label.replace('"', '""')
    return f'=HYPERLINK("{escaped_url}","{escaped_label}")'


def notice_sheet_rows(
    records: Iterable[tuple[Path, dict[str, Any]]],
) -> list[list[str]]:
    """Render the workflow-owned columns for the Google Sheets notice log."""

    result: list[list[str]] = []
    seen: set[str] = set()
    for _, record in records:
        critique = record["critique"]
        topics = "\n".join(
            f"{index}. {topic}"
            for index, topic in enumerate(critique["compact_topics"], start=1)
        )
        source_url = critique.get("episode_source", {}).get("url", "")
        for notice in record["notices"]:
            notice_id = notice["id"]
            if notice_id in seen:
                raise OutreachError(f"Duplicate notice ID for sheet sync: {notice_id}")
            seen.add(notice_id)
            result.append(
                [
                    notice_id,
                    critique["slug"][:10],
                    critique["podcast"],
                    critique["episode_title"],
                    google_sheet_hyperlink(source_url, "Open episode source"),
                    google_sheet_hyperlink(critique["url"], "Open critique"),
                    recommended_notice_text(record, notice),
                    notice["notice_text"],
                    topics,
                    SUGGESTED_DESTINATIONS.get(
                        critique["podcast"],
                        "Use only an official post that matches the episode or topic",
                    ),
                    notice["status"],
                    notice["updated_at"],
                ]
            )
    return result


def quote_sheet_title(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def plan_notice_sheet_upsert(
    canonical_rows: Sequence[Sequence[str]],
    existing_rows: Sequence[Sequence[str]],
    *,
    sheet_title: str = "Notices",
) -> dict[str, Any]:
    """Plan range writes without ever overwriting the five manual columns."""

    canonical_width = len(NOTICE_CANONICAL_HEADERS)
    full_width = len(NOTICE_SHEET_HEADERS)
    for row in canonical_rows:
        if len(row) != canonical_width:
            raise OutreachError(
                f"Canonical sheet rows must contain {canonical_width} values."
            )

    initialized = not existing_rows or not any(existing_rows[0])
    if initialized:
        rows: list[list[str]] = [list(NOTICE_SHEET_HEADERS)]
    else:
        header = list(existing_rows[0])
        header += [""] * (full_width - len(header))
        if header[:full_width] != NOTICE_SHEET_HEADERS:
            raise OutreachError(
                "The Notices sheet headers do not match the workflow schema; "
                "refusing to overwrite manual columns."
            )
        rows = [list(row) for row in existing_rows]

    existing_by_id: dict[str, int] = {}
    for row_number, row in enumerate(rows[1:], start=2):
        notice_id = row[0].strip() if row else ""
        if not notice_id:
            continue
        if notice_id in existing_by_id:
            raise OutreachError(f"Duplicate notice ID in Google Sheet: {notice_id}")
        existing_by_id[notice_id] = row_number

    last_used_row = max(
        (index for index, row in enumerate(rows, start=1) if any(row)),
        default=1,
    )
    sheet = quote_sheet_title(sheet_title)
    writes: list[dict[str, Any]] = []
    if initialized:
        writes.append(
            {
                "range": f"{sheet}!A1:Q1",
                "values": [NOTICE_SHEET_HEADERS],
            }
        )

    inserted_rows: list[int] = []
    updated = 0
    seen_canonical: set[str] = set()
    for canonical in canonical_rows:
        notice_id = canonical[0]
        if notice_id in seen_canonical:
            raise OutreachError(f"Duplicate canonical notice ID: {notice_id}")
        seen_canonical.add(notice_id)
        if notice_id in existing_by_id:
            row_number = existing_by_id[notice_id]
            writes.append(
                {
                    "range": f"{sheet}!A{row_number}:L{row_number}",
                    "values": [list(canonical)],
                }
            )
            updated += 1
            continue

        last_used_row += 1
        writes.append(
            {
                "range": f"{sheet}!A{last_used_row}:Q{last_used_row}",
                "values": [list(canonical) + NOTICE_MANUAL_DEFAULTS],
            }
        )
        inserted_rows.append(last_used_row)

    return {
        "writes": writes,
        "updated": updated,
        "inserted": len(inserted_rows),
        "inserted_rows": inserted_rows,
        "initialized": initialized,
        "last_used_row": last_used_row,
    }


def load_google_sheet_config(
    outreach_dir: Path,
    *,
    required: bool = False,
) -> dict[str, str] | None:
    """Load the non-secret Google Sheet destination configuration."""

    path = outreach_dir / SHEET_CONFIG_FILENAME
    if not path.is_file():
        if required:
            raise OutreachError(f"Google Sheet config does not exist: {path}")
        return None
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OutreachError(f"Invalid Google Sheet config in {path}: {exc}") from exc
    if not isinstance(config, dict):
        raise OutreachError(f"Google Sheet config must be an object: {path}")
    spreadsheet_id = config.get("spreadsheet_id")
    notices_sheet = config.get("notices_sheet", "Notices")
    if not isinstance(spreadsheet_id, str) or not spreadsheet_id.strip():
        raise OutreachError(f"spreadsheet_id cannot be blank in {path}")
    if not isinstance(notices_sheet, str) or not notices_sheet.strip():
        raise OutreachError(f"notices_sheet cannot be blank in {path}")
    return {
        "spreadsheet_id": spreadsheet_id.strip(),
        "notices_sheet": notices_sheet.strip(),
    }


def build_google_sheets_service() -> Any:
    """Create an authenticated Sheets API client from local ADC credentials."""

    try:
        import google.auth
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise OutreachError(
            "Google Sheets sync dependencies are missing; reinstall the project."
        ) from exc
    try:
        credentials, _ = google.auth.default(scopes=[GOOGLE_SHEETS_SCOPE])
    except Exception as exc:
        raise OutreachError(
            "Google Sheets sync needs Application Default Credentials. Set "
            "GOOGLE_APPLICATION_CREDENTIALS to an editor service-account JSON "
            "file or run `gcloud auth application-default login` once."
        ) from exc
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _notice_sheet_format_requests(
    *,
    sheet_id: int,
    inserted_rows: Sequence[int],
    initialized: bool,
    last_used_row: int,
) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    if initialized:
        requests.extend(
            [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": len(NOTICE_SHEET_HEADERS),
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColorStyle": {
                                    "rgbColor": {
                                        "red": 0.055,
                                        "green": 0.31,
                                        "blue": 0.25,
                                    }
                                },
                                "textFormat": {
                                    "bold": True,
                                    "foregroundColorStyle": {
                                        "rgbColor": {"red": 1, "green": 1, "blue": 1}
                                    },
                                },
                                "horizontalAlignment": "CENTER",
                                "verticalAlignment": "MIDDLE",
                                "wrapStrategy": "WRAP",
                            }
                        },
                        "fields": "userEnteredFormat",
                    }
                },
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet_id,
                            "gridProperties": {"frozenRowCount": 1},
                        },
                        "fields": "gridProperties.frozenRowCount",
                    }
                },
            ]
        )

    for row_number in inserted_rows:
        start = row_number - 1
        requests.extend(
            [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": start,
                            "endRowIndex": start + 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": len(NOTICE_SHEET_HEADERS),
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "verticalAlignment": "TOP",
                                "wrapStrategy": "WRAP",
                            }
                        },
                        "fields": (
                            "userEnteredFormat.verticalAlignment,"
                            "userEnteredFormat.wrapStrategy"
                        ),
                    }
                },
                {
                    "setDataValidation": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": start,
                            "endRowIndex": start + 1,
                            "startColumnIndex": 12,
                            "endColumnIndex": 13,
                        },
                        "rule": {
                            "condition": {
                                "type": "ONE_OF_LIST",
                                "values": [
                                    {"userEnteredValue": "Ready to post"},
                                    {"userEnteredValue": "Posted"},
                                    {"userEnteredValue": "Skipped"},
                                    {"userEnteredValue": "Failed"},
                                ],
                            },
                            "strict": True,
                            "showCustomUi": True,
                        },
                    }
                },
                {
                    "setDataValidation": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": start,
                            "endRowIndex": start + 1,
                            "startColumnIndex": 15,
                            "endColumnIndex": 16,
                        },
                        "rule": {
                            "condition": {
                                "type": "ONE_OF_LIST",
                                "values": [
                                    {"userEnteredValue": "Unchecked"},
                                    {"userEnteredValue": "Visible"},
                                    {"userEnteredValue": "Missing / held"},
                                    {"userEnteredValue": "Removed"},
                                ],
                            },
                            "strict": True,
                            "showCustomUi": True,
                        },
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": start,
                            "endIndex": start + 1,
                        },
                        "properties": {"pixelSize": 560},
                        "fields": "pixelSize",
                    }
                },
            ]
        )

    if initialized or inserted_rows:
        requests.extend(
            [
                {"clearBasicFilter": {"sheetId": sheet_id}},
                {
                    "setBasicFilter": {
                        "filter": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 0,
                                "endRowIndex": last_used_row,
                                "startColumnIndex": 0,
                                "endColumnIndex": len(NOTICE_SHEET_HEADERS),
                            }
                        }
                    }
                },
            ]
        )
    return requests


def sync_google_sheet(
    outreach_dir: Path,
    *,
    service: Any | None = None,
    required_config: bool = True,
) -> dict[str, Any] | None:
    """Upsert workflow fields by notice ID while preserving manual sheet fields."""

    config = load_google_sheet_config(outreach_dir, required=required_config)
    if config is None:
        return None
    client = service or build_google_sheets_service()
    spreadsheet_id = config["spreadsheet_id"]
    sheet_title = config["notices_sheet"]
    quoted_sheet = quote_sheet_title(sheet_title)
    try:
        spreadsheets = client.spreadsheets()
        existing = (
            spreadsheets.values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=f"{quoted_sheet}!A:Q",
                valueRenderOption="FORMULA",
            )
            .execute()
            .get("values", [])
        )
        plan = plan_notice_sheet_upsert(
            notice_sheet_rows(load_records(outreach_dir)),
            existing,
            sheet_title=sheet_title,
        )
        if plan["writes"]:
            spreadsheets.values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "valueInputOption": "USER_ENTERED",
                    "data": plan["writes"],
                },
            ).execute()

        if plan["initialized"] or plan["inserted_rows"]:
            metadata = spreadsheets.get(
                spreadsheetId=spreadsheet_id,
                fields="sheets.properties",
            ).execute()
            sheet_id = next(
                (
                    item["properties"]["sheetId"]
                    for item in metadata.get("sheets", [])
                    if item.get("properties", {}).get("title") == sheet_title
                ),
                None,
            )
            if sheet_id is None:
                raise OutreachError(
                    f"Google Sheet tab does not exist: {sheet_title}"
                )
            format_requests = _notice_sheet_format_requests(
                sheet_id=sheet_id,
                inserted_rows=plan["inserted_rows"],
                initialized=plan["initialized"],
                last_used_row=plan["last_used_row"],
            )
            if format_requests:
                spreadsheets.batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={"requests": format_requests},
                ).execute()
    except OutreachError:
        raise
    except Exception as exc:
        raise OutreachError(f"Google Sheets sync failed: {exc}") from exc

    return {
        "spreadsheet_id": spreadsheet_id,
        "sheet": sheet_title,
        "updated": plan["updated"],
        "inserted": plan["inserted"],
        "manual_rows_preserved": plan["updated"],
    }


def render_contents(record: dict[str, Any], *, compact: bool = False) -> str:
    contents = record["critique"]["contents"]
    if compact:
        contents = compact_contents(contents)
    return "Contents:\n" + "\n".join(contents) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="str-outreach",
        description="Maintain the version-controlled outreach notice log.",
    )
    parser.add_argument(
        "--outreach-dir",
        type=Path,
        default=Path("outreach"),
        help="Log directory (default: outreach)",
    )
    parser.add_argument(
        "--no-sheet-sync",
        action="store_true",
        help="Skip the configured Google Sheet sync for this command",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Initialize a critique record from HTML")
    init.add_argument("page", type=Path, help="Rendered critique index.html")
    init.add_argument("--podcast", help="Override extracted/inferred podcast name")
    init.add_argument("--critique-url", help="Override the canonical critique URL")
    init.add_argument("--episode-title", help="Override the extracted h1 title")
    init.add_argument("--at", help="ISO-8601 creation timestamp; defaults to now")

    add = subparsers.add_parser("add-notice", help="Add an exact notice as a draft")
    add.add_argument("slug", help="Critique slug")
    add.add_argument("--platform", required=True, help="Platform slug, e.g. youtube")
    add.add_argument(
        "--target-type", required=True, help="Target type, e.g. episode-video"
    )
    add.add_argument("--target-url", required=True, help="Public target URL")
    add.add_argument(
        "--notice-file",
        type=Path,
        required=True,
        help="UTF-8 file containing the exact notice text",
    )
    add.add_argument("--method", choices=sorted(METHODS), default="manual")
    add.add_argument("--actor", default="local")
    add.add_argument("--at", help="ISO-8601 drafted timestamp; defaults to now")

    event = subparsers.add_parser("event", help="Append a lifecycle event")
    event.add_argument("slug", help="Critique slug")
    event.add_argument("notice_id", help="Notice ID")
    event.add_argument("event", choices=sorted(EVENTS - {"drafted"}))
    event.add_argument("--posted-url", help="Public permalink; required for posted")
    event.add_argument("--actor", default="local")
    event.add_argument("--note")
    event.add_argument("--at", help="ISO-8601 event timestamp; defaults to now")

    contents = subparsers.add_parser(
        "contents", help="Print the full or character-limited Contents block"
    )
    contents.add_argument("slug", help="Critique slug")
    contents.add_argument(
        "--compact",
        action="store_true",
        help="Abbreviate every claim heading between Claim map and Overall assessment",
    )

    subparsers.add_parser("rebuild", help="Regenerate Markdown and CSV indexes")
    subparsers.add_parser("validate", help="Validate JSON records and generated indexes")
    subparsers.add_parser(
        "sync-sheet",
        help="Upsert canonical notice fields into the configured Google Sheet",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    outreach_dir: Path = args.outreach_dir

    def sync_if_configured(*, required: bool = False) -> None:
        if args.no_sheet_sync:
            if required:
                raise OutreachError("sync-sheet cannot be used with --no-sheet-sync")
            return
        result = sync_google_sheet(
            outreach_dir,
            required_config=required,
        )
        if result:
            print(
                "Synced Google Sheet "
                f"{result['sheet']}: {result['updated']} updated, "
                f"{result['inserted']} inserted; manual fields preserved."
            )

    try:
        if args.command == "init":
            path = initialize_record(
                args.page,
                outreach_dir,
                podcast_override=args.podcast,
                critique_url_override=args.critique_url,
                episode_title_override=args.episode_title,
                at=args.at,
            )
            print(path)
            sync_if_configured()
        elif args.command == "add-notice":
            if not args.notice_file.is_file():
                raise OutreachError(f"Notice file does not exist: {args.notice_file}")
            notice_id = add_notice(
                record_path(outreach_dir, args.slug),
                platform=args.platform,
                target_type=args.target_type,
                target_url=args.target_url,
                notice_text=args.notice_file.read_text(encoding="utf-8"),
                method=args.method,
                actor=args.actor,
                at=args.at,
            )
            print(notice_id)
            sync_if_configured()
        elif args.command == "event":
            append_event(
                record_path(outreach_dir, args.slug),
                args.notice_id,
                args.event,
                posted_url=args.posted_url,
                actor=args.actor,
                note=args.note,
                at=args.at,
            )
            print(f"{args.notice_id}: {args.event}")
            sync_if_configured()
        elif args.command == "contents":
            record = read_record(record_path(outreach_dir, args.slug))
            errors = validate_record(record, record_path(outreach_dir, args.slug))
            if errors:
                raise OutreachError("\n".join(errors))
            print(render_contents(record, compact=args.compact), end="")
        elif args.command == "rebuild":
            rebuild_indexes(outreach_dir)
            print(f"Rebuilt {outreach_dir / 'index.md'} and {outreach_dir / 'index.csv'}")
            sync_if_configured()
        elif args.command == "validate":
            errors = validate_outreach(outreach_dir)
            if errors:
                raise OutreachError("\n".join(errors))
            print(f"Outreach log is valid: {outreach_dir}")
        elif args.command == "sync-sheet":
            sync_if_configured(required=True)
    except OutreachError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
