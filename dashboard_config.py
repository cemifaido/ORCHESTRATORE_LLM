#!/usr/bin/env python3
"""Configurazione e percorsi dell'Orchestratore LLM per la Dashboard.

Modulo estratto da interfaccia.py nel Lotto D (backlog architetturale D2).
Centralizza la risoluzione dei percorsi di root, delle variabili d'ambiente,
delle porte/host e del controllo di sicurezza sul bind di rete.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent

# CSS/JS di interfaccia.html
PERCORSO_STATIC = RADICE / "static"
PERCORSO_PROGETTI = RADICE / "dati_locali" / "progetti.json"
PERCORSO_HTML = RADICE / "interfaccia.html"
PERCORSO_FLUSSI = RADICE / "config" / "flussi"
SCRIPT_SENTINELLA_CENTRALE = RADICE / "sentinella.py"
SCRIPT_INTERFACCIA = RADICE / "interfaccia.py"

_INDIRIZZI_LOOPBACK = {"127.0.0.1", "localhost", "::1"}
AGENTI_BACHECA_DASHBOARD = ("claude", "codex", "gemini")


def carica_env(percorso_env: Path | None = None) -> list[str]:
    """Caricamento configurazione da file .env se presente.

    Loader minimale senza dipendenza python-dotenv esterna.
    Rimuove virgolette dai valori e ignora commenti/linee vuote.
    """
    if percorso_env is None:
        percorso_env = RADICE / ".env"
    if not percorso_env.exists():
        return []
    righe_lette = []
    try:
        righe_env = percorso_env.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        print(f"[.ENV] Impossibile leggere {percorso_env}: {e}", file=sys.stderr)
        return []
    for num_riga, riga in enumerate(righe_env, start=1):
        riga = riga.strip()
        if not riga or riga.startswith("#"):
            continue
        if "=" not in riga:
            print(f"[.ENV] Riga {num_riga} ignorata (manca '='): {riga!r}", file=sys.stderr)
            continue
        k, v = riga.split("=", 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        if k and k not in os.environ:
            os.environ[k] = v
            righe_lette.append(k)
    return righe_lette


# Carica .env all'importazione
carica_env()

HOST_DASHBOARD = os.environ.get("ORCHESTRATORE_HOST", "127.0.0.1")
PORTA_DASHBOARD = int(os.environ.get("ORCHESTRATORE_PORTA", "8095"))
CHIAVE_API_DASHBOARD = os.environ.get("ORCHESTRATORE_API_KEY", "")


def bind_e_loopback(host: str) -> bool:
    """Restituisce True se l'host appartiene agli indirizzi di loopback locali."""
    return host in _INDIRIZZI_LOOPBACK




def verifica_bind_sicuro(host: str | None = None, chiave_api: str | None = None) -> None:
    """Fail-closed: un bind non-loopback senza chiave condivisa espone senza
    autenticazione le route che mutano stato. Se non sicuro solleva SystemExit."""
    if host is None:
        host = HOST_DASHBOARD
    if chiave_api is None:
        chiave_api = CHIAVE_API_DASHBOARD
    if not bind_e_loopback(host) and not chiave_api:
        sys.exit(
            f"ORCHESTRATORE_HOST e' impostato a un indirizzo non-loopback ('{host}') "
            "ma manca ORCHESTRATORE_API_KEY: la dashboard si rifiuta di avviarsi senza una "
            "chiave condivisa esplicita. Imposta ORCHESTRATORE_API_KEY oppure torna a un bind "
            "loopback (127.0.0.1/localhost)."
        )
