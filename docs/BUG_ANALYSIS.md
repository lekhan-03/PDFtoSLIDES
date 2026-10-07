# MCQ to Slides — Bug Analysis & Remediation Specification

**Project:** MCQ to Slides
**Document:** Bug Analysis
**Status:** Active Engineering Specification
**Primary Regression Fixture:** `test3.docx` → `test3.json` → `test3.pptx`

---

## 1. Purpose

This document records the defects observed in the MCQ-to-Slides pipeline and defines the engineering requirements for fixing them.

The pipeline is expected to convert source documents containing MCQs into structured JSON and then render that JSON into presentation slides without losing:

* questions
* options
* mathematical expressions
* formatting
* tables
* images
* ordering
* metadata
* question boundaries
* semantic question types

The primary pipeline is:

```text
DOCX / PDF
    ↓
Extraction
    ↓
OMML / Math Normalization
    ↓
Parser
    ↓
Validation
    ↓
Fallback / Recovery
    ↓
Canonical JSON
    ↓
PPTX Renderer
    ↓
Rendered Slides
```

The central engineering requirement is:

> No source question may disappear silently between extraction, parsing, validation, fallback, JSON generation, and rendering.

---

# 2. Severity Classification

| Severity | Meaning                                                              |
| -------- | -------------------------------------------------------------------- |
| P0       | Data loss, silent question loss, corruption of mathematical meaning  |
| P1       | Incorrect parsing/rendering that materially changes question meaning |
| P2       | Formatting, metadata, or fidelity defect                             |
| P3       | Cosmetic or low-impact issue                                         |

P0/P1 defects must be fixed before the pipeline is considered reliable.

---

# 3. Confirmed vs Inferred Findings

Some findings are directly observable from the generated artifacts.

Other findings are architectural hypotheses inferred from the behavior.

Implementation agents MUST inspect the actual source code before claiming an inferred root cause is confirmed.

Use the following terminology:

```text
OBSERVED
    Directly demonstrated by source/output artifacts.

INFERRED
    Likely root cause based on observed behavior.
    Must be verified against implementation before modification.

REQUIRED
    Engineering behavior that must exist regardless of current implementation.
```

---

# 4. Critical Pipeline Defects

## BUG-001 — Silent Question Loss

**Severity:** P0

### Observed

Questions present in the source can disappear before reaching the final PPTX.

### Risk

This is the most serious pipeline defect because the generated presentation can appear valid while silently omitting source content.

### Required behavior

Every processing stage must preserve a countable representation of questions.

At minimum:

```text
source_count
extracted_count
parsed_count
resolved_count
rendered_count
```

The final pipeline must verify:

```text
source_count == resolved_count == rendered_count
```

unless an item is explicitly classified as:

```text
excluded
duplicate
invalid_source
manual_review
```

Every exception must be recorded.

### Acceptance criteria

A missing question causes a visible pipeline failure.

The renderer must never silently skip an unresolved question.

---

# 5. Mathematical Content Defects

## BUG-MTH-001 — Native OMML Without Portable Fallback

**Severity:** P0

### Observed

Native Office Math content may be placed inside `mc:AlternateContent` without a usable `mc:Fallback`.

### Risk

Mathematics can disappear when rendered by applications/viewers that do not consume the native OMML branch.

### Required behavior

Every native math representation must have an explicit fallback.

Preferred representation:

```text
Native OMML
    +
Plain-text / alternate representation
    +
Optional SVG/PNG fallback for complex expressions
```

---

## BUG-MTH-002 — Formula-Only Options Become Empty

**Severity:** P0

### Observed

Options containing only mathematical expressions can extract as empty strings.

Example conceptual input:

```text
(A) [formula]
(B) [formula]
```

can become:

```json
{
  "option": ""
}
```

### Required behavior

Formula-only content must remain valid option content.

---

## BUG-MTH-003 — Piecewise Expressions Collapse

**Severity:** P1

### Observed

Piecewise mathematical expressions can collapse from multiple cases into a single line.

### Required behavior

Piecewise expressions must preserve:

* all cases
* case conditions
* row ordering
* structural relationship

