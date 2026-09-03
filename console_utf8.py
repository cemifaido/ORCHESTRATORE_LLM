#!/usr/bin/env python3
"""Forza i flussi standard a UTF-8 indipendentemente dalla codepage della console.

Perche': su Windows `sys.stdout`/`stderr`/`stdin` ripiegano su `cp1252`/OEM. Il
testo non-ASCII generato dai modelli o scritto dagli agenti (note di codice,
messaggi di bacheca, risposte JSON-RPC del server MCP) allora esce con caratteri
sostituiti - o, peggio, con `UnicodeEncodeError` che interrompe un loop di
servizio. La pipeline dati su disco e' gia' tutta `encoding="utf-8"` esplicito
(vedi docs/RFC_BACHECA_MULTIAGENTE.md §6.4, causa isolata il 2026-08-25): l'unico
punto ancora fragile e' l'I/O sui flussi standard dei comandi CLI.

Chiamare `forza_console_utf8()` a inizio `main()`. Prima questo pattern era
copiato a mano in tre-quattro entry point (bacheca, sentinella, triage_locale,
setup_wizard) e ogni nuovo comando se ne dimenticava: un modulo solo cosi' non
si ripete piu'.
"""
from __future__ import annotations

import sys


def forza_console_utf8(*, anche_stdin: bool = False) -> None:
    """Riconfigura stdout/stderr (e stdin se richiesto) a UTF-8 con
    `errors="replace"`. No-op dove `reconfigure` non esiste (flusso gia'
    sostituito, es. in cattura di test) o non e' applicabile."""
    flussi = [sys.stdout, sys.stderr]
    if anche_stdin:
        flussi.append(sys.stdin)
    for flusso in flussi:
        riconfigura = getattr(flusso, "reconfigure", None)
        if not callable(riconfigura):
            continue
        try:
            riconfigura(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
