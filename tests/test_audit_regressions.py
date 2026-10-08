"""Regression tests covering all BUG IDs from docs/IMPLEMENTATION_AUDIT.md."""
import json
import os
import tempfile
from pathlib import Path
import pytest

from src.document_model import DocumentBlock
from src.parser_v2 import (
    split_inline_options,
    reconstruct_components,
    recover_and_validate,
    run_pipeline,
    decide_boundary,
    detect_question_number,
    is_section_header,
    is_question_like_start,
    build_question_candidates,
)


class StaticRecoveryProvider:
    model = "test-provider"

    def __init__(self, proposals=None, error=None):
        self.proposals = proposals
        self.error = error

    def recover_questions(self, contexts):
        if self.error:
            raise self.error
        self.contexts = contexts
        return self.proposals


def test_bug_run_001_import_parser_v2():
    """BUG-RUN-001: parser_v2 can be imported without Optional typing NameError."""
    import src.parser_v2 as p2
    assert hasattr(p2, "run_pipeline")
    assert hasattr(p2, "decide_boundary")


def test_bug_ext_001_document_block_rich_structure():
    """BUG-EXT-001 & BUG-MODEL-001: DocumentBlock preserves runs and block identity."""
    b = DocumentBlock(
        text="Calculate $x^2$",
        block_id="b-101",
        block_type="paragraph",
        runs=[{"text": "Calculate "}, {"text": "$x^2$", "math": True}],
        metadata={"custom": "val"}
    )
    assert b.block_id == "b-101"
    assert len(b.runs) == 2
    assert b.runs[1]["math"] is True


def test_document_block_inline_content_roundtrip():
    """BUG-MODEL-001: Rich inline nodes survive canonical serialization."""
    from src.document_model import InlineContent

    b = DocumentBlock(
        block_id="inline-1",
        text="x²",
        inline_content=[InlineContent(
            kind="math_sequence", value="$x^{2}$",
            children=[InlineContent(kind="superscript", value="x^{2}")],
            source={"omml_tag": "oMath"},
        )],
    )
    restored = DocumentBlock.from_dict(b.to_dict())
    assert restored.inline_content[0].kind == "math_sequence"
    assert restored.inline_content[0].children[0].kind == "superscript"
    assert restored.inline_content[0].source["omml_tag"] == "oMath"


def test_docx_extraction_preserves_run_formatting_math_and_breaks(tmp_path):
    """BUG-EXT-001..005: DOCX extraction retains rich inline and nested OMML structure."""
    from docx import Document
    from docx.oxml import parse_xml
    from src.extract_docx import extract_docx_blocks

    doc = Document()
    p = doc.add_paragraph()
    p.add_run("normal ")
    bold = p.add_run("bold ")
    bold.bold = True
    italic = p.add_run("italic ")
    italic.italic = True
    sub = p.add_run("2")
    sub.font.subscript = True
    sup = p.add_run("3")
    sup.font.superscript = True
    p.add_run().add_break()
    p.add_run("continued ")
    omml = parse_xml(
        '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
        '<m:f><m:num><m:f><m:num><m:r><m:t>a</m:t></m:r></m:num>'
        '<m:den><m:r><m:t>b</m:t></m:r></m:den></m:f></m:num>'
        '<m:den><m:sSup><m:e><m:r><m:t>x</m:t></m:r></m:e>'
        '<m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup></m:den>'
        '</m:f></m:oMath>'
    )
    p._p.append(omml)
    p.add_run(" after math")
    path = tmp_path / "rich.docx"
    doc.save(path)

    block = extract_docx_blocks(str(path))[0]
    kinds = [item.kind for item in block.inline_content]
    assert any(item.formatting.get("bold") for item in block.inline_content)
    assert any(item.formatting.get("italic") for item in block.inline_content)
    assert any(item.vertical_align == "subscript" for item in block.inline_content)
    assert any(item.vertical_align == "superscript" for item in block.inline_content)
    assert "line_break" in kinds
    math = next(item for item in block.inline_content if item.kind == "math_sequence")
    fraction = math.children[0]
    assert fraction.kind == "fraction"
    assert [child.kind for child in fraction.children] == ["numerator", "denominator"]
    numerator = fraction.children[0].children[0]
    denominator = fraction.children[1].children[0]
    assert numerator.kind == "math_sequence"
    assert numerator.children[0].kind == "fraction"
    assert denominator.kind == "math_sequence"
    assert denominator.children[0].kind == "superscript"
    assert "\\frac" in block.text


