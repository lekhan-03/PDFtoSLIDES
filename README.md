# MCQ → Slides: extraction & parsing stage

Converts a computer-typed MCQ PDF or Word doc into structured JSON.
Regex does the heavy lifting; Groq LLM is only called as a last resort —
in **one batched request** — for whatever the regex couldn't confidently parse.

---

## Project structure

```
mcq2slides/
├── src/
│   ├── extract_pdf.py    PyMuPDF text extraction + header/footer noise removal
│   ├── extract_docx.py   python-docx paragraph/table extraction
│   ├── parser.py         Regex splitting: text lines → {question, options}
│   ├── llm_fallback.py   ONE batched Groq call, only for regex failures
│   └── main.py           CLI: ties extraction → parsing → (optional) LLM
├── data/
│   └── questions.json    Generated output (re-created each run)
├── tests/
│   └── test_parser.py    pytest unit tests for the parser
├── config/
│   └── .env.example      Template for GROQ_API_KEY
├── requirements.txt
└── README.md
```

---

## Setup

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

---

## Usage

```bash
# Regex-only (default — no API key needed, zero tokens spent)
python -m src.main data/input.pdf  data/questions.json
python -m src.main data/input.docx data/questions.json

# Fix regex failures via Groq LLM (free tier available)
# Windows PowerShell
$env:GROQ_API_KEY = "gsk_..."
# Linux / macOS
export GROQ_API_KEY="gsk_..."

python -m src.main data/input.pdf data/questions.json --use-llm
```

### Override the Groq model

```bash
# Use the lighter 8B model for faster/cheaper inference
$env:MCQ_LLM_MODEL = "llama3-8b-8192"
python -m src.main data/input.pdf data/questions.json --use-llm
```

Available models: `llama-3.3-70b-versatile` (default) · `llama3-8b-8192` · `mixtral-8x7b-32768`
Get a free Groq key at <https://console.groq.com>.

---

## Pipeline

```
PDF / DOCX
    ↓
extract_pdf.py / extract_docx.py   →   clean text lines
    ↓
parser.py (regex)                  →   question blocks  +  failed blocks
    ↓  (only failed blocks)
llm_fallback.py (Groq, optional)   →   fixed question dicts
    ↓
questions.json
```

---

## How the LLM stays minimal

| Concern | Behaviour |
|---------|-----------|
| Cost | Only `parsed_ok: False` blocks are ever sent — never the whole doc |
| Latency | All failures go in **one** batched request, not one call per question |
| Default | LLM is **opt-in** via `--use-llm`; regex handles ≥99% of questions |
| Model | Groq free tier is plenty; `llama-3.3-70b-versatile` is the default |

On the sample chemistry PDF the regex parsed **194/195** questions with **zero** API calls.

---

## Known parser edge case

"Match the column" questions (e.g. Q38, Q111 in the sample PDF) can contain
two lettered (A)–(D) sequences: one for column labels, one for real answer
options. The parser detects this and marks them `parsed_ok: False` with
`review_reason` set, rather than silently grabbing the wrong sequence.
Pass `--use-llm` or fix them manually in the JSON.

---

## Tests

```bash
python -m pytest tests/ -v
```

---

## Next steps (not built yet)

- Answer-key merge (fill in the `answer` field from a separate key sheet)
- `python-pptx` slide generator that reads `questions.json`
