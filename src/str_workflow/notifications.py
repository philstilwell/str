from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


READY_TRANSCRIPT_STATUSES = {"found_official", "generated_asr"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git_output(args: list[str]) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return result.stdout


def git_changed_metadata_paths(corpus_dir: Path) -> list[Path]:
    tracked = git_output(["diff", "--name-only", "--diff-filter=AM", "--", str(corpus_dir)])
    untracked = git_output(["ls-files", "--others", "--exclude-standard", "--", str(corpus_dir)])
    paths = []
    for line in [*tracked.splitlines(), *untracked.splitlines()]:
        path = Path(line)
        if path.name == "metadata.json" and "episodes" in path.parts:
            paths.append(path)
    return sorted(set(paths))


def git_head_json(path: Path) -> dict[str, Any] | None:
    result = subprocess.run(
        ["git", "show", f"HEAD:{path.as_posix()}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def transcript_status(metadata: dict[str, Any] | None) -> str | None:
    transcript = metadata.get("transcript") if isinstance(metadata, dict) else None
    if not isinstance(transcript, dict):
        return None
    status = transcript.get("status")
    return status if isinstance(status, str) else None


def transcript_became_ready(current: dict[str, Any], previous: dict[str, Any] | None) -> bool:
    current_status = transcript_status(current)
    previous_status = transcript_status(previous)
    return current_status in READY_TRANSCRIPT_STATUSES and previous_status not in READY_TRANSCRIPT_STATUSES


def link_for_path(repo_url: str | None, path: Path) -> str:
    display = path.as_posix()
    if not repo_url:
        return f"`{display}`"
    return f"[`{display}`]({repo_url.rstrip('/')}/blob/main/{display})"


def notice_from_metadata(
    *,
    metadata_path: Path,
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    repo_url: str | None = None,
    run_url: str | None = None,
) -> dict[str, Any] | None:
    if not transcript_became_ready(current, previous):
        return None

    transcript = current.get("transcript") if isinstance(current.get("transcript"), dict) else {}
    podcast = current.get("podcast") if isinstance(current.get("podcast"), dict) else {}
    podcast_title = podcast.get("title") or podcast.get("id") or "Unknown podcast"
    episode_title = current.get("title") or metadata_path.parent.name
    transcript_path = metadata_path.parent / str(transcript.get("path") or "transcript.md")
    title = f"New transcript ready: {podcast_title} - {episode_title}"
    lines = [
        "A new transcript is ready for OnReason critique work.",
        "",
        f"- Podcast: {podcast_title}",
        f"- Episode: {episode_title}",
        f"- Release date: {current.get('pub_date') or 'Unknown'}",
        f"- Transcript status: `{transcript.get('status')}`",
        f"- ASR model: `{transcript.get('asr_model') or 'not applicable'}`",
        f"- Official episode URL: {current.get('podcast_page_url') or 'not recorded'}",
        f"- Transcript path: {link_for_path(repo_url, transcript_path)}",
        f"- Metadata path: {link_for_path(repo_url, metadata_path)}",
    ]
    if run_url:
        lines.append(f"- Workflow run: {run_url}")
    lines.extend(
        [
            "",
            "Next action:",
            "- [ ] Create or update the OnReason critique page for this episode.",
        ]
    )
    return {
        "title": title,
        "body": "\n".join(lines) + "\n",
        "metadata_path": metadata_path.as_posix(),
        "transcript_path": transcript_path.as_posix(),
        "podcast": podcast,
        "episode_title": episode_title,
        "transcript_status": transcript.get("status"),
    }


def collect_ready_transcript_notices(
    *,
    corpus_dir: Path,
    repo_url: str | None = None,
    run_url: str | None = None,
    metadata_paths: list[Path] | None = None,
) -> list[dict[str, Any]]:
    paths = metadata_paths if metadata_paths is not None else git_changed_metadata_paths(corpus_dir)
    notices = []
    for path in paths:
        if not path.exists() or path.name != "metadata.json":
            continue
        current = read_json(path)
        previous = git_head_json(path)
        notice = notice_from_metadata(
            metadata_path=path,
            current=current,
            previous=previous,
            repo_url=repo_url,
            run_url=run_url,
        )
        if notice:
            notices.append(notice)
    return notices


def write_notice_files(notices: list[dict[str, Any]], out_path: Path, body_dir: Path) -> None:
    body_dir.mkdir(parents=True, exist_ok=True)
    serializable = []
    for index, notice in enumerate(notices, start=1):
        body_path = body_dir / f"transcript-ready-{index}.md"
        body_path.write_text(notice["body"], encoding="utf-8")
        serializable.append({**notice, "body_file": str(body_path)})
    write_json(out_path, serializable)


def issue_exists(title: str) -> bool:
    result = subprocess.run(
        ["gh", "issue", "list", "--state", "all", "--search", title, "--json", "title"],
        check=True,
        capture_output=True,
        text=True,
    )
    issues = json.loads(result.stdout or "[]")
    return any(issue.get("title") == title for issue in issues)


def create_github_issues(notices_path: Path) -> int:
    notices = json.loads(notices_path.read_text(encoding="utf-8")) if notices_path.exists() else []
    created = 0
    for notice in notices:
        title = notice["title"]
        if issue_exists(title):
            print(f"Transcript-ready issue already exists: {title}", flush=True)
            continue
        subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body-file", notice["body_file"]],
            check=True,
        )
        created += 1
    print(f"Created {created} transcript-ready issue(s).", flush=True)
    return created


def github_repo_url_from_env() -> str | None:
    server = os.getenv("GITHUB_SERVER_URL")
    repository = os.getenv("GITHUB_REPOSITORY")
    if not server or not repository:
        return None
    return f"{server}/{repository}"


def github_run_url_from_env() -> str | None:
    repo_url = github_repo_url_from_env()
    run_id = os.getenv("GITHUB_RUN_ID")
    if not repo_url or not run_id:
        return None
    return f"{repo_url}/actions/runs/{run_id}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect and publish transcript-ready notices.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect-ready-transcripts")
    collect.add_argument("--corpus-dir", type=Path, default=Path("corpus"))
    collect.add_argument("--out", type=Path, required=True)
    collect.add_argument("--body-dir", type=Path, required=True)
    collect.add_argument("--repo-url", default=github_repo_url_from_env())
    collect.add_argument("--run-url", default=github_run_url_from_env())

    create = subparsers.add_parser("create-issues")
    create.add_argument("--notices", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "collect-ready-transcripts":
        notices = collect_ready_transcript_notices(
            corpus_dir=args.corpus_dir,
            repo_url=args.repo_url,
            run_url=args.run_url,
        )
        write_notice_files(notices, args.out, args.body_dir)
        print(f"Collected {len(notices)} transcript-ready notice(s).", flush=True)
        return 0
    if args.command == "create-issues":
        create_github_issues(args.notices)
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
