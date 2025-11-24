import ast,sys,traceback
p='c:/Users/User/OneDrive/Desktop/BizTrack_PRO/biztrack.py'
src=open(p,'r',encoding='utf-8').read()
try:
    ast.parse(src)
    print('OK')
except Exception:
    traceback.print_exc()
    sys.exit(1)
