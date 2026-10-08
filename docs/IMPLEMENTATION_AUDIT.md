# PDFtoSLIDES — Actual Source Code Bug Audit

**Repository:** `lekhan-03/PDFtoSLIDES`  
**Audited branch:** `main`  
**Audit date:** 2026-10-07  
**Scope:** Current production source under `src/`, current README/docs, and the implemented execution path.

> Important: this audit distinguishes **confirmed code defects** from defects that require fixture/runtime reproduction. The GitHub source is the authority for implementation claims.

---

## 1. Executive Summary

The current repository does **not** match the architecture described in the project's own documentation.

The live execution path is:

```text
src/main.py
    ↓
extract_docx.py / extract_pdf.py
    ↓
parser_v2.run_pipeline()
    ↓
remove_noise()
detect_sections()
extract_metadata_spans()
split_inline_options()
build_question_candidates()
reconstruct_components()
extract_features()
classify_question()
recover_and_validate()
    ↓
JSON
```

The PPTX renderer is a **separate CLI**:

```text
JSON
  ↓
generate_pptx.py
  ↓
LayoutEngine
  ↓
PPTX
```

The most important confirmed findings are:

1. **`parser_v2.py` uses `Optional` without importing it.** On a normal Python version where annotations are evaluated at function definition, importing `parser_v2` raises `NameError`. This is a P0 runtime defect.
2. **`main.py` accepts `--use-llm` but never uses it.** The LLM fallback is therefore not connected to the current `parser_v2` pipeline.
3. **`llm_fallback.py` exists but is architecturally attached to the old `parser.py` shape**, not the current `parser_v2` candidate/AST shape.
4. **`run_pipeline()` explicitly reports `orphan_blocks: 0` and `duplicate block references: 0` without computing either.**
5. **`run_pipeline()` uses `list(set(section_map.values()))`, destroying document-order determinism.**
6. **`reconstruct_components()` hard-codes every `source_blocks[].role` to `"stem"`.**
7. **`reconstruct_components()` uses `list(set(metadata_appearances))`, also destroying appearance ordering.**
8. **Every reconstructed question starts with confidence `0.95`/`1.0`, independent of actual quality.**
9. **`recover_and_validate()` does not perform the validation contract described by the architecture.** It mostly performs a few heuristics after the object has already been marked valid.
10. **The PPTX renderer silently filters out `parsed_ok == false` questions.** This directly violates the no-silent-loss invariant.
11. **The PPTX title is hard-coded to `"Chemistry Midterm — MCQ Practice"` unless the CLI is explicitly overridden.**
12. **PPTX math rendering creates `mc:AlternateContent` with an `a14:m` Choice but does not create `mc:Fallback`.**
13. **The PPTX math path catches broad exceptions and falls back to text without surfacing the failure as a diagnostic.**
14. **Table rendering uses ordinary text and bypasses the math/rich-content renderer.**
15. **Images are extracted into filesystem paths rather than a canonical media object, and missing images are only printed as warnings.**
16. **The DOCX extractor aggressively flattens OMML into strings and uses descendant `.find('.//...')` lookups for structurally significant operands.**
17. **DOCX run formatting such as `w:vertAlign` is not captured by `DocumentBlock`; the model only stores flattened `text`, making run-level superscript/subscript unrecoverable after extraction.**
18. **DOCX line breaks are split into separate `DocumentBlock`s, which can break semantic inline math/content continuity.**
19. **`split_inline_options()` recreates blocks with the same `block_id`, creating multiple physical blocks with identical IDs.**
20. **The section map is computed before `split_inline_options()`, but split blocks inherit only copied metadata, not a recomputed structural identity/order.**
21. **`detect_sections()` can classify generic uppercase/title-like content as a section using heuristic capitalization rather than a closed section vocabulary plus parser state.**
22. **`decide_boundary()` has a strong “section transition → NEW_QUESTION” rule, so section heuristics can terminate a live candidate.**
23. **`build_question_candidates()` never actually uses `numbering_context["observed"]` to reject duplicate/reordered question numbers.**
24. **`extract_features()` sets `has_equation` to `False` and never updates it based on `q_dict["equations"]`.**
25. **`extract_features()` sets `has_match_list` using broad text heuristics and then `classify_question()` relies on that heuristic rather than a dedicated match structure.**
26. **Match/table semantics are not consistently represented in the canonical model.**
27. **The project contains multiple overlapping math/chemistry conversion systems (`extract_docx`, `convert/math.py`, `convert/chem.py`, `chem_convert.py`, `formula_render.py`, `unmarked.py`) with no single canonical content model.**
28. **`generate_pdf.py` deliberately converts output to Latin-1 with replacement, which can corrupt Greek letters, Unicode math, chemistry subscripts, and other non-Latin content.**
29. **`generate_pptx.py` and `render_engine.py` duplicate layout/rendering responsibilities instead of having a single source-of-truth renderer.**
30. **`render_engine.py` contains a `LayoutEngine.add_table()` implementation that is literally `pass`, while `generate_pptx.py` contains its own table implementation.**

---

# 2. Actual Runtime Architecture

