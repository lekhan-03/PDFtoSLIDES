import json
from src.parser import parse_block
from src.extract_pdf import extract_pdf_questions

items = extract_pdf_questions('data/tests/chemistry.pdf')
for b in items:
    text = '\n'.join(b['lines'])
    if 'Cl2' in text and 'Application Based Questions' in text:
        print("FOUND BLOCK!")
        rs = parse_block(b)
        print("PARSE_BLOCK RESULT:", rs)
