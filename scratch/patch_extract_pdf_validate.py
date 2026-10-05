with open("src/extract_pdf.py", "r", encoding="utf-8") as f:
    text = f.read()

old_loop = """        parsed = parse_question_text(text, q_id)
        
        if validate_question(text, parsed):
            questions.append(parsed)
        else:
            parsed['parsed_ok'] = False
            questions.append(parsed)
            # Only flag actual questions, not the title block
            if q_num > 0 or "A)" in text or "a)" in text:
                flagged.append(f"Q{q_id} (Page {page})")"""

new_loop = """        parsed_res = parse_question_text(text, q_id)
        if not isinstance(parsed_res, list):
            parsed_res = [parsed_res]
            
        for parsed in parsed_res:
            if parsed.get("question_type") == "divider":
                questions.append(parsed)
                continue
                
            if validate_question(text, parsed):
                questions.append(parsed)
            else:
                parsed['parsed_ok'] = False
                questions.append(parsed)
                # Only flag actual questions, not the title block
                if q_num > 0 or "A)" in text or "a)" in text:
                    flagged.append(f"Q{q_id} (Page {page})")"""

text = text.replace(old_loop, new_loop)

with open("src/extract_pdf.py", "w", encoding="utf-8") as f:
    f.write(text)