## 2.1 Input/Parsing Path

`src/main.py`:

```text
CLI
 ↓
DOCX → extract_docx_blocks()
PDF  → extract_pdf_blocks()
 ↓
parser_v2.run_pipeline()
 ↓
JSON
```

The `--use-llm` argument is parsed but not consumed.

## 2.2 PPTX Path

The main parser does not generate PPTX.

A separate invocation of:

```text
python -m src.generate_pptx input.json output.pptx
```

is required.

Therefore the architecture is currently **two disconnected CLI stages**, not one closed pipeline.

---

# 3. Critical P0 Bugs

## BUG-RUN-001 — `Optional` Is Not Imported in `parser_v2.py`

**Severity:** P0  
**Status:** CONFIRMED

### Location

```text
src/parser_v2.py
```

Imports:

```python
from typing import List, Dict, Any, Tuple
```

But later:

```python
def detect_question_number(text: str) -> Optional[Dict[str, Any]]:
```

and:

```python
def decide_boundary(
    current_cand: Optional[Dict[str, Any]],
    ...
    num_info: Optional[Dict[str, Any]],
)
```

### Root cause

`Optional` is referenced but not imported.

### Impact

On Python configurations where annotations are evaluated immediately, importing `src.parser_v2` raises `NameError: name 'Optional' is not defined`.

Because `src.main` imports:

```python
from src.parser_v2 import run_pipeline
```

this can prevent the entire CLI from starting.

### Required change

```python
from typing import Any, Dict, List, Optional, Tuple
```

### Regression test

Add an import smoke test:

```python
def test_parser_v2_imports():
    import src.parser_v2
```

---

## BUG-LLM-001 — `--use-llm` Is Parsed but Ignored

**Severity:** P0  
**Status:** CONFIRMED

### Location

```text
src/main.py
```

The CLI defines:

```python
ap.add_argument("--use-llm", action="store_true")
```

But after parsing:

```python
parsed_data = run_pipeline(blocks)
```

No use of:

```python
args.use_llm
```

exists.

### Root cause

The CLI option survived from the older architecture but was not integrated into `parser_v2`.

### Impact

Running:

```bash
python -m src.main input.docx output.json --use-llm
```

does not enable LLM fallback.

### Required change

Do not simply call the LLM from `main.py`.

The fallback should be integrated into the structured pipeline:

```text
candidate
 ↓
parse/reconstruct
 ↓
validate
 ↓
failed candidate
 ↓
LLM fallback
 ↓
merge
 ↓
revalidate
```

The CLI should pass an explicit configuration flag into `run_pipeline()`.

---

# 4. Extraction Bugs

## BUG-EXT-001 — DOCX Extraction Flattens Rich Runs

**Severity:** P0  
**Status:** CONFIRMED

### Location

```text
src/extract_docx.py
extract_node()
```

The extractor returns a string assembled into:

```python
text.append(...)
```

and ultimately:

```python
DocumentBlock(..., text=line, ...)
```

### Root cause

`DocumentBlock` has only:

```python
text: str
```

and no inline run/content model.

### Consequence

After extraction, information such as:

- run-level bold
- italic
- superscript
- subscript
- run boundaries
- inline math boundaries

is no longer structurally represented.

### Required change

Introduce canonical inline content before flattening:

```text
TextRun
MathRun
SupRun
SubRun
ImageRun
```

or an equivalent model.

---

## BUG-EXT-002 — `w:vertAlign` Is Not Captured

**Severity:** P0  
**Status:** CONFIRMED

### Location

```text
src/extract_docx.py
extract_node()
```

The code reads text nodes but does not inspect Word run properties such as:

```xml
<w:rPr>
    <w:vertAlign w:val="superscript"/>
</w:rPr>
```

### Impact

Run-level:

```text
10¹⁴
tan²x
H₂SO₄
mL⁻¹
```

can be flattened before the semantic layer can distinguish the formatting.

### Required change

Capture vertical alignment in the extraction model.

---

## BUG-EXT-003 — OMML Uses Descendant Lookups for Structural Operands

**Severity:** P0/P1  
**Status:** CONFIRMED

### Location

```text
src/extract_docx.py
extract_node()
```

Examples:

```python
node.find(f'.//{M_NS}num')
node.find(f'.//{M_NS}den')
node.find(f'.//{M_NS}e')
node.find(f'.//{M_NS}sup')
node.find(f'.//{M_NS}sub')
```

### Root cause

`.//` searches descendants rather than the direct operand slot.

### Impact

Nested structures can return an inner operand when the conversion requires the direct child.

This is exactly the class of defect expected for:

- nested fractions
- nested superscripts
- radicals inside limits
- n-ary structures
- nested equations

### Required change

Use structural direct-child queries where required:

```python
./m:e
./m:num
./m:den
./m:sup
./m:sub
```

and create dedicated conversion functions per OMML construct.

---

## BUG-EXT-004 — Fractions Are Flattened to `(a)/(b)`

**Severity:** P1  
**Status:** CONFIRMED

### Location

`src/extract_docx.py`

