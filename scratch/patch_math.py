import re
with open("src/convert/math.py", "r", encoding="utf-8") as f:
    text = f.read()
    
# Remove specific scripts from SYMBOLS
text = text.replace(', "ˣ": "^{x}", "²": "^{2}", "³": "^{3}"', '')

func = """def unicode_scripts(s: str) -> str:
    sup = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿˣ", "0123456789+-=()nx")
    sub = str.maketrans("₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎", "0123456789+-=()")
    
    # We want to replace sequences of superscripts with ^{...} and subscripts with _{...}
    def repl_sup(m):
        return "^{" + m.group(0).translate(sup) + "}"
    def repl_sub(m):
        return "_{" + m.group(0).translate(sub) + "}"
        
    s = re.sub(r'[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿˣ]+', repl_sup, s)
    s = re.sub(r'[₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎]+', repl_sub, s)
    return s
"""

if "def unicode_scripts" not in text:
    # insert before convert_math
    idx = text.find("def convert_math(")
    text = text[:idx] + func + "\n" + text[idx:]
    
    # Call it in convert_math
    idx2 = text.find("s = s.translate(INVISIBLE)")
    if idx2 != -1:
        text = text[:idx2+26] + "\n    s = unicode_scripts(s)" + text[idx2+26:]
        
with open("src/convert/math.py", "w", encoding="utf-8") as f:
    f.write(text)