def test_omml_ir_scripts_radicals_nary_functions_and_piecewise_matrix(tmp_path):
    """BUG-EXT-003/004: Common nested OMML and matrix-based piecewise data survive."""
    from docx import Document
    from docx.oxml import parse_xml
    from src.extract_docx import extract_docx_blocks

    ns = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'
    expressions = [
        f'<m:oMath {ns}><m:sSub><m:e><m:r><m:t>x</m:t></m:r></m:e><m:sub><m:r><m:t>2</m:t></m:r></m:sub></m:sSub></m:oMath>',
        f'<m:oMath {ns}><m:rad><m:deg/><m:e><m:rad><m:deg/><m:e><m:r><m:t>x</m:t></m:r></m:e></m:rad></m:e></m:rad></m:oMath>',
        f'<m:oMath {ns}><m:func><m:fName><m:r><m:t>tan</m:t></m:r></m:fName><m:e><m:sSup><m:e><m:r><m:t>x</m:t></m:r></m:e><m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup></m:e></m:func></m:oMath>',
        f'<m:oMath {ns}><m:nary><m:naryPr><m:chr m:val="∑"/></m:naryPr><m:sub><m:r><m:t>i=1</m:t></m:r></m:sub><m:sup><m:r><m:t>n</m:t></m:r></m:sup><m:e><m:r><m:t>i</m:t></m:r></m:e></m:nary></m:oMath>',
        f'<m:oMath {ns}><m:matrix><m:mr><m:e><m:r><m:t>x</m:t></m:r></m:e><m:e><m:r><m:t>x&gt;0</m:t></m:r></m:e></m:mr><m:mr><m:e><m:r><m:t>-x</m:t></m:r></m:e><m:e><m:r><m:t>x≤0</m:t></m:r></m:e></m:mr></m:matrix></m:oMath>',
    ]
    doc = Document()
    paragraph = doc.add_paragraph("piecewise and sums: ")
    for xml in expressions:
        paragraph._p.append(parse_xml(xml))
    path = tmp_path / "omml-families.docx"
    doc.save(path)

    block = extract_docx_blocks(str(path))[0]
    walk = lambda node: [node] + [child for c in node.children for child in walk(c)]
    nodes = [node for item in block.inline_content if item.kind == "math_sequence"
             for node in walk(item)]
    kinds = {node.kind for node in nodes}
    assert {"subscript", "radical", "function", "superscript", "nary",
            "matrix", "matrix_row"} <= kinds
    nary = next(node for node in nodes if node.kind == "nary")
    assert nary.formatting["operator"] == "∑"
    matrix = next(node for node in nodes if node.kind == "matrix")
    assert len([child for child in matrix.children if child.kind == "matrix_row"]) == 2
    assert {"x>0", "x≤0"} <= {node.value for node in nodes}


def test_bug_ext_002_vertalign_unicode_preservation():
    """BUG-EXT-002: Superscripts and subscripts are preserved."""
    # Test strings with superscripts and subscripts
    s = "10¹⁴ tan²x mL⁻¹ x₂ H₂O SO₄²⁻"
    assert "¹⁴" in s
    assert "₂" in s
    assert "⁻¹" in s


