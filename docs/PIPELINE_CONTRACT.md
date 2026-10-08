# MCQ to Slides — Pipeline Contract

**Project:** MCQ to Slides
**Document:** Pipeline Contract
**Status:** Mandatory Engineering Contract

---

# 1. Purpose

This document defines the invariants that must hold across the MCQ-to-Slides pipeline.

The purpose is to prevent silent data loss and ensure that:

```text
Source
  ↓
Extraction
  ↓
Parsing
  ↓
Validation
  ↓
Fallback
  ↓
JSON
  ↓
Rendering
```

remains traceable and deterministic.

---

# 2. Core Principle

> A question may only disappear if the system explicitly records why it disappeared.

Valid explicit dispositions include:

```text
parsed
repaired
duplicate
noise
excluded
manual_review
invalid_source
failed
```

There must be no implicit:

```text
dropped
ignored
lost
```

state.

---

# 3. Identity Contract

Every source block must have a stable identifier.

Example:

```json
{
  "source_id": "doc_001",
  "block_id": "block_0042",
  "source_order": 42
}
```

Every parsed question must retain its source relationship.

Example:

```json
{
  "question_id": "Q012",
  "source_blocks": [
    "block_0042",
    "block_0043",
    "block_0044"
  ]
}
```

This allows the system to trace:

```text
PPTX slide
→ question
→ JSON object
→ source blocks
→ original document
```

---

# 4. Count Invariant

The pipeline must maintain count information.

At minimum:

```text
source_count
extracted_count
candidate_count
parsed_count
resolved_count
rendered_count
```

The final invariant is:

```text
resolved_count == rendered_count
```

and, unless explicitly accounted for:

```text
source_question_count == resolved_count
```

---

# 5. Exception Accounting

If:

```text
source_question_count != resolved_count
```

the pipeline must produce a reconciliation report.

Example:

```json
{
  "source_question_count": 50,
  "resolved_question_count": 48,
  "missing": [
    {
      "source_blocks": ["block_083"],
      "reason": "unresolved_parser_failure"
    }
  ]
}
```

The pipeline must fail loudly rather than producing a seemingly successful PPTX.

---

# 6. Ordering Contract

Source order must be preserved.

For questions:

```text
Q001
Q002
Q003
...
```

must correspond to source order unless the source explicitly specifies a different ordering.

The following are prohibited as sources of semantic ordering:

* unordered sets
* arbitrary hash iteration
* random sorting
* database result order without explicit sorting

---

# 7. Text Contract

Text must preserve semantic content.

The pipeline must not unintentionally:

* concatenate words
* delete words
* duplicate words
* change operators
* lose punctuation
* remove meaningful line relationships

Whitespace may be normalized, but semantic boundaries must remain intact.

---

# 8. Whitespace Contract

Normalization should produce consistent whitespace.

Examples:

```text
"Find    x"
```

may become:

```text
"Find x"
```

but:

```text
"Find"
"x"
```

must not accidentally become:

```text
"Findx"
```

Subparts must remain separated.

---

# 9. Unicode Contract

Invisible formatting/control characters that are not semantically required must be removed.

Unicode superscript/subscript characters must be normalized consistently.

The pipeline must not mix multiple incompatible representations without an explicit reason.

---

# 10. Formatting Contract

Formatting information that affects meaning must survive extraction.

Required support:

```text
superscript
subscript
bold
italic
underline
```

Example:

```text
10¹⁴
```

must not become:

```text
1014
```

---

# 11. Math Contract

Mathematical expressions are semantic content.

They must never be treated as optional decoration.

The pipeline must preserve:

* operands
* operators
* grouping
* fractions
* powers
* subscripts
* functions
* delimiters
* piecewise rows
* coordinates
* intervals
* adjacent fragments

---

# 12. Formula-Only Content Contract

An option containing only a formula is still a valid option.

Example:

```text
(A) x² + 1
(B) x² - 1
```

must not become:

```json
{
  "options": [
    "",
    ""
  ]
}
```

---

# 13. Fraction Contract

Fractions must preserve numerator and denominator.

Canonical representation should be structurally equivalent to:

```text
\frac{a}{b}
```

rather than relying on ambiguous flattened strings.

---

# 14. Piecewise Contract

A piecewise expression must preserve:

```text
case 1
condition 1

case 2
condition 2

...
```

Flattening all cases into a single text line is considered data corruption.

---

# 15. OMML Contract

OMML structures must be interpreted according to their hierarchy.

For structural nodes, operand lookup must respect direct-child relationships.

Examples:

```text
fraction
  numerator
  denominator

superscript
  base
  exponent

subscript
  base
  subscript
```

Broad descendant queries must not accidentally capture nested operands belonging to another structure.

---

# 16. Math Fragment Contract

Adjacent math fragments representing one expression must be merged when appropriate.

Example conceptual input:

```text
math("x")
math("^2")
math("+1")
```

should become one coherent expression:

```text
x² + 1
```

rather than unrelated expressions.

