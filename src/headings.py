import re

def is_heading(text: str) -> bool:
    """Returns True if the text is a chapter heading or divider."""
    text = text.strip()
    words = text.split()
    
    if len(words) > 7 or not text or not text[0].isalpha():
        return False
        
    if re.search(r'\([A-Da-d]\)', text):
        return False
        
    if text.endswith(':'):
        # A valid heading ending in colon should usually start with an uppercase letter, 
        # or a single letter like 'd' or 'p-'
        if text[0].isupper() or (len(words[0]) == 1 and words[0][0].islower()) or (len(words[0]) > 1 and words[0][1] == '-'):
            return True
            
    # For standalone headings without a colon (like "Solutions")
    if len(words) <= 4 and text.istitle() and len(text) > 3 and not re.search(r'\d', text):
        return True
        
    return False

def strip_trailing_heading(text: str):
    """Splits a trailing heading from text. Returns (text_without_heading, heading_if_any)"""
    words = text.split()
    for i in range(min(7, len(words) - 1), 0, -1):
        suffix = ' '.join(words[-i:]).strip()
        if suffix.endswith(':') and is_heading(suffix) and ' '.join(words[:-i]).strip():
            # Remove trailing colon from divider text
            divider = suffix.rstrip(':').strip()
            return ' '.join(words[:-i]).strip(), divider
            
    return text, None
