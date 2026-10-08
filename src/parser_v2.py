import re
from typing import List, Dict, Any, Tuple, Optional
from src.document_model import DocumentBlock

# ── Regex Constants ──────────────────────────────────────────

_OPTION_LABEL_RE = re.compile(
    r'^(?:\([A-Da-d]\)|(?<!-)[A-Da-d][.)]\s)', re.IGNORECASE)
OPTION_RE_TEMPLATE = r"(?:(?<!-)\({L}\)|(?<![a-zA-Z0-9-])\b{L}\.(?=\s|$)|(?<![a-zA-Z0-9(-])\b{L}\)(?=\s|$))\s*"

_MARKS_HEADER_RE = re.compile(
    r'^\d+\s+[Mm]arks?(\s*\(.*?\))?\s*$', re.IGNORECASE)
_KNOWN_SECTION_HEADERS_RE = re.compile(
    r'^(?:Multiple Choice Questions|Fill in the blanks?(\s*\(.*?\))?|FIB|'
    r'Match the (?:following|column)|Assertion and Reason|'
    r'Very Short Answer Questions?|Short Answer Questions?|Long Answer Questions?|'
    r'(?:Section|Part)\s+[A-Z\d]+(?:\s*[:\-–—].*)?|'
    r'Physics|Chemistry|Biology|'
    r'Previous Years Questions|NCERT Based Questions)\s*$',
    re.IGNORECASE
)
_NON_SECTION_STARTERS = re.compile(
    r'^(?:Define|State|Explain|Evaluate|Find|Integrate|Calculate|Prove|Show|Verify|Determine|Solve|Write|Give|Name|Mention)\b',
    re.IGNORECASE
)
_Q_NUM_RE = re.compile(r'^(\d+)(?:\.(?!\d)|\))\s+(.*)$')

# ── Metadata Extraction ──────────────────────────────────────


def is_math_or_chem(content: str) -> bool:
    if re.search(r'[+=\<\>\*/∈∞π]', content):
        return True
    if re.search(r'\b[a-zA-Z]\s*∈', content):
        return True
    m = re.match(r'^\s*(\d+)\s*,\s*(\d+)\s*$', content)
    if m:
        y1, y2 = m.groups()
        if len(y1) == 4 and len(y2) == 4 and y1.startswith(('19', '20')) and y2.startswith(('19', '20')):
            return False  # it's metadata (e.g. 2017,2019)
        return True
    return False


def extract_metadata_spans(text: str) -> Tuple[str, List[str]]:
    pattern = r'(\[([^\]]+)\]|\(([^)]+)\))'
    matches = list(re.finditer(pattern, text))
    cleaned_text = text
    appearances = []

    for m in reversed(matches):
        raw = m.group(1)
        content = m.group(2) if m.group(2) is not None else m.group(3)

        # Avoid extracting scientific brackets like [Fe(CN)6]3-
        if not re.search(r'\b(?:19|20)\d{2}(?![0-9])', content):
            continue

        if is_math_or_chem(content):
            continue

        if ',' in content and re.match(r'^[\d\w\s,-]+$', content):
            parts = [p.strip() for p in content.split(',')]
            valid = True
            for p in parts:
                if not re.match(r'^\d{2,4}[a-zA-Z\d-]*$', p):
                    valid = False
            if valid:
                appearances.extend(reversed(parts))
                cleaned_text = cleaned_text[:m.start()] + \
                                                     cleaned_text[m.end():]
                continue

        appearances.append(content.strip())
        cleaned_text = cleaned_text[:m.start()] + cleaned_text[m.end():]

    appearances.reverse()
    return cleaned_text.strip(), appearances

# ── Pipeline ─────────────────────────────────────────────────


