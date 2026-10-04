import sys
sys.stdout.reconfigure(encoding='utf-8')
from src.extract_pdf import extract_pdf_questions
qs = extract_pdf_questions('data/chemistry.pdf')
for q in qs:
    if '52.' in str(q.get('question', '')):
        print(f"ID {q['id']} extracted options: {q.get('options')}")