---

# 17. Parser Boundary Contract

A question consists of all source content belonging to that question.

The parser must support:

```text
multi-line stems
continuation lines
instructions
statements
subparts
options
match lists
mathematical blocks
```

A generic line pattern must not override semantic context.

---

# 18. Question Start Contract

A line is not automatically a new question because it:

* starts with a number-like pattern
* resembles a Roman numeral
* ends with punctuation
* looks like a heading
* resembles a section label

Question-start detection must consider parser state.

---

# 19. Section Contract

Section headers must not steal content from an active question.

Examples such as:

```text
Column I
Column II
II
```

require contextual interpretation.

---

# 20. Option Contract

For standard MCQs, options should normally be represented individually.

Example:

```json
{
  "options": [
    {"label": "A", "content": []},
    {"label": "B", "content": []},
    {"label": "C", "content": []},
    {"label": "D", "content": []}
  ]
}
```

The exact schema may differ, but the semantic distinction must remain.

---

# 21. Question Type Contract

The system must identify question type before applying type-specific validation.

Supported conceptual types:

```text
mcq
statement_mcq
assertion_reason
match
numerical
open_question
unknown
```

---

# 22. Validation Contract

Validation must determine whether a parsed object is safe to render.

Validation must inspect:

```text
structure
content
question type
options
math
metadata
media
source relationships
```

---

# 23. Standard MCQ Contract

A standard MCQ must normally have:

```text
non-empty stem
valid options
stable ordering
valid question identity
```

If the source format intentionally differs, the question type must explain the difference.

---

# 24. Match Question Contract

Match questions must preserve:

```text
left column
right column
row ordering
labels
relationships
```

A match question must not be flattened into unrelated text.

---

# 25. Validation Failure Contract

A validation failure must produce structured diagnostics.

Example:

```json
{
  "valid": false,
  "errors": [
    {
      "code": "MISSING_OPTION",
      "message": "Expected 4 options; found 3"
    }
  ]
}
```

---

# 26. Confidence Contract

Confidence must represent evidence.

It must be possible to explain why confidence is low.

Example:

```json
{
  "confidence": 0.62,
  "needs_review": true,
  "review_reasons": [
    "ambiguous_question_boundary",
    "fallback_used"
  ]
}
```

Hard-coded universal confidence is prohibited.

---

# 27. Fallback Contract

Fallback must only operate on unresolved or invalid content.

Required sequence:

```text
parse
 ↓
validate
 ↓
fallback
 ↓
merge
 ↓
revalidate
```

Fallback output is not trusted until revalidated.

---

# 28. Fallback Context Contract

Fallback must receive sufficient context.

The context may include:

```text
previous block
current block
next block
question marker
options
section information
metadata
math representation
```

The exact context window may vary by parser.

---

# 29. Fallback Merge Contract

When fallback successfully repairs an item:

```text
original failed item
        ↓
repaired item
        ↓
replace/merge
        ↓
remove orphan fragments
        ↓
revalidate
```

The original and repaired item must not both appear as separate questions.

---

# 30. JSON Contract

The JSON output is the semantic contract between parsing and rendering.

It must contain enough information to render the final presentation without re-reading the original document.

At minimum, it must represent:

```text
question identity
question type
stem
options
math
metadata
source relationship
validation state
diagnostics
```

When applicable:

```text
tables
images
charts
statements
subparts
```

---

# 31. Renderer Contract

The renderer consumes canonical JSON.

It must not:

* reparse source text
* reconstruct lost math
* guess question boundaries
* invent options
* invent metadata
* silently skip invalid questions

---

# 32. Render Contract

For every resolved question:

```text
exactly one semantic question representation
```

must reach the renderer.

If one question intentionally requires multiple slides, that relationship must be explicit.

---

# 33. Missing Content Contract

If a question cannot safely be rendered, the renderer must not silently omit it.

Allowed behavior:

```text
review slide
```

or:

```text
pipeline failure
```

depending on configured strictness.

---

# 34. Media Contract

Images and graphs must have explicit representation and relationship.

A question containing an image must not become text-only merely because image extraction failed.

Instead:

```text
needs_review = true
```

with a diagnostic such as:

```text
MISSING_IMAGE
```

---

# 35. Table Contract

Tables must preserve:

```text
rows
columns
cells
order
cell content
math inside cells
```

Table cells must use the same math normalization pipeline as ordinary paragraphs.

---

# 36. Metadata Contract

Metadata must be derived from source information.

Do not hard-code:

```text
subject
exam
board
year
title
```

unless explicitly configured.

---

# 37. Tag Contract

Tags must be:

* parsed consistently
* normalized
* deduplicated where appropriate
* stored deterministically

---

# 38. Diagnostics Contract

Every major stage should be traceable.

Recommended diagnostic structure:

```json
{
  "stage": "parser",
  "question_id": "Q014",
  "source_blocks": [
    "block_120",
    "block_121"
  ],
  "severity": "warning",
  "code": "AMBIGUOUS_BOUNDARY",
  "message": "Potential section header detected inside active question"
}
```