```python
text.append(f'({n_txt})/({d_txt})')
```

### Impact

The source structure is destroyed before the canonical math layer sees it.

Although `convert_math.linear_fractions()` later tries to reconstruct:

```text
\frac{a}{b}
```

this is reverse-engineering a flattened structure.

### Required change

Either:

1. preserve a structured fraction node, or
2. emit a canonical LaTeX representation directly from structurally correct OMML.

Do not rely on a later regex to reconstruct arbitrary nested fractions.

---

## BUG-EXT-005 — DOCX `<br>` Becomes Independent Paragraph Blocks

**Severity:** P1  
**Status:** CONFIRMED

### Location

`src/extract_docx.py`

The code handles:

```python
elif tag == 'br':
    text.append('\n')
```

and later:

```python
lines = [line.strip() for line in text.split('\n') if line.strip()]
for line in lines:
    blocks.append(DocumentBlock(...))
```

### Impact

An inline line break can become a new semantic block.

This can split:

- math
- sentence continuations
- subparts
- options
- inline content

before parser state is applied.

### Required change

Preserve paragraph/run structure and distinguish:

```text
soft line break
paragraph boundary
page break
```

---

## BUG-EXT-006 — Image Extraction Is Filesystem-Based, Not Canonical Media

**Severity:** P1/P2  
**Status:** CONFIRMED

### Location

`src/extract_docx.py`

Images become:

```text
[IMG: filesystem/path]
```

inside text.

### Impact

Media is represented as text markup rather than first-class source content.

### Required change

Represent images as structured media nodes with:

```text
media_id
source_block_id
relationship
path/blob reference
order
```

---

# 5. Block Identity Bugs

## BUG-BLOCK-001 — `split_inline_options()` Duplicates `block_id`

**Severity:** P0/P1  
**Status:** CONFIRMED

### Location

`src/parser_v2.py`

When splitting a block, every generated block uses:

```python
block_id=b.block_id
```

### Impact

One source block can become multiple logical blocks with the same ID.

This breaks:

- source traceability
- orphan detection
- duplicate detection
- question-to-source mapping
- count reconciliation

### Required change

Generate stable derived IDs, e.g.:

```text
42.1
42.2
42.3
```

or preserve the original source ID plus a fragment ID.

---

# 6. Parser Boundary Bugs

## BUG-BND-001 — Section Detection Is Used as a Hard Question Boundary

**Severity:** P0  
**Status:** CONFIRMED

### Location

`src/parser_v2.py`

`detect_sections()` uses:

```python
if is_section_header(b.text):
    current_section = ...
```

Then `build_question_candidates()` does:

```python
if b.block_type == "paragraph" and is_section_header(b.text):
    continue
```

and `decide_boundary()` contains:

```python
elif section_transition:
    decision = "NEW_QUESTION"
```

### Root cause

A heuristic header detector directly controls candidate termination.

### Impact

A false header can:

1. terminate a live question,
2. discard the header itself,
3. assign later content to a new section,
4. create a false question.

### Required change

Section detection must be context-aware and must not automatically terminate an open question unless structural evidence is strong.

---

## BUG-BND-002 — Generic Capitalization Heuristic Can Create False Sections

**Severity:** P1  
**Status:** CONFIRMED

### Location

`is_section_header()`

It considers a line a header when:

```python
upper_words / len(significant_words) >= 0.7
```

and:

```python
len(words) <= 10
```

### Impact

Educational question content that happens to be title-cased or uppercase-heavy can be misclassified.

### Required change

Use:

- explicit section vocabulary
- source formatting evidence
- question state
- numbering context
- neighboring blocks

instead of capitalization alone.

---

## BUG-BND-003 — `decide_boundary()` Has a Broad “Candidate Complete” Rule

**Severity:** P1  
**Status:** CONFIRMED

### Location

`src/parser_v2.py`

```python
cand_seems_complete = ends_sentence or has_options
```

and later:

```python
elif not re.match(OPTION_RE_TEMPLATE.format(L="[A-Ea-e]"), text, re.I):
    decision = "NEW_QUESTION"
```

### Impact

Any non-option block after a candidate that appears to have options can start a new question, even if it is:

- continuation text
- instruction
- metadata
- explanation
- table continuation

### Required change

Replace binary completion with question-state-aware continuation rules.

---

## BUG-BND-004 — `detect_question_number()` Treats Roman Numerals as Question Number Candidates

**Severity:** P1  
**Status:** CONFIRMED

### Location

`src/parser_v2.py`

```python
m_roman = re.match(r'^(X|IX|IV|V?I{0,3})\. ...')
```

### Impact

A standalone:

```text
II.
```

can be structurally classified as a `roman` number and then retained as a subpart/continuation signal.

This is dangerous around:

```text
Column I
Column II
Statement I
Statement II
```

### Required change

Roman numerals need contextual ownership before being classified as question structure.

---

## BUG-BND-005 — Main Question Number Recognition Does Not Enforce Sequence

**Severity:** P1/P2  
**Status:** CONFIRMED

### Location

`build_question_candidates()`

The code stores:

```python
numbering_context["observed"]
```

