"""Choose verified X accounts and a small set of relevant discovery hashtags."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any


ACCOUNTS_PATH = Path("outreach/x-accounts.json")
MAX_MENTIONS = 4
TOPIC_TAGS = (
    ("#ArtificialIntelligence", ("artificial intelligence", "AI")),
    ("#FreeWill", ("free will", "determinism")),
    ("#ProblemOfEvil", ("problem of evil", "suffering")),
    ("#Science", ("science", "evolution", "universe", "cosmology", "intelligent design")),
    ("#Ethics", ("ethics", "morality", "moral", "charity", "justice", "abortion")),
    ("#History", ("history", "historical", "marxism", "revolution", "founding")),
    ("#Bible", ("bible", "biblical", "scripture", "gospels", "testament", "hebrews")),
    ("#Theology", ("salvation", "trinity", "doctrine", "theology", "hell", "resurrection")),
    ("#Philosophy", ("philosophy", "consciousness", "objective", "worldview", "truth")),
)


def normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().replace("’", "'").split())


def name_position(text: str, alias: str) -> int | None:
    match = re.search(r"(?<!\w)" + re.escape(normalized(alias)) + r"(?!\w)", normalized(text))
    return match.start() if match else None


def load_accounts(path: Path = ACCOUNTS_PATH) -> dict[str, Any]:
    accounts = json.loads(path.read_text(encoding="utf-8"))
    if accounts.get("schema_version") != 1:
        raise ValueError("Invalid X account directory version")
    for entry in accounts["podcasts"] + accounts["speakers"]:
        if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", entry["handle"]):
            raise ValueError("Invalid verified X handle")
        if not entry.get("sources") or not entry.get("verified_on"):
            raise ValueError("X account is missing verification evidence")
    for podcast in accounts["podcasts"]:
        if not re.fullmatch(r"#[A-Za-z][A-Za-z0-9]{0,23}", podcast["hashtag"]):
            raise ValueError("Invalid podcast hashtag")
    return accounts


def social_tags(critique: dict[str, Any]) -> tuple[list[str], list[str]]:
    accounts = load_accounts()
    podcast_name = normalized(critique.get("podcast", ""))
    podcast = next((item for item in accounts["podcasts"]
                    if podcast_name in map(normalized, item["names"])), None)
    mentions = ["@" + podcast["handle"]] if podcast else []
    speaker_text = critique.get("speaker", "")
    matches = []
    for speaker in accounts["speakers"]:
        aliases = list(speaker["names"])
        if podcast:
            aliases += speaker.get("podcast_aliases", {}).get(podcast["id"], [])
        positions = [pos for alias in aliases
                     if (pos := name_position(speaker_text, alias)) is not None]
        # Some pages credit only "Frank Turek and guest". An explicit guest
        # introduction in the title is also evidence of participation.
        for alias in speaker["names"]:
            guest = re.search(
                r"\b(?:with\s+|interview:\s*)(?:(?:dr\.?|prof\.?|professor)\s+)?"
                + re.escape(normalized(alias)) + r"(?!\w)",
                normalized(critique["episode_title"]),
            )
            if guest:
                positions.append(len(speaker_text) + guest.start())
        if positions:
            matches.append((min(positions), "@" + speaker["handle"]))
    # Prioritize the podcast and credited speakers, then explicit title guests.
    for _, handle in sorted(matches):
        if handle.casefold() not in {item.casefold() for item in mentions}:
            mentions.append(handle)
    title = critique["episode_title"]
    topics = " ".join(critique["compact_topics"])
    scored = [(sum(3 * (name_position(title, term) is not None)
                   + (name_position(topics, term) is not None) for term in terms), tag)
              for tag, terms in TOPIC_TAGS]
    topic_tag = max(scored, key=lambda item: item[0])
    hashtags = [podcast["hashtag"]] if podcast else []
    hashtags.append(topic_tag[1] if topic_tag[0] else "#Apologetics")
    return mentions[:MAX_MENTIONS], list(dict.fromkeys(hashtags))
