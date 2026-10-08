# Phase 3 Render Coverage

This matrix records the renderer behavior implemented in Phase 3. Canonical nodes remain the source of truth when the node can be aligned to a rendered component; compatibility text is retained as an explicit fallback.

| Content | PPTX | PDF | Fallback and diagnostics |
| --- | --- | --- | --- |
| Plain text | DrawingML text runs | Unicode-readable text | Component alignment fallback reports `TEXT_LAYOUT_DEGRADED` |
| Formatting | Bold, italic, underline on DrawingML runs | Readable text | Formatting not represented by the PDF path |
| Subscript and superscript | DrawingML baseline positioning | Unicode script glyphs | Compatibility text retained; degraded alignment is traced |
| Line breaks | Native DrawingML line breaks | Text line breaks | Unsupported nodes report `RENDER_NODE_UNSUPPORTED` |
| Math sequences / OMML | Source OMML where valid; normalized or generated OMML where conversion succeeds; native `a14:m` plus readable `mc:Fallback` | Readable Unicode form | `MATH_FALLBACK_USED` or `MATH_RENDER_FAILED` |
| Images | Image when resolvable; visible placeholder otherwise | Image when resolvable; visible placeholder otherwise | `MEDIA_RENDER_FAILED` includes question and source context |
| Tables | Native PPTX table, rich cell nodes, content-sized rows | Readable row and cell text | Cell mismatch reports `TEXT_LAYOUT_DEGRADED`; legacy renderer reports `RENDER_NODE_UNSUPPORTED` |
| Unknown or invalid nodes | Readable value when present | Readable value when present | `RENDER_NODE_UNSUPPORTED` or `INVALID_CANONICAL_NODE` |

Render diagnostics carry `code`, `severity`, `question_id`, `component_id`, `source_block_id`, `node_id`, `reason`, `fallback`, and `slide_ids`; unavailable identity fields are null. PPTX render status/counts and question render metadata persist into JSON. PDF status/counts persist under `diagnostics.pdf_render`, with per-question `render.pdf` metadata.

## Verification

- Full repository suite: **84 passed**.
- Golden test3: 73 rendered questions, 74 PPTX slides, 8 PDF pages, no leaked raw math markers.
- Golden test3 diagnostics: 28 `TEXT_LAYOUT_DEGRADED`, 1 `MATH_FALLBACK_USED`; overall PPTX status is `degraded`.
- Golden test3 has 154 native math AlternateContent entries. The Phase 2 snapshot had 160, including ordinary `II` option labels incorrectly marked as math. Invalid math fragments now use a readable fallback.
- Visual fixture coverage: math, chemistry, vector notation, valid image, fraction and scripted table cells, long option, and multiline stem. The PowerPoint-generated PDF was visually inspected; the Artifact Tool preview does not paint the `a14:m` Choice content.

Known limitation: the 28 golden-run source-to-component alignments that use compatibility text are traceable in diagnostics but still need alignment recovery work. Test3 has no source tables, so rich table layout is covered by generated DOCX and JSON fixtures.