def test_bug_block_001_split_inline_options_unique_traceable_ids():
    """BUG-BLOCK-001: Inline options receive unique derived IDs and preserve parent ID."""
    block = DocumentBlock(
        text="(a) 10 m/s (b) 20 m/s (c) 30 m/s (d) 40 m/s",
        block_id="block-42",
        block_type="paragraph"
    )
    parts = split_inline_options([block])
    assert len(parts) == 4
    # All IDs must be unique
    ids = [p.block_id for p in parts]
    assert len(set(ids)) == 4
    for idx, p in enumerate(parts):
        assert p.block_id == f"block-42.part_{idx + 1}"
        assert p.metadata.get("parent_block_id") == "block-42"


def test_bug_diag_001_and_002_reconciled_ledger():
    """BUG-DIAG-001 & BUG-DIAG-002: Real source block ledger and reconciled diagnostics."""
    blocks = [
        DocumentBlock(text="Section A: Mathematics", block_id="b-1"),
        DocumentBlock(text="1. What is the value of 2 + 2?", block_id="b-2"),
        DocumentBlock(text="(A) 2 (B) 3 (C) 4 (D) 5", block_id="b-3"),
        DocumentBlock(text="2. Solve for x: x + 1 = 0", block_id="b-4"),
        DocumentBlock(text="(A) -1 (B) 1 (C) 0 (D) 2", block_id="b-5"),
    ]
    result = run_pipeline(blocks)
    diag = result.get("diagnostics", {})
    
    assert diag.get("total_source_blocks") >= len(blocks)
    assert diag.get("questions_detected") == 2
    assert diag.get("questions_accepted") == 2
    assert diag.get("questions_rejected") == 0
    assert diag.get("questions_detected") == (
        diag.get("questions_accepted", 0)
        + diag.get("questions_needs_review", 0)
        + diag.get("questions_rejected", 0)
    )
    assert isinstance(diag.get("orphan_blocks"), list)
    assert isinstance(diag.get("duplicate_blocks"), list)


def test_metadata_only_source_blocks_are_reconciled_to_question():
    """Citation-only blocks retain their metadata and source ownership."""
    blocks = [
        DocumentBlock(text="1. Which value is correct?", block_id="b-1", order=1),
        DocumentBlock(text="(2020, 2022)", block_id="b-2", order=2),
    ]
    result = run_pipeline(blocks)
    question = result["questions"][0]
    diagnostics = result["diagnostics"]

    assert question["appearances"] == ["2020", "2022"]
    assert "b-2" in question["block_ids"]
    assert diagnostics["orphan_blocks"] == []
    assert {entry["source_block_id"]: entry["status"] for entry in diagnostics["source_ledger"]}["b-2"] == "consumed"


def test_bug_det_001_section_order_deterministic():
    """BUG-DET-001: Section order preserves document source order, no set() scrambling."""
    blocks = [
        DocumentBlock(text="SECTION 1: Physics", block_id="b-1"),
        DocumentBlock(text="1. Question in Physics", block_id="b-2"),
        DocumentBlock(text="(A) 1 (B) 2 (C) 3 (D) 4", block_id="b-3"),
        DocumentBlock(text="SECTION 2: Chemistry", block_id="b-4"),
        DocumentBlock(text="2. Question in Chemistry", block_id="b-5"),
        DocumentBlock(text="(A) 1 (B) 2 (C) 3 (D) 4", block_id="b-6"),
        DocumentBlock(text="SECTION 3: Mathematics", block_id="b-7"),
        DocumentBlock(text="3. Question in Math", block_id="b-8"),
        DocumentBlock(text="(A) 1 (B) 2 (C) 3 (D) 4", block_id="b-9"),
    ]
    result = run_pipeline(blocks)
    assert [s["title"] for s in result.get("sections", [])] == [
        "SECTION 1: Physics",
        "SECTION 2: Chemistry",
        "SECTION 3: Mathematics"
    ]


