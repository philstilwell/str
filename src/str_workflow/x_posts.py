"""Queue and publish one X announcement for each newly published assessment.

Before any POST, a sending claim is pushed to GitHub. An interrupted or ambiguous
attempt is held for inspection instead of risking a duplicate on the next run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable

import requests
from bs4 import BeautifulSoup

from .outreach import atomic_write, extract_critique, utc_now, validate_slug

STATE_PATH = Path("outreach/x-posts.json")
DOCS_DIR = Path("docs/episodes")
API_URL = "https://api.x.com/2"
SECRET_NAMES = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
STATES = {"pending", "sending", "posted", "uncertain"}


class PostingError(ValueError):
    pass


def text_weight(text: str) -> int:
    """Conservative X character count; compound emoji may be overcounted."""
    total = 0
    for char in unicodedata.normalize("NFC", text):
        code = ord(char)
        total += 1 if (
            code <= 0x10FF or 0x2000 <= code <= 0x200D
            or 0x2010 <= code <= 0x201F or 0x2032 <= code <= 0x2037
        ) else 2
    return total


def shorten(text: str, limit: int) -> str:
    text = unicodedata.normalize("NFC", " ".join(text.split()))
    if text_weight(text) <= limit:
        return text
    fragment = ""
    for char in text:
        if text_weight(fragment + char + "…") > limit:
            break
        fragment += char
    if " " in fragment:
        fragment = fragment.rsplit(" ", 1)[0]
    return fragment.rstrip(" ,;:.") + "…"


def compose_post(critique: dict[str, Any]) -> str:
    title = shorten(critique["episode_title"], 110)
    lead = f"New OnReason assessment: {title}"
    footer = f"\n\nRead the assessment: {critique['url']}"
    # X wraps the single canonical URL to 23 characters.
    remaining = 280 - text_weight(lead + "\n\nTopics: \n\nRead the assessment: ") - 23
    topics = shorten("; ".join(critique["compact_topics"][:2]), remaining)
    return f"{lead}\n\nTopics: {topics}{footer}"


def validate_post(slug: str, post: dict[str, Any]) -> None:
    validate_slug(slug)
    url = f"https://onreason.com/episodes/{slug}/"
    text = post.get("text", "")
    if post.get("url") != url or not text.endswith(url):
        raise PostingError(f"Invalid canonical assessment URL for {slug}")
    # Only the terminal canonical URL is allowed; metadata must not add links.
    body = text[:-len(url)]
    if re.search(r"https?://|www\.", body, re.IGNORECASE):
        raise PostingError(f"Unexpected extra URL in announcement for {slug}")
    if text_weight(body) + 23 > 280:
        raise PostingError(f"Announcement exceeds X's character limit: {slug}")
    if post.get("status") not in STATES or not post.get("title"):
        raise PostingError(f"Invalid announcement state for {slug}")
    if post["status"] == "posted" and not re.fullmatch(
        r"https://x\.com/i/web/status/[0-9]+", post.get("posted_url", "")
    ):
        raise PostingError(f"Posted announcement is missing its permalink: {slug}")


def read_state(path: Path) -> dict[str, Any]:
    # Never silently recreate missing/corrupt history: doing so could repost pages.
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or state.get("schema_version") != 1 or not isinstance(state.get("baseline_slugs"), list):
        raise PostingError("Invalid X announcement history; restore it before posting.")
    if not isinstance(state.get("posts"), dict):
        raise PostingError("X announcement history has no posts mapping.")
    for slug in state["baseline_slugs"]:
        validate_slug(slug)
    for slug, post in state["posts"].items():
        validate_post(slug, post)
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    atomic_write(path, json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def enqueue(state: dict[str, Any], docs_dir: Path) -> int:
    known = set(state["baseline_slugs"]) | set(state["posts"])
    added = 0
    for page in sorted(docs_dir.glob("*/index.html")):
        slug = page.parent.name
        if slug in known:
            continue
        critique = extract_critique(page)
        post = {
            "url": critique["url"], "title": critique["episode_title"],
            "text": compose_post(critique), "status": "pending",
            "created_at": utc_now(), "history": [],
        }
        validate_post(slug, post)
        state["posts"][slug] = post
        added += 1
    return added


def live_page_matches(post: dict[str, Any], get: Callable = requests.get) -> bool:
    # This request deliberately has no X authorization header or session.
    try:
        response = get(post["url"], timeout=30, allow_redirects=False)
        if response.status_code != 200:
            return False
        soup = BeautifulSoup(response.text, "html.parser")
        canonical = soup.select_one('link[rel~="canonical"]')
        heading = soup.find("h1")
        return bool(
            canonical and canonical.get("href") == post["url"] and heading
            and heading.get_text(" ", strip=True) == post["title"]
            and soup.select_one("#overall")
        )
    except requests.RequestException:
        return False


def wait_for_page(post: dict[str, Any], attempts: int) -> bool:
    for attempt in range(attempts):
        if live_page_matches(post):
            return True
        if attempt + 1 < attempts:
            time.sleep(30)
    return False


def x_session() -> requests.Session:
    missing = [name for name in SECRET_NAMES if not os.getenv(name)]
    if missing:
        raise PostingError("Missing GitHub secrets: " + ", ".join(missing))
    from requests_oauthlib import OAuth1

    session = requests.Session()
    session.auth = OAuth1(*(os.environ[name] for name in SECRET_NAMES))
    return session


def verify_account(session: requests.Session, expected: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", expected):
        raise PostingError("Set X_USERNAME to the intended account name without @.")
    response = session.get(f"{API_URL}/users/me", timeout=30, allow_redirects=False)
    if response.status_code != 200:
        raise PostingError(f"X account verification failed (HTTP {response.status_code}).")
    user = response.json().get("data", {})
    if user.get("username", "").casefold() != expected.casefold() or not user.get("id"):
        raise PostingError("X credentials do not match X_USERNAME; no announcement was sent.")
    return str(user["id"])


def require_workflow() -> None:
    if os.getenv("GITHUB_REF_NAME") != "main" or os.getenv("GITHUB_ACTIONS") != "true":
        raise PostingError("Live posting requires the serialized GitHub workflow on main.")


def git_checkpoint(path: Path) -> None:
    """Durably push only announcement history; fail before posting if push fails."""
    require_workflow()
    branch = "main"
    if subprocess.check_output(["git", "diff", "--cached", "--name-only"], text=True).strip():
        raise PostingError("Unexpected staged changes; refusing to include them in X history.")
    subprocess.run(["git", "add", "--", str(path)], check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode:
        subprocess.run(["git", "commit", "-m", "Record X assessment announcement state"], check=True)
    subprocess.run(["git", "pull", "--rebase", "origin", branch], check=True)
    subprocess.run(["git", "push", "origin", f"HEAD:{branch}"], check=True)


def transition(post: dict[str, Any], status: str, note: str) -> None:
    post["status"] = status
    post["history"].append({"status": status, "at": utc_now(), "note": note})


def publish(
    state: dict[str, Any], *, session: requests.Session,
    expected_username: str, checkpoint: Callable[[], None],
    page_ready: Callable[[dict[str, Any]], bool],
) -> int:
    held = [slug for slug, post in state["posts"].items() if post["status"] in {"sending", "uncertain"}]
    if held:
        raise PostingError("Inspect uncertain X attempts before continuing: " + ", ".join(held))
    account_id = None
    sent = 0
    deferred = []
    for slug, post in state["posts"].items():
        if post["status"] != "pending":
            continue
        validate_post(slug, post)
        if not page_ready(post):
            deferred.append(slug)
            continue
        if account_id is None:
            account_id = verify_account(session, expected_username)
        if post.get("account_id") not in {None, account_id}:
            raise PostingError("A queued announcement belongs to a different X account.")
        post["account_id"] = account_id
        post["username"] = expected_username
        transition(post, "sending", "Attempt claimed before contacting X.")
        checkpoint()  # Must reach origin/main before a paid, externally visible write.
        try:
            response = session.post(
                f"{API_URL}/tweets", json={"text": post["text"]},
                timeout=30, allow_redirects=False,
            )
        except requests.RequestException:
            transition(post, "uncertain", "Connection failed; inspect X before retrying.")
            checkpoint()
            raise PostingError(f"X result uncertain for {slug}; automatic retry is blocked.") from None
        # Only explicit authentication, billing, or rate-limit rejections are safe
        # to retry automatically. Other results require inspection (including 5xx).
        if response.status_code in {401, 402, 403, 429}:
            transition(post, "pending", f"X rejected request (HTTP {response.status_code}).")
            checkpoint()
            raise PostingError(f"X rejected announcement (HTTP {response.status_code}); retained for a later run.")
        try:
            post_id = response.json().get("data", {}).get("id") if response.status_code == 201 else None
        except (ValueError, AttributeError):
            post_id = None
        if not isinstance(post_id, str) or not post_id.isdigit():
            transition(post, "uncertain", f"Unconfirmed response (HTTP {response.status_code}); inspect X.")
            checkpoint()
            raise PostingError(f"X result uncertain for {slug}; automatic retry is blocked.")
        post["posted_url"] = f"https://x.com/i/web/status/{post_id}"
        transition(post, "posted", "X confirmed creation and returned the post ID.")
        checkpoint()
        print(f"Posted {slug}: {post['posted_url']}", flush=True)
        sent += 1
    if deferred:
        raise PostingError("Assessment pages are not live yet; retained for the next run: " + ", ".join(deferred))
    return sent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=STATE_PATH)
    parser.add_argument("--docs-dir", type=Path, default=DOCS_DIR)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("enqueue", help="Queue new pages without contacting X.")
    preview = commands.add_parser("preview", help="Preview a page without changing history or calling X.")
    preview.add_argument("page", type=Path)
    send = commands.add_parser("publish", help="Publish queued posts from the GitHub workflow.")
    send.add_argument("--page-check-attempts", type=int, default=10)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "preview":
            critique = extract_critique(args.page)
            print(compose_post(critique))
            return 0
        state = read_state(args.state)
        if args.command == "enqueue":
            added = enqueue(state, args.docs_dir)
            save_state(args.state, state)
            print(f"Queued {added} new X assessment announcement(s).")
            if os.getenv("GITHUB_OUTPUT"):
                pending = any(post["status"] == "pending" for post in state["posts"].values())
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                    output.write(f"pending={str(pending).lower()}\n")
            return 0
        if os.getenv("X_POSTING_ENABLED", "").lower() != "true":
            print("X posting is disabled. Queued announcements are retained.")
            return 0
        if not 1 <= args.page_check_attempts <= 20:
            raise PostingError("Page check attempts must be between 1 and 20.")
        if all(post["status"] == "posted" for post in state["posts"].values()):
            print("No X announcements are pending.")
            return 0
        require_workflow()

        def checkpoint() -> None:
            save_state(args.state, state)
            git_checkpoint(args.state)

        with x_session() as session:
            sent = publish(
                state, session=session, expected_username=os.getenv("X_USERNAME", ""),
                checkpoint=checkpoint,
                page_ready=lambda post: wait_for_page(post, args.page_check_attempts),
            )
        print(f"Published {sent} X announcement(s).")
        return 0
    except (PostingError, OSError, ValueError, subprocess.CalledProcessError, requests.RequestException) as exc:
        # Do not print HTTP response bodies, credentials, or request headers.
        message = str(exc) if isinstance(exc, PostingError) else type(exc).__name__
        print(f"X announcement step failed: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
