import json
import sys
import os
from pathlib import Path

try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None

def _get_unicode_font():
    candidate_fonts = [
        r"C:\Windows\Fonts\seguisym.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for font_path in candidate_fonts:
        if os.path.exists(font_path):
            return font_path
    return None

def generate_pdf(json_path, pdf_path):
    if not pymupdf:
        sys.exit("[ERROR] pymupdf is required for Unicode PDF generation. Run: pip install pymupdf")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    questions = data.get("questions", []) if isinstance(data, dict) else data
    if not isinstance(questions, list):
        questions = []
    render_diagnostics = []
    try:
        from src.formula_render import latex_to_readable
    except ImportError:
        latex_to_readable = lambda text: str(text or "")

    doc = pymupdf.open()
    font_file = _get_unicode_font()
    font_name = "UniFont" if font_file else "helv"

    page_width, page_height = 595, 842  # Standard A4 in points
    margin = 50
    usable_width = page_width - (2 * margin)
    content_bottom_limit = page_height - margin - 20

    current_page = None
    y_pos = margin

    def add_page():
        nonlocal current_page, y_pos
        current_page = doc.new_page(width=page_width, height=page_height)
        if font_file:
            current_page.insert_font(fontname=font_name, fontfile=font_file)

        # Header
        current_page.insert_text(
            (margin, 35),
            "Structured Question Export",
            fontname=font_name,
            fontfile=font_file,
            fontsize=12
        )
        # Separator line
        current_page.draw_line(
            pymupdf.Point(margin, 42),
            pymupdf.Point(page_width - margin, 42),
            color=(0.7, 0.7, 0.7),
            width=0.5
        )
        y_pos = margin

    def ensure_space(needed_height):
        nonlocal current_page, y_pos
        if current_page is None or (y_pos + needed_height > content_bottom_limit):
            add_page()

    def print_block(text, fontsize=10, is_bold=False, indent=0, space_after=4):
        nonlocal current_page, y_pos
        if not text:
            return
        text = latex_to_readable(str(text))
        rect = pymupdf.Rect(margin + indent, y_pos, page_width - margin, content_bottom_limit)
        # Measure or insert
        res = current_page.insert_textbox(
            rect,
            text,
            fontname=font_name,
            fontfile=font_file,
            fontsize=fontsize
        )
        if res < 0:
            # Did not fit completely, start a new page
            add_page()
            rect = pymupdf.Rect(margin + indent, y_pos, page_width - margin, content_bottom_limit)
            res = current_page.insert_textbox(
                rect,
                text,
                fontname=font_name,
                fontfile=font_file,
                fontsize=fontsize
            )
        consumed = rect.height - max(0.0, res)
        y_pos += consumed + space_after

    add_page()
    current_section = None

    def add_image(question, image_item, image_index):
        nonlocal current_page, y_pos
        image_path = (image_item.get("path") or image_item.get("filename")
                      if isinstance(image_item, dict) else str(image_item or ""))
        source_block_id = image_item.get("source_block_id") if isinstance(image_item, dict) else None
        media_id = image_item.get("id") if isinstance(image_item, dict) else None
        candidates = [Path(image_path), Path(json_path).parent / image_path, Path.cwd() / image_path]
        path = next((candidate for candidate in candidates if candidate.is_file()), None)
        if path is None:
            render_diagnostics.append({
                "code": "MEDIA_RENDER_FAILED", "severity": "warning",
                "question_id": question.get("id"), "component_id": f"image:{image_index + 1}",
                "source_block_id": source_block_id,
                "node_id": media_id or f"image-{image_index + 1}",
                "reason": "missing_file", "source_path": image_path,
                "fallback": "visible placeholder",
            })
            print_block("[Image unavailable]", fontsize=9, indent=15)
            return
        try:
            if path.suffix.lower() == ".pdf":
                with pymupdf.open(str(path)) as image_doc:
                    pix = pymupdf.Pixmap(image_doc, 0)
                    import tempfile
                    tmp_img = Path(tempfile.gettempdir()) / f"pdf_media_{question.get('id')}_{image_index}.png"
                    pix.save(str(tmp_img))
                    path = tmp_img
            ensure_space(185)
            image_rect = pymupdf.Rect(margin + 15, y_pos, page_width - margin, y_pos + 180)
            current_page.insert_image(image_rect, filename=str(path), keep_proportion=True)
            y_pos += 185
        except Exception as exc:
            render_diagnostics.append({
                "code": "MEDIA_RENDER_FAILED", "severity": "warning",
                "question_id": question.get("id"), "component_id": f"image:{image_index + 1}",
                "source_block_id": source_block_id,
                "node_id": media_id or f"image-{image_index + 1}",
                "reason": repr(exc), "source_path": image_path,
                "fallback": "visible placeholder",
            })
            print_block("[Image unavailable]", fontsize=9, indent=15)

    for q in questions:
        sec_title = q.get("section") or "General"
        if sec_title != current_section:
            ensure_space(35)
            print_block(f"\nSection: {sec_title}", fontsize=13, is_bold=True, space_after=6)
            current_section = sec_title

        src_no = q.get("source_question_number") or q.get("id") or "?"
        q_type = q.get("question_type", "mcq")
        q_header = f"Question {src_no} [{q_type.upper()}]"
        
        ensure_space(30)
        print_block(q_header, fontsize=11, is_bold=True, space_after=3)
        print_block(str(q.get("question") or ""), fontsize=10, space_after=4)

        for image_index, image_item in enumerate(q.get("images", []) or []):
            add_image(q, image_item, image_index)

        for stmt in q.get("statements", []):
            if isinstance(stmt, dict):
                lbl = stmt.get("label", "")
                txt = stmt.get("text", "")
                print_block(f"{lbl}. {txt}" if lbl else txt, fontsize=9.5, indent=15, space_after=2)
            elif isinstance(stmt, str):
                print_block(stmt, fontsize=9.5, indent=15, space_after=2)

        for sub in q.get("subparts", []):
            if isinstance(sub, dict):
                lbl = sub.get("label", "")
                txt = sub.get("text", "")
                print_block(f"({lbl}) {txt}" if lbl else txt, fontsize=9.5, indent=15, space_after=2)
            elif isinstance(sub, str):
                print_block(sub, fontsize=9.5, indent=15, space_after=2)

        opts = q.get("options", {})
        if isinstance(opts, dict):
            for k in ("A", "B", "C", "D"):
                if k in opts and opts[k]:
                    print_block(f"({k}) {opts[k]}", fontsize=9.5, indent=15, space_after=2)
            for k, v in opts.items():
                if k not in ("A", "B", "C", "D") and v:
                    print_block(f"({k}) {v}", fontsize=9.5, indent=15, space_after=2)
        elif isinstance(opts, list):
            for item in opts:
                if isinstance(item, dict):
                    lbl = item.get("label", "")
                    txt = item.get("text", "")
                    print_block(f"({lbl}) {txt}", fontsize=9.5, indent=15, space_after=2)

        table_values = q.get("table")
        tables = ([table_values] if isinstance(table_values, dict) else []) + [
            item for item in (q.get("tables") or []) if isinstance(item, dict)]
        for table in tables:
            for row_index, row in enumerate(table.get("rows", [])):
                if not isinstance(row, list):
                    continue
                rich_row = (table.get("cell_content", [])[row_index]
                            if row_index < len(table.get("cell_content", [])) else [])
                cells = []
                for cell_index, value in enumerate(row):
                    rich_cell = (rich_row[cell_index] if cell_index < len(rich_row) else {})
                    cells.append(str((rich_cell or {}).get("text", value) or ""))
                print_block("    |    ".join(cells), fontsize=9.5, indent=15)

        y_pos += 8  # Separation between questions

    # Add page numbers in footer
    total_pages = len(doc)
    for pno, page in enumerate(doc, 1):
        if font_file:
            page.insert_font(fontname=font_name, fontfile=font_file)
        page.insert_text(
            (page_width / 2 - 20, page_height - 25),
            f"Page {pno} of {total_pages}",
            fontname=font_name,
            fontfile=font_file,
            fontsize=8,
            color=(0.4, 0.4, 0.4)
        )

    out_p = Path(pdf_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_p))
    doc.close()
    print(f"[OK] Saved PDF -> {out_p}")
    result = {"rendered_questions": len(questions), "output_path": str(out_p),
              "render_diagnostics": render_diagnostics}
    if isinstance(data, dict):
        data.setdefault("diagnostics", {})["pdf_render"] = {
            "rendered_count": len(questions), "page_count": total_pages,
            "status": "degraded" if render_diagnostics else "rendered",
            "render_diagnostics": render_diagnostics,
        }
        for question in questions:
            if isinstance(question, dict):
                per_question = [item for item in render_diagnostics
                                if str(item.get("question_id")) == str(question.get("id"))]
                question.setdefault("render", {})["pdf"] = {
                    "status": "degraded" if per_question else "rendered",
                    "diagnostics": per_question,
                }
        Path(json_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return result

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.generate_pdf <input.json> <output.pdf>")
        sys.exit(1)
    generate_pdf(sys.argv[1], sys.argv[2])
