import re

def is_heading(text: str) -> bool:
    """Returns True if the text is a chapter heading or divider."""
    text = text.strip()
    words = text.split()
    
    if len(words) > 7 or not text or not text[0].isalpha():
        return False
        
    if re.search(r'\([A-Da-d]\)', text):
        return False
        
    known_chapters = [
        "solutions", "electrochemistry", "chemical kinetics", 
        "surface chemistry", "metallurgy", "p-block elements", 
        "d and f block elements", "coordination compounds", 
        "haloalkanes and haloarenes", "alcohols, phenols and ethers", 
        "aldehydes, ketones and carboxylic acids", "amines", 
        "biomolecules", "polymers", "chemistry in everyday life", 
        "integrals", "application based questions"
    ]
    
    clean_text = text.rstrip(':').lower().strip()
    
    if clean_text in known_chapters:
        return True

    return False
