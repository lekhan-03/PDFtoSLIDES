import re

def normalize_math_block(match):
    math_content = match.group(1)
    math_content = math_content.replace('.dx', '\\,dx')
    
    # Add space before function if preceded by a word character
    math_content = re.sub(r'([a-zA-Z0-9])(sin|cos|tan|cot|sec|log|ln|lim|cosec)', r'\1 \2', math_content)
    
    funcs = r'(sin|cos|tan|cot|sec|log|ln|lim|cosec)'
    
    math_content = re.sub(rf'\b{funcs}([a-df-zA-Z])\b', r'\\\1 \2', math_content)
    math_content = re.sub(rf'(?<!\\)\b{funcs}\b', r'\\\1', math_content)
    math_content = re.sub(rf'(?<!\\)\b{funcs}(?=\^)', r'\\\1', math_content)
    math_content = re.sub(r'\\cosec\b', r'\\operatorname{cosec}', math_content)
    
    def _func_space_sub(m):
        return f"{m.group(1)} {m.group(2)}"

    math_content = re.sub(r'(\\(?:sin|cos|tan|cot|sec|log|ln|lim)(?:\^\{[^}]+\}|\^[-0-9a-z]+)?)([a-zA-Z0-9\\])', _func_space_sub, math_content)
    math_content = re.sub(r'(\\operatorname\{cosec\}(?:\^\{[^}]+\}|\^[-0-9a-z]+)?)([a-zA-Z0-9\\])', _func_space_sub, math_content)
    
    math_content = re.sub(r'  +', ' ', math_content)
    return f"${math_content}$"

def render_math_text(text: str) -> str:
    # mock get_latex_text returning the text as is if it has $
    latex_text = text
    if '$' not in latex_text:
        latex_text = f"${text}$" # mock auto_latex adding $
        
    normalized = re.sub(r'\$([^\$]+)\$', normalize_math_block, latex_text)
    return normalized

print(render_math_text("$-xcosx-sinx+c$"))
print(render_math_text("$x\\cos x+\\sin x+c$"))
print(render_math_text("$sec x+C$"))
print(render_math_text("using $cosine$")) # wait, if cosine is in math, it will be \cos ine
print(render_math_text("$sin^{-1}x+C$"))
print(render_math_text("$\\frac{1}{x\\sqrt{x^{2}-1}}, x>1$"))