---

# 39. Source Reconciliation Contract

At the end of processing, the system should be able to produce a reconciliation table:

| Source Block | Outcome   | Question | Reason           |
| ------------ | --------- | -------- | ---------------- |
| block_001    | parsed    | Q001     | valid            |
| block_002    | parsed    | Q001     | continuation     |
| block_003    | parsed    | Q002     | valid            |
| block_004    | noise     | —        | promotional text |
| block_005    | repaired  | Q003     | fallback         |
| block_006    | duplicate | Q004     | duplicate source |

No source block should remain unexplained.

---

# 40. Pre-Render Gate

Before PPTX generation, the following checks are mandatory:

```text
[ ] all resolved questions have IDs
[ ] source ordering is valid
[ ] no duplicate question IDs
[ ] no unresolved parsed failures
[ ] validation completed
[ ] fallback items revalidated
[ ] media relationships resolved
[ ] question count reconciled
[ ] renderer input schema valid
```

Failure must stop or explicitly downgrade the pipeline according to configured strictness.

---

# 41. Post-Render Gate

After PPTX generation:

```text
[ ] expected slides exist
[ ] question order is preserved
[ ] no question was dropped
[ ] math exists where expected
[ ] options exist where expected
[ ] images/tables exist where expected
[ ] title metadata is correct
[ ] question numbers are correct
```

Where possible, the generated PPTX should be reopened and inspected structurally.

---

# 42. Regression Contract

Every known bug must have a regression test.

A bug is not considered permanently fixed until:

```text
regression test passes
+
full pipeline passes
```

---

# 43. Golden Fixture Contract

The repository should maintain golden fixtures containing:

```text
source document
expected semantic JSON
expected PPTX
expected diagnostics
```

The PPTX should not normally be compared byte-for-byte.

Instead compare:

```text
slide count
question count
text
math
ordering
metadata
shape semantics
relationships
```

---

# 44. Determinism Contract

Same:

```text
input
configuration
code version
```

must produce the same semantic result.

Minor binary differences in PPTX packaging are acceptable if semantic output is identical.

---

# 45. Strictness Modes

The pipeline should conceptually support:

## Strict

Any unresolved question or invariant failure stops generation.

## Review

Question is retained and rendered with a review indicator.

## Best Effort

Pipeline continues, but every omitted/invalid item must be explicitly reported.

Silent best-effort behavior is prohibited.

---

# 46. Error Handling Contract

Never convert an exception into success.

Bad:

```python
try:
    parse()
except Exception:
    return []
```

Correct conceptual behavior:

```python
try:
    parse()
except Exception as exc:
    record_failure(exc)
    mark_review_or_fail()
```

---

# 47. Contract Between Components

## Extraction guarantees

```text
source order preserved
math preserved
formatting preserved where meaningful
media discovered
source IDs assigned
```

## Parser guarantees

```text
question boundaries established
question types identified
options grouped
source relationships preserved
```

## Validation guarantees

```text
invalid structures identified
diagnostics generated
confidence justified
```

## Fallback guarantees

```text
failed content receives recovery attempt
repaired content is merged
repaired content is revalidated
```

## JSON guarantees

```text
canonical semantic representation
deterministic ordering
complete diagnostics
```

## Renderer guarantees

```text
every resolved question rendered
ordering preserved
math rendered
media rendered
no silent drops
```

---

# 48. Master Invariant

The most important system invariant is:

```text
SOURCE
  ↓
EXTRACTED
  ↓
PARSED
  ↓
VALIDATED
  ↓
RESOLVED
  ↓
RENDERED
```

For every question, there must be a traceable path through every stage.

Conceptually:

```text
source_question_id
        │
        ├── extracted_blocks
        │
        ├── parsed_question
        │
        ├── validation_result
        │
        ├── fallback_result (optional)
        │
        ├── canonical_json
        │
        └── rendered_slide(s)
```

---

# 49. Final Acceptance Criteria

The pipeline is contract-compliant only when:

```text
✓ No silent question loss
✓ No silent option loss
✓ No silent math loss
✓ No unexplained source blocks
✓ Source order preserved
✓ Question identity preserved
✓ Question type preserved
✓ Math structure preserved
✓ Superscript/subscript preserved
✓ Tables preserved
✓ Images accounted for
✓ Fallback output revalidated
✓ Validation is type-aware
✓ Confidence is evidence-based
✓ Metadata is source-derived
✓ Rendering consumes canonical JSON
✓ Pre-render invariants enforced
✓ Post-render QA performed
✓ Regression suite passes
```

---

# 50. Implementation Rule

When a conflict exists between convenience and data preservation:

> Preserve the data and raise a diagnostic.

When a conflict exists between a parser heuristic and explicit source structure:

> Prefer explicit source structure.

When uncertain whether content belongs to a question:

> Preserve the content, mark uncertainty, and require review rather than silently deleting it.
