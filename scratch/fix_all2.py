import re

with open("src/parser.py", "r", encoding="utf-8") as f:
    text = f.read()

# Fix dic syntax error
text = text.replace("def _extract_options(text: str, positions: dict) -> dic\n    keys = list(\"ABCD\")", "def _extract_options(text: str, positions: dict) -> dict[str, str]:\n    keys = list(\"ABCD\")")

with open("src/parser.py", "w", encoding="utf-8") as f:
    f.write(text)