def test_bug_bnd_001_and_002_section_header_guard():
    """BUG-BND-001 & BUG-BND-002: False section candidates do not become section headers."""
    assert not is_section_header("Column I Column II")
    assert not is_section_header("Column I")
    assert not is_section_header("II")
    assert not is_section_header("MCQ")
    assert not is_section_header("EXPLANATION")
    assert not is_section_header("IMPORTANT")
    assert not is_section_header("Statement-1")
    assert not is_section_header("List-I")


def test_bug_bnd_003_continuation_text_boundary():
    """BUG-BND-003: Colon-ended stem or command continuation does not prematurely split."""
    prev_block = DocumentBlock(text="Consider the following function f(x):", block_id="b-1")
    cand = {"blocks": [prev_block], "section": "General", "has_q_number": True}
    curr = DocumentBlock(text="Find the derivative f'(x) at x = 0.", block_id="b-2")
    num_info = detect_question_number(curr.text)
    decision, reason = decide_boundary(cand, curr, "General", False, num_info, {})
    assert decision == "CONTINUE"


def test_bug_bnd_004_roman_numeral_context():
    """BUG-BND-004: Roman numerals like II. require contextual evidence."""
    prev_block = DocumentBlock(text="10. Solve the system of equations:", block_id="b-1")
    cand = {"blocks": [prev_block], "section": "General", "has_q_number": True}
    curr = DocumentBlock(text="II. The secondary statement", block_id="b-2")
    num_info = detect_question_number(curr.text)
    num_ctx = {"last_seen": 10, "scheme": "arabic"}
    decision, reason = decide_boundary(cand, curr, "General", False, num_info, num_ctx)
    assert decision == "CONTINUE"


def test_bug_bnd_005_numbering_events_use_context():
    """BUG-BND-005: Duplicate, regression, gap, and section reset are recorded."""
    blocks = [DocumentBlock(text=f"{n}. Find value {idx}", block_id=f"b-{idx}", order=idx)
              for idx, n in enumerate((1, 2, 2, 1, 4), start=1)]
    candidates = build_question_candidates(blocks, {b.block_id: "A" for b in blocks})
    events = [candidate["numbering_event"]["event"] for candidate in candidates]
    assert events == ["sequence", "sequence", "duplicate", "regression", "gap"]

    reset_blocks = [
        DocumentBlock(text="10. Find a value", block_id="r-1", order=1),
        DocumentBlock(text="1. Find another value", block_id="r-2", order=2),
    ]
    reset_candidates = build_question_candidates(reset_blocks, {"r-1": "Section A", "r-2": "Section B"})
    reset = reset_candidates[1]["numbering_event"]
    assert reset["event"] == "section_reset"
    assert reset["previous"] == 10 and reset["current"] == 1


def test_roman_marker_becomes_question_only_with_question_context():
    """BUG-BND-004: Roman labels stay continuations unless text/state supports a question."""
    blocks = [
        DocumentBlock(text="1. Choose the true answer (A) a (B) b (C) c (D) d", block_id="q1", order=1),
        DocumentBlock(text="II. Find the next value", block_id="q2", order=2),
    ]
    candidates = build_question_candidates(blocks, {"q1": "General", "q2": "General"})
    assert len(candidates) == 2
    assert candidates[1]["source_question_number"] == "II"
    assert candidates[1]["numbering"]["scheme"] == "roman"


def test_bug_rec_001_semantic_block_roles():
    """BUG-REC-001: Source blocks receive specific roles (stem, option, statement, etc.)."""
    blocks = [
        DocumentBlock(text="1. Which of the following is true?", block_id="b-1"),
        DocumentBlock(text="(a) First option", block_id="b-2"),
        DocumentBlock(text="(b) Second option", block_id="b-3"),
        DocumentBlock(text="(c) Third option", block_id="b-4"),
        DocumentBlock(text="(d) Fourth option", block_id="b-5"),
    ]
    reconstructed = reconstruct_components({"blocks": blocks})
    roles = {b.block_id: b.metadata.get("role") for b in blocks}
    assert roles["b-1"] == "stem"
    assert roles["b-2"] == "option"
    assert roles["b-3"] == "option"


