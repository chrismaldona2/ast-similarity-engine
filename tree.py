import os

IGNORAR = {".git", "node_modules", ".venv", "__pycache__"}

for raiz, dirs, archivos in os.walk("."):
    dirs[:] = [d for d in dirs if d not in IGNORAR]

    nivel = raiz.count(os.sep)
    indent = "    " * nivel

    print(f"{indent}{os.path.basename(raiz)}/")

    for archivo in archivos:
        if archivo not in IGNORAR:
            print(f"{indent}    {archivo}")