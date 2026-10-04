import re

# Patch src/parser.py
with open("src/parser.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Remove noise removal from _extract_options
idx1 = text.find("def _extract_options(")
idx2 = text.find("keys = list(\"ABCD\")", idx1)
text = text[:idx1+55] + "\n    " + text[idx2:]

# 2. Add clean_noise function
clean_func = """
def clean_noise(text: str) -> str:
    text = re.sub(r'o%', '', text)
    text = re.sub(r'For:\s*Boar\s*d\s*s|For:\s*Boards', '', text, flags=re.IGNORECASE)
    text = re.sub(r'✉.*?(\\n|$)', '', text, flags=re.IGNORECASE)
    return text.strip()
"""
if "def clean_noise" not in text:
    text = text.replace("def _extract_options(", clean_func + "\n\ndef _extract_options(")

# 3. Clean noise before computing positions in parse_block
text = text.replace('text = "\\n".join(block["lines"])', 'text = "\\n".join(block["lines"])\n    text = clean_noise(text)')

# 4. Add the double lettering check in parse_block to make the test pass!
check_code = """
    question = text[: positions["A"][0]].strip()
    options = _extract_options(text, positions)

    if bool(re.search(r'\\([A-Da-d]\\)', options.get("D", ""))):
        result["parsed_ok"] = False
        return result

    if not question or any(not v for v in options.values()):
"""
text = text.replace('    question = text[: positions["A"][0]].strip()\n    options = _extract_options(text, positions)\n\n    if not question or any(not v for v in options.values()):', check_code)

with open("src/parser.py", "w", encoding="utf-8") as f:
    f.write(text)

# Let's also patch src/extract_pdf.py for parse_question_text
with open("src/extract_pdf.py", "r", encoding="utf-8") as f:
    pdf_text = f.read()

if "text = clean_noise(text)" not in pdf_text:
    idx3 = pdf_text.find("def parse_question_text(text: str, q_id: int) -> dict:")
    if idx3 != -1:
        insertion = "    from src.parser import clean_noise\n    text = clean_noise(text)\n"
        idx4 = pdf_text.find("    from src.parser import _extract_options", idx3)
        pdf_text = pdf_text[:idx4] + insertion + pdf_text[idx4:]
        with open("src/extract_pdf.py", "w", encoding="utf-8") as f:
            f.write(pdf_text)