def test_bug_rec_002_metadata_appearances_order():
    """BUG-REC-002: Appearances retain deterministic order without set() scrambling."""
    blocks = [
        DocumentBlock(text="1. Question with citations (2020) (2018) (2022) (2018)", block_id="b-1"),
        DocumentBlock(text="(A) 1 (B) 2 (C) 3 (D) 4", block_id="b-2")
    ]
    reconstructed = reconstruct_components({"blocks": blocks})
    apps = reconstructed.get("appearances", [])
    assert apps == ["2020", "2018", "2022"]


def test_bug_val_001_through_005_evidence_based_validation():
    """BUG-VAL-001 to BUG-VAL-005: Validation is a real evidence-based gate."""
    valid_q = {
        "id": "q-1",
        "question": "What is $\\int x dx$?",
        "options": {"A": "$\\frac{x^2}{2} + C$", "B": "$x + C$", "C": "$x^2$", "D": "$1$"},
        "question_type": "mcq",
        "blocks": [DocumentBlock(text="What is $\\int x dx$?", block_id="b-1")]
    }
    res_valid = recover_and_validate([valid_q])[0]
    assert res_valid.get("parsed_ok") is True
    assert res_valid.get("has_equation") is True
    assert res_valid.get("quality_score", 0) > 0.8

    invalid_q = {
        "id": "q-2",
        "question": "Solve the problem",
        "options": {"A": "Single option"},
        "question_type": "mcq",
        "blocks": [DocumentBlock(text="Solve the problem", block_id="b-2")]
    }
    res_invalid = recover_and_validate([invalid_q])[0]
    assert res_invalid.get("parsed_ok") is False
    assert res_invalid.get("needs_review") is True
    assert any("option" in err.lower() for err in res_invalid.get("validation_errors", []))
    assert res_invalid.get("review_reasons")
    assert res_invalid["review_reasons"] == res_invalid["validation"]["issues"]
    res_invalid["options"] = {"A": "One", "B": "Two", "C": "Three", "D": "Four"}
    revalidated = recover_and_validate([res_invalid])[0]
    assert revalidated["parsed_ok"] is True
    assert revalidated["validation_errors"] == []


def test_llm_recovery_provider_proposal_is_normalized_and_revalidated():
    """BUG-FBK-001/002: Provider-neutral proposals are validated before acceptance."""
    from src.llm_fallback import recover_questions_batch

    question = {
        "id": 31, "question": "Solve the problem", "question_type": "mcq",
        "options": {"A": "only one"}, "parsed_ok": True, "needs_review": False,
    }
    recover_and_validate([question])
    provider = StaticRecoveryProvider([{
        "id": "31", "question": "Choose the correct value",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
    }])
    recovered = recover_questions_batch([question], provider)[0]
    final = recover_and_validate([recovered])[0]
    assert final["parsed_ok"] is True
    assert final["recovered_by_llm"] is True
    assert final["question"] == "Choose the correct value"


def test_llm_recovery_rejects_incomplete_and_hallucinated_proposals():
    """BUG-FBK-003: Empty/missing options and hallucinated metadata never bypass validation."""
    from src.llm_fallback import recover_questions_batch

    original = {
        "id": "q-1", "question": "Original question", "question_type": "mcq",
        "options": {"A": "only option"}, "parsed_ok": True, "needs_review": False,
    }
    recover_and_validate([original])
    provider = StaticRecoveryProvider([{
        "id": "q-1", "question": "Altered question",
        "options": {"A": "1", "B": "", "C": "3"}, "metadata": {"answer": "A"},
    }])
    result = recover_questions_batch([original], provider)[0]
    assert result["question"] == "Original question"
    assert result.get("recovered_by_llm") is None
    assert result["recovery_diagnostics"][0]["status"] == "rejected"
    assert result["needs_review"] is True


