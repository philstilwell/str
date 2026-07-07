# STR Podcast Transcript Workflow

This repository monitors the Stand to Reason weekly podcast RSS feed and builds a local corpus of episode metadata and transcripts.

The durable source is the Podbean RSS feed:

`https://feed.podbean.com/strweekly/feed.xml`

The initial workflow:

1. Polls the RSS feed on a schedule or by manual dispatch.
2. Detects new episode GUIDs.
3. Stores episode metadata under `corpus/episodes/`.
4. Checks for official transcript hints in RSS and on the linked episode page.
5. If no official transcript is found, transcribes the MP3 when an ASR provider is configured.
6. Commits new metadata/transcripts back to `main`.

Raw audio is downloaded only into temporary workspace storage during a run and is intentionally ignored by git.

## Enable Transcription

The GitHub Action can transcribe with OpenAI's audio transcription API when the repository has an `OPENAI_API_KEY` secret. The default model is `gpt-4o-mini-transcribe`, and the workflow splits large MP3s into upload-sized chunks before transcription.

Required secret:

`OPENAI_API_KEY`

Optional workflow environment variables:

`ASR_MODEL`: transcription model. Defaults to `gpt-4o-mini-transcribe`.

`MAX_EPISODES_PER_RUN`: cap on newly discovered episodes handled per scheduled run. Defaults to `2`.

`TRANSCRIBE`: `auto`, `always`, or `never`. Defaults to `auto`, which transcribes only when credentials are available.

## Local Use

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m str_workflow.ingest --max-new 1 --transcribe never
```

To run local ASR, export `OPENAI_API_KEY` and use `--transcribe auto` or `--transcribe always`.

## Corpus Layout

```text
corpus/
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
     --episode-dir corpus/episodes/YYYY-MM-DD-episode-slug
   ```

   This writes a local draft packet under `output/critique-drafts/`. The `output/` directory is ignored so transcript-derived working files do not become public by accident.

4. Fill every `TODO` in `critique-draft.json`. Each substantive section must include:

   - short transcript quotes with timestamp ranges when possible;
   - an `episode_nav` block whose `previous` link points to the older adjacent critique and whose `next` link points to the newer adjacent critique, using `null` only at the oldest/newest endpoints;
   - Free of Faith / local framework research anchors;
   - compact research-map anchor pills separated by plain spaces, with no semicolon punctuation between links;
   - an expanded `◉` explanation;
   - a claim/evidence/critique audit table;
   - natural LaTeX formalization;
   - LogFall and CogBias diagnostic cards that explain how the tag applies to specific transcript claims;
   - evidence-needed calibration tests customized to each section's claim, with distinct criteria for what would raise or lower confidence;
   - a steelmanned AI prompt whose claims are actually grounded in the transcript.
   - numbered substantive section kickers rendered as dark container-wide bars with light text, while non-numbered framework kickers keep the standard green text treatment.
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

## Quality Gates

The `Validate OnReason workflow` GitHub Action runs the Python tests on push and pull request. The tests check RSS ingest helpers, critique spec validation, HTML generation, and the current public page's required features.

Critique depth is a production contract, not a copy-editing preference. The validator rejects draft specs or rendered pages that omit section-level Free of Faith anchors, underdevelop `◉` explanations, shallow research notes, one-row audit tables, thin tag applications, under-explained formalizations, short evidence-calibration tests, underdeveloped epistemic-reality rebukes, repeated boilerplate, label-like AI steelman claims, public links to the private OnReason source index, or lowercase proper names inherited from ASR/transcript text.
