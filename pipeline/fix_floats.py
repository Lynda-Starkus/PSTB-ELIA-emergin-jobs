"""Make all floats of research-paper/main.tex span both columns (figure* / table*) for the 5p two-column layout."""
import sys, re
p = sys.argv[1]; s = open(p, encoding='utf-8').read()
s = re.sub(r'\\begin\{figure\}\[(t|h|htbp)\]', r'\\begin{figure*}[t]', s)
s = s.replace('\\end{figure}', '\\end{figure*}').replace('\\end{figure**}', '\\end{figure*}')
s = re.sub(r'\\begin\{table\}\[(t|h|htbp)\]', r'\\begin{table*}[t]', s)
s = s.replace('\\end{table}', '\\end{table*}').replace('\\end{table**}', '\\end{table*}')
s = s.replace('\\begin{figure**}', '\\begin{figure*}').replace('\\begin{table**}', '\\begin{table*}')
open(p, 'w', encoding='utf-8').write(s)
print('figure* count', s.count('\\begin{figure*}'), 'end', s.count('\\end{figure*}'), '| table*', s.count('\\begin{table*}'), s.count('\\end{table*}'))