but does not use it to validate sequence, duplicates, regressions, or gaps.

### Impact

The parser cannot detect:

```text
10 → 10
10 → 14
14 → 13
```

as structural anomalies.

### Required change

Use source numbering as evidence and diagnostics, not merely metadata.

---

# 7. Reconstruction Bugs

## BUG-REC-001 — All Source Blocks Are Labeled `"stem"`

**Severity:** P1  
**Status:** CONFIRMED

### Location

`reconstruct_components()`

```python
source_blocks.append({
    "block_id": b.block_id,
    "role": "stem"
})
```

### Impact

Options, statements, tables, images, subparts, and continuation blocks all receive the same semantic role.

### Required change

Assign roles after reconstruction:

```text
stem
statement
subpart
option
table
image
instruction
metadata
continuation
```

---

## BUG-REC-002 — Appearance Ordering Is Destroyed

**Severity:** P2  
**Status:** CONFIRMED

### Location

`reconstruct_components()`

```python
"appearances": list(set(metadata_appearances))
```

### Impact

Set conversion destroys source order.

### Required change

Stable de-duplication:

```python
list(dict.fromkeys(metadata_appearances))
```

or equivalent.

---

## BUG-REC-003 — Equation Confidence Is Hard-Coded

**Severity:** P2  
**Status:** CONFIRMED

```python
"confidence": 0.95
```

### Impact

Malformed equations are represented with the same confidence as verified equations.

---

## BUG-REC-004 — Question Confidence Is Hard-Coded

**Severity:** P1  
**Status:** CONFIRMED

```python
"overall": 0.95,
"boundary": 0.95,
"components": 0.95,
"classification": 0.95,
"metadata": 1.0
```

### Impact

The confidence field is not an assessment.

### Required change

Derive confidence from evidence.

---

# 8. Validation Bugs

## BUG-VAL-001 — Validation Is Not a Real Validation Layer

**Severity:** P0  
**Status:** CONFIRMED

### Location

`recover_and_validate()`

The object is initially created as:

```python
"parsed_ok": True,
"needs_review": False,
"validation": {
    "valid": True,
    ...
}
```

before validation runs.

The validator only adds a few special cases afterward.

### Impact

The implementation is optimistic by default.

### Required change

Construct the object with an unresolved state, then validate it.

---

## BUG-VAL-002 — Standard MCQ Validation Happens Only After Classification

**Severity:** P1

```python
if q["question_type"] == "mcq" and len(q.get("options", {})) != 4:
```

### Impact

Question classification itself is heuristic and may classify malformed content as something other than `mcq`, avoiding the option-count rule.

### Required change

Validation must be type-aware but must also validate the classification itself.

---

## BUG-VAL-003 — `has_equation` Is Always False

**Severity:** P1  
**Status:** CONFIRMED

`extract_features()` initializes:

```python
"has_equation": False,
```

but never sets it from:

```python
q_dict["equations"]
```

### Impact

Equation feature reporting is incorrect.

### Required change

Derive:

```python
has_equation = bool(q_dict.get("equations"))
```

and validate equation completeness.

---

## BUG-VAL-004 — `validation.checks` Are Hard-Coded Optimistically

**Severity:** P1

`reconstruct_components()` creates:

```python
"options_consistent": True,
"source_blocks_accounted_for": True,
"metadata_cleaned": True,
"no_duplicate_components": True
```

without actually checking these conditions.

### Impact

The validation output can claim properties that were never tested.

### Required change

Populate these only from actual validators.

---

## BUG-VAL-005 — No Math Validation Is Connected

**Severity:** P1

`convert/math.py` provides:

```python
check_math()
```

but the current `parser_v2` validation path does not use it to validate extracted equations.

### Impact

Malformed LaTeX can remain `parsed_ok=True`.

---

# 9. Diagnostics Bugs

## BUG-DIAG-001 — Orphan Blocks Are Faked as Zero

**Severity:** P0  
**Status:** CONFIRMED

`run_pipeline()` prints:

```text
Orphan blocks: 0
Duplicate block references: 0
```

and returns:

```python
"orphan_blocks": [],
"warnings": [],
"errors": []
```

without computing these inventories.

### Impact

The diagnostics actively hide the very failures the architecture requires them to detect.

### Required change

Track all source block IDs and all consumed block IDs.

Compute:

```text
orphan = source - consumed
duplicates = IDs with multiple owners
```

---

## BUG-DIAG-002 — No Source-to-Question Reconciliation

**Severity:** P0

`total_source_blocks` is reported, but there is no source question inventory and no resolution ledger.

### Required change

Introduce a source inventory and question-resolution ledger.

---

# 10. Determinism Bugs

## BUG-DET-001 — Section Order Is Nondeterministic

**Severity:** P1  
**Status:** CONFIRMED

```python
unique_sections = list(set(section_map.values()))
```

### Impact

Set iteration is not a document-order contract.

### Required change

Use first-seen order:

```python
unique_sections = list(dict.fromkeys(section_map.values()))
```

---

## BUG-DET-002 — Metadata Appearance Order Is Nondeterministic

