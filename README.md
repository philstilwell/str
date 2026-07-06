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

## Planned GitHub Pages Layer

The next layer can publish argument critique pages generated from the corpus without publishing raw copyrighted transcripts. A good split is:

- Keep full transcripts private in `corpus/`.
- Generate public critique artifacts into `site/` or `docs/`.
- Cite short excerpts only where needed and link back to official STR episode pages.
- Add review status fields so critiques can distinguish machine-generated drafts from human-reviewed arguments.

