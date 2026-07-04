import os
import sys
from pathlib import Path

def scrivi_hook(radice: Path, hook_path: Path) -> None:
    # Contenuto del pre-commit in Python
    contenuto = f"""#!/usr/bin/env python
# Hook pre-commit generato dall'Orchestratore Centrale.
# Verifica i quality gate (ruff, mypy, xenon) prima di consentire il commit.

import subprocess
import sys
from pathlib import Path

def main():
    radice = Path(r"{radice}")
    sentinella = radice / "sentinella.py"
    
    comandi = [
        ("Linting (Ruff)", ["python", str(sentinella), "controllo_lint"]),
        ("Type Check (Mypy)", ["python", str(sentinella), "controllo_tipi"]),
        ("Complessità (Xenon)", ["python", str(sentinella), "controllo_complessita"]),
    ]
    
    print("=== AVVIO QUALITY GATE PRE-COMMIT ===")
    for nome, cmd in comandi:
        print(f"Esecuzione {{nome}}...")
        res = subprocess.run(cmd, cwd=str(radice), text=True, capture_output=True)
        if res.returncode != 0:
            print(f"\\n[FALLITO] {{nome}} ha riscontrato delle violazioni:")
            print(res.stdout or res.stderr)
            print("=== COMMIT ANNULLATO ===")
            return 1
            
    print("[SUPERATO] Tutti i quality gate sono verdi.")
    print("=== PROCESSO COMPLETATO ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""
    hook_path.write_text(contenuto, encoding="utf-8")


def installa():
    radice = Path(__file__).resolve().parent.parent
    cartella_hooks = radice / ".git" / "hooks"
    
    if not cartella_hooks.exists():
        print(f"Errore: Cartella .git/hooks non trovata in {cartella_hooks}. Assicurati che questo sia un repository Git.")
        return 1
        
    hook_path = cartella_hooks / "pre-commit"
    scrivi_hook(radice, hook_path)
    
    # Rendiamo eseguibile su sistemi POSIX (Linux/macOS)
    if os.name != 'nt':
        os.chmod(hook_path, 0o755)
        
    print(f"Hook pre-commit installato con successo in {hook_path}")
    return 0

if __name__ == "__main__":
    sys.exit(installa())
