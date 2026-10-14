"""Upload local exported VPN profiles to the repository Secret, never to Git."""
import argparse,json,re,subprocess,sys
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('folder',type=Path)
    parser.add_argument('--repo',default='Shisetsu-Code/Tester-Spin')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',args.repo):parser.error('Repositorio inválido')
    values={}
    for path in sorted(args.folder.glob('*.conf')):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',path.stem):parser.error('Los nombres de perfil deben usar letras, números, guiones o guion bajo')
        values[path.stem]=path.read_text(encoding='utf-8-sig')
    if not values:parser.error('No hay perfiles .conf en la carpeta')
    data=json.dumps(values,ensure_ascii=True)
    if len(data.encode())>48*1024:parser.error('El conjunto excede el tamaño permitido para un Secret; usá menos perfiles')
    result=subprocess.run(['gh','secret','set','WG_CONFIGS_JSON','--repo',args.repo],input=data,text=True,capture_output=True)
    if result.returncode:print('No se pudo guardar el Secret; comprobá la sesión y permisos de gh.',file=sys.stderr);return 2
    print('WG_CONFIGS_JSON actualizado sin publicar las configuraciones.');return 0

if __name__=='__main__':raise SystemExit(main())
