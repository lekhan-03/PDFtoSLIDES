with open("src/parser.py", "r", encoding="utf-8") as f:
    text = f.read()

old_loop = """    for b in blocks:
        r = parse_block(b)
        if r["parsed_ok"]:
            parsed.append(r)
        else:
            failed.append(b)"""

new_loop = """    for b in blocks:
        rs = parse_block(b)
        if not isinstance(rs, list): rs = [rs]
        for r in rs:
            if r["parsed_ok"]:
                parsed.append(r)
            else:
                failed.append(b)"""

text = text.replace(old_loop, new_loop)

with open("src/parser.py", "w", encoding="utf-8") as f:
    f.write(text)
