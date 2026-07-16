# OnReason Podcast Transcript Workflow

This repository monitors apologetics podcast feeds and builds local corpora of episode metadata and transcripts for OnReason critique work.

The current durable sources are:

- Stand to Reason Weekly Podcast: `https://feed.podbean.com/strweekly/feed.xml`
- Frank Turek's "I Don't Have Enough FAITH to Be an ATHEIST": `https://crossexamined.org/category/podcast/feed/`

The initial workflow:

1. Polls the RSS feed on a schedule or by manual dispatch.
2. Detects new episode GUIDs per podcast corpus.
3. Stores episode metadata under `corpus/podcasts/<podcast-id>/episodes/`.
4. Checks for official transcript hints in RSS and on the linked episode page.
5. Discovers embedded audio players when the RSS feed links to a show-note page without an MP3 enclosure.
6. If no official transcript is found, transcribes the MP3 when an ASR provider is configured.
7. Commits new metadata/transcripts back to `main`.
8. Opens a GitHub issue when a transcript newly becomes ready for critique.
9. Starts a second workflow after successful ingestion to create, validate, and publish critiques for every ready transcript that does not yet have one, with a daily recovery sweep as backup.

Raw audio is downloaded only into temporary workspace storage during a run and is intentionally ignored by git.

Podcast assets stay separated under `corpus/podcasts/<podcast-id>/`; do not mix episode metadata,
transcripts, or generated ASR artifacts across podcast directories.

## Enable Transcription

The GitHub Action can transcribe with OpenAI's audio transcription API when the repository has an `OPENAI_API_KEY` secret. The default model is `gpt-4o-mini-transcribe`, and the workflow splits large MP3s into upload-sized chunks before transcription.

Required secret:

`OPENAI_API_KEY`

Optional workflow environment variables:

`ASR_MODEL`: transcription model. Defaults to `gpt-4o-mini-transcribe`.

`MAX_EPISODES_PER_RUN`: cap on newly discovered episodes handled per scheduled run. Defaults to `2`.

`TRANSCRIBE`: `auto`, `always`, or `never`. The scheduled GitHub Action defaults to `always`, so a missing `OPENAI_API_KEY` secret fails the run visibly instead of leaving new episodes at `pending_asr`. Manual local runs may still use `auto` when you want transcription only if credentials are available.

## Transcript-Ready Notices

The scheduled ingest workflow creates a GitHub issue whenever an episode transcript newly reaches a ready status:

- `found_official`
- `generated_asr`

Each issue includes the podcast, episode title, release date, transcript status, ASR model when applicable, official episode URL, transcript path, metadata path, workflow run, and a checklist item to create or update the OnReason critique page. The workflow compares changed metadata against `HEAD`, so reruns do not create a duplicate notice for transcripts that were already ready.

## Scheduled Critique Generation

`.github/workflows/critiques.yml` starts when the `Ingest podcast episodes` workflow completes successfully, so critique generation follows the actual availability of committed transcripts instead of assuming ingestion finishes within a fixed window. A daily `16:15 UTC` schedule remains as an idempotent recovery sweep, and manual dispatch remains available. Each run finds every episode whose transcript status is `found_official` or `generated_asr` and whose `docs/episodes/<slug>/index.html` page is missing.

For each missing page, the workflow uses structured model output to create five transcript-grounded critique sections plus a two-part overall assessment: a dark epistemic-reality rebuke and a dark red challenge section aimed at the weakest points in the transcript. It verifies direct quotes against the stored transcript, resolves research anchors only from `research/source-index.json`, retries drafts that fail a quality check, renders the page atomically, refreshes adjacent-episode navigation and the five most recent homepage cards, rebuilds SEO discovery files, runs the full test suite, and commits only validated `docs/` changes.

The workflow reuses the existing `OPENAI_API_KEY` secret. `CRITIQUE_MODEL` is optional and defaults to `gpt-5.5`; `CRITIQUE_REASONING_EFFORT` defaults to `high` in the batch command. A manual dispatch can override the model or limit the number of episodes, while the scheduled run processes all missing critiques.

To inspect the queue without making an API call:

```bash
python -m str_workflow.critique_batch --dry-run
```

## Local Use

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m str_workflow.ingest --max-new 1 --transcribe never

python -m str_workflow.ingest \
  --feed-url https://crossexamined.org/category/podcast/feed/ \
  --out-dir corpus/podcasts/idont-have-enough-faith \
  --podcast-id idont-have-enough-faith \
  --podcast-title "I Don't Have Enough FAITH to Be an ATHEIST" \
  --podcast-home-url https://crossexamined.org/podcasts/ \
  --max-new 1 \
  --transcribe never
```

To run local ASR, export `OPENAI_API_KEY` and use `--transcribe auto` or `--transcribe always`.

## Corpus Layout

```text
corpus/
  podcasts/
    stand-to-reason/
      episodes.json
      episodes/
        YYYY-MM-DD-episode-slug/
          metadata.json
          transcript.md
          transcript.json
    idont-have-enough-faith/
      episodes.json
      episodes/
        YYYY-MM-DD-episode-slug/
          metadata.json
          transcript.md
          transcript.json
