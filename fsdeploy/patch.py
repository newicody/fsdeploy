python3 -c "
import glob, re
for f in glob.glob('/opt/fsdeploy/fsdeploy/lib/ui/screens/*.py'):
    with open(f) as fh: txt = fh.read()
    new = re.sub(r';\s*self\.name\s*=\s*[\"\\'][^\"\\'\n]*[\"\\']', '', txt)
    new = re.sub(r'^\s*self\.name\s*=\s*[\"\\'][^\"\\'\n]*[\"\\'].*\n', '', new, flags=re.MULTILINE)
    if new != txt:
        with open(f, 'w') as fh: fh.write(new)
        print(f'  fixed {f}')
"