---

## BUG-MTH-004 — Fraction Structure Lost

**Severity:** P1

### Observed

Fractions can become pseudo-text such as:

```text
(a)/(b)
```

instead of preserving mathematical structure.

### Required representation

Canonical LaTeX-like representation should use:

```text
\frac{a}{b}
```

or an equivalent structured representation.

---

## BUG-MTH-005 — Run-Level Superscript/Subscript Lost

**Severity:** P0

### Observed

Formatting such as:

```text
10¹⁴
tan²x
mL⁻¹
e⁻ˣ
```

can become:

```text
1014
tan2x
mL-1
e-x
```

### Root cause

**INFERRED:** Extraction is not converting `w:vertAlign` into a canonical superscript/subscript representation.

### Required behavior

The extraction layer must preserve:

```text
normal
superscript
subscript
```

as explicit content semantics.

---

## BUG-MTH-006 — Chemistry / Units Incorrectly Treated as Mathematics

**Severity:** P1

### Observed

Expressions such as units or chemistry notation may be incorrectly rendered in mathematical styling.

Examples:

```text
mL⁻¹
kg m⁻³
H₂O
CO₂
```

### Required behavior

Math detection must distinguish:

* mathematical expressions
* scientific notation
* chemistry notation
* units
* ordinary text containing symbols

---

## BUG-MTH-007 — Over-Broad Formula Detection

**Severity:** P1

### Observed

Ordinary words may be incorrectly classified as mathematical content.

Examples include terms resembling:

```text
explanation
MCQ
II
```

### Required behavior

Formula detection must require stronger evidence than individual characters or short alphabetic tokens.

---

## BUG-MTH-008 — Punctuation Pulled Into Equations

**Severity:** P1

### Observed

Sentence punctuation can become part of extracted mathematical expressions.

Example:

```text
Find x.
```

becoming something equivalent to:

```text
Find x.
```

where punctuation is included inside the math node.

### Required behavior

Math boundaries must be explicit and punctuation must remain ordinary text unless mathematically meaningful.

---

## BUG-MTH-009 — `<` Operator Breaks Option Content

**Severity:** P1

### Observed

Expressions containing `<` can interfere with parsing or serialization.

### Required behavior

Operators such as:

```text
<
>
≤
≥
≠
=
```

must survive extraction, JSON serialization, and PPTX rendering.

---

## BUG-MTH-010 — Nested OMML Structures Misparsed

**Severity:** P0

### Observed

Nested OMML constructs may produce incomplete or malformed expressions.

### Inferred root cause

A likely cause is descendant selection such as:

```python
.find(".//m:e")
```

when structural conversion requires direct-child access.

### Required behavior

OMML conversion must distinguish:

```text
direct child
```

from:

```text
descendant
```

For example:

```text
./m:e
./m:num
./m:den
./m:sup
./m:sub
```

must be used where structure requires direct-child semantics.

---

## BUG-MTH-011 — Intervals Lose Endpoints

**Severity:** P1

Expressions such as:

```text
[a,b]
```

must preserve both endpoints and delimiters.

---

## BUG-MTH-012 — Coordinate Pairs Lose Structure

Coordinate expressions such as:

```text
(a,b)
(x,y,z)
```

must preserve:

* every component
* commas
* parentheses
* order

---

## BUG-MTH-013 — Connective Words Become Standalone Equations

**Severity:** P1

Words/operators used to connect mathematical expressions can become separate math nodes.

### Required behavior

Adjacent math fragments and connecting text must be normalized into a coherent inline representation.

---

## BUG-MTH-014 — Math Split Across Line Breaks Disappears

**Severity:** P0

A mathematical expression split across source line breaks can be lost or treated as incomplete.

### Required behavior

Line boundaries must not automatically terminate a mathematical expression.

---

## BUG-MTH-015 — Duplicate Function Names

**Severity:** P1

Conversion can produce output similar to:

```text
sinsin x
```

instead of:

```text
sin x
```

### Required behavior

The converter must avoid duplicating function names when they already exist in an operand.

---

## BUG-MTH-016 — Invisible Unicode Characters Leak