def run_pipeline(blocks: List[DocumentBlock], use_llm: bool = False) -> Dict[str, Any]:
    initial_block_ids = {b.block_id for b in blocks}
    cleaned_blocks = remove_noise(blocks)
    noise_block_ids = initial_block_ids - {b.block_id for b in cleaned_blocks}

    section_map = detect_sections(cleaned_blocks)

    for b in cleaned_blocks:
        if b.block_type == "paragraph":
            cleaned, apps = extract_metadata_spans(b.text)
            b.text = cleaned
            if apps:
                if 'appearances' not in b.metadata:
                    b.metadata['appearances'] = []
                b.metadata['appearances'].extend(apps)

    split_blocks = split_inline_options(cleaned_blocks)
    for b in split_blocks:
        if "parent_block_id" in b.metadata and b.metadata["parent_block_id"] in section_map:
            section_map[b.block_id] = section_map[b.metadata["parent_block_id"]]

    candidates = build_question_candidates(split_blocks, section_map)

    parsed = []
    global_id = 1

    for cand in candidates:
        q_dict = reconstruct_components(cand)
        q_dict["id"] = global_id
        global_id += 1

        q_dict = extract_features(q_dict)
        q_dict = classify_question(q_dict)

        parsed.append(q_dict)

    final_questions = recover_and_validate(parsed)

    # Optional LLM recovery if requested (BUG-LLM-001 / BUG-FBK-001)
    if use_llm:
        try:
            from src.llm_fallback import recover_questions_batch
            final_questions = recover_questions_batch(final_questions)
            final_questions = recover_and_validate(final_questions)
        except Exception as e:
            print(f"⚠️ LLM recovery skipped: {e}")

    # Citation-only paragraphs have no candidate text after metadata extraction.
    # Attach them to the nearest preceding question (or the first following one)
    # so their source identity and appearances remain traceable.
    metadata_only = [b for b in cleaned_blocks
                     if b.block_type == "paragraph" and not b.text.strip()
                     and b.metadata.get("appearances")]
    order_by_id = {b.block_id: b.order for b in blocks}
    order_by_id.update({b.block_id: order_by_id.get(b.metadata.get("parent_block_id"), b.order)
                        for b in split_blocks if "parent_block_id" in b.metadata})
    for source_block in metadata_only:
        preceding = [q for q in final_questions if any(
            order_by_id.get(block_id, -1) < source_block.order
            for block_id in q.get("block_ids", []))]
        target = preceding[-1] if preceding else (final_questions[0] if final_questions else None)
        if target is None:
            continue
        target["appearances"] = list(dict.fromkeys(
            target.get("appearances", []) + source_block.metadata["appearances"]))
        if source_block.block_id not in target.setdefault("block_ids", []):
            target["block_ids"].append(source_block.block_id)
        source_refs = target.setdefault("source_blocks", [])
        if not any(ref.get("block_id") == source_block.block_id for ref in source_refs):
            source_refs.append({"block_id": source_block.block_id, "role": "metadata"})

    # BUG-DET-001: Extract unique sections preserving document appearance order
    unique_sections = list(dict.fromkeys(section_map.values()))
    sections_list = [{"id": f"section-{i+1}", "title": s}
        for i, s in enumerate(unique_sections)]

    # Source Block Ledger & Reconciliation (BUG-DIAG-001, BUG-DIAG-002)
    assigned_block_ids = []
    block_owners = {}
    for q in final_questions:
        for bid in q.get("block_ids", []):
            assigned_block_ids.append(bid)
            block_owners.setdefault(bid, []).append(q.get("id"))

    from collections import Counter
    counts = Counter(assigned_block_ids)
    duplicate_blocks = [bid for bid, count in counts.items() if count > 1]
    assigned_set = set(assigned_block_ids)

    orphan_blocks = []
    source_ledger = []
    for source in blocks:
        bid = source.block_id
        if bid in noise_block_ids:
            source_ledger.append({"source_block_id": bid, "status": "ignored_with_reason", "reason": "matched configured noise filter"})
            continue
        # If bid was split, check if its derived parts were assigned
        is_assigned = (bid in assigned_set) or any(
            isinstance(ab, str) and ab.startswith(f"{bid}.part_") for ab in assigned_set
        )
        if is_assigned:
            owner_id = next((qid for owned_id, owners in block_owners.items()
                             if owned_id == bid or (isinstance(owned_id, str) and owned_id.startswith(f"{bid}.part_"))
                             for qid in owners), None)
            source_ledger.append({"source_block_id": bid, "question_id": owner_id, "status": "consumed"})
            continue
        if not is_assigned:
            # Also check if it was a standalone section header
            if source.block_type == "paragraph" and is_section_header(source.text):
                source_ledger.append({"source_block_id": bid, "status": "ignored_with_reason", "reason": "section heading retained in section metadata"})
                continue
            orphan_blocks.append(bid)
            source_ledger.append({"source_block_id": bid, "status": "orphaned"})

    numbered = sum(1 for q in final_questions if q.get("source_question_number"))
    unnumbered = len(final_questions) - numbered
    subparts_count = sum(len(q.get("subparts", [])) for q in final_questions)
    tables_count = sum(1 for q in final_questions if q.get("table"))
    images_count = sum(len(q.get("images", [])) for q in final_questions)
    suspicious = sum(1 for q in final_questions if any("SUSPICIOUS" in issue for issue in q.get("validation", {}).get("issues", [])))
    
    accepted_count = sum(1 for q in final_questions if q.get("parsed_ok") and not q.get("needs_review"))
    # Keep outcome buckets disjoint so diagnostics reconcile to detected count.
    needs_review_count = sum(1 for q in final_questions if q.get("needs_review") and q.get("parsed_ok"))
    rejected_count = sum(1 for q in final_questions if not q.get("parsed_ok"))
    numbering_events = [q["numbering_event"] for q in final_questions
                        if q.get("numbering_event")
                        and q["numbering_event"].get("event") != "sequence"]

    print("\nParser Audit")
    print("-" * 23)
    print(f"Sections: {len(unique_sections)}")
    print(f"Questions: {len(final_questions)}")
    print(f"  Accepted: {accepted_count}")
    print(f"  Needs Review: {needs_review_count}")
    print(f"  Rejected: {rejected_count}")
    print(f"Numbered: {numbered}")
    print(f"Unnumbered: {unnumbered}")
    print(f"Subparts: {subparts_count}")
    print(f"Tables: {tables_count}")
    print(f"Images: {images_count}")
    print(f"Suspicious candidates: {suspicious}")
    print(f"Orphan blocks: {len(orphan_blocks)}")
    print(f"Duplicate block references: {len(duplicate_blocks)}\n")

    return {
        "schema_version": "2.0",
        "source": {
            "filename": "document",
            "file_type": "docx",
            "parser_version": "2.0.0"
        },
        "sections": sections_list,
        "questions": final_questions,
        "diagnostics": {
            "total_source_blocks": len(initial_block_ids),
            "total_questions": len(final_questions),
            "questions_detected": len(final_questions),
            "questions_accepted": accepted_count,
            "questions_needs_review": needs_review_count,
            "questions_rejected": rejected_count,
            "questions_flagged_for_review": sum(1 for q in final_questions if q.get("needs_review")),
            "orphan_blocks": orphan_blocks,
            "duplicate_blocks": duplicate_blocks,
            "source_ledger": source_ledger,
            "numbering_events": numbering_events,
            "warnings": [],
            "errors": []
        }
    }


def remove_noise(blocks: List[DocumentBlock]) -> List[DocumentBlock]:
    noise_patterns = [
        re.compile(
            r'\b(Crash Course|DPPs|PYQs|Mentorship|Doubt Sessions|Concept videos)\b', re.I),
        re.compile(r'^Join\b', re.I),
        re.compile(r'Paid Courses', re.I),
        re.compile(r'Subscribe to our', re.I),
        re.compile(r'For:\s*Boar\s*d\s*s', re.I),
        re.compile(r'✉', re.I)
    ]
    clean = []
    for b in blocks:
        if b.block_type == "paragraph":
            if any(p.search(b.text) for p in noise_patterns):
                continue
            if not b.text.strip():
                continue
        clean.append(b)
    return clean


