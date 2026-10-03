import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

texts = [
    'Prove that$∫_{0}^{a} f(x).dx={2∫_{0}^{a} f(x)dx, if f(x)is an even function 0, if f(x)is an odd function $ and hence evaluate $∫_{-1}^{1} sin^{5}xcos^{4}x dx$ (2015,2017s)',
    'Prove that$∫_{0}^{a} f(x).dx={2∫_{0}^{a} f(x)dx, if f(2a-x)=f(x) 0, if f(2a-x)= -f(x) $ and hence evaluate $∫_{0}^{2π} cos^{5}x dx$ (2016)',
    'Prove that $∫_{-a}^{a} f(x)dx={2∫_{0}^{a} f(x)dx if f(x) is even function 0,if f (x)is odd function $ And hence evaluate $∫_{-(π)/(2)}^{(π)/(2)} sin7x dx$ (2018s,2024m)'
]

pattern = re.compile(r'=\s*\{\s*(2[^,i]+?dx)\s*,?\s*if\s+(.*?)\s+(0)\s*,?\s*if\s+([^$]+?)\s*(?=\$)')

for t in texts:
    m = pattern.search(t)
    if m:
        print(m.groups())
    else:
        print("NO MATCH:", t)