**Severity:** P2

Characters such as:

```text
U+2061
```

may appear in output.

### Required behavior

Invisible control characters must be normalized unless explicitly required for semantic representation.

---

## BUG-MTH-017 — Adjacent Math Fragments Not Merged

**Severity:** P1

Separate math runs that form one expression may remain as unrelated fragments.

### Required behavior

Adjacent compatible math fragments should be merged into one canonical inline expression.

---

# 6. Parser Boundary Defects

## BUG-BND-001 — False Section Headers

**Severity:** P0

Text such as:

```text
Column I Column II
II
```

can be incorrectly interpreted as a new question/section.

### Required behavior

Section/header detection must consider parser state and context.

A line should not become a section merely because it matches a generic pattern.

---

## BUG-BND-002 — Open Question Context Not Protected

**Severity:** P0

A question currently being parsed can be interrupted by an incorrectly detected section/header.

### Required behavior

Once a question is open, structural detection must respect the current parser state.

---

## BUG-BND-003 — Colon-Ended Stems Over-Split

**Severity:** P1

A colon can be a natural part of a question stem.

Example:

```text
Which of the following is true:
A ...
B ...
C ...
D ...
```

The parser must not unnecessarily create a new block.

---

## BUG-BND-004 — Subparts Split Incorrectly

Patterns such as:

```text
(i)
(ii)
(a)
(b)
```

may be confused with top-level questions.

### Required behavior

Subparts must remain associated with their parent question unless the source explicitly defines them as independent questions.

---

## BUG-BND-005 — Premise / Command Separation

Questions containing:

```text
Statement:
...
Choose the correct answer:
```

must remain one semantic question.

---

## BUG-BND-006 — Unnumbered Continuation Prompts Lost

An unnumbered line following a stem may actually be part of the same question.

The parser must support multi-line stems and continuation instructions.

---

## BUG-BND-007 — Multi-Question Blocks Not Split

Multiple questions extracted into one text block must be segmented correctly.

---

## BUG-BND-008 — Match-the-Column Questions Misparsed

Structures such as:

```text
Column I
A ...
B ...

Column II
P ...
Q ...
```

must preserve both columns and their ordering.

---

## BUG-BND-009 — Promotional / Noise Text Becomes Questions

Text such as advertisements, URLs, promotional messages, or unrelated document content must not become MCQs.

---

## BUG-BND-010 — Instruction Lines Attached Incorrectly

Document-level instructions must not accidentally become part of the next question.

---

## BUG-BND-011 — Metadata Continuation Lines Lost

Year/exam metadata occurring on continuation lines must be preserved when it belongs to the question.

---

## BUG-BND-012 — Question Type Precedence Is Ambiguous

Generic MCQ detection must not override specialized structures such as:

* statement questions
* match-the-column
* assertion/reason
* numerical/open questions

---

# 7. Parser Architecture Requirement

The current parser is effectively too local/stateless for the complexity of extracted educational documents.

### Required architecture

Do not replace the existing `parser_v2.py` regexes wholesale.

Instead add:

```text
Pre-segmentation
       ↓
Existing parser_v2 regexes
       ↓
State-aware guards
       ↓
Post-processing
       ↓
Validation
       ↓
Fallback
```

Existing regex behavior should be preserved unless a regression test demonstrates that a change is necessary.

---

# 8. Validation Defects

## BUG-VAL-001 — Invalid Option Counts Pass

**Severity:** P0

A multiple-choice question with:

```text
0 options
1 option
2 options
3 options
```

must not silently pass as a valid standard MCQ.

---

## BUG-VAL-002 — Type-Blind Validation

Different question types require different validation rules.

For example:

```text
MCQ
Statement MCQ
Match
Numerical
Open question
```

must not all use the same validation criteria.

---

## BUG-VAL-003 — Math Completeness Not Validated

A question may pass validation even when an option's formula is visibly incomplete.

---

## BUG-VAL-004 — Confidence Hard-Coded

Confidence must not be a constant such as:

```text
0.95
```

for all successfully parsed questions.

Confidence should reflect actual integrity.

---

