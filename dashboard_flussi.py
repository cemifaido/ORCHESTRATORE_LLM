#!/usr/bin/env python3
"""Gestione e lettura dei flussi dichiarati per la Dashboard.

Modulo estratto da interfaccia.py nel Lotto D (backlog architetturale D2).
Carica le definizioni JSON in config/flussi/ e fa da adapter verso motore_flusso.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import dashboard_config
import motore_flusso

PERCORSO_FLUSSI = dashboard_config.PERCORSO_FLUSSI


def leggi_flussi_dichiarati(percorso_flussi: Path | None = None) -> dict[str, dict]:
    """Carica i flussi dichiarati presenti in config/flussi/*.json."""
    if percorso_flussi is None:
        percorso_flussi = PERCORSO_FLUSSI
    flussi = {}
    if percorso_flussi.exists():
        for p in percorso_flussi.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                flusso_id = data.get("id_flusso", p.stem)
                flussi[flusso_id] = data
            except Exception:
                pass
    return flussi


def calcola_fase_flusso(
    messaggi: list[dict],
    thread_id: str,
    eventi: list[dict] | None = None,
    flusso: dict | None = None,
) -> str | None:
    """Adapter sottile verso motore_flusso.deriva_stato.

    Ritorna la fase attiva se lo stato e' attivo, 'chiusura' se completato,
    None se lo stato e' incoerente o invalido (fail-safe: nessun avanzamento inventato).
    """
    if flusso is None:
        flussi = leggi_flussi_dichiarati()
        flusso = flussi.get("compito_standard", {})
    if eventi is None:
        eventi = []

    dto = motore_flusso.deriva_stato(flusso, eventi, messaggi, thread_id)
    if dto["stato"] == "attivo":
        return dto["fase"]
    elif dto["stato"] == "completato":
        return "chiusura"
    return None