See BUG-REC-002.

---

# 11. LLM Fallback Bugs

## BUG-FBK-001 — LLM Fallback Is Disconnected From `parser_v2`

**Severity:** P0  
**Status:** CONFIRMED

`llm_fallback.py` exists, but `src/main.py` and `src/parser_v2.py` do not call it.

### Impact

The advertised fallback architecture is not the actual runtime architecture.

---

## BUG-FBK-002 — Fallback Schema Matches Old Parser, Not `parser_v2`

`llm_fallback.py` asks for:

```json
{
  "id": 1,
  "question": "...",
  "options": {
    "A": "...",
    "B": "...",
    "C": "...",
    "D": "..."
  }
}
```

But `parser_v2` produces a much richer object containing:

```text
section
source_question_number
raw_question_number
statements
options
appearances
images
subparts
equations
blanks
features
question_type
confidence
validation
source_blocks
```

### Impact

Even if connected directly, the fallback would not produce a complete canonical `parser_v2` object.

### Required change

LLM output should be a narrow recovery proposal, then be normalized into the canonical model and revalidated.

---

## BUG-FBK-003 — Fallback Accepts Missing Options as Empty Strings

`llm_fallback.py` explicitly instructs the LLM:

```text
If a question has fewer than 4 options, use an empty string "" for missing ones.
```

### Impact

This encodes malformed input as a syntactically valid result.

### Required change

Return explicit missing-field diagnostics and let the validator decide.

---

# 12. PPTX Silent-Loss Bugs

## BUG-PPT-001 — Failed Questions Are Silently Filtered Out

**Severity:** P0  
**Status:** CONFIRMED

### Location

`src/generate_pptx.py`

```python
ok_qs = [
    q for q in questions
    if q.get("parsed_ok", True) is not False
]
```

### Impact

Any failed question simply disappears from the deck.

This is a direct violation of:

> No source question may disappear silently.

### Required change

Before rendering, enforce a pre-render gate.

For unresolved questions either:

1. fail the build, or
2. render an explicit “Needs Review” slide.

Never silently filter.

---

## BUG-PPT-002 — PPTX Title Is Hard-Coded

**Severity:** P1  
**Status:** CONFIRMED

```python
def generate(..., title="Chemistry Midterm — MCQ Practice", ...)
```

and CLI:

```python
ap.add_argument(
    "--title",
    default="Chemistry Midterm — MCQ Practice"
)
```

### Impact

Physics/Math/other decks inherit Chemistry branding unless manually overridden.

### Required change

Derive title from metadata/config.

---

## BUG-PPT-003 — Subtitle Count Is Based on Filtered Questions

```python
subtitle = f"{len(ok_qs)} Questions  ·  For: Boards"
```

### Impact

The deck reports the count after silently removing failures.

The user cannot see that questions were dropped.

---

## BUG-PPT-004 — Math `AlternateContent` Has No `mc:Fallback`

**Severity:** P0  
**Status:** CONFIRMED

### Location

`_insert_omml_math_into_paragraph()`

The renderer creates:

```xml
<mc:AlternateContent>
  <mc:Choice Requires="a14">
    <a14:m>...</a14:m>
  </mc:Choice>
</mc:AlternateContent>
```

but does not append:

```xml
<mc:Fallback>...</mc:Fallback>
```

### Impact

Non-supporting consumers can render the math as empty.

### Required change

Create a real fallback branch containing equivalent accessible text or an alternate rendering.

---

## BUG-PPT-005 — Broad Math Exception Is Silently Swallowed

```python
except Exception:
    pass
```

inside `_insert_omml_math_into_paragraph()`.

### Impact

Math conversion failures become visually degraded text without diagnostics.

### Required change

Catch expected exceptions, record a diagnostic, then use an explicit fallback.

---

## BUG-PPT-006 — Table Rendering Bypasses Math Rendering

### Location

`LayoutEngine._render_table()`

```python
cell.text = str(cell_text)
```

### Impact

Math/chemistry in table cells is treated as plain text.

### Required change

Render table cell inline content through the same canonical renderer as body text.

---

## BUG-PPT-007 — Missing Images Only Print a Warning

`render_images()` does:

```python
print(f"[!] Warning: Image {img_path} not found")
continue
```

### Impact

A question can lose a required graph/image while the deck still succeeds.

### Required change

Make missing media a structured diagnostic and optionally a build-gate failure.

---

# 13. Renderer Architecture Bugs

## BUG-RENDER-001 — Duplicate Layout Implementations

There is a `LayoutEngine` in:

```text
src/generate_pptx.py
src/render_engine.py
```

and both contain overlapping layout logic.

### Impact

Two sources of truth can diverge.

### Required change

Select one renderer architecture and make the other a thin compatibility wrapper or remove it after migration.

---

## BUG-RENDER-002 — `render_engine.LayoutEngine.add_table()` Is Unimplemented

The method contains:

```python
def add_table(self, table_data):
    # ... logic to render table using PPTX tables ...
    pass
```

### Impact

The architecture advertises a renderer capability that is not implemented in this class.

---

# 14. PDF Output Bugs

