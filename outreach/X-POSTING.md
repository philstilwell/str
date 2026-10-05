# Automatic assessment announcements on X

The critique workflow posts one standalone announcement on the connected account
for each new assessment. It uses the assessment's title, up to two claim topics,
and its `https://onreason.com/episodes/.../` link. No additional AI request is
needed. Announcements fit the standard 280-character limit, allowing for X's
23-character treatment of links and conservatively counting Unicode characters.

## Connect the account

1. In the [X Developer Console](https://developer.x.com/), create or select your
   app, enable OAuth 1.0a user authentication, and give the app **Read and Write**
   access. Generate the access token and its secret for the account that will
   publish. Regenerate the user tokens if permissions were changed after their
   creation. An app-only bearer token cannot replace these user credentials.
2. In [this repository's Actions secrets](https://github.com/philstilwell/str/settings/secrets/actions),
   add `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, and `X_ACCESS_TOKEN_SECRET`.
   Keep the values in GitHub secrets; never put them in a file, issue, or chat.
3. In [Actions variables](https://github.com/philstilwell/str/settings/variables/actions),
   set `X_USERNAME` to the publishing account's name, without `@`. The job checks
   the authenticated account against this name before sending.
4. Review `outreach/x-posts.json`, add X API credits if needed, then set the
   variable `X_POSTING_ENABLED` to `true` to activate automatic posting. Remove it
   or set it to `false` to pause posting while assessments continue normally.

The next normal assessment/recovery run processes the queue. There is no need to
start another paid critique-generation run just to test credentials. Tests use
simulated responses and do not post on X.

## Cost estimate

As checked on October 5, 2026, [X's published rates](https://docs.x.com/x-api/getting-started/pricing)
are **$0.20 for a post containing a URL** and **$0.01 per returned user record**.
This integration verifies the account once per run that has a live, pending
assessment. For one assessment daily, estimate **$6.30 per 30 days**; for 60
assessments across 30 posting runs, **$12.30**. No X requests are made when the
queue is empty or posting is disabled. These estimates exclude any applicable
taxes, pricing changes, and retries; the existing assessment-generation costs
remain separate. No paid test posts are needed for installation.

## Preview without posting

From the repository directory:

```bash
python -m str_workflow.x_posts preview \
  docs/episodes/2026-07-15-we-have-an-obligation-to-help-the-poor/index.html
```

Preview does not change the queue or contact X. `enqueue` discovers newly added
assessment pages and saves their exact announcement text locally, also without
contacting X. Live `publish` runs in the GitHub workflow on `main`, whose shared
concurrency group prevents overlapping posting jobs.

## History and recovery

`outreach/x-posts.json` is the automatic-posting queue and durable history. The
manual outreach records and Google Sheet synchronization remain separate. The
baseline excludes assessments that predate installation; preserve that list and
all completed entries to avoid duplicate announcements.

Each post is pushed to GitHub as `sending` **before** the request to X. A confirmed
response becomes `posted`, with its exact text, X account, public permalink, and
timestamp saved and pushed. Completed entries are skipped on subsequent runs.
Each run also retains a recovery copy of the history as a GitHub Actions artifact
for 90 days. History contains public information only, never credentials.

- A page that is not live remains `pending` for the next run. The job checks for
  roughly five minutes per page and reports delayed publication as a failure.
- Authentication, billing, permission, and rate-limit rejections (401, 402, 403,
  429) retain the item as `pending` and stop that run. Fix the reported cause;
  a later scheduled run tries again.
- Timeouts, server errors, or unrecognized responses become `uncertain`. An
  interrupted run can leave `sending`. Neither state is automatically resent,
  and the job requests inspection before further posting.
- If X accepted a post but saving the receipt failed, use the run's recovery
  artifact and the account's public posts to recover its permalink. The prior
  `sending` claim on GitHub prevents another automatic attempt.

To resolve a held item, inspect the account first. If it exists on X, update the
entry to `posted`, set `posted_url` to `https://x.com/i/web/status/POST_ID`, and
append a history event recording the verification. Only after confirming that
no post exists may you return it to `pending`, with a history note explaining
the check. Commit and push the corrected history before the next run. Do not
delete entries or reset the history to retry a job.

If the account is renamed, update `X_USERNAME`. Changing to a different account
requires reviewing any entries already tied to the old account ID. The workflow
refuses to silently move such attempts to another account.
