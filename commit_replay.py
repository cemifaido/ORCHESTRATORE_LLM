#!/usr/bin/env python3
"""Ricostruisce, a partire da un commit git e dal registro condiviso, la sequenza di
eventi che hanno portato a quel commit — per il pannello "Live Agent Handoff" in
modalita' replay (dati reali gia' accaduti, non uno scenario finto). Vedi
docs/ORCHESTRAZIONE_LAVORATORI.md, sezione Capoturno.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RADICE = Path(__file__).resolve().parent
sys.path.insert(0, str(RADICE))

import registro  # noqa: E402

# GPT-4o-mini, prezzo pubblico per i token in input (riferimento dichiarato, non il
# costo reale dell'orchestratore): usato solo per stimare quanto sarebbe costato lo
# stesso controllo di routine su un modello a pagamento invece che sul modello locale
# gratuito. Scelto il prezzo input (il piu' basso) come stima conservativa, per non
# gonfiare il risparmio mostrato.
PREZZO_RIFERIMENTO_USD_PER_TOKEN = 0.15 / 1_000_000
MODELLO_RIFERIMENTO = "GPT-4o-mini (prezzo pubblico input, stima conservativa)"

# tipo_compito che, se svolti da un agente diverso da 'locale', rappresentano lavoro
# di verifica/controllo che e' finito su un agente a pagamento invece che essere
# assorbito gratis dal triage locale.
TIPI_VERIFICA_A_PAGAMENTO = {"revisione", "sicurezza", "errore_test"}


def _a_utc(timestamp_iso: str) -> datetime:
    """Converte un timestamp ISO8601 (con 'Z' o offset esplicito, come quelli emessi
    da git e dal registro) in un datetime timezone-aware normalizzato a UTC.
    Confrontare le stringhe grezze sarebbe sbagliato: git usa il fuso locale del
    computer (es. +02:00), il registro usa sempre UTC ('Z') — un confronto testuale
    ignorerebbe la differenza e sfaserebbe la finestra del commit."""
    normalizzato = timestamp_iso.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalizzato)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _timestamp_commit(percorso_repo: Path, riferimento: str) -> str | None:
    risultato = subprocess.run(
        ["git", "show", "-s", "--format=%cI", riferimento],
        cwd=percorso_repo, capture_output=True, text=True, encoding="utf-8", timeout=10,
    )
    if risultato.returncode != 0:
        return None
    return risultato.stdout.strip() or None


def lista_commit(percorso_repo: Path, limite: int = 20) -> list[dict[str, str]]:
    # encoding="utf-8" esplicito: su Windows subprocess.run(text=True) userebbe la
    # codifica di default della console (spesso cp1252), mangliando em-dash e accenti
    # nei messaggi di commit.
    risultato = subprocess.run(
        ["git", "log", f"-{limite}", "--format=%H|%cI|%an|%s"],
        cwd=percorso_repo, capture_output=True, text=True, encoding="utf-8", timeout=10,
    )
    if risultato.returncode != 0:
        raise ValueError(f"impossibile leggere git log: {risultato.stderr.strip()}")
    commit = []
    for riga in risultato.stdout.strip().splitlines():
        if not riga:
            continue
        hash_commit, data, autore, messaggio = riga.split("|", 3)
        commit.append({"hash": hash_commit, "data": data, "autore": autore, "messaggio": messaggio})
    return commit


def finestra_temporale_commit(percorso_repo: Path, hash_commit: str) -> tuple[datetime, datetime]:
    """Ritorna (inizio, fine) in UTC: fine e' il timestamp del commit scelto, inizio
    quello del commit precedente (o l'inizio dei tempi se e' il primo commit)."""
    fine_iso = _timestamp_commit(percorso_repo, hash_commit)
    if fine_iso is None:
        raise ValueError(f"commit non trovato: {hash_commit}")
    inizio_iso = _timestamp_commit(percorso_repo, f"{hash_commit}~1")
    inizio = _a_utc(inizio_iso) if inizio_iso else datetime(1970, 1, 1, tzinfo=timezone.utc)
    return inizio, _a_utc(fine_iso)


def eventi_nella_finestra(percorso_registro: Path, inizio: datetime, fine: datetime) -> list[dict[str, Any]]:
    if not percorso_registro.exists():
        return []
    tutti = registro.leggi_eventi(percorso_registro)
    return [e for e in tutti if inizio < _a_utc(e["timestamp"]) <= fine]


def stima_risparmio(eventi: list[dict[str, Any]]) -> dict[str, Any]:
    """Percentuale di controlli di verifica gestiti gratis dal modello locale sul
    totale dei controlli di verifica nella finestra (locale + eventuali revisioni a
    pagamento), piu' una stima in $ basata sui token reali misurati — non un numero
    inventato: contribuiscono solo eventi agente='locale' con token_totali noto."""
    eventi_locale = [e for e in eventi if e.get("agente") == "locale"]
    eventi_a_pagamento = [
        e for e in eventi
        if e.get("agente") != "locale" and e.get("tipo_compito") in TIPI_VERIFICA_A_PAGAMENTO
    ]
    totale_verifica = len(eventi_locale) + len(eventi_a_pagamento)

    token_totali_locale = sum(int(e.get("metadati", {}).get("token_totali") or 0) for e in eventi_locale)
    risparmio_usd = token_totali_locale * PREZZO_RIFERIMENTO_USD_PER_TOKEN

    return {
        "controlli_locale": len(eventi_locale),
        "controlli_a_pagamento": len(eventi_a_pagamento),
        "percentuale_gratis": round(len(eventi_locale) / totale_verifica * 100, 1) if totale_verifica else None,
        "token_totali_locale": token_totali_locale,
        "risparmio_stimato_usd": round(risparmio_usd, 6),
        "modello_riferimento": MODELLO_RIFERIMENTO,
    }