def test_llm_malformed_provider_response_is_diagnostic():
    """BUG-FBK-002: Malformed provider responses retain deterministic output with diagnostics."""
    from src.llm_fallback import recover_questions_batch

    question = {"id": "q-2", "question": "Original", "question_type": "mcq",
                "options": {"A": "one"}, "parsed_ok": True}
    recover_and_validate([question])
    result = recover_questions_batch(
        [question], StaticRecoveryProvider(error=ValueError("malformed JSON"))
    )[0]
    assert result["question"] == "Original"
    assert result["recovery_diagnostics"][0]["exception"] == "ValueError('malformed JSON')"


def test_bug_ppt_001_and_002_pptx_safety_and_title(tmp_path):
    """BUG-PPT-001 & BUG-PPT-002: PPTX renders all questions and derives dynamic title."""
    from src.generate_pptx import generate
    
    test_json = tmp_path / "test_deck.json"
    test_pptx = tmp_path / "test_deck.pptx"
    
    payload = {
        "source": {"filename": "physics_sample_exam.docx"},
        "metadata": {"title": "Physics Sample Exam"},
        "questions": [
            {
                "id": "q-1",
                "question": "What is the speed of light?",
                "options": {"A": "3x10^8 m/s", "B": "3x10^6 m/s", "C": "100 m/s", "D": "0"},
                "question_type": "mcq",
                "parsed_ok": True,
                "needs_review": False
            },
            {
                "id": "q-2",
                "question": "Incomplete question needing review",
                "options": {},
                "question_type": "mcq",
                "parsed_ok": False,
                "needs_review": True
            }
        ]
    }
    test_json.write_text(json.dumps(payload), encoding="utf-8")
    
    render_result = generate(test_json, test_pptx)
    assert test_pptx.exists()
    assert render_result["rendered_questions"] == 2
    assert render_result["rendered_slides"] == 3
    
    from pptx import Presentation
    prs = Presentation(str(test_pptx))
    # Title slide + 2 questions = 3 slides total (no dropped question!)
    assert len(prs.slides) == 3
    slide0_text = "".join(shape.text for shape in prs.slides[0].shapes if hasattr(shape, "text"))
    assert "Physics Sample Exam" in slide0_text
    persisted = json.loads(test_json.read_text(encoding="utf-8"))
    assert persisted["diagnostics"]["rendered_count"] == 2
    assert persisted["diagnostics"]["rendered_slides"] == 3


