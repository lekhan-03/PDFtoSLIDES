# MCQ to Slides — Target Architecture

**Project:** MCQ to Slides
**Document:** Architecture Specification
**Status:** Active Engineering Specification

---

# 1. Objective

The system converts educational documents containing MCQs into structured JSON and presentation slides while preserving semantic and visual information.

The architecture must prioritize:

1. correctness
2. data preservation
3. deterministic behavior
4. debuggability
5. recoverability
6. mathematical fidelity
7. testability

---

# 2. Target Pipeline

```text
                ┌──────────────────────┐
                │ DOCX / PDF / Source  │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ Source Inventory     │
                │ blocks / media /     │
                │ tables / metadata    │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ Canonical Extraction │
                │ text + math +        │
                │ formatting + media   │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ Math / OMML          │
                │ Normalization        │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ Pre-Segmentation     │
                │ question boundaries  │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ parser_v2            │
                │ existing regexes     │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ State Guards /       │
                │ Post Processing      │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ Validation           │
                │ semantic + structural│
                └──────────┬───────────┘
                           │
                  ┌────────┴────────┐
                  │                 │
                PASS              FAIL
                  │                 │
                  │                 ▼
                  │       ┌──────────────────┐
                  │       │ Fallback /       │
                  │       │ Recovery         │
                  │       └────────┬─────────┘
                  │                │
                  │                ▼
                  │       ┌──────────────────┐
                  │       │ Revalidation     │
                  │       └────────┬─────────┘
                  │                │
                  └────────┬───────┘
                           ▼
                ┌──────────────────────┐
                │ Canonical JSON       │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ Pre-render Gate      │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ PPTX Renderer        │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ Render QA /          │
                │ Structural QA        │
                └──────────────────────┘
```

---

# 3. Architectural Principles

## 3.1 Preserve Information Early

The extraction layer must be loss-minimizing.

Do not flatten rich source content into plain strings before preserving:

* math
* superscript
* subscript
* tables
* images
* source positions
* semantic runs

---

## 3.2 Normalize Once

Canonical normalization should happen as early as practical.

Downstream components should consume normalized representations rather than independently guessing what a string means.

---

## 3.3 Parse Structure, Not Just Lines

The parser must understand document state.

A line is not necessarily:

* a question
* a section
* an option
* a continuation
* a heading

Its role depends on surrounding context.

---

## 3.4 Validate Before Rendering

Invalid JSON must not reach the renderer unnoticed.

The renderer is responsible for presentation, not semantic repair.

---

## 3.5 Never Silently Drop Data

Every source block must have an outcome.

Valid outcomes include:

```text
consumed
parsed
repaired
duplicate
noise
excluded
manual_review
failed
```

There must be no unexplained disappearance.

---

# 4. Layer Responsibilities

## 4.1 Source Inventory

Responsible for discovering:

* paragraphs
* runs
* tables
* images
* equations
* document metadata
* source order

It must assign stable source identifiers.

Example:

```json
{
  "source_id": "doc1",
  "block_id": "p_0042",
  "order": 42
}
```

---

# 5. Canonical Extraction Layer

The canonical extraction model should represent inline content structurally.

Conceptual representation:

```json
{
  "type": "paragraph",
  "content": [
    {
      "kind": "text",
      "value": "Find "
    },
    {
      "kind": "math",
      "value": "x^2 + 1"
    },
    {
      "kind": "text",
      "value": " where "
    },
    {
      "kind": "text",
      "value": "x",
      "vertical_align": "subscript"
    }
  ]
}
```

The exact implementation may differ, but the architecture must preserve semantic distinctions.

---

# 6. Formatting Model

At minimum support:

```text
normal
superscript
subscript
bold
italic
underline
```

Math and text styling must remain distinguishable.

Do not infer superscript from Unicode alone when source formatting is available.

---

# 7. Math Model

Mathematical content should have a canonical representation.

The converter must support:

