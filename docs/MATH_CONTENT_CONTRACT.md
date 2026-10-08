# Math and Inline Content Contract

## Canonical extraction shape

`DocumentBlock.inline_content` is the loss-minimizing content representation. Each item has:

```json
{
  "kind": "text | math_sequence | image | line_break | ...",
  "value": "readable compatibility text",
  "vertical_align": "superscript | subscript | null",
  "formatting": {"bold": false, "italic": true},
  "children": [],
  "source": {}
}
```

`DocumentBlock.text` remains the compatibility string consumed by the existing parser. It may contain a LaTeX-like rendering of source math and Unicode script characters. It is not the authoritative representation when `inline_content` is present.

## OMML nodes

An OMML expression is represented as `kind: "math_sequence"`, with structural children. For example:

```text
math_sequence
└── fraction
    ├── numerator
    │   └── math_sequence
    └── denominator
        └── math_sequence
```

Fraction, script, radical, n-ary, function, delimiter, limit, accent, and bar operands are read from direct OMML children. The `source.omml` field on the expression root retains the original XML. Child `value` fields provide compatibility text only; renderers must prefer the structural children when they support them.

## PDF spans

PDF extraction uses the same inline item fields. A span keeps its original text and records `vertical_align` from its size and baseline geometry. `DocumentBlock.text` continues to contain the existing Unicode/script rendering for compatibility.

## Conversion ownership

`src/convert/math.py` remains the existing string-to-LaTeX normalization and validation utility. Extraction records source structure; it must not add another independent math heuristic. `formula_render.py` and the PPTX/PDF renderers are output adapters. They must not overwrite or discard the canonical inline tree.

## Compatibility and current limits

The legacy `runs` list and flattened `text` remain available. `inline_content` is additive. Current parser reconstruction carries inline items to question JSON with source block IDs and source order. Renderer consumption of all structural node types is incremental; unsupported nodes must remain available in JSON and produce an explicit fallback or review diagnostic.

## Tables and rendering reconciliation

Reconstructed tables keep the compatibility `rows` strings and a parallel `cell_content` matrix. Each rich cell records its text, source block ID, and inline items. PPTX uses the rich cell text when present and routes math markers through the same math adapter as other text; the structured cell data remains in the JSON for consumers that can render superscript/subscript directly.

After a successful PPTX save, JSON `diagnostics` receives `rendered_count`, `rendered_slides`, and `render_diagnostics`. A title slide is included in `rendered_slides`, not `rendered_count`. When parser outcome counts are present, rendering checks that accepted + needs-review + rejected equals the number of question records before creating the deck. Missing or unreadable media produces a visible placeholder and a diagnostic with question, source block, media ID, path, reason, exception, and fallback.
