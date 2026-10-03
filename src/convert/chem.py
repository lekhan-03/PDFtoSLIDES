import re

def convert_chem(s: str) -> str:
    """CHEM runs only. Applies subscripts and superscripts for chemistry formulas."""
    
    # [A] 2 -> [A]^{2} only inside rate-law / concentration expressions.
    # Note: since this is a CHEM run, it will only apply to isolated formulas that matched CHEM patterns.
    s = re.sub(r'\]\s*(\d)', r']^{\1}', s)
    
    # Subscripts for digits after element symbols
    # A simple regex to find Element-like patterns (e.g. C, H, Cl, Na) followed by digits
    # Since we use unicode subscripts when not wrapped in math, wait, the prompt says:
    # "CCl4 -> CCl₄, Ca2+ -> Ca²⁺"
    # Wait, if we use unicode subscripts, how is it handled if it is wrapped in math?
    # Actually, the user's test cases: "CCl4 -> CCl₄ ; CH2Cl2 -> CH₂Cl₂ ; Rate = K[A] 2 [B] 2 -> \text{Rate}=K[A]^{2}[B]^{2}"
    
    SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    SUP = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
    
    # Replace charges like 2+
    s = re.sub(r'([A-Za-z\]\)])(\d?[+-])(?=[\s.,;:<>]|$)', lambda m: m.group(1) + m.group(2).translate(SUP), s)
    
    # Replace subscript digits after elements
    s = re.sub(r'([A-Z][a-z]?|[\)])(\d+)', lambda m: m.group(1) + m.group(2).translate(SUB), s)
    
    return s