## BUG-PDF-001 — Latin-1 Replacement Corrupts Unicode Content

### Location

`src/generate_pdf.py`

```python
def clean_text(text):
    return str(text).encode('latin-1', 'replace').decode('latin-1')
```

### Impact

Greek/math/chemistry Unicode may become `?`.

Examples at risk:

```text
π
∞
≤
≥
Δ
₂
⁺
⁻
```

### Required change

Use a Unicode-capable font and PDF encoding.

---

# 15. Canonical Model Gap

## BUG-MODEL-001 — `DocumentBlock` Is Too Weak for the Target Contract

Current model:

```python
class DocumentBlock:
    block_id
    block_type
    text
    page
    order
    source
    metadata
    children
```

### Missing first-class concepts

```text
inline runs
math
chemistry
superscript/subscript
media
source relationship
role
reading order
diagnostics
```

### Impact

Later layers must infer information that extraction already flattened.

---

# 16. Math Pipeline Duplication

The repository contains multiple independent systems:

```text
extract_docx.py
convert/math.py
convert/chem.py
chem_convert.py
unmarked.py
formula_render.py
generate_pptx.py rich-text fallback
pdf_spans.py
```

### Problem

There is no single canonical content representation.

The same string can be interpreted independently by:

```text
DOCX extractor
math splitter
chem converter
renderer fallback
PPTX renderer
```

### Required architecture

```text
Source
 ↓
Canonical inline model
 ↓
Canonical math representation
 ↓
Renderer-specific representation
```

---

# 17. Specific Existing Code That Should NOT Be Rewritten Yet

Do not immediately replace:

```text
parser_v2.py
convert/math.py
pdf_spans.py
chem_convert.py
```

The better first sequence is:

```text
1. Fix runtime/import failures
2. Add source/block identity
3. Add regression tests
4. Introduce canonical inline extraction
5. Fix OMML structurally
6. Fix parser boundaries
7. Implement semantic validation
8. Connect fallback
9. Close render gate
10. Consolidate renderers
```

---

# 18. Priority Matrix

| Priority | Bug | Layer |
|---|---|---|
| P0 | BUG-RUN-001 | Runtime |
| P0 | BUG-LLM-001 | Pipeline |
| P0 | BUG-EXT-001 | Extraction |
| P0 | BUG-EXT-002 | Extraction |
| P0 | BUG-EXT-003 | OMML |
| P0 | BUG-BLOCK-001 | Identity |
| P0 | BUG-DIAG-001 | Diagnostics |
| P0 | BUG-PPT-001 | Rendering |
| P0 | BUG-PPT-004 | Math rendering |
| P0 | BUG-PDF-001 | PDF fidelity |
| P1 | BUG-EXT-004 | Math |
| P1 | BUG-BND-001 | Parser |
| P1 | BUG-BND-002 | Parser |
| P1 | BUG-BND-003 | Parser |
| P1 | BUG-REC-001 | Reconstruction |
| P1 | BUG-REC-004 | Confidence |
| P1 | BUG-VAL-001 | Validation |
| P1 | BUG-VAL-003 | Validation |
| P1 | BUG-VAL-004 | Validation |
| P1 | BUG-DET-001 | Determinism |
| P1 | BUG-FBK-001 | Fallback |
| P1 | BUG-FBK-002 | Fallback |
| P1 | BUG-PPT-002 | Metadata |
| P1 | BUG-PPT-003 | Metadata |
| P1 | BUG-PPT-006 | Rendering |
| P1 | BUG-MODEL-001 | Architecture |

---

# 19. Recommended Implementation Order

## Phase 0 — Make the current application runnable

Fix:

```text
BUG-RUN-001
```

Add import smoke tests.

---

## Phase 1 — Establish traceability

Fix:

```text
BUG-BLOCK-001
BUG-DIAG-001
BUG-DET-001
BUG-REC-002
```

Create:

```text
source inventory
block ownership ledger
question resolution ledger
```

---

## Phase 2 — Extraction correctness

Fix:

```text
BUG-EXT-001
BUG-EXT-002
BUG-EXT-003
BUG-EXT-004
BUG-EXT-005
BUG-EXT-006
```

Do not add more regex heuristics until rich source content survives extraction.

---

## Phase 3 — Parser correctness

Fix:

```text
BUG-BND-001
BUG-BND-002
BUG-BND-003
BUG-BND-004
BUG-BND-005
```

Preserve the existing parser regexes where possible.

---

## Phase 4 — Validation

Fix:

```text
BUG-VAL-001
BUG-VAL-002
BUG-VAL-003
BUG-VAL-004
BUG-VAL-005
```

---

## Phase 5 — LLM fallback

Fix:

```text
BUG-LLM-001
BUG-FBK-001
BUG-FBK-002
BUG-FBK-003
```

Use the LLM only for deterministic failures.

The fallback output must be normalized into the same canonical model and revalidated.

---

## Phase 6 — Rendering safety

Fix:

```text
BUG-PPT-001
BUG-PPT-004
BUG-PPT-005
BUG-PPT-006
BUG-PPT-007
```

