#!/usr/bin/env python3
"""Instradamento: dato un tipo di compito, suggerisce l'agente giusto.

Regola-base deterministica (tabella), poi — se il registro ha storia — aggiunge una nota
sul rework passato di quell'agente per quel tipo. Non decide da solo: propone, tu confermi.
Output JSON, come tutto ciò che produce il capoturno locale.

    python instrada.py --tipo interfaccia
    python instrada.py --tipo servizi --rischio alto
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import registro

# Confini di proprietà (vedi docs/ORCHESTRAZIONE_LAVORATORI.md). Mappa i tipi dello schema
# evento.v1.json → agente più adatto.
TABELLA = {
    "interfaccia": ("gemini", "frontend/UX/CSS: veloce e visivo"),
    "servizi": ("claude", "backend/logica: correttezza e dipendenze"),
    "database": ("claude", "schema/dati: rischio alto, un agente forte alla volta"),
    "documentazione": ("claude", "architettura e chiarezza"),
    "errore_test": ("locale", "prima triage deterministico del fallimento"),
    "revisione": ("codex", "review puntigliosa"),
    "sicurezza": ("codex", "security/concurrency: il notaio"),
    "monitoraggio": ("locale", "gate e watchdog"),
    "orchestrazione": ("locale", "manutenzione handoff/registro"),
    "sconosciuto": ("umano", "tipo non chiaro: chiedi prima di instradare"),
}


def storico_rework(percorso: Path, agente: str, tipo: str) -> dict[str, int] | None:
    if not percorso.exists():
        return None
    eventi = [e for e in registro.leggi_eventi(percorso)
              if e.get("agente") == agente and e.get("tipo_compito") == tipo]
    if not eventi:
        return None
    rework = sum(1 for e in eventi if registro.evento_indica_rework(e))
    return {"eventi": len(eventi), "rework": rework}


def instrada(tipo: str, rischio: str, percorso: Path) -> dict:
    agente, motivo = TABELLA.get(tipo, ("umano", "tipo non mappato"))
    serve_umano = rischio == "alto" or agente == "umano"
    nota = None
    if rischio == "alto":
        nota = "rischio alto: passa prima da SignorPaolo (gate umano), poi all'agente forte."
    storico = storico_rework(percorso, agente, tipo)
    return {
        "tipo_compito": tipo,
        "agente_suggerito": agente,
        "motivo": motivo,
        "serve_umano_prima": serve_umano,
        "nota": nota,
        "storico": storico,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Suggerisce l'agente per un tipo di compito")
    parser.add_argument("--tipo", choices=sorted(TABELLA), required=True)
    parser.add_argument("--rischio", choices=["basso", "medio", "alto"], default="basso")
    parser.add_argument("--registro", default=str(registro.PERCORSO_REGISTRO_PREDEFINITO))
    args = parser.parse_args()
    print(json.dumps(instrada(args.tipo, args.rischio, Path(args.registro)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
