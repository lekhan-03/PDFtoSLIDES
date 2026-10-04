with open("src/main.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('parsed.sort(key=lambda q: q["id"])', 'parsed.sort(key=lambda q: q["id"] if q.get("id") is not None else float("inf"))')

with open("src/main.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Patched main.py")
