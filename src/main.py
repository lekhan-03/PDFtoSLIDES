"""CLI entry point — MCQ PDF/DOCX → structured questions.json

Usage (run from project root):
    # Output auto-named: data/outputs/<stem>_YYYYMMDD_HHMMSS.json
    python -m src.main data/chemistry.pdf
    python -m src.main data/chemistry.docx

    # Explicit output path
    python -m src.main data/chemistry.pdf data/my_output.json

    # Fix regex failures via Groq LLM
    python -m src.main data/chemistry.pdf --use-llm

Each run always writes a NEW file — no data is ever overwritten.
Output folder: data/outputs/  (created automatically).

.env keys used:
    GROQ_API_KEY  – required when --use-llm is passed
    GROQ_MODEL    – Groq model name  (default: llama-3.3-70b-versatile)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Load .env FIRST so every subsequent os.environ.get() sees the values ──────
def _load_dotenv() -> None:
    """Load .env from the project root (two levels up from this file: src/ → root)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        # python-dotenv not installed — env vars must be set manually
        return
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)  # real env vars win over .env

_load_dotenv()
# ──────────────────────────────────────────────────────────────────────────────

import os  # noqa: E402  (imported after dotenv intentionally)

# Support both `python -m src.main` (package) and `python src/main.py` (direct)
try:
    from src.parser import parse_all
except ModuleNotFoundError:
    from parser import parse_all  # type: ignore[no-redef]


# ── Extraction ─────────────────────────────────────────────────────────────────

def get_lines(path: Path) -> list[str]:
    """Dispatch to the correct extractor based on file extension."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            from src.extract_pdf import extract_pdf_questions
        except ModuleNotFoundError:
            from extract_pdf import extract_pdf_questions  # type: ignore[no-redef]
        return extract_pdf_questions(str(path))
    elif suffix == ".docx":
        try:
            from src.extract_docx import extract_lines
        except ModuleNotFoundError:
            from extract_docx import extract_lines  # type: ignore[no-redef]
        return extract_lines(str(path))
    else:
        raise ValueError(f"Unsupported file type: '{path.suffix}'. Use .pdf or .docx")


# ── Output path helpers ────────────────────────────────────────────────────────

def auto_output_path(in_path: Path) -> Path:
    """Build a unique output path from the input filename + current timestamp.

    Example:  data/chemistry_2026_09_29_104500.json
    The 'data/outputs/' folder is created automatically if it doesn't exist.
    """
    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    stem = in_path.stem          # e.g. "chemistry"  (no extension)
    filename = f"{stem}_{timestamp}.json"
    return Path("data") / "outputs" / filename


# ── CLI ────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Convert an MCQ PDF/DOCX into structured JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("input", help="Path to .pdf or .docx file")
    ap.add_argument(
        "output",
        nargs="?",
        default=None,
        help=(
            "Path to write the output JSON. "
            "If omitted, a new timestamped file is created automatically in data/outputs/"
        ),
    )
    ap.add_argument(
        "--use-llm",
        action="store_true",
        help="Send regex-failed blocks to Groq LLM fallback (needs GROQ_API_KEY in .env)",
    )
    return ap


def main() -> None:
    args = build_parser().parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        sys.exit(f"❌  Input file not found: {in_path}")

    # Resolve output path — auto-generate a unique timestamped name if not given
    out_path = Path(args.output) if args.output else auto_output_path(in_path)
    print(f"📁  Output will be written to: {out_path}")

    # ── Extract ────────────────────────────────────────────────────────────────
    print(f"📄  Extracting text from: {in_path}")
    if in_path.suffix.lower() == ".pdf":
        all_questions = get_lines(in_path)
        parsed = [q for q in all_questions if q.get("parsed_ok")]
        failed = [q for q in all_questions if not q.get("parsed_ok")]
        print(f"    → {len(all_questions)} questions extracted via geometry")
    else:
        lines = get_lines(in_path)
        print(f"    → {len(lines)} lines extracted")
        # ── Parse (regex) ──────────────────────────────────────────────────────────
        parsed, failed = parse_all(lines)
        
    print(f"✅  Regex parsed : {len(parsed)} questions")
    if failed:
        print(f"⚠️   Regex failed : {len(failed)} question(s)  →  ids: {[b['id'] for b in failed]}")
    else:
        print("✅  Regex failed : 0 questions")

    # ── LLM fallback (optional) ────────────────────────────────────────────────
    if failed:
        if args.use_llm:
            try:
                from src.llm_fallback import fix_with_llm
            except ModuleNotFoundError:
                from llm_fallback import fix_with_llm  # type: ignore[no-redef]

            model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
            print(f"🤖  Sending {len(failed)} failed block(s) to Groq [{model}] …")
            fixed = fix_with_llm(failed)
            parsed.extend(fixed)
            print(f"✅  Groq fixed   : {len(fixed)} question(s)")
        else:
            print(
                "ℹ️   Skipping LLM fallback (pass --use-llm to enable). "
                "Failed blocks will appear in output with parsed_ok=False."
            )
            for b in failed:
                parsed.append({
                    "id":        b["id"],
                    "section":   b["section"],
                    "question":  " ".join(b["lines"]) if "lines" in b else (b.get("question") or ""),
                    "options":   {},
                    "answer":    None,
                    "parsed_ok": False,
                })

    # ── Write output ───────────────────────────────────────────────────────────
    
    # Apply corrections if they exist
    corr_path = Path(f"data/corrections/{in_path.stem}.json")
    if corr_path.exists():
        from src.corrections import apply_corrections
        corr_dict = json.loads(corr_path.read_text(encoding="utf-8"))
        parsed = apply_corrections(parsed, corr_dict)

    # Sort using _sort_order if available, to preserve divider positions
    parsed.sort(key=lambda q: q.get("_sort_order", q.get("id") if q.get("id") is not None else float("inf")))
    
    # Remove _sort_order
    for q in parsed:
        if "_sort_order" in q:
            del q["_sort_order"]
            
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"💾  Wrote {len(parsed)} questions → {out_path}")

    still_bad = [q["id"] for q in parsed if not q.get("parsed_ok", True)]
    if still_bad:
        print(f"⚠️   NEEDS MANUAL REVIEW: question ids {still_bad}")
    else:
        print("✅  All questions parsed successfully.")


if __name__ == "__main__":
    main()