def split_inline_options(blocks: List[DocumentBlock]) -> List[DocumentBlock]:
    new_blocks = []

    # We want to match (a) or a) or A. etc., but we MUST NOT match within a word.
    pattern = re.compile(
        r"((?:(?<!-)\([A-Da-d]\)|(?<![a-zA-Z0-9-])\b[A-Da-d]\.(?=\s|$)|(?<![a-zA-Z0-9(-])\b[A-Da-d]\)(?=\s|$))\s*)")

    for b in blocks:
        if b.block_type != "paragraph":
            new_blocks.append(b)
            continue

        text = b.text
        # Only split if we find at least TWO option labels in the SAME block,
        # OR if there's text before the first option label.
        matches = list(pattern.finditer(text))
        if not matches:
            new_blocks.append(b)
            continue

        # If there's only one match and it's exactly at the start, no need to split
        if len(matches) == 1 and matches[0].start() == 0:
            new_blocks.append(b)
            continue

        # Split it up with stable derived IDs (BUG-BLOCK-001)
        last_idx = 0
        part_idx = 1
        for m in matches:
            # Add text before this option if any
            if m.start() > last_idx:
                pre_text = text[last_idx:m.start()].strip()
                if pre_text:
                    sub_meta = b.metadata.copy()
                    sub_meta["parent_block_id"] = b.block_id
                    sub_meta["derived_part"] = part_idx
                    new_blocks.append(DocumentBlock(
                        block_id=f"{b.block_id}.part_{part_idx}",
                        block_type="paragraph",
                        text=pre_text,
                        order=b.order,
                        source=b.source,
                        metadata=sub_meta,
                        runs=b.runs,
                        inline_content=b.inline_content
                    ))
                    part_idx += 1
            last_idx = m.start()

        # Add the last option and its text
        if last_idx < len(text):
            post_text = text[last_idx:].strip()
            if post_text:
                sub_meta = b.metadata.copy()
                sub_meta["parent_block_id"] = b.block_id
                sub_meta["derived_part"] = part_idx
                new_blocks.append(DocumentBlock(
                    block_id=f"{b.block_id}.part_{part_idx}",
                    block_type="paragraph",
                    text=post_text,
                    order=b.order,
                    source=b.source,
                    metadata=sub_meta,
                    runs=b.runs,
                    inline_content=b.inline_content
                ))

    return new_blocks


def is_instruction(text: str) -> bool:
    t = text.lower()
    return "match list" in t or "choose the correct" in t or "consider the following" in t


def is_section_header(text: str) -> bool:
    stripped = text.strip()
    if stripped.upper() in ("MCQ", "MCQS", "MCQ'S", "MCQ’S", "EXPLANATION", "IMPORTANT", "NOTE", "II", "III", "IV"):
        return False
    if _MARKS_HEADER_RE.match(stripped) or _KNOWN_SECTION_HEADERS_RE.match(stripped):
        return True
    if len(stripped) < 3 or len(stripped) > 80:
        return False
    if re.match(r'^\d+\.?$', stripped):
        return False
    if _NON_SECTION_STARTERS.match(stripped):
        return False
    if _Q_NUM_RE.match(stripped) or _OPTION_LABEL_RE.match(stripped):
        return False

    # Exclude column headers, statements, and match items (BUG-BND-002)
    t_lower = stripped.lower()
    if re.search(r'\b(?:column\s*[iIvV\d]+|list\s*[-–—]?[iIvV\d]+|statement\s*[-–—]?[iIvV\d]+)\b', t_lower):
        return False
    if re.match(r'^(?:[ivxIVX]+|[a-eA-E])\b', stripped) and len(stripped.split()) <= 2:
        return False
    # Exclude math formulas
    if any(m in stripped for m in ('$', '\\int', '\\frac', '=', '∫', '∑', '√', '±', '→')):
        return False
    if is_instruction(text):
        return False

    words = stripped.split()
    if not words:
        return False
    if words[-1].lower() in ('is', 'are', 'be', 'of', 'the', 'for', 'a', 'an', 'as', 'to', 'in', 'on', 'with'):
        return False
    if stripped.endswith('?') or stripped.endswith('.') or stripped.endswith(','):
        return False

    significant_words = [w for w in words if w.lower() not in (
        'and', 'or', 'of', 'the', 'in', 'for', 'to', 'with')]
    if not significant_words:
        return False
    upper_words = sum(
        1 for w in significant_words if (w.rstrip(':.,') and (w.rstrip(':.,')[0].isupper() or w.rstrip(':.,')[0].isdigit())))
    return upper_words / len(significant_words) >= 0.7 and len(words) <= 10


def detect_sections(blocks: List[DocumentBlock]) -> Dict[int, str]:
    section_map = {}
    current_section = "General"
    for b in blocks:
        if b.block_type == "paragraph":
            if is_section_header(b.text):
                current_section = b.text.rstrip(':').strip()
        section_map[b.block_id] = current_section
    return section_map


def is_question_like_start(text: str) -> bool:
    t = text.strip()
    if not t: return False
    if re.match(r'^[\$∫∑√]', t): return True
    words = t.split()
    if not words: return False
    first = words[0].lower()
    if first in ["evaluate", "find", "calculate", "prove", "determine", "state", "explain", "derive",
                 "what", "which", "how", "why", "when", "where", "write", "solve", "show", "describe", "integrate"]:
        return True
    if "fill in the blank" in t.lower() or t.startswith("____"):
        return True
    if "match list" in t.lower(): return True
    return False