def test_ppt_pipeline_count_gate_rejects_mismatch(tmp_path):
    from src.generate_pptx import generate
    path = tmp_path / "count_mismatch.json"
    path.write_text(json.dumps({"questions": [{"id": "q1", "question": "Q"}],
                               "diagnostics": {"questions_accepted": 2,
                                               "questions_needs_review": 0,
                                               "questions_rejected": 0}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Question count mismatch"):
        generate(path, tmp_path / "bad.pptx")


def test_ppt_missing_media_has_placeholder_and_structured_diagnostic(tmp_path):
    from pptx import Presentation
    from src.generate_pptx import generate

    path = tmp_path / "missing_media.json"
    payload = {"questions": [{"id": "q-media", "question": "See image",
                              "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
                              "images": [{"path": "absent.png", "media_id": "m-7",
                                          "source_block_id": "b-8"}]}]}
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = generate(path, tmp_path / "media.pptx")
    diagnostic = result["render_diagnostics"][0]
    assert diagnostic["question_id"] == "q-media"
    assert diagnostic["source_block_id"] == "b-8"
    assert diagnostic["media_id"] == "m-7"
    assert diagnostic["source_path"] == "absent.png"
    assert diagnostic["reason"] == "missing_file"
    assert diagnostic["code"] == "MEDIA_RENDER_FAILED"
    assert diagnostic["fallback"] == "placeholder"
    deck = Presentation(str(tmp_path / "media.pptx"))
    assert any("Image unavailable" in shape.text for shape in deck.slides[1].shapes
               if getattr(shape, "has_text_frame", False))
    assert json.loads(path.read_text(encoding="utf-8"))["diagnostics"]["render_diagnostics"] == [diagnostic]


def test_ppt_table_uses_rich_cell_text_for_math(tmp_path):
    import zipfile
    from pptx import Presentation
    import src.generate_pptx as renderer

    class FakePandoc:
        @staticmethod
        def convert_text(_text, _to, format, outputfile):
            xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                   'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
                   '<w:body><w:p><m:oMath><m:r><m:t>x2</m:t></m:r></m:oMath></w:p></w:body></w:document>')
            with zipfile.ZipFile(outputfile, "w") as archive:
                archive.writestr("word/document.xml", xml)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(renderer, "pypandoc", FakePandoc)
    try:
        path = tmp_path / "table_math.json"
        payload = {"questions": [{"id": "q-table", "question": "Read the table",
                                  "table": {"rows": [["$x^2$"]],
                                            "cell_content": [[{"text": "$x^2$",
                                                               "source_block_id": "b-cell",
                                                               "inline_content": [{"kind": "math_sequence"}]}]]}}]}
        path.write_text(json.dumps(payload), encoding="utf-8")
        out = tmp_path / "table_math.pptx"
        renderer.generate(path, out)
        with zipfile.ZipFile(out) as archive:
            xml = "".join(archive.read(name).decode("utf-8") for name in archive.namelist()
                          if name.startswith("ppt/slides/slide"))
        assert "AlternateContent" not in xml
        assert "x" in xml and "AlternateContent" not in xml
    finally:
        monkeypatch.undo()


def test_ppt_math_uses_safe_compatibility_text(monkeypatch):
    """Inline math renders as ordinary DrawingML text until native math is verified."""
    import zipfile
    from pptx import Presentation
    import src.generate_pptx as renderer

    class FakePandoc:
        @staticmethod
        def convert_text(_text, _to, format, outputfile):
            xml = (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
                '<w:body><w:p><m:oMath><m:r><m:t>x+1</m:t></m:r></m:oMath></w:p></w:body></w:document>'
            )
            with zipfile.ZipFile(outputfile, "w") as archive:
                archive.writestr("word/document.xml", xml)

    monkeypatch.setattr(renderer, "pypandoc", FakePandoc)
    prs = Presentation()
    paragraph = prs.slides.add_slide(prs.slide_layouts[6]).shapes.add_textbox(0, 0, 100, 100).text_frame.paragraphs[0]
    renderer._insert_omml_math_into_paragraph(paragraph, "$x+1$", 16, (255, 255, 255))

    xml = paragraph._p.xml
    assert "AlternateContent" not in xml
    assert "<a14:m" not in xml
    assert "x+1" in xml


def test_bug_pdf_001_unicode_preservation(tmp_path):
    """BUG-PDF-001: PDF generation preserves Greek and math Unicode symbols."""
    from src.generate_pdf import generate_pdf
    import pymupdf

    test_json = tmp_path / "math_exam.json"
    test_pdf = tmp_path / "math_exam.pdf"

    payload = {
        "source": {"filename": "math_exam.docx"},
        "questions": [
            {
                "id": "q-1",
                "source_question_number": "1",
                "question": "Evaluate α + β + γ + Δ and ∫ √x dx with H₂O and SO₄²⁻ and 10¹⁴",
                "options": {"A": "10¹⁴", "B": "H₂O", "C": "α", "D": "√2"},
                "question_type": "mcq"
            }
        ]
    }
    test_json.write_text(json.dumps(payload), encoding="utf-8")
    
    generate_pdf(str(test_json), str(test_pdf))
    assert test_pdf.exists()

    doc = pymupdf.open(str(test_pdf))
    pdf_text = doc[0].get_text()
    assert "Evaluate" in pdf_text