---

## Phase 7 — Metadata/fidelity

Fix:

```text
BUG-PPT-002
BUG-PPT-003
BUG-MODEL-001
BUG-PDF-001
```

---

# 20. Required Regression Tests

At minimum add tests for:

```text
test_parser_v2_import
test_cli_llm_flag_changes_pipeline_config
test_duplicate_block_ids_after_inline_split
test_section_order_is_stable
test_appearance_order_is_stable
test_vert_align_preserved
test_nested_omml_fraction
test_nested_omml_superscript
test_formula_only_option
test_failed_question_not_silently_rendered
test_render_gate_detects_missing_question
test_has_equation_is_accurate
test_validation_does_not_claim_unchecked_properties
test_missing_image_creates_diagnostic
test_pptx_math_contains_fallback
test_pdf_preserves_unicode
```

---

# 21. Most Important Architectural Finding

The previous bug report correctly identified the **symptoms**, but the current source code reveals that the central problem is deeper:

> **The project does not yet have a true canonical intermediate representation.**

Instead, it has several stages that repeatedly transform strings:

```text
DOCX XML
 ↓
flattened string
 ↓
regex math detection
 ↓
regex parser
 ↓
regex reconstruction
 ↓
JSON string
 ↓
regex math detection again
 ↓
PPTX
```

This is why math, formatting, parser boundaries, and rendering failures interact.

The highest-value architectural change is therefore not "make the regex smarter."

It is:

```text
Source XML
 ↓
Canonical rich DocumentBlock / InlineContent
 ↓
Semantic Question AST
 ↓
Validated JSON
 ↓
Deterministic renderer
```

---

# 22. LLM Migration Recommendation

Because the immediate goal is changing the LLM, do **not** start by editing `llm_fallback.py` alone.

The current LLM integration is already disconnected.

First define the fallback contract:

```text
Deterministic parser
      ↓
Validation failure
      ↓
Context window
      ↓
LLM
      ↓
Recovery proposal
      ↓
Canonicalization
      ↓
Validation
      ↓
Accept / Review / Reject
```

The LLM should NOT be allowed to directly manufacture arbitrary final JSON and bypass validation.

Recommended interface:

```python
recover_question(
    context: RecoveryContext
) -> RecoveryProposal
```

Then:

```python
proposal = llm.recover_question(context)
candidate = normalize_recovery(proposal)
result = validate(candidate)

if result.valid:
    accept(candidate)
else:
    needs_review(candidate, result.errors)
```

The model name/provider should be configuration, not parser logic.

---

# 23. Final Audit Conclusion

The current repository is not ready for a simple "change the LLM model" operation.

The first blockers are:

```text
1. parser_v2 import/runtime correctness
2. actual LLM integration
3. canonical source/block identity
4. extraction fidelity
5. validation/diagnostics
6. renderer silent-loss behavior
```

Once those contracts are established, changing the LLM becomes an isolated provider-level concern instead of another source of pipeline instability.

**Do not rewrite `parser_v2.py` wholesale.**

**Do not make the new LLM responsible for deterministic parsing defects.**

**Fix the earliest layer that loses information, then use the LLM only for genuinely ambiguous recovery.**

---

# 24. Phase 2 Implementation Addendum (2026-10-07)

This addendum records verified changes in the current working tree; it supersedes earlier findings above where they describe the previous implementation state.

| Area | Current status | Evidence |
| --- | --- | --- |
| Rich document model and extraction | `InlineContent` retains formatting, math structure, explicit line breaks, media references, and source metadata while preserving legacy text/runs. DOCX/PDF extraction populate it. | `tests/test_audit_regressions.py`; `tests/test_pdf_spans.py` |
| OMML structure | Direct-child operand extraction retains fractions, scripts, radicals, n-ary operators, functions, delimiters, and other source XML. | nested/generated OMML tests in `tests/test_audit_regressions.py` |
| Parser boundaries and numbering | Candidate construction records numbering events and uses context to avoid promoting arbitrary Roman labels; revalidation rebuilds dynamic errors. | boundary and numbering regressions in `tests/test_audit_regressions.py` |
| LLM recovery | `run_pipeline(use_llm=True)` delegates recovery through a provider-neutral batch interface; proposals are normalized and revalidated. | provider, malformed response, incomplete options, and metadata regressions in `tests/test_audit_regressions.py` |
| PPTX tables and media | Table JSON retains parallel rich cell content; math text goes through the existing renderer. Missing/unreadable images create a placeholder and structured render diagnostic. | table math and missing-media regressions in `tests/test_audit_regressions.py` |
| Render reconciliation | Renderer checks parser outcome totals before creating a deck, then persists rendered question/slide counts and diagnostics into the JSON. | count-gate and persistence regressions in `tests/test_audit_regressions.py` |

Full suite at this addendum: **76 passed**. Golden `data/tests/test3.docx`: **133 source blocks**, **73 questions** (70 accepted, 2 needs review, 1 rejected), **0 orphan blocks**, **0 duplicate block references**, and **73 rendered questions / 74 slides** (the extra slide is the title slide). The generated deck contained **160 `mc:AlternateContent` entries**, each with an `a14:m` Choice and readable `mc:Fallback`; no raw math markers were detected. Test3 has 53 questions with equation features, one extracted image, and no tables. Render diagnostics were empty because the image resolved successfully.

