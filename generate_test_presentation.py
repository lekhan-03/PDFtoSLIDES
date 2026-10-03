import json
from pathlib import Path
from src.generate_pptx import generate

test_data = [
    {
        "parsed_ok": True,
        "question": "Solve the integral: $\\int e^{x}\\left(\\frac{1}{x}-\\frac{1}{x^{2}}\\right)dx$",
        "options": {
            "A": "$e^{-x}\\left(\\frac{1}{x}\\right)+c$",
            "B": "$e^{x}\\left(\\frac{1}{x}\\right)+c$",
            "C": "$\\frac{e^x}{x^2}+c$",
            "D": "None of the above"
        },
        "answer": "B",
        "section": "Math",
        "question_type": "mcq"
    }
]

Path("test_input.json").write_text(json.dumps(test_data), encoding="utf-8")
generate(Path("test_input.json"), Path("test_stacked_fractions.pptx"))
