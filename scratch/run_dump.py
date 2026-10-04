import sys
sys.stdout.reconfigure(encoding='utf-8')
import runpy
sys.argv = ['dump_lines.py', 'data/chemistry.pdf', 'Arrhenius equation']
runpy.run_path('dump_lines.py', run_name='__main__')

print("\n--- Q33 ---\n")
sys.argv = ['dump_lines.py', 'data/chemistry.pdf', 'radioactive decay']
runpy.run_path('dump_lines.py', run_name='__main__')
