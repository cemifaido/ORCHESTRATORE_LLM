#!/usr/bin/env python3
"""Contratto condiviso di osservabilita': un logger strutturato a riga
singola JSON su stderr, pensato per sostituire gradualmente i print() sparsi
nel progetto (D7 del backlog architetturale, revisione sicurezza v3) - non
una migrazione immediata dei print() esistenti, solo l'interfaccia che i
nuovi moduli (Lotto B/D di D2) devono usare invece di introdurne altri ad
hoc.

Non e' un framework di logging generico: e' una sola funzione, pensata per
essere greppabile riga per riga (un oggetto JSON per riga, come gli altri
formati append-only del progetto - eventi.jsonl, messaggi.jsonl) e per
portare sempre un contesto minimo di correlazione (thread_id/id_compito/
progetto_id) quando disponibile, cosa che un print() libero non garantisce
mai."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

LIVELLI_NOTI = ("debug", "info", "warning", "error")
CAMPI_RISERVATI = frozenset({"timestamp", "modulo", "livello", "messaggio"})


def log_evento(modulo: str, livello: str, messaggio: str, **contesto: Any) -> None:
    """Scrive una riga JSON strutturata su stderr.

    `livello` e' per convenzione uno di LIVELLI_NOTI (non validato a runtime:
    la lettura di questi log e' sempre machine-readable via json.loads, un
    livello inatteso non deve mai far perdere la riga). `contesto` sono campi
    liberi aggiuntivi (thread_id, id_compito, progetto_id, ecc.) - solo
    quelli davvero noti al chiamante, mai inventati per riempire lo schema.

    Le chiavi di CAMPI_RISERVATI non sono ammesse in `contesto`: se fossero
    permesse, un dict merge (**contesto dopo i campi base) le sovrascriverebbe
    silenziosamente, permettendo a un chiamante di falsificare modulo/livello
    di una riga di log (trovato in revisione, 2026-08-26). Rifiuto esplicito
    invece di un merge silenzioso: e' un errore del chiamante, non un caso
    valido da assorbire senza dirlo."""
    sovrapposti = CAMPI_RISERVATI & contesto.keys()
    if sovrapposti:
        raise ValueError(f"contesto non puo' sovrascrivere campi riservati: {sorted(sovrapposti)}")
    riga = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "modulo": modulo,
        "livello": livello,
        "messaggio": messaggio,
        **contesto,
    }
    print(json.dumps(riga, ensure_ascii=False), file=sys.stderr, flush=True)