## BUG-VAL-005 — `needs_review` Lacks Reason

If an item requires review, the JSON must explain why.

Example:

```json
{
  "needs_review": true,
  "review_reasons": [
    "missing_option",
    "incomplete_math"
  ]
}
```

---

## BUG-VAL-006 — Feature Flags Are Incorrect

Fields such as:

```text
has_equation
```

must be derived from actual content, not default values.

---

## BUG-VAL-007 — Empty Stem Causes False Failure

Statement/match/numerical structures may not fit a simple `stem != ""` rule.

Validation must be type-aware.

---

# 9. Fallback / Recovery Defects

## BUG-FBK-001 — Failed Items Not Always Repaired

A failed parser item may remain unresolved instead of entering fallback processing.

---

## BUG-FBK-002 — Fallback Scope Too Narrow

Fallback must receive enough neighboring context to reconstruct a broken question.

It should not operate on an isolated fragment when surrounding blocks contain required information.

---

## BUG-FBK-003 — Repaired Item Not Merged Correctly

Fallback output must replace or merge with the original failed item deterministically.

---

## BUG-FBK-004 — Orphan Blocks Remain

After fallback, fragments belonging to a repaired question must not remain as independent blocks.

---

## BUG-FBK-005 — Revalidation Missing

Fallback output must pass through the same validation layer again.

Required:

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

---

## BUG-FBK-006 — Failure Diagnostics Insufficient

Every fallback event should record:

* original block
* failure reason
* fallback attempt
* fallback result
* validation result

---

# 10. Metadata and Presentation Defects

## BUG-META-001 — Hard-Coded Title

Presentation title contains hard-coded subject/exam information.

### Required behavior

Title must be derived from actual input metadata.

No subject such as:

```text
Chemistry
```

should appear in a Physics/Math presentation unless present in the source metadata.

---

## BUG-META-002 — Question Ordering Is Not Deterministic

Questions must retain source order.

Avoid unordered data structures where ordering matters.

---

## BUG-META-003 — Tags Not Normalized

Tags such as:

```text
2024m,3
```

must be parsed consistently.

Case normalization and delimiter handling must occur once at the canonicalization layer.

---

## BUG-META-004 — Hard Newlines Cause Double Spaces

Whitespace normalization must happen centrally.

---

## BUG-META-005 — Subparts Concatenate

Bad:

```text
Finda
andb
```

Expected:

```text
Find a
and b
```

or an equivalent semantically correct representation.

---

## BUG-META-006 — Slide Context Missing

Slides should expose enough context to identify:

* question number
* section
* marks, when available
* question type, where useful

---

## BUG-META-007 — `source_blocks.role` Incorrect

If every block is labelled:

```text
stem
```

regardless of actual content, the field is not useful.

Roles should represent actual semantic roles.

---

## BUG-META-008 — Unicode Normalization Inconsistent

Different superscript/subscript codepoint families must normalize to the canonical representation.

---

# 11. Fidelity Defects

## BUG-FID-001 — Images Not Preserved

Images/graphs/charts from the source must not disappear from the structured representation.

---

## BUG-FID-002 — Table Reading Order Lost

Table content must preserve row/column structure.

---

## BUG-FID-003 — Duplicate Questions Not Detected

Duplicate source questions should be detected and explicitly classified.

---

## BUG-FID-004 — Suspicious Source Text Passes as High Confidence

Truncated options, malformed source text, or obvious corruption must lower confidence or trigger review.

---

## BUG-FID-005 — Trailing Source Blocks Unexplained

Every extracted block must be accounted for.

A final diagnostic must identify:

```text
consumed
ignored
noise
duplicate
unresolved
```

---

# 12. Regression Test Catalogue

The following test IDs must be implemented.

## Math

```text
TC-MTH-01  OMML portability
TC-MTH-02  Formula-only option
TC-MTH-03  Piecewise expression
TC-MTH-04  Fraction
TC-MTH-05  Table-cell math
TC-MTH-06  Chemistry / units
TC-MTH-07  Math visibility
```

## Formatting