* fractions
* superscripts
* subscripts
* roots
* functions
* matrices
* piecewise expressions
* intervals
* coordinates
* operators
* limits
* n-ary expressions
* adjacent math runs

The canonical representation should be independent of the final renderer.

---

# 8. OMML Architecture

OMML conversion must be structural.

For nodes where direct operands matter:

```text
./m:e
./m:num
./m:den
./m:sup
./m:sub
```

must be preferred over broad descendant searches.

Structural relationships must be represented explicitly.

For example:

```text
fraction
├── numerator
└── denominator
```

rather than relying on flattened descendant order.

---

# 9. Math Rendering Strategy

The preferred rendering hierarchy is:

```text
Primary:
Native OMML

Fallback:
Portable plain-text / alternate representation

Complex fallback:
SVG / PNG where appropriate
```

Native OMML must include an appropriate fallback representation when the container requires it.

The renderer must not assume every viewer supports every Office math feature.

---

# 10. Pre-Segmentation

Before the main parser, extracted blocks should be grouped into meaningful candidate question regions.

Responsibilities include:

* detecting obvious question starts
* preventing false section boundaries
* preserving continuation lines
* identifying likely instruction blocks
* detecting multi-question blocks
* protecting tables/match structures

Pre-segmentation should be conservative.

When uncertain, preserve content rather than discard it.

---

# 11. Parser Architecture

The existing `parser_v2.py` regexes are valuable and should not be replaced wholesale.

Target structure:

```text
raw candidate
      ↓
pre-segmentation
      ↓
parser_v2 regex detection
      ↓
state guard
      ↓
semantic grouping
      ↓
question object
```

---

# 12. Parser State Machine

A conceptual state machine:

```text
DOCUMENT
   │
   ▼
INSTRUCTIONS
   │
   ▼
QUESTION_START
   │
   ▼
STEM
   │
   ├──────────────┐
   ▼              ▼
STATEMENTS       SUBPARTS
   │              │
   └──────┬───────┘
          ▼
        OPTIONS
          │
          ▼
       COMPLETE
```

Specialized branches:

```text
STEM
 ├── STANDARD_MCQ
 ├── STATEMENT_MCQ
 ├── ASSERTION_REASON
 ├── MATCH
 ├── NUMERICAL
 └── OPEN_QUESTION
```

---

# 13. Question Object

A canonical question should conceptually contain:

```json
{
  "question_id": "Q001",
  "source_id": "doc1",
  "source_order": 1,
  "question_type": "mcq",
  "stem": [],
  "options": [],
  "statements": [],
  "metadata": {},
  "features": {},
  "confidence": 0.0,
  "needs_review": false,
  "review_reasons": [],
  "diagnostics": {}
}
```

The exact schema may differ from this example.

---

# 14. Question Type System

At minimum distinguish:

```text
mcq
statement_mcq
assertion_reason
match
numerical
open_question
unknown
```

Validation rules must depend on question type.

---

# 15. Validation Layer

Validation should operate at multiple levels.

## Structural

Check:

* required fields
* option structure
* identifiers
* ordering
* duplicate IDs

## Semantic

Check:

* question type
* option count
* meaningful stem
* statement integrity

## Math

Check:

* incomplete expressions
* malformed formulas
* missing operands
* broken delimiters

## Fidelity

Check:

* missing media
* missing table cells
* unexplained source blocks

---

# 16. Confidence Model

Confidence should be evidence-based.

Possible factors:

```text
+ clear question marker
+ valid option count
+ complete stem
+ valid math
+ expected structure
+ source continuity

- missing option
- malformed math
- ambiguous boundary
- fallback used
- suspicious source
- incomplete content
```

Do not use a universal constant such as:

```text
0.95
```

---

# 17. Fallback Architecture

Fallback is a recovery mechanism, not the primary parser.

