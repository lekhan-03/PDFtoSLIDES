
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

def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)

_load_dotenv()
import os

from src.extract_docx import extract_docx_blocks
from src.parser_v2 import run_pipeline

def auto_output_path(in_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    stem = in_path.stem
    filename = f"{stem}_{timestamp}.json"
    return Path("data") / "outputs" / filename

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Path to .pdf or .docx file")
    ap.add_argument("output", nargs="?", default=None)
    ap.add_argument("--use-llm", action="store_true")
    ap.add_argument("--debug", action="store_true")
    return ap

def main() -> None:
    args = build_parser().parse_args()
    in_path = Path(args.input)
    if not in_path.exists():
        sys.exit(f"❌ Input file not found: {in_path}")

    out_path = Path(args.output) if args.output else auto_output_path(in_path)
    print(f"📁 Output will be written to: {out_path}")

    print(f"📄 Extracting structure from: {in_path}")
    if in_path.suffix.lower() == ".docx":
        blocks = extract_docx_blocks(str(in_path))
        print(f"    → {len(blocks)} document blocks extracted")
        
        if args.debug:
            debug_dir = out_path.parent / f"{in_path.stem}_debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            with open(debug_dir / "raw_blocks.json", "w", encoding="utf-8") as f:
                json.dump([b.to_dict() for b in blocks], f, indent=2, ensure_ascii=False)
    else:
        from src.extract_pdf import extract_pdf_blocks
        blocks = extract_pdf_blocks(str(in_path))
        print(f"    → {len(blocks)} document blocks extracted")
        
        if args.debug:
            debug_dir = out_path.parent / f"{in_path.stem}_debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            with open(debug_dir / "raw_blocks.json", "w", encoding="utf-8") as f:
                json.dump([b.to_dict() for b in blocks], f, indent=2, ensure_ascii=False)
                
    parsed_data = run_pipeline(blocks)
    if isinstance(parsed_data, dict) and "questions" in parsed_data:
        parsed_questions = parsed_data["questions"]
        if "source" in parsed_data:
            parsed_data["source"]["filename"] = in_path.name
            parsed_data["source"]["file_type"] = in_path.suffix.lower().lstrip(".")
        parsed_to_save = parsed_data
        
        if args.debug:
            with open(debug_dir / "parsed_questions.json", "w", encoding="utf-8") as f:
                json.dump(parsed_questions, f, indent=2, ensure_ascii=False)
    else:
        parsed_questions = parsed_data
        parsed_to_save = parsed_data
        
        if args.debug:
            with open(debug_dir / "parsed_questions.json", "w", encoding="utf-8") as f:
                json.dump(parsed_questions, f, indent=2, ensure_ascii=False)
        
    failed = [q for q in parsed_questions if not q.get("parsed_ok")]
    
    print(f"✅ Parsed : {len(parsed_questions)} questions")
    if failed:
        print(f"⚠️ Failed : {len(failed)} question(s)")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(parsed_to_save, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"💾 Wrote questions → {out_path}")

if __name__ == "__main__":
    main()
