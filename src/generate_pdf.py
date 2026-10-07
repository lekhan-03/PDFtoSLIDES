import json
import sys
import os
from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "Structured Question Export", 0, 1, "C")

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")

def clean_text(text):
    if not text: return ""
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def generate_pdf(json_path, pdf_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    sections = {sec["id"]: sec["title"] for sec in data.get("sections", [])}
    
    current_section = None

    for q in data.get("questions", []):
        sec_title = q.get("section", "Unknown Section")
        if sec_title != current_section:
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, clean_text(sec_title), 0, 1, "L")
            current_section = sec_title
            
        pdf.set_font("Arial", "B", 11)
        src_no = q.get("source_question_number", "?")
        
        # Header info
        hdr_txt = f"Question {src_no} (ID: {q.get('id')}) - {q.get('question_type', 'unknown')}"
        pdf.cell(0, 8, clean_text(hdr_txt), 0, 1, "L")
        
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 6, clean_text(q.get("question", "")))
        
        for stmt in q.get("statements", []):
            pdf.set_font("Arial", "I", 11)
            pdf.multi_cell(0, 6, clean_text(f"  {stmt.get('label', '')}: {stmt.get('text', '')}"))
            
        for sub in q.get("subparts", []):
            pdf.set_font("Arial", "", 11)
            pdf.multi_cell(0, 6, clean_text(f"  ({sub.get('label', '')}) {sub.get('text', '')}"))
            
        opts = q.get("options", {})
        if opts:
            pdf.set_font("Arial", "", 11)
            for k, v in opts.items():
                pdf.multi_cell(0, 6, clean_text(f"  ({k}) {v}"))
        
        pdf.ln(5)

    pdf.output(pdf_path)
    print(f"[OK] Saved PDF -> {pdf_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_pdf.py <input.json> <output.pdf>")
        sys.exit(1)
    generate_pdf(sys.argv[1], sys.argv[2])