```text
Parser
   ↓
Validator
   ↓
Failure
   ↓
Context expansion
   ↓
Fallback
   ↓
Merge
   ↓
Revalidate
```

Fallback must have access to relevant neighboring source blocks.

---

# 18. LLM Usage

LLM-based recovery may be used only after deterministic processing fails.

Preferred order:

```text
deterministic extraction
        ↓
deterministic parser
        ↓
deterministic validation
        ↓
deterministic recovery
        ↓
LLM fallback
```

LLM output must still pass validation.

---

# 19. Canonical JSON

The JSON output becomes the contract between parsing and rendering.

The renderer must not reconstruct semantic meaning from raw source text.

JSON should contain enough information to render:

* text
* math
* options
* statements
* tables
* images
* metadata
* review status

---

# 20. Rendering Architecture

Renderer responsibilities:

```text
Canonical JSON
      ↓
Slide planning
      ↓
Layout
      ↓
Text / Math / Table / Image rendering
      ↓
PPTX
```

Renderer must not:

* silently discard invalid questions
* guess missing options
* infer subject metadata
* reorder questions

---

# 21. Pre-Render Gate

Before rendering:

```text
source_count
resolved_count
render_count
```

must reconcile.

The pre-render gate must reject unresolved inconsistencies.

For review-required content, the renderer should produce an explicit review representation rather than silently omit the item.

---

# 22. Media Architecture

Images and graphs should be represented explicitly.

Conceptual model:

```json
{
  "kind": "image",
  "source_id": "image_004",
  "order": 5,
  "relationship": "question_stem"
}
```

Tables should retain:

```text
row
column
cell
order
inline content
```

---

# 23. Ordering

Ordering must be explicit.

Use:

```text
source_order
question_order
slide_order
```

Never depend on:

* set iteration
* unordered dictionaries where ordering is semantically important
* database ordering without an explicit key

---

# 24. Diagnostics

Every major stage should emit structured diagnostics.

Example:

```json
{
  "stage": "validation",
  "question_id": "Q012",
  "severity": "warning",
  "code": "MISSING_OPTION",
  "message": "Expected 4 options but found 3"
}
```

Diagnostics should be machine-readable and human-readable.

---

# 25. Observability

At minimum log:

```text
document ID
source block ID
question ID
pipeline stage
status
reason
fallback usage
validation result
render result
```

A failure should be traceable from final slide back to source block.

---

# 26. Determinism

Given identical input and configuration:

```text
same source
→ same canonical JSON
→ same question ordering
→ same semantic PPTX
```

The pipeline must avoid nondeterministic behavior.

---

# 27. Error Handling

Do not use:

```python
try:
    ...
except Exception:
    pass
```

or equivalent silent recovery.

Errors must become:

```text
diagnostic
failure
review item
```

depending on severity.

---

# 28. Regression Strategy

Every fixed bug must gain a regression test.

Preferred pattern:

```text
bug discovered
      ↓
minimal fixture
      ↓
failing test
      ↓
implementation change
      ↓
test passes
      ↓
full regression suite
```

---

# 29. Golden Corpus

Maintain representative documents covering:

* plain MCQ
* mathematical MCQ
* chemistry
* physics
* tables
* images
* match-the-column
* statement questions
* mixed formatting
* malformed source

`test3` is one golden regression fixture, not the only expected document shape.

---

# 30. Implementation Constraint

Do not rewrite the project wholesale.

Prefer:

```text
existing implementation
+
guards
+
canonicalization
+
validation
+
post-processing
+
tests
```

Replace components only when tests demonstrate that incremental correction cannot provide reliable behavior.

---

# 31. Definition of Done

Architecture is considered successfully implemented when:

* extraction is loss-minimizing
* math is canonicalized
* parser boundaries are state-aware
* validation is type-aware
* fallback is controlled
* renderer consumes canonical JSON
* source order is preserved
* media is accounted for
* diagnostics are available
* invariant checks are enforced
* regression tests pass
* no content disappears silently
