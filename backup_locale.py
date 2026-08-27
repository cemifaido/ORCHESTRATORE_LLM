#!/usr/bin/env python3
"""Snapshot dei dati locali che git non protegge (2026-08-27).

Rete di sicurezza contro l'errore accidentale, non contro un attacco: bacheca,
registro, catalogo capability e il piano di industrializzazione sono tutti
gitignored di proposito (dati proprietari o bozze non condivise, vedi
CLAUDE.md "Dati proprietari non generici") - git quindi non ne tiene nessuna
storia. Se un bug (di un agente o dell'umano) li corrompe o cancella, oggi non
c'e' alcun modo di recuperarli.

Uso:
    python backup_locale.py salva      # crea uno snapshot con timestamp
    python backup_locale.py lista      # elenca gli snapshot esistenti

Ripristino: manuale e deliberato, non automatizzato qui apposta (un comando
'ripristina' che sovrascrive dati vivi e' esso stesso un rischio di errore
accidentale). Per ripristinare: copia a mano il contenuto della cartella dello
snapshot scelto sopra i percorsi originali.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RADICE = Path(__file__).resolve().parent
CARTELLA_BACKUP = RADICE / "backup_locale"

# Percorsi ad alto valore e non protetti da git (vedi .gitignore). Volutamente
# non include le config hook (.claude/.codex/.gemini/.agents): quelle sono
# gia' rigenerabili da template via setup_wizard.inizializza_config_agenti().
PERCORSI_DA_SALVARE = [
    RADICE / "dati_locali",
    RADICE / "config" / "capability_catalogo.json",
    RADICE / "docs" / "PIANO_INDUSTRIALIZZAZIONE.md",
    RADICE / ".env",
]


def timestamp_snapshot() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def salva_snapshot(percorsi: list[Path] | None = None, cartella_backup: Path | None = None) -> Path:
    """Copia ogni percorso esistente in una nuova sottocartella con timestamp.
    Percorsi assenti vengono saltati in silenzio (non tutti i progetti hanno
    ancora un .env o un catalogo capability reale). I default sono risolti a
    ogni chiamata (non come valore di default vincolato a definizione), cosi'
    un override nei test (patch.object su PERCORSI_DA_SALVARE/CARTELLA_BACKUP)
    ha davvero effetto."""
    percorsi = percorsi if percorsi is not None else PERCORSI_DA_SALVARE
    cartella_backup = cartella_backup if cartella_backup is not None else CARTELLA_BACKUP
    destinazione = cartella_backup / timestamp_snapshot()
    destinazione.mkdir(parents=True, exist_ok=True)

    salvati: list[str] = []
    for percorso in percorsi:
        if not percorso.exists():
            continue
        bersaglio = destinazione / percorso.name
        if percorso.is_dir():
            shutil.copytree(percorso, bersaglio)
        else:
            shutil.copy2(percorso, bersaglio)
        salvati.append(percorso.name)

    (destinazione / "MANIFESTO.txt").write_text(
        "Snapshot creato: " + datetime.now(timezone.utc).isoformat() + "\n"
        "Contenuto: " + ", ".join(salvati) + "\n",
        encoding="utf-8",
    )
    return destinazione


def elenca_snapshot(cartella_backup: Path | None = None) -> list[Path]:
    cartella_backup = cartella_backup if cartella_backup is not None else CARTELLA_BACKUP
    if not cartella_backup.exists():
        return []
    return sorted((p for p in cartella_backup.iterdir() if p.is_dir()), reverse=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sotto = parser.add_subparsers(dest="comando", required=True)
    sotto.add_parser("salva", help="crea un nuovo snapshot dei dati locali")
    sotto.add_parser("lista", help="elenca gli snapshot esistenti")
    args = parser.parse_args(argv)

    if args.comando == "salva":
        destinazione = salva_snapshot()
        print(f"Snapshot creato in: {destinazione}")
        return 0

    if args.comando == "lista":
        snapshot = elenca_snapshot()
        if not snapshot:
            print("Nessuno snapshot presente.")
            return 0
        for percorso in snapshot:
            print(percorso.name)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