def detect_question_number(text: str) -> Optional[Dict[str, Any]]:
    t = text.strip()
    
    m_main = re.match(r'^(?:Q(?:uestion)?\s*(?:No\.?)?\s*|Q\.\s*)?0*(\d+)(?:[\.\):]|\s*-)(?:\s+|$)', t, re.IGNORECASE)
    if m_main:
        raw = m_main.group(0).strip()
        val = int(m_main.group(1))
        return {"raw": raw, "value": val, "kind": "main", "confidence": 0.9}
        
    m_sub = re.match(r'^(\d+)?\(([a-z]{1,3}|[ivx]+)\)(?:\s+|$)', t, re.IGNORECASE)
    if m_sub:
        raw = m_sub.group(0).strip()
        val = m_sub.group(2)
        return {"raw": raw, "value": val, "kind": "subpart", "confidence": 0.9}

    m_roman = re.match(r'^(X|IX|IV|V?I{0,3})\.(?:\s+|$)', t, re.IGNORECASE)
    if m_roman and m_roman.group(1).upper() in ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]:
        raw = m_roman.group(0).strip()
        return {"raw": raw, "value": m_roman.group(1).upper(), "kind": "roman", "confidence": 0.8}

    return None

def decide_boundary(
    current_cand: Optional[Dict[str, Any]], 
    b: DocumentBlock, 
    section_context: str, 
    section_transition: bool,
    num_info: Optional[Dict[str, Any]],
    numbering_context: Dict[str, Any],
    debug: bool = False
) -> Tuple[str, str]:
    if not current_cand:
        return "NEW_QUESTION", "No current candidate"
        
    if b.block_type == "table": return "CONTINUE", "Table continuation"
    if b.block_type == "image": return "CONTINUE", "Image continuation"
        
    text = b.text.strip()
    if not text: return "CONTINUE", "Empty text"
    
    p_blocks = [cb for cb in current_cand["blocks"] if cb.block_type == "paragraph"]
    text_so_far = " ".join([cb.text for cb in p_blocks])
    
    has_options = bool(re.search(OPTION_RE_TEMPLATE.format(L="[Aa]"), text_so_far, re.I)) and \
                  bool(re.search(OPTION_RE_TEMPLATE.format(L="[Bb]"), text_so_far, re.I)) and \
                  bool(re.search(OPTION_RE_TEMPLATE.format(L="[Cc]"), text_so_far, re.I)) and \
                  bool(re.search(OPTION_RE_TEMPLATE.format(L="[Dd]"), text_so_far, re.I))
                  
    signals = {
        "question_number": 0.0,
        "section_change": 0.0,
        "candidate_complete": 0.0,
        "new_question_like": 0.0,
        "continuation": 0.0,
        "subpart": 0.0
    }
    
    ends_sentence = False
    if text_so_far and text_so_far.strip().endswith(('.', '?', '!', ':', ']', ')', '$')):
        ends_sentence = True
        
    cand_seems_complete = ends_sentence or has_options
    if cand_seems_complete:
        signals["candidate_complete"] = 0.8
        
    decision = "CONTINUE"
    reason = "Default to continue"

    # 1. Main Question Number
    if num_info and num_info["kind"] == "main":
        signals["question_number"] = 0.95
        decision = "NEW_QUESTION"
        reason = "Strong main-question marker"
        if cand_seems_complete:
            reason += " + completed previous candidate"
    elif num_info and num_info["kind"] in ("subpart", "roman"):
        signals["subpart"] = 0.9
        decision = "CONTINUE"
        reason = "Subpart/Roman numeral"
    elif section_transition:
        # BUG-BND-001: Only split if current candidate is substantial
        if current_cand["blocks"] and (has_options or num_info or is_question_like_start(text)):
            signals["section_change"] = 0.9
            decision = "NEW_QUESTION"
            reason = "Section transition"
        else:
            signals["section_change"] = 0.4
            decision = "CONTINUE"
            reason = "Section transition but current candidate incomplete"
    elif is_instruction(text):
        signals["continuation"] = 0.9
        decision = "CONTINUE"
        reason = "Instruction block"
    elif re.match(OPTION_RE_TEMPLATE.format(L="[A-Da-d]"), text, re.I):
        signals["continuation"] = 0.9
        decision = "CONTINUE"
        reason = "Option label"
    elif re.match(r'^[Ee]\.\s+', text):
        signals["continuation"] = 0.9
        decision = "CONTINUE"
        reason = "Option E"
    elif text.startswith("[IMG:"):
        signals["continuation"] = 0.9
        decision = "CONTINUE"
        reason = "Image marker"
    elif len(text) > 0 and text[0].islower():
        signals["continuation"] = 0.8
        decision = "CONTINUE"
        reason = "Starts with lowercase"
    else:
        if current_cand["blocks"] and current_cand["blocks"][-1].block_type in ("table", "image"):
            if re.match(r'^(where|which|find|the order|choose|select)\b', text, re.I):
                signals["continuation"] = 0.8
                decision = "CONTINUE"
                reason = "Follow-up question to table/image"
                
        if has_options:
            if is_question_like_start(text):
                signals["new_question_like"] = 0.9
                decision = "NEW_QUESTION"
                reason = "Looks like a new question after options"
            elif not re.match(OPTION_RE_TEMPLATE.format(L="[A-Ea-e]"), text, re.I):
                signals["candidate_complete"] = 1.0
                decision = "NEW_QUESTION"
                reason = "Candidate already has options, non-option text encountered"
                
        if is_question_like_start(text):
            signals["new_question_like"] = 0.7
            # BUG-BND-003: Do not split premise + command (e.g. "Let f(x)... Find...")
            is_premise_cmd = not has_options and not num_info and any(text.lower().startswith(w) for w in ["find", "evaluate", "calculate", "prove", "determine", "then", "hence", "where"])
            if cand_seems_complete and not is_premise_cmd:
                decision = "NEW_QUESTION"
                reason = "Looks like new question + previous complete"
                
        if re.match(r'^Question\s+\d+', text, re.I): 
            signals["new_question_like"] = 1.0
            decision = "NEW_QUESTION"
            reason = "Explicit 'Question N' text"

    if debug:
        print("-" * 40)
        print("QUESTION BOUNDARY DECISION")
        print("-" * 40)
        print(f"Section: {section_context}")
        print("\nPrevious candidate:")
        print(f"  source_number = {current_cand.get('source_question_number')}")
        print(f"  blocks = {[cb.block_id for cb in current_cand['blocks']]}")
        print("\nCurrent block:")
        print(f"  block_id = {b.block_id}")
        print(f"  text = {text[:50]!r}")
        if num_info:
            print("\nDetected number:")
            for k, v in num_info.items():
                print(f"  {k} = {v}")
        print("\nSignals:")
        for k, v in signals.items():
            if v > 0:
                print(f"  {k} = +{v:.2f}")
        print(f"\nDecision:\n  {decision}")
        print(f"Reason:\n  {reason}")
        print("-" * 40)
        
    return decision, reason

