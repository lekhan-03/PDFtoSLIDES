from src.convert.math import split_question
from src.run_merge import merge_runs
import sys

q = 'Statement 1: The anti-derivative of $((1)/(sqrt(1+X^{2})) )$with respect to x'
tag, runs = split_question(q)
print('After split:', runs)
merged = merge_runs(runs)
print('After merge:', merged)
