import re
text = "52. Consider the Arrhenius equation k=e−Ea/RT and mark the correct option (A) Rate constant increases exponentially with increasing activation energy and decreasing temperature. (B) Rate constant decreases exponentially with increasing activation energy and decreasing temperature. (C) Rate constant increases exponentially with increasing activation energy and increasing temperature. (D) Rate constant increases exponentially with decreasing activation energy and decreasing temperature."

OPTION_RE_TEMPLATE = r'\({L}\)|{L}\.'

positions = {}
search_from = 0
for letter in "ABCD":
    pattern = re.compile(OPTION_RE_TEMPLATE.format(L=letter), re.IGNORECASE)
    match = pattern.search(text, search_from)
    positions[letter] = (match.start(), match.end())
    search_from = match.end()

print("Positions:", positions)

from src.parser import _extract_options
print("Extracted options:", _extract_options(text, positions))
