# Outreach post log

This directory is the durable audit trail for notices posted about published OnReason critiques. One canonical JSON record lives in `posts/` for each critique. `index.md` and `index.csv` are generated views; do not edit them by hand.

The log stores only public outreach information:

- critique identity, podcast, source episode, and canonical URL;
- the complete critique Contents list;
- a compact version of every substantive heading between **Claim map** and **Overall assessment**;
- the exact notice text, platform, target type, and target URL;
- the posting method and public permalink;
- append-only lifecycle events with UTC timestamps, actors, and optional notes.

Never put credentials, cookies, private messages, or other private data in an outreach record.

## Initialize a critique

Run this after the critique page has been rendered. Metadata and Contents are extracted from the page, and both indexes are rebuilt automatically.

```bash
python3 -m str_workflow.outreach --outreach-dir outreach init \
  docs/episodes/YYYY-MM-DD-episode-slug/index.html
```

The command refuses to overwrite an existing record.

## Get the Contents text

Use the full list where the platform has room:

```bash
python3 -m str_workflow.outreach --outreach-dir outreach contents \
  YYYY-MM-DD-episode-slug
```

For character-limited platforms, request the compact variant:

```bash
python3 -m str_workflow.outreach --outreach-dir outreach contents \
  YYYY-MM-DD-episode-slug --compact
```

Only the claim headings are abbreviated. Every heading between **Claim map** and **Overall assessment** remains present.

## Log and post a notice

Save the exact proposed notice in a UTF-8 text file, then add it as a draft:

```bash
python3 -m str_workflow.outreach --outreach-dir outreach add-notice \
  YYYY-MM-DD-episode-slug \
  --platform youtube \
  --target-type episode-video \
  --target-url 'https://www.youtube.com/watch?v=VIDEO_ID' \
  --notice-file notice.txt \
  --method manual \
  --actor phil
```

The command prints the notice ID. Use that ID for subsequent events:

```bash
python3 -m str_workflow.outreach --outreach-dir outreach event \
  YYYY-MM-DD-episode-slug NOTICE_ID approved --actor phil

python3 -m str_workflow.outreach --outreach-dir outreach event \
  YYYY-MM-DD-episode-slug NOTICE_ID posted \
  --posted-url 'https://public.example/comment/permalink' \
  --actor phil

python3 -m str_workflow.outreach --outreach-dir outreach event \
  YYYY-MM-DD-episode-slug NOTICE_ID verified_visible \
  --note '24h visibility check' \
  --actor phil
```

Repeat `verified_visible` with a `7d visibility check` note after seven days. If the result differs, append `visibility_unknown` or `removed`. Failed attempts and intentional omissions use `failed` and `skipped`.

The normal state flow is:

```text
drafted -> approved -> posted -> verified_visible
                  \-> failed
drafted/approved  \-> skipped
posted/verified_visible -> visibility_unknown or removed
```

A `posted` event requires a public permalink. The tool will not post directly; it records the result of an approved manual, browser-assisted, or API action.

## Duplicate protection

The idempotency key combines the critique URL, platform, and normalized target URL. URL fragments and common tracking parameters are ignored. Adding the same critique to the same platform thread twice therefore fails before a second draft can be recorded.

## Validate or rebuild

Every mutation rebuilds the indexes. These commands are also available for review and recovery:

```bash
python3 -m str_workflow.outreach --outreach-dir outreach validate
python3 -m str_workflow.outreach --outreach-dir outreach rebuild
```

JSON timestamps are stored in UTC. `index.md` displays Eastern time, while `index.csv` provides both UTC and Eastern columns. The CSV includes the exact notice text and is suitable for filtering or importing into a spreadsheet.