def build_question_candidates(blocks: List[DocumentBlock], section_map: Dict[int, str]) -> List[Dict[str, Any]]:
    import sys
    debug = "--debug" in sys.argv
    candidates = []
    current_cand = None
    
    numbering_context = {"section": "General", "current_main": None,
                         "observed": set(), "last_kind": None}
    roman_values = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
                    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
    
    for b in blocks:
        if b.block_type == "paragraph" and is_section_header(b.text): continue
        if b.block_type == "paragraph" and not b.text.strip(): continue
            
        block_section = section_map.get(b.block_id, "General")
        section_transition = False
        section_previous_main = None
        if block_section != numbering_context["section"]:
            section_previous_main = numbering_context["current_main"]
            numbering_context["section"] = block_section
            numbering_context["current_main"] = None
            numbering_context["observed"] = set()
            numbering_context["last_kind"] = None
            section_transition = True
            
        num_info = None
        if b.block_type == "paragraph":
            num_info = detect_question_number(b.text)
            
        roman_as_main = False
        if num_info and num_info["kind"] == "roman":
            roman_body = re.sub(r'^[IVX]+\.\s*', '', b.text.strip(), flags=re.I)
            current_text = " ".join(x.text for x in current_cand["blocks"]) if current_cand else ""
            has_complete_options = all(re.search(
                OPTION_RE_TEMPLATE.format(L=f"[{letter.lower()}{letter.upper()}]"), current_text, re.I)
                for letter in "ABCD")
            roman_as_main = is_question_like_start(roman_body) and (
                current_cand is None or has_complete_options or section_transition)

        if current_cand:
            decision, _ = decide_boundary(
                current_cand, b, block_section, section_transition, 
                num_info, numbering_context, debug=debug
            )
            if roman_as_main:
                decision = "NEW_QUESTION"
            
            if decision == "NEW_QUESTION":
                candidates.append(current_cand)
                current_cand = None
                
        if current_cand is None:
            current_cand = {"blocks": [b], "section": block_section}
            if num_info and (num_info["kind"] == "main" or roman_as_main):
                scheme = "roman" if roman_as_main else "arabic"
                value = roman_values[num_info["value"]] if roman_as_main else num_info["value"]
                label = str(num_info["value"])
                previous = section_previous_main if section_transition else numbering_context["current_main"]
                if section_transition and section_previous_main is not None:
                    event = "section_reset"
                elif scheme != numbering_context["last_kind"] and numbering_context["last_kind"]:
                    event = "numbering_scheme_transition"
                elif previous is not None and value < previous:
                    event = "regression"
                elif value in numbering_context["observed"]:
                    event = "duplicate"
                elif previous is not None and value > previous + 1:
                    event = "gap"
                else:
                    event = "sequence"
                current_cand["source_question_number"] = label
                current_cand["raw_question_number"] = num_info["raw"]
                current_cand["numbering"] = {"scheme": scheme, "value": value,
                                              "section": block_section}
                current_cand["numbering_event"] = {
                    "event": event, "previous": previous, "current": value,
                    "scheme": scheme, "section": block_section,
                    "duplicate": value in numbering_context["observed"],
                }
                numbering_context["current_main"] = value
                numbering_context["observed"].add(value)
                numbering_context["last_kind"] = scheme
        else:
            current_cand["blocks"].append(b)
                
    if current_cand: candidates.append(current_cand)
    return candidates

