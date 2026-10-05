import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from str_workflow import x_posts as x


PAGE = Path("docs/episodes/2026-07-15-we-have-an-obligation-to-help-the-poor/index.html")


def state_with_post():
    critique = x.extract_critique(PAGE)
    return {
        "schema_version": 1, "baseline_slugs": [],
        "posts": {critique["slug"]: {
            "url": critique["url"], "title": critique["episode_title"],
            "text": x.compose_post(critique), "status": "pending", "history": [],
        }},
    }


class Session:
    def __init__(self, response=None, username="example", before_post=None):
        self.response = response if response is not None else reply(201, {"data": {"id": "123456"}})
        self.username = username
        self.before_post = before_post
        self.posts = []
        self.gets = []

    def get(self, url, **kwargs):
        self.gets.append(url)
        return reply(200, {"data": {"id": "789", "username": self.username}})

    def post(self, url, **kwargs):
        if self.before_post:
            self.before_post()
        self.posts.append((url, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def reply(status, data):
    return SimpleNamespace(status_code=status, json=lambda: data)


def send(state, session, checkpoint=lambda: None, page_ready=lambda _: True):
    return x.publish(
        state, session=session, expected_username="example", checkpoint=checkpoint,
        page_ready=page_ready,
    )


def test_success_is_claimed_before_sending_and_never_reposted_after_reload(tmp_path):
    state = state_with_post()
    path = tmp_path / "state.json"
    snapshots = []

    def checkpoint():
        x.save_state(path, state)
        snapshots.append(x.read_state(path))

    def before_post():
        assert next(iter(x.read_state(path)["posts"].values()))["status"] == "sending"

    session = Session(before_post=before_post)
    assert send(state, session, checkpoint) == 1
    assert [next(iter(item["posts"].values()))["status"] for item in snapshots] == ["sending", "posted"]
    assert send(x.read_state(path), session, checkpoint) == 0
    assert len(session.posts) == 1
    assert len(session.gets) == 1
    assert session.posts[0][0] == "https://api.x.com/2/tweets"
    assert session.posts[0][1]["allow_redirects"] is False


def test_failed_durable_claim_never_contacts_post_endpoint():
    state = state_with_post()
    session = Session()

    def failed_checkpoint():
        raise OSError("Cannot push state")

    with pytest.raises(OSError):
        send(state, session, failed_checkpoint)
    assert session.posts == []


@pytest.mark.parametrize("response", [
    requests.Timeout("connection dropped"),
    reply(500, {}), reply(201, {}), reply(201, {"data": None}),
    reply(302, {}), reply(400, {}),
])
def test_ambiguous_result_is_held_and_not_retried(response):
    state = state_with_post()
    saved = []
    session = Session(response)
    with pytest.raises(x.PostingError, match="uncertain"):
        send(state, session, lambda: saved.append(copy.deepcopy(state)))
    assert next(iter(saved[-1]["posts"].values()))["status"] == "uncertain"
    with pytest.raises(x.PostingError, match="Inspect uncertain"):
        send(state, session)
    assert len(session.posts) == 1


def test_success_followed_by_failed_receipt_push_is_held_on_next_run():
    state = state_with_post()
    durable = []

    def checkpoint():
        if durable:
            raise OSError("Receipt push failed")
        durable.append(copy.deepcopy(state))

    session = Session()
    with pytest.raises(OSError):
        send(state, session, checkpoint)
    with pytest.raises(x.PostingError, match="Inspect uncertain"):
        send(durable[0], session)
    assert len(session.posts) == 1


@pytest.mark.parametrize("code", [401, 402, 403, 429])
def test_explicit_rejection_is_retained_for_later_run(code):
    state = state_with_post()
    session = Session(reply(code, {}))
    with pytest.raises(x.PostingError, match="retained for a later run"):
        send(state, session)
    assert next(iter(state["posts"].values()))["status"] == "pending"
    session.response = reply(201, {"data": {"id": "54321"}})
    assert send(state, session) == 1


def test_unpublished_page_never_calls_x_and_stays_pending():
    state = state_with_post()
    session = Session()
    with pytest.raises(x.PostingError, match="not live yet"):
        send(state, session, page_ready=lambda _: False)
    assert session.posts == session.gets == []
    assert next(iter(state["posts"].values()))["status"] == "pending"


def test_wrong_account_cannot_publish():
    session = Session(username="wrong_account")
    with pytest.raises(x.PostingError, match="do not match"):
        send(state_with_post(), session)
    assert session.posts == []


def test_live_page_requires_correct_canonical_title_and_assessment():
    post = next(iter(state_with_post()["posts"].values()))
    html = PAGE.read_text()

    def check(body, status=200):
        return x.live_page_matches(post, lambda *a, **k: SimpleNamespace(status_code=status, text=body))

    assert check(html)
    assert not check(html, 404)
    assert not check(html, 302)
    assert not check(html.replace(post["url"], "https://onreason.com/"))
    assert not check(html.replace(post["title"], "Wrong episode"))
    assert not check("<h1>Not found</h1>")


def test_queue_ignores_baseline_and_existing_posts_and_retains_original_text(tmp_path):
    page = tmp_path / PAGE.parent.name / "index.html"
    page.parent.mkdir()
    page.write_text(PAGE.read_text())
    state = {"schema_version": 1, "baseline_slugs": [PAGE.parent.name], "posts": {}}
    assert x.enqueue(state, tmp_path) == 0
    state["baseline_slugs"] = []
    assert x.enqueue(state, tmp_path) == 1
    before = copy.deepcopy(state)
    page.write_text("changed after queueing")
    assert x.enqueue(state, tmp_path) == 0
    assert state == before


def test_every_existing_assessment_can_produce_a_valid_topic_specific_post():
    for page in Path("docs/episodes").glob("*/index.html"):
        critique = x.extract_critique(page)
        post = {
            "url": critique["url"], "title": critique["episode_title"],
            "text": x.compose_post(critique), "status": "pending",
        }
        x.validate_post(page.parent.name, post)
        assert "Topics: " in post["text"]
        assert post["text"].endswith(critique["url"])


def test_long_unicode_title_and_topics_fit_without_cutting_off_link():
    critique = x.extract_critique(PAGE)
    critique["episode_title"] = "漢字😀é " * 150
    critique["compact_topics"] = ["🧑‍🔬 Causality " * 100, "Second topic"]
    post = {"url": critique["url"], "title": critique["episode_title"], "text": x.compose_post(critique), "status": "pending"}
    x.validate_post(critique["slug"], post)


def test_corrupt_or_missing_history_never_becomes_an_empty_queue(tmp_path):
    path = tmp_path / "state.json"
    with pytest.raises(FileNotFoundError):
        x.read_state(path)
    path.write_text('{}')
    with pytest.raises(x.PostingError):
        x.read_state(path)


def test_disabled_posting_does_not_load_credentials_or_contact_x(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    x.save_state(path, state_with_post())
    monkeypatch.delenv("X_POSTING_ENABLED", raising=False)
    monkeypatch.setattr("sys.argv", ["x_posts", "--state", str(path), "publish"])
    monkeypatch.setattr(x, "x_session", lambda: pytest.fail("Contacted X while disabled"))
    assert x.main() == 0


def test_live_posting_outside_workflow_stops_before_loading_credentials(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    x.save_state(path, state_with_post())
    monkeypatch.setenv("X_POSTING_ENABLED", "true")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr("sys.argv", ["x_posts", "--state", str(path), "publish"])
    monkeypatch.setattr(x, "x_session", lambda: pytest.fail("Loaded credentials outside workflow"))
    assert x.main() == 1


def test_workflow_queues_before_commit_and_preserves_posting_recovery():
    workflow = Path(".github/workflows/critiques.yml").read_text()
    assert workflow.index("run: pytest") < workflow.index("x_posts enqueue") < workflow.index("git add docs outreach/x-posts.json")
    assert "pages/builds" in workflow
    assert "needs: critique" in workflow
    assert "group: critique-generation" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "x_posts publish" in workflow
    assert "x-announcement-history-" in workflow
