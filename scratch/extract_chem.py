import json
from src.extract_pdf import extract_pdf_questions
from src.parser import parse_all

out = extract_pdf_questions("data/tests/chemistry.pdf")
# out is a list of strings? Let me check what extract_pdf_questions returns.
# Oh, extract_pdf_questions currently returns a list of dictionaries with "lines" or something?
# Let's import stage1 and see how it works.
import sys
# Wait, let's just run stage1.py directly since it does exactly this.