def reconstruct_components(cand: Dict[str, Any]) -> Dict[str, Any]:
    blocks = cand["blocks"]
    metadata_appearances = []
    tables = []
    images = []
    combined_text = ""
    
    equations = []
    
    # Import math converter
    try:
        from src.convert.math import convert_math
    except ImportError:
        convert_math = lambda x: x
    
    source_blocks = []
    block_ids = []
    inline_content = []
    seen_inline_sources = set()
    for b in blocks:
        extracted_text = b.text
        source_paragraph_id = b.metadata.get(
            "source_paragraph_id", b.metadata.get("parent_block_id", b.block_id))
        if b.inline_content and source_paragraph_id not in seen_inline_sources:
            seen_inline_sources.add(source_paragraph_id)
            for inline in b.inline_content:
                item = inline.to_dict() if hasattr(inline, "to_dict") else dict(inline)
                item["source_block_id"] = b.metadata.get("parent_block_id", b.block_id)
                item["source_order"] = b.order
                item["inline_index"] = len(inline_content)
                inline_content.append(item)
        if b.block_type == "paragraph":
            # Keep citations/appearance tags in their source block metadata even
            # when reconstruct_components is called outside the full pipeline.
            extracted_text, inline_appearances = extract_metadata_spans(b.text)
            if inline_appearances:
                existing = b.metadata.setdefault("appearances", [])
                b.metadata["appearances"] = list(dict.fromkeys(existing + inline_appearances))
        if b.block_id not in block_ids:
            block_ids.append(b.block_id)
            # BUG-REC-001: Assign meaningful roles to source blocks
            role = "stem"
            if b.block_type == "table":
                role = "table"
            elif b.block_type == "image" or "[IMG:" in b.text:
                role = "image"
            elif re.match(OPTION_RE_TEMPLATE.format(L="[A-Ea-e]"), b.text, re.I):
                role = "option"
            elif re.match(r'^(?:Statement\s*(?:I|II|1|2)|[A-E]\.\s+)', b.text, re.I):
                role = "statement"
            elif re.match(r'^\([a-zivx]+\)\s+', b.text, re.I):
                role = "subpart"
            b.metadata["role"] = role
            source_blocks.append({"block_id": b.block_id, "role": role})
            
        if b.metadata.get("appearances"): metadata_appearances.extend(b.metadata["appearances"])
        if b.block_type == "table":
            tables.append(b)
        elif b.block_type == "paragraph":
            def img_replacer(match):
                img_path = match.group(1)
                images.append({"id": f"img-{len(images)+1}", "path": img_path, "source_block_id": b.block_id, "confidence": 1.0})
                return ""
            t = re.sub(r'\[IMG:\s*(.*?)\]', img_replacer, extracted_text)
            
            for m in re.finditer(r'\$(.*?)\$', t):
                raw_text = m.group(1).strip()
                equations.append({
                    "id": f"eq-{len(equations)+1}",
                    "raw": m.group(0),
                    "latex": convert_math(raw_text),
                    "source_block_id": b.block_id,
                    "confidence": 0.95
                })
                
            combined_text += t + "\n"
            
    combined_text = combined_text.strip()
    if cand.get("numbering", {}).get("scheme") == "roman":
        combined_text = re.sub(r'^[IVX]+[\.\)]\s*', '', combined_text, flags=re.IGNORECASE).strip()
    else:
        combined_text = re.sub(r'^(?:Q\s*)?\d+[\.\)]\s*', '', combined_text, flags=re.IGNORECASE).strip()
    
    extracted_options = {}
    stem = combined_text
    
    matches_A = list(re.finditer(re.compile(OPTION_RE_TEMPLATE.format(L="[Aa]"), re.IGNORECASE), combined_text))
    if matches_A:
        for match_A in reversed(matches_A):
            positions = {"A": (match_A.start(), match_A.end())}
            search_from = match_A.end()
            valid = True
            for letter in "BCD":
                pattern = re.compile(OPTION_RE_TEMPLATE.format(L=letter), re.IGNORECASE)
                m = pattern.search(combined_text, search_from)
                if not m:
                    valid = False
                    break
                positions[letter] = (m.start(), m.end())
                search_from = m.end()
                
            if valid:
                for i, letter in enumerate("ABCD"):
                    end = positions["ABCD"[i + 1]][0] if i < 3 else len(combined_text)
                    extracted_options[letter] = combined_text[positions[letter][1]: end].strip()
                stem = combined_text[:positions["A"][0]].strip()
                break
                
    extracted_statements = []
    m_stmt_a = re.search(r'(?:^|\n)([A-E])\.\s+(.*)', stem)
    if m_stmt_a and m_stmt_a.group(1) == 'A':
        pos_A = m_stmt_a.start()
        stmt_text = stem[pos_A:]
        stem = stem[:pos_A].strip()
        for letter in "ABCDE":
            m_curr = re.search(fr'(?:^|\n){letter}\.\s+', stmt_text)
            if not m_curr: break
            next_letter = chr(ord(letter) + 1)
            m_next = re.search(fr'(?:^|\n){next_letter}\.\s+', stmt_text[m_curr.end():])
            if m_next:
                extracted_statements.append({"label": letter, "text": stmt_text[m_curr.end():m_curr.end() + m_next.start()].strip()})
            else:
                extracted_statements.append({"label": letter, "text": stmt_text[m_curr.end():].strip()})
    else:
        m_stmt_1 = re.search(r'(?:^|\n)(Statement\s*(I|1))\s*[:\.]\s+', stem, re.IGNORECASE)
        if m_stmt_1:
            pos_1 = m_stmt_1.start()
            stmt_text = stem[pos_1:]
            stem = stem[:pos_1].strip()
            
            # Simple split for Statement I and Statement II
            m_curr = re.search(r'(?:^|\n)Statement\s*(I|1)\s*[:\.]\s+', stmt_text, re.IGNORECASE)
            m_next = re.search(r'(?:^|\n)Statement\s*(II|2)\s*[:\.]\s+', stmt_text, re.IGNORECASE)
            if m_curr and m_next:
                extracted_statements.append({"label": m_curr.group(1), "text": stmt_text[m_curr.end():m_next.start()].strip()})
                extracted_statements.append({"label": m_next.group(1), "text": stmt_text[m_next.end():].strip()})
                
    extracted_subparts = []
    m_roman_start = re.search(r'(?:^|\n)\(\s*i\s*\)\s+(.*)', stem, re.IGNORECASE)
    if m_roman_start:
        pos_i = m_roman_start.start()
        subpart_text = stem[pos_i:]
        stem = stem[:pos_i].strip()
        
        romans = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii"]
        for idx, r in enumerate(romans):
            m_curr = re.search(fr'(?:^|\n)\(\s*{r}\s*\)\s+', subpart_text, re.IGNORECASE)
            if not m_curr: break
            if idx + 1 < len(romans):
                next_r = romans[idx+1]
                m_next = re.search(fr'(?:^|\n)\(\s*{next_r}\s*\)\s+', subpart_text[m_curr.end():], re.IGNORECASE)
                if m_next:
                    extracted_subparts.append({"label": r, "text": subpart_text[m_curr.end():m_curr.end() + m_next.start()].strip()})
                    continue
            extracted_subparts.append({"label": r, "text": subpart_text[m_curr.end():].strip()})
    else:
        m_alpha_start = re.search(r'(?:^|\n)\(\s*a\s*\)\s+(.*)', stem, re.IGNORECASE)
        if m_alpha_start:
            pos_a = m_alpha_start.start()
            subpart_text = stem[pos_a:]
            stem = stem[:pos_a].strip()
            
            alphas = ["a", "b", "c", "d", "e", "f", "g", "h"]
            for idx, a in enumerate(alphas):
                m_curr = re.search(fr'(?:^|\n)\(\s*{a}\s*\)\s+', subpart_text, re.IGNORECASE)
                if not m_curr: break
                if idx + 1 < len(alphas):
                    next_a = alphas[idx+1]
                    m_next = re.search(fr'(?:^|\n)\(\s*{next_a}\s*\)\s+', subpart_text[m_curr.end():], re.IGNORECASE)
                    if m_next:
                        extracted_subparts.append({"label": a, "text": subpart_text[m_curr.end():m_curr.end() + m_next.start()].strip()})
                        continue
                extracted_subparts.append({"label": a, "text": subpart_text[m_curr.end():].strip()})

    has_num = bool(cand.get("source_question_number"))
    has_stem = bool(stem.strip())
    has_full_mcq = (len(extracted_options) == 4)

    score = 0.90
    if not has_num: score -= 0.15
    if not has_stem: score -= 0.30
    if extracted_options and not has_full_mcq: score -= 0.10
    score = round(max(0.10, min(1.0, score)), 2)

    q_dict = {
        "section": cand.get("section", "General"),
        "source_question_number": cand.get("source_question_number"),
        "raw_question_number": cand.get("raw_question_number"),
        "numbering": cand.get("numbering"),
        "numbering_event": cand.get("numbering_event"),
        "question": stem,
        "statements": extracted_statements,
        "options": extracted_options,
        "appearances": list(dict.fromkeys(metadata_appearances)),
        "images": images,
        "subparts": extracted_subparts,
        "equations": equations,
        "blanks": [],
        "answer": None,
        "parsed_ok": True,
        "needs_review": False,
        "block_ids": block_ids,
        "source_blocks": source_blocks,
        "inline_content": inline_content,
        "confidence": {
            "overall": score,
            "boundary": 0.95 if has_num else 0.75,
            "components": 0.95 if (has_full_mcq or extracted_statements or extracted_subparts) else 0.85,
            "classification": 0.90,
            "metadata": 1.0 if metadata_appearances else 0.85
        },
        "validation": {
            "valid": True,
            "issues": [],
            "checks": {
                "has_question_stem": bool(stem.strip()),
                "options_consistent": len(extracted_options) in (0, 4, 5) and len(set(extracted_options.values())) == len(extracted_options),
                "source_blocks_accounted_for": len(block_ids) > 0,
                "metadata_cleaned": True,
                "no_duplicate_components": len(block_ids) == len(set(block_ids))
            }
        }
    }
    
    if tables:
        tbl = tables[0]
        table_data = {"headers": [], "rows": [], "cell_content": [],
                      "source_block_ids": [tbl.block_id]}
        for i, r in enumerate(tbl.children):
            row_data = []
            rich_row = []
            for c in r.children:
                row_data.append(c.text.strip())
                cell_inline = [item.to_dict() if hasattr(item, "to_dict") else dict(item)
                               for child in c.children for item in child.inline_content]
                for inline_index, item in enumerate(cell_inline):
                    item.setdefault("source_block_id", c.block_id)
                    item["inline_index"] = inline_index
                rich_row.append({
                    "text": c.text.strip(),
                    "source_block_id": c.block_id,
                    "inline_content": cell_inline,
                })
            if i == 0:
                table_data["headers"] = row_data
            table_data["rows"].append(row_data)
            table_data["cell_content"].append(rich_row)
        q_dict["table"] = table_data
    else:
        q_dict["table"] = None
        
    return q_dict