```

`metadata.json` records the RSS GUID, title, publication date, MP3 URL, linked episode page, transcript status, and ASR provenance.

`transcript.json` stores chunk-level timestamps and model metadata. `transcript.md` is the human-readable version.

## Critique Production Workflow

OnReason critique pages are generated from a structured critique spec rather than assembled ad hoc. The hardened path is:

1. Ingest the episode metadata/transcript:

   ```bash
   python -m str_workflow.ingest --max-new 1 --transcribe auto
   ```

2. Refresh the compact research map when Free of Faith or local framework sources have changed:

   ```bash
   python3 tools/build_source_index.py
   ```

3. Scaffold a local critique draft from the transcript and source index:

   ```bash
   python -m str_workflow.critique scaffold \
     --episode-dir corpus/podcasts/stand-to-reason/episodes/YYYY-MM-DD-episode-slug
   ```

   This writes a local draft packet under `output/critique-drafts/`. The `output/` directory is ignored so transcript-derived working files do not become public by accident.

4. Fill every `TODO` in `critique-draft.json`. Each substantive section must include:

   - short transcript quotes with timestamp ranges when possible;
   - an `episode_nav` block whose `previous` link points to the older adjacent critique and whose `next` link points to the newer adjacent critique, using `null` only at the oldest/newest endpoints;
   - Free of Faith / local framework research anchors, including relevant Insights, Considerations, and Featured posts;
   - compact research-map anchor pills separated by plain spaces, with no semicolon punctuation between links;
   - an expanded `◉` explanation;
   - a claim/evidence/critique audit table;
   - natural LaTeX formalization;
   - LogFall and CogBias diagnostic cards that explain how the tag applies to specific transcript claims;
   - evidence-needed calibration tests customized to each section's claim, with distinct criteria for what would raise or lower confidence;
   - a dark red "The challenge" section below "The epistemic reality" that polemically targets the weakest transcript-specific claims;
   - a steelmanned AI prompt whose claims are actually grounded in the transcript.
   - numbered substantive section kickers rendered as dark container-wide bars with light text, while non-numbered framework kickers keep the standard green text treatment.
   - no deprecated top-level quote-strip / quote-chip summary card section; transcript quotes belong inside the relevant substantive critique sections.
   - no reused boilerplate repair paragraphs, source notes, tag explanations, formalizations, overall assessments, or calibration-table prose; the validator rejects known stale phrases and repeated explanatory text.

5. Validate the spec before rendering:

   ```bash
   python -m str_workflow.critique validate \
     --spec output/critique-drafts/YYYY-MM-DD-episode-slug/critique-draft.json
   ```

6. Render the public page:

   ```bash
   python -m str_workflow.critique render \
     --spec output/critique-drafts/YYYY-MM-DD-episode-slug/critique-draft.json \
     --out docs/episodes/YYYY-MM-DD-episode-slug/index.html
   ```

7. Validate the rendered page:

   ```bash
   python -m str_workflow.critique validate-page \
     --page docs/episodes/YYYY-MM-DD-episode-slug/index.html
   ```

8. Run the full test suite:

   ```bash
   pytest
   ```

The public page should cite only short excerpts and link back to official STR episode pages. Full transcripts remain local/private unless there is a separate decision to publish them.

Research-map anchor styling is part of the production contract: rendered Free of Faith anchors use compact pill links in the source-map table, and the renderer/validator reject semicolon-separated link markup such as `</a>;`.

## Outreach Post Log

Published-critique notices are tracked in [`outreach/`](outreach/README.md). The canonical records preserve the complete Contents list, compact claim topics for character-limited platforms, exact notice text, destination, approval/posting state, public permalink, and append-only visibility history. Markdown and CSV indexes are regenerated after every logged change.

When `outreach/google-sheets.json` is present, outreach mutations and rebuilds also upsert
the workflow-owned notice columns into the configured Google Sheet while preserving the
manual posting fields.

Initialize the log entry for a newly rendered critique with:

```bash
python3 -m str_workflow.outreach --outreach-dir outreach init \
  docs/episodes/YYYY-MM-DD-episode-slug/index.html
```

See the outreach README for the draft, approval, posting, verification, duplicate-protection, and validation commands.

## Quality Gates

The `Validate OnReason workflow` GitHub Action runs the Python tests on push and pull request. The tests check RSS ingest helpers, critique spec validation, HTML generation, and the current public page's required features.

Critique depth is a production contract, not a copy-editing preference. The validator rejects draft specs or rendered pages that omit the five-card method framework (`Calibration`, `Symmetry`, `Architecture`, `Alternatives`, and `Bounded Agency`), section-level Free of Faith anchors, underdeveloped `◉` explanations, shallow research notes, one-row audit tables, thin tag applications, under-explained formalizations, short evidence-calibration tests, underdeveloped epistemic-reality rebukes, missing dark red challenge sections, repeated boilerplate, label-like AI steelman claims, deprecated quote-strip summary cards, public links to the private OnReason source index, or lowercase proper names inherited from ASR/transcript text.

The standing epistemic stance is that faith is epistemically inadequate when it is invoked to license confidence that exceeds, bypasses, or resists the degree of relevant evidence. Biblical faith-language can instead express trust, reliance, or loyalty and must not be treated as an evidential category merely because it uses the word “faith.” Critiques should steelman faith claims charitably, but they should not treat faith-based overconfidence as an epistemic virtue.
