# Research Source Index

`source-index.json` is a compact source map for OnReason critique drafting. It contains metadata, short excerpts, relevance tags, and reflection summaries, not full mirrors of Free of Faith articles or local PDFs.

Rebuild it from the repository root:

```sh
python3 tools/build_source_index.py
```

Current inputs:

- Public Free of Faith `Insights`, `Considerations`, and `Featured` archives.
- Local reflection summaries from Phil Stilwell academic and audit-framework files.

Use the index to map transcript claims to source IDs before drafting a critique. The public page should then surface the most relevant anchors directly, so readers can see which Free of Faith articles and local frameworks shaped the argument.