def extract_features(q_dict: Dict[str, Any]) -> Dict[str, Any]:
    stem = q_dict.get("question", "")
    opts = q_dict.get("options", {})
    stmts = q_dict.get("statements", [])
    tables = q_dict.get("table", {})
    section = q_dict.get("section", "").lower()
    images = q_dict.get("images", [])
    
    stmt_texts = [s["text"] for s in stmts] if isinstance(stmts, list) else list(stmts.values())
    full_text = stem + "\n" + "\n".join(stmt_texts) + "\n".join(opts.values())
    
    features = {
        "has_options": len(opts) > 0,
        "option_count": len(opts),
        "has_table": bool(tables),
        "has_image": bool(images),
        "has_assertion": False,
        "has_reason": False,
        "has_blank": False,
        "has_equation": bool(q_dict.get("equations")),
        "has_statement_list": len(stmts) > 0,
        "has_numeric_instruction": False,
        "has_match_list": False,
        "has_multiple_correct_instruction": False
    }
    
    if re.search(r"_{3,}|{{BLANK}}", full_text) or "fill in the blank" in section: features["has_blank"] = True
    if re.search(r"\bAssertion\s*(?:A|:)\s*", full_text, re.I): features["has_assertion"] = True
    if re.search(r"\bReason\s*(?:R|:)\s*", full_text, re.I): features["has_reason"] = True
    if "List-I" in full_text and "List-II" in full_text or "Column I" in full_text: features["has_match_list"] = True
    if re.search(r"\bStatement\s*(?:I|1)\s*[:\.]", full_text, re.I): features["has_statement_list"] = True
    if re.search(r"\b(?:Which|Select)\s*(?:of the following|statements)\s*(?:are correct|are true)\b", full_text, re.I) or "one or more options may be correct" in full_text.lower():
        features["has_multiple_correct_instruction"] = True
        
    q_dict["features"] = features
    return q_dict

def classify_question(q_dict: Dict[str, Any]) -> Dict[str, Any]:
    features = q_dict.get("features", {})
    section = q_dict.get("section", "").lower()
    text = q_dict.get("question", "")
    
    q_type = "open"
    if features["has_assertion"] and features["has_reason"]: q_type = "assertion_reason"
    elif features["has_match_list"]: q_type = "match_list"
    elif features["has_statement_list"]: q_type = "statement_based"
    elif features["has_multiple_correct_instruction"]: q_type = "multiple_correct"
    elif features["has_blank"]: q_type = "fill_in_the_blank"
    elif features["has_options"]: q_type = "mcq"
    else:
        if "numerical" in section or re.search(r"\b(?:Calculate|Find|Evaluate|Determine)\b", text, re.I): q_type = "numerical"
        elif "integer" in section or "integer" in text.lower(): q_type = "integer_answer"
        elif re.search(r"\b(?:Explain|Describe|Discuss|Derive|Prove)\b", text, re.I): q_type = "subjective"
        elif re.search(r"\b(?:Write|Mention|State|Name)\b", text, re.I): q_type = "short_answer"
        elif features["has_table"]: q_type = "table_based"
        elif features["has_image"]: q_type = "image_based"
        else: q_type = "open_question"
            
    q_dict["question_type"] = q_type
    return q_dict