```text
TC-FMT-01  Superscript
TC-FMT-02  Subscript
TC-FMT-03  Canonical encoding
TC-FMT-04  Formula over-detection
TC-FMT-05  Punctuation boundaries
TC-FMT-06  Operator preservation
```

## OMML

```text
TC-OMM-01  Direct operand scoping
TC-OMM-02  Nested structures
TC-OMM-03  Intervals
TC-OMM-04  Coordinates
TC-OMM-05  Formula fragments
TC-OMM-06  Line breaks
TC-OMM-07  Duplicate function names
TC-OMM-08  Adjacent math
TC-OMM-09  Fraction representation
```

## Boundaries

```text
TC-BND-01  Section header protection
TC-BND-02  Section integrity
TC-BND-03  Stem accumulation
TC-BND-04  Subparts
TC-BND-05  Premise/command
TC-BND-06  Statement continuation
TC-BND-07  Multi-question block
TC-BND-08  Match lists
TC-BND-09  Promotional noise
TC-BND-10  Instruction lines
TC-BND-11  Metadata continuation
TC-BND-12  Question type precedence
```

## Validation

```text
TC-VAL-01  Option count
TC-VAL-02  Type-specific validation
TC-VAL-03  Math completeness
TC-VAL-04  Confidence
TC-VAL-05  Feature flags
```

## Fallback

```text
TC-FBK-01  Fallback trigger
TC-FBK-02  Context window
TC-FBK-03  Merge
TC-FBK-04  Failure handling
TC-FBK-05  Count invariants
TC-FBK-06  Diagnostics
```

## Metadata

```text
TC-META-01  Title
TC-META-02  Ordering
TC-META-03  Tags
TC-META-04  Whitespace
TC-META-05  Subparts
TC-META-06  Slide context
TC-META-07  Unicode
```

## Fidelity

```text
TC-FID-01  Images
TC-FID-02  Tables
TC-FID-03  Duplicates
TC-FID-04  Suspect source
TC-FID-05  Trailing blocks
```

---

# 13. Required Remediation Order

Do not attempt to fix all defects simultaneously.

Implement in this order:

```text
Phase 1
Safety / invariants

Phase 2
Canonical extraction model

Phase 3
OMML normalization

Phase 4
Parser segmentation and state guards

Phase 5
Validation

Phase 6
Fallback / recovery

Phase 7
Renderer / math contract

Phase 8
Metadata

Phase 9
Fidelity

Phase 10
Golden corpus / CI
```

---

# 14. Critical Engineering Rules

The implementation MUST NOT:

* silently drop questions
* silently drop options
* silently discard formulas
* replace malformed content with empty strings
* use hard-coded confidence
* use LLM parsing as the first/default parser
* replace `parser_v2.py` regexes wholesale
* rely on unordered structures for source ordering
* hard-code subject/exam metadata
* mark failed items as successful
* catch exceptions and continue without diagnostics

---

# 15. Definition of Done

The bug-fix effort is complete only when:

1. Source question counts reconcile.
2. Parsed question counts reconcile.
3. Rendered question counts reconcile.
4. No unresolved question disappears silently.
5. Mathematical expressions survive extraction.
6. Superscript/subscript survives extraction.
7. Nested OMML expressions are structurally correct.
8. Fractions retain structure.
9. Piecewise expressions retain cases.
10. Formula-only options remain visible.
11. Parser preserves question boundaries.
12. Match-the-column structures remain intact.
13. Validation is type-aware.
14. Fallback repairs are revalidated.
15. Presentation metadata is source-derived.
16. Question order is deterministic.
17. Images and tables are accounted for.
18. Duplicate questions are detected.
19. Regression tests cover all listed test IDs.
20. The complete `test3` fixture passes end-to-end.

---

# 16. Important Implementation Note

This document is an engineering specification.

It contains both observed defects and inferred root causes.

Before changing implementation code:

```text
1. Inspect the actual code.
2. Confirm the inferred root cause.
3. Add/identify a regression test.
4. Make the smallest safe change.
5. Run the regression suite.
6. Run the complete pipeline.
7. Verify source → JSON → PPTX.
```

Do not treat an inferred implementation detail as proven merely because it appears in this document.
