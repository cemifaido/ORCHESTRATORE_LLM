#!/usr/bin/env python3
"""Controllo pre-dispatch della contesa sul working tree — l'"80% leggero" di
§15 Slice C (git worktree), che resta differita (vedi
docs/PIANO_INDUSTRIALIZZAZIONE.md §15.4).

Idea: prima di spawnare la CLI di un agente headless, guarda se sul working tree
ci sono modifiche NON committate che toccano i file che quell'agente sta per
scrivere (il suo `write_set` di piano). Se sì, il dispatch si ferma invece di
far pestare due scritture non committate — il pilastro che si perde senza
worktree. Non è una barriera di sicurezza: se git non è disponibile o il thread
non dichiara un piano a corsie, il check si fa da parte (fail-open) e il
dispatch prosegue come prima.

Il check NON sa attribuire le modifiche: blocca su modifiche non committate di
*chiunque* (un altro dispatch, l'operatore, tu stesso in una sessione parallela).
È una contesa del working tree, non un'accusa a un attore specifico.

Ogni contesa rilevata va in `contese.jsonl` (append-only): serve a decidere su
dati reali se e quando costruire davvero Slice C.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable

import piano_overlap
import registro
import scrittura_jsonl

LIBERO = "libero"
CONTESO = "conteso"
NON_VERIFICABILE = "non_verificabile"  # git assente / non un repo -> fail-open

# Un write_set con glob largo ('docs/**') su un tree molto sporco puo' far
# collidere decine di file: la DECISIONE di bloccare resta (conservativa), ma
# la lista che finisce in nota/JSONL va limitata per non gonfiare i messaggi.
_MAX_FILE_ELENCATI = 20


def _percorso_log(radice: Path) -> Path:
    return radice / "dati_locali" / "orchestrazione" / "contese.jsonl"


def file_non_committati(
    radice: Path, *, esegui: Callable[..., Any] = subprocess.run
) -> list[str] | None:
    """Percorsi repo-relative ('/') con modifiche non committate: file tracked
    modificati + file untracked. `None` se la cartella non è un repo git o git
    non è invocabile (il chiamante allora NON blocca).

    `--porcelain=v1 -z`: i record sono separati da NUL e i percorsi sono
    letterali (nessun quoting/escaping C, nessuna ambiguità sul ' -> ' dei
    rename) — rilievo Codex 2026-09-03. Un record di rename/copia (X o Y = R/C)
    porta due percorsi: quello nuovo nel record, quello vecchio nel campo
    successivo; li includiamo entrambi (conservativo)."""
    try:
        risultato = esegui(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=str(radice), capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace", check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if getattr(risultato, "returncode", 1) != 0:
        return None
    campi = [c for c in (risultato.stdout or "").split("\0")]
    fuori: list[str] = []
    i = 0
    while i < len(campi):
        record = campi[i]
        if len(record) < 4:
            i += 1
            continue
        stato_xy, percorso = record[:2], record[3:]
        fuori.append(percorso.replace("\\", "/"))
        if "R" in stato_xy or "C" in stato_xy:  # rename/copy: c'è anche l'origine
            if i + 1 < len(campi) and campi[i + 1]:
                fuori.append(campi[i + 1].replace("\\", "/"))
            i += 2
        else:
            i += 1
    return sorted(set(fuori))


def valuta_contesa(
    radice: Path, write_set: object, *, esegui: Callable[..., Any] = subprocess.run
) -> dict[str, Any]:
    """Il working tree ha modifiche non committate che toccano `write_set`?

    - `{"esito": "libero"}` — nessun file conteso (o nessun write_set dichiarato:
      senza un piano a corsie non c'è base per bloccare, §14.3 è l'altro pilastro);
    - `{"esito": "conteso", "file": [...]}` — sovrapposizione con file sporchi;
    - `{"esito": "non_verificabile"}` — git non disponibile: il chiamante non blocca.
    """
    ws = piano_overlap.normalizza_set(write_set if isinstance(write_set, list) else [])
    if not ws:
        return {"esito": LIBERO, "motivo": "nessun_write_set"}
    sporchi = file_non_committati(radice, esegui=esegui)
    if sporchi is None:
        return {"esito": NON_VERIFICABILE}
    if not sporchi:
        return {"esito": LIBERO}
    sporchi_norm = piano_overlap.normalizza_set(sporchi) or []
    if piano_overlap.interseca(sporchi_norm, ws) == piano_overlap.DISGIUNTO:
        return {"esito": LIBERO}
    # normalizza_set() ordina/dedupe: per sapere QUALI file collidono va
    # rifatto uno per uno, non con uno zip che sarebbe disallineato.
    contesi = sorted({
        grezzo for grezzo in sporchi
        if (n := piano_overlap.normalizza_set([grezzo]))
        and piano_overlap.interseca(n, ws) != piano_overlap.DISGIUNTO
    }) or sorted(set(sporchi))
    return {
        "esito": CONTESO,
        "file": contesi[:_MAX_FILE_ELENCATI],
        "totale": len(contesi),
    }


def registra_contesa(
    radice: Path, *, agente: str, thread_id: str,
    write_set: list[str], file_contesi: list[str], totale: int | None = None,
) -> None:
    """Append-only in `contese.jsonl`. Best-effort: un errore qui non deve mai
    far fallire il dispatch (che si sta già fermando per altri motivi).

    `file_contesi` puo' arrivare gia' troncato da `valuta_contesa`: `totale` (il
    conteggio reale prima del troncamento) va passato esplicitamente, altrimenti
    il JSONL - che e' proprio il dato per decidere su Slice C - sottostima."""
    contesi = sorted(set(file_contesi))
    record = {
        "versione_schema": 1,
        "quando": registro.adesso_utc(),
        "agente": agente,
        "thread_id": thread_id,
        "write_set": [w for w in write_set if isinstance(w, str)],
        "file_contesi": contesi[:_MAX_FILE_ELENCATI],
        "file_contesi_totale": totale if totale is not None else len(contesi),
    }
    try:
        scrittura_jsonl.aggiungi_riga_jsonl(_percorso_log(radice), record)
    except (OSError, ValueError, TimeoutError):
        pass
