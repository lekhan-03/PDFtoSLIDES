# Phase 3A Renderer Regression Fixes

Date: 2026-10-07  
Scope: PPTX rendering, canonical-node alignment, math fallbacks, and renderer diagnostics. Parser and extraction behavior were not changed in this phase.

## Changes

- Math conversion now tokenizes component text and converts one delimited math expression at a time. Each `mc:Fallback` receives the readable text for that expression only; surrounding text is emitted as ordinary DrawingML runs.
- Canonical inline rendering remains exclusive: when canonical nodes align, the renderer emits those nodes and returns without appending the compatibility component text. Compatibility text is used only when canonical alignment fails.
- Span matching normalizes superscript/subscript glyphs, LaTeX script notation, and spacing around operators while preserving offsets into the canonical node stream. Option matching prefers the corresponding component source and option label.
- Option diagnostics use the option source relationship when available. Unknown source IDs remain null; mixed numeric/string source IDs are normalized to strings at the renderer diagnostic boundary.
- Invalid math is rejected before conversion. Readable fallbacks remove empty script fragments, and fallback diagnostics retain both the original fragment and the emitted readable value.
- Isolated operators in canonical text no longer trigger automatic math conversion.
- Render summaries include canonical math-node, native math-entry, fallback-entry, failed-node, and reconciliation counts.

## Run 2 Fixture Results

The existing `data/tests/testing_file.json` was copied to a temporary path and rendered. Its parsed question content was byte-for-value unchanged after removing renderer metadata.

| Metric | Run 2 baseline | Phase 3A result |
| --- | ---: | ---: |
| Questions / accepted / review / rejected | 33 / 32 / 1 / 0 | 33 / 32 / 1 / 0 |
| Question content differences | 0 | 0 |
| Slides including title | — | 34 |
| `TEXT_LAYOUT_DEGRADED` | 58 in report (64 total diagnostics) | 2 |
| Fallbacks longer than 60 characters | 37 | 0 |
| Native math entries | 118 | 77 |
| Canonical math nodes | unchanged canonical JSON | 77 renderable top-level nodes |
| Fallback entries | — | 77 |
| Math fallback / render failures | 6 in report | 0 |
| Incorrect option source diagnostics | 47 in report | 0 option diagnostics; all emitted diagnostics have source IDs |
| Raw math markers | 0 | 0 |

The current deck has 77 native entries and 77 fallbacks, matching the 77 top-level canonical `math_sequence` nodes. The prior 118-entry count is not used as the target; the node-to-output reconciliation is the target. The two remaining layout warnings concern components where the canonical text includes embedded option/image structure and does not align to the rendered stem text. They are retained as warnings with source and node IDs.

Every emitted `mc:AlternateContent` has a `Choice` containing native `a14:m` and one non-empty `Fallback`. No fallback exceeded 60 characters, and no raw converter markers appeared in fallback text. Repeated short fallback values on one slide correspond to distinct canonical nodes that share the same expression; the XML-level tests verify each entry is independently local to its math node.

Fallback-path visual QA used a disposable copy of the deck with each Choice's `Requires` set to an unsupported namespace, leaving the fallback branch intact and valid. PowerPoint exported the 34-slide copy to PDF. Representative math/options slides were inspected, including Q16: its four fractions displayed once as readable numerator/denominator text, with no duplicated `AB` or variable fragments. Native-math XML on the production deck was separately verified.

The Q16 fixture exposes an upstream component-shape mismatch: `question.options` is empty, but the question string contains options A–D while the canonical source ledger marks their source blocks as options. Phase 3A leaves that parser output unchanged, renders the compatibility text once, and records one traceable `TEXT_LAYOUT_DEGRADED` warning. A fixture-specific regression preserves this finding until the parser contract is corrected in a separate phase.

## Tests

New focused tests cover fallback isolation, script-aware alignment, single emission of superscript nodes, option source traceability, malformed fallback output, isolated operators, canonical/native/fallback count reconciliation, and the Q16 upstream component mismatch. The full suite result is recorded in the implementation audit after the final run.

Final verification: **94 tests passed**; `git diff --check` reported no whitespace errors.