Remaining limits: rich inline trees are preserved canonically, but all renderers do not yet interpret every structural node directly; unsupported structures still depend on compatibility text. Test3 has no table coverage, so table extraction is verified through generated regression fixtures rather than this integration document. Math normalization/render exceptions have text fallback and warnings, but do not yet all flow into the structured per-question `render_diagnostics` array. These are known follow-up items, not evidence of test3 failure.

---

# 25. Phase 3 Fidelity and Renderer Coverage (2026-10-07)

Phase 3 adds direct canonical-node rendering, readable fallbacks, and question/component/source-node diagnostics. The table below describes the current supported paths, including intentional fallbacks.

| Content | PPTX | PDF | Diagnostic behavior |
| --- | --- | --- | --- |
| Plain text and formatted runs | DrawingML text runs; bold, italic, underline retained | Unicode-readable text | Alignment loss warns `TEXT_LAYOUT_DEGRADED` |
| Inline superscript/subscript | DrawingML baseline positioning; Unicode script glyphs preserved in compatibility text | Unicode script glyphs | Alignment loss warns `TEXT_LAYOUT_DEGRADED` |
| Explicit line breaks | Native DrawingML paragraph break | Text line break | Unsupported node warns `RENDER_NODE_UNSUPPORTED` |
| Math sequences and source OMML | Source OMML inserted as native `a14:m` with readable fallback; normalized/generated OMML where conversion succeeds | Readable Unicode text | Fallback warns `MATH_FALLBACK_USED`; hard conversion failure warns `MATH_RENDER_FAILED` |
| Images | Source image where resolvable; visible placeholder on missing/invalid media | Image where resolvable; visible placeholder on missing/invalid media | `MEDIA_RENDER_FAILED` with source/question context |
| Tables | Native PPTX table with rich cell nodes and content-sized rows | Readable cell text in table-row layout | Cell mismatch warns `TEXT_LAYOUT_DEGRADED`; unsupported legacy table rendering warns `RENDER_NODE_UNSUPPORTED` |
| Unknown or invalid canonical nodes | Known readable value rendered where available | Known readable value rendered where available | `RENDER_NODE_UNSUPPORTED` or `INVALID_CANONICAL_NODE` |

Every renderer diagnostic carries explicit `code`, `severity`, `question_id`, `component_id`, `source_block_id`, `node_id`, `reason`, `fallback`, and `slide_ids` keys (values may be null where a source does not provide that identity). Render status and diagnostic counts are persisted to JSON, with question-level render status/slide IDs. The PDF pipeline stores its own aggregate and per-question status under `diagnostics.pdf_render` and `render.pdf`.

Validation: **84 tests pass**. The golden test3 run retains 73 rendered questions and 74 slides, with 0 leaked raw math markers. It reports 28 `TEXT_LAYOUT_DEGRADED` warnings and one `MATH_FALLBACK_USED`; malformed derivative fragments use readable text fallback. Its deck has 154 AlternateContent math entries versus 160 in the Phase 2 snapshot: ordinary `II` option labels are now text, and invalid math fragments are routed through fallback. A PowerPoint-generated PDF was visually inspected. The Artifact Tool preview does not paint DrawingML `a14:m` Choice content, so it is not a reliable visual proxy for those formulas.

Visual QA also covered a valid image, a table with fraction and chemical scripts, a long option, a multiline stem, and vector notation. Rich table rows now reserve extra height for fractions and math sequences. Remaining risk: the 28 source-to-component alignments that use compatibility text are traceable but still require a future alignment-recovery improvement; this run is degraded, not warning-free.

---

# 26. Phase 3A Renderer Regression Fixes (2026-10-07)

Phase 3A corrected the renderer issues in the Run 2 artifact without changing parser or extraction behavior. See [Phase 3A Renderer Fixes](PHASE3A_RENDERER_FIXES.md) for reproduction details and the verification matrix.

The existing 33-question `testing_file.json` content remained unchanged. The regenerated deck contains 34 slides, with **77 canonical top-level math nodes → 77 native math entries → 77 local readable fallbacks**; no math node failed. No fallback exceeds 60 characters, no raw math markers leak, and no incorrect option-source diagnostic remains. Renderer diagnostics dropped from the Run 2 report's 64 to **2 retained `TEXT_LAYOUT_DEGRADED` warnings**. These identify unmatched canonical components and include source and node IDs rather than being suppressed.

PowerPoint-generated PDF inspection of a disposable fallback-selecting copy confirmed the fraction fallbacks display once as readable numerator/denominator text. The native production XML was separately verified. The fixture reveals an upstream component-shape mismatch in Q16 (`question.options` is empty while option text is embedded in `question` and source blocks are marked as options); Phase 3A preserves and diagnoses this condition, with a focused regression test for separate parser work.

Final repository suite: **94 passed**. `git diff --check`: clean.