def recover_and_validate(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        from src.convert.math import check_math
    except ImportError:
        check_math = lambda x: []

    for i, q in enumerate(questions):
        if "validation" not in q:
            q["validation"] = {"valid": True, "issues": [], "checks": {}}
        validation = q["validation"]
        validation.setdefault("base_parsed_ok", bool(q.get("parsed_ok", True)))
        validation.setdefault("base_needs_review", bool(q.get("needs_review", False)))
        validation.setdefault("source_issues", list(validation.get("issues", [])))
        q["parsed_ok"] = validation["base_parsed_ok"]
        q["needs_review"] = validation["base_needs_review"]
        issues = list(validation["source_issues"])
        validation["issues"] = issues

        stem = q.get("question", "").strip()
        opts = q.get("options", {})
        q_type = q.get("question_type", "")
        validation_errors = []
        q["validation_errors"] = validation_errors

        def add_error(message: str) -> None:
            if message not in issues:
                issues.append(message)
            if message not in validation_errors:
                validation_errors.append(message)

        # Check empty stem and missing content
        if not stem and not q.get("table") and not q.get("images"):
            q["parsed_ok"] = False
            q["needs_review"] = True
            add_error("EMPTY_STEM_NO_CONTENT")

        # Validate MCQ option counts & values (BUG-VAL-002)
        if q_type == "mcq" or (opts and len(opts) > 0):
            if len(opts) not in (4, 5):
                q["parsed_ok"] = False
                q["needs_review"] = True
                add_error(f"INVALID_OPTION_COUNT: got {len(opts)}, expected 4")

            # Check empty options
            empty_opts = [k for k, v in opts.items() if not str(v).strip()]
            if empty_opts:
                q["needs_review"] = True
                add_error(f"EMPTY_OPTIONS: {empty_opts}")

            # Check duplicate options
            non_empty_vals = [str(v).strip() for v in opts.values() if str(v).strip()]
            if len(non_empty_vals) != len(set(non_empty_vals)):
                q["needs_review"] = True
                if "DUPLICATE_OPTION_VALUES" not in issues:
                    issues.append("DUPLICATE_OPTION_VALUES")

        # Validate math formulas (BUG-VAL-005)
        # Detect equations across the stem and options as well as extracted IR.
        equation_text = "\n".join([stem, *(str(v) for v in opts.values())])
        has_equation = bool(q.get("equations")) or bool(re.search(r"\$[^$]+\$|\\(?:frac|sqrt|int|sum|prod|pi|alpha|beta)\b|[=∫∑√∞]", equation_text))
        q["has_equation"] = has_equation
        for eq in q.get("equations", []):
            latex = eq.get("latex", "")
            math_probs = check_math(latex)
            if math_probs:
                for problem in math_probs:
                    add_error(f"MATH_ISSUE: {problem}")
                q["needs_review"] = True

        if "00 g" in q.get("question", ""):
            q["needs_review"] = True
            
        # SUSPICIOUS MERGE
        num_main_markers = len(re.findall(r'(?:^|\n)(?:Q(?:uestion)?\s*(?:No\.?)?\s*|Q\.\s*)?0*\d+(?:[\.\):]|\s*-)(?:\s+|$)', stem, re.IGNORECASE))
        starts = len(re.findall(r'\b(?:Evaluate|Find|Calculate|Prove|Determine|Explain|Define|Mention|Write|State|Describe|Deduce|Derive)\b', stem, re.IGNORECASE))
        
        if (num_main_markers >= 1 and not q.get("source_question_number")) or (starts >= 3 and len(q.get("block_ids", [])) > 5) or len(q.get("block_ids", [])) >= 20:
            q["needs_review"] = True
            if len(q.get("block_ids", [])) >= 20:
                if "SUSPICIOUS_LARGE_CANDIDATE" not in issues:
                    issues.append("SUSPICIOUS_LARGE_CANDIDATE")
            else:
                if "SUSPICIOUS_MERGE" not in issues:
                    issues.append("SUSPICIOUS_MERGE")
                
        # SUSPICIOUS SPLIT
        if i > 0:
            if not q.get("source_question_number") and not q.get("options"):
                if stem.startswith("where ") or stem.startswith("which ") or (len(stem) > 0 and stem[0].islower()):
                    q["needs_review"] = True
                    if "SUSPICIOUS_SPLIT" not in issues:
                        issues.append("SUSPICIOUS_SPLIT")

        # Update valid flag and checks dynamically (BUG-VAL-001, BUG-VAL-004)
        # Validation errors determine parsed_ok; review warnings may still leave
        # a question renderable, but never make malformed structure look valid.
        q["parsed_ok"] = bool(q.get("parsed_ok", True)) and not validation_errors
        validation["valid"] = q["parsed_ok"] and not bool(q.get("needs_review", False))
        validation["checks"] = {
            "has_question_stem": bool(stem),
            "options_consistent": len(opts) in (0, 4, 5) and len(set(opts.values())) == len(opts),
            "source_blocks_accounted_for": len(q.get("block_ids", [])) > 0,
            "metadata_cleaned": True,
            "no_duplicate_components": len(q.get("block_ids", [])) == len(set(q.get("block_ids", [])))
        }
        q["quality_score"] = round(max(0.0, min(1.0,
            0.65 + (0.2 if stem else 0.0) + (0.15 if len(opts) in (4, 5) else 0.0)
            - (0.25 if validation_errors else 0.0)
            - (0.1 if q.get("needs_review") else 0.0))), 2)
        q["review_reasons"] = list(dict.fromkeys(issues)) if q.get("needs_review") else []
        if q.get("needs_review") and not q["review_reasons"]:
            q["review_reasons"] = ["REVIEW_REQUIRED"]

    return questions
