# Automatic assessment announcements through Buffer

The critique workflow publishes one standalone X announcement through Buffer for
each new assessment. It uses the assessment title, up to two claim topics, and
its canonical OnReason link. No X developer account or direct X API credentials
are needed, and no additional AI request is made.

## Connect the account

1. Create a [free Buffer account](https://buffer.com/pricing) and verify its email.
2. In Buffer, connect the intended regular X account and authorize Buffer to
   publish. Confirm the displayed account name before granting access.
3. In [Buffer Settings → API](https://publish.buffer.com/settings/api), create an
   automation key with account-reading, post-reading, and post-writing access.
   Keep the key private. Store it in this repository's
   [Actions secrets](https://github.com/philstilwell/str/settings/secrets/actions)
   as `BUFFER_API_KEY`; never put it in a file committed to GitHub or in chat.
4. Set these [Actions variables](https://github.com/philstilwell/str/settings/variables/actions):
   - `BUFFER_CHANNEL_ID`: the Buffer channel ID for the connected X account.
   - `X_USERNAME`: the intended X account name without `@`.
   - `BUFFER_POSTING_ENABLED`: `true` after the connection has been verified.

The job checks that the selected channel is X, matches the expected account,
and is connected, unlocked, and not paused. It then requests immediate automatic
publication through Buffer's `shareNow` mode. It does not require a browser to
stay signed in or a Mac to remain awake. Set `BUFFER_POSTING_ENABLED` to `false`
to pause announcements while assessment generation continues.

The initial history excludes the 142 assessments already present when this
feature was installed. Later assessments remain queued while posting is disabled;
review that queue before activation if setup has been delayed. The original X
API credential path has been removed.

## Cost estimate

As checked October 5, 2026, [Buffer's free plan](https://buffer.com/pricing)
includes up to three channels, ten scheduled posts per channel at a time
(refilled after publication), and 3,000 API requests per month. The expected
additional cost for this workflow is **$0 within those limits**. Account checks,
creation, and delivery checks use Buffer's allowance. There are no direct paid X
API calls. Existing assessment-generation costs are separate. No paid plan,
payment method, or trial is required.

## Preview without posting

From the repository directory:

```bash
python -m str_workflow.x_posts preview \
  docs/episodes/2026-07-15-we-have-an-obligation-to-help-the-poor/index.html
```

Preview does not change history or contact Buffer. `enqueue` saves announcements
for newly added pages without contacting Buffer. Tests use simulated responses
and do not create public test posts. Live `publish` runs in the serialized GitHub
workflow on `main`.

## Publication and recovery

`outreach/x-posts.json` preserves the exact text, account, Buffer post ID,
publication status, and public X permalink. The older manual outreach records
and Google Sheet remain separate. Never delete completed entries or the baseline
to retry a run.

Before asking Buffer to publish, the job pushes a `sending` claim to GitHub.
Buffer acceptance becomes `submitted`; only a confirmed `sent` result with a
public X link becomes `posted`. The job saves and pushes both stages. Subsequent
runs check existing Buffer post IDs instead of creating duplicate posts.

- `pending`: awaiting publication of the assessment or an explicitly rejected
  request. A later normal run retries it.
- `sending` or `uncertain`: an interruption, timeout, or ambiguous response
  needs inspection in Buffer and X. Automatic resubmission is blocked.
- `submitted`: Buffer accepted the post. The job checks delivery for about
  25 seconds and resumes checking on a later run if delivery is still pending.
- `failed`: Buffer reports an error, draft, or approval requirement. Inspect and
  resolve the existing Buffer post; the workflow does not create another copy.
- `posted`: confirmed published, with its X permalink. Later runs skip it.

A failed announcement never rolls back an assessment or repeats paid critique
generation. History recovery artifacts are kept for 90 days. The job also
requests a GitHub Pages build after assessment commits and while publication is
pending, then checks the public assessment title, canonical URL, and content
before sending a new announcement.

To resolve an uncertain attempt, inspect Buffer and X first. If the post exists,
record its `buffer_post_id` and `buffer_channel_id`, then set the entry to
`submitted` so the job can verify it. If publication on X is already confirmed,
record `posted_url` as `https://x.com/i/web/status/POST_ID` and set it to `posted`.
Append a timestamped history note explaining the verification. Only after
confirming that neither a Buffer post nor an X post exists may it be returned to
`pending`. Commit and push the correction before the next run.

For a `failed` post resolved inside Buffer, return the same entry to `submitted`
with its existing Buffer ID and a history note. Do not create a new post merely
because delivery was delayed. If the account is renamed, update `X_USERNAME`.
Changing accounts requires reviewing entries already tied to the previous X
account ID and Buffer channel.
