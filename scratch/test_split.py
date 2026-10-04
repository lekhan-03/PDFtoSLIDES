from src.parser import split_questions
q52_text = """1. q
(A) a
temperature.
(B) b
temperature.
(C) c
temperature.
(D) d
temperature."""
blocks = split_questions(q52_text.split('\n'))
print(blocks[0]['lines'])
