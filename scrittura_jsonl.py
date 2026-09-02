#!/usr/bin/env python3
"""Contratto condiviso per l'append sicuro di una riga JSON (JSONL) fra
processi concorrenti - usato oggi in modo quasi identico e duplicato da
registro.aggiungi_evento e bacheca.aggiungi_messaggio, pensato per i moduli
che nasceranno dallo split di D2 (backlog architetturale, revisione
sicurezza v3) cosi' non duplicano ancora la stessa logica una terza volta.

Perche' un lock anche per un append puro (non un read-modify-write): H5
(revisione sicurezza v3, 2026-08-25, vedi postino.py) ha dimostrato in
questo stesso progetto che assumere scritture "abbastanza piccole da essere
atomiche" sia sufficiente e' un'assunzione fragile su Windows - un lock
leggero a costo quasi zero (stesso pattern gia' verificato in postino.py) e'
piu' economico di un bug di interleaving da diagnosticare dopo.

`bacheca.aggiungi_messaggio` e' migrata a questo modulo (2026-09-02, rilievo
Codex durante la revisione del server MCP: prima era un `open("a")` nudo).
`consegne_risveglio.py` lo usa dalla nascita. `registro.aggiungi_evento` NON
e' ancora migrato: e' una decisione del lotto che lo tocchera'."""
from __future__ import annotations

import contextlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

TIMEOUT_LOCK_SECONDI_PREDEFINITO = 10.0

# Fissa e indipendente dal timeout del chiamante (vedi sotto il perche'):
# un append JSONL e' un'operazione da millisecondi, 30s e' gia' molto
# generoso per un disco lento/antivirus che scansiona il file.
SOGLIA_LOCK_ABBANDONATO_SECONDI = 30.0


def _percorso_lock(percorso: Path) -> Path:
    return percorso.with_suffix(percorso.suffix + ".lock")


@contextlib.contextmanager
def _blocco(percorso: Path, *, timeout_secondi: float = TIMEOUT_LOCK_SECONDI_PREDEFINITO):
    """Lock a file (stesso pattern di postino._blocco_stato): creazione
    atomica garantita dal sistema operativo sia su Windows sia su POSIX
    (os.O_CREAT | os.O_EXCL), senza bisogno di fcntl/msvcrt specifici per
    piattaforma. Un lock piu' vecchio di SOGLIA_LOCK_ABBANDONATO_SECONDI si
    considera abbandonato (processo terminato senza pulire) e viene rimosso
    invece di bloccare per sempre.

    La soglia di abbandono e' un valore FISSO, non `timeout_secondi`: sono
    due concetti distinti che nel pattern originale di postino coincidevano
    per caso (un solo timeout usato per entrambi) - con timeout brevi (pochi
    secondi) questo rende TimeoutError irraggiungibile, perche' un lock
    ancora attivamente detenuto comincerebbe a sembrare "abbandonato" prima
    ancora che il chiamante rinunci. "Quanto sono disposto ad aspettare"
    (per chiamata) e "da quanto un lock e' certamente abbandonato" (fisso,
    di sistema) devono restare indipendenti."""
    percorso_lock = _percorso_lock(percorso)
    percorso_lock.parent.mkdir(parents=True, exist_ok=True)
    scadenza = time.monotonic() + timeout_secondi
    while True:
        try:
            fd = os.open(percorso_lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except (FileExistsError, PermissionError):
            # PermissionError: su Windows la creazione O_CREAT|O_EXCL puo'
            # sollevarlo invece di FileExistsError quando un altro processo
            # ha il file in mano nello stesso istante - stessa contesa di
            # lock, va trattato allo stesso modo, non come un errore reale
            # di permessi (quello, se genuino, fa comunque scadere il
            # timeout sotto invece di restare bloccato per sempre).
            try:
                eta_lock = time.time() - percorso_lock.stat().st_mtime
            except OSError:
                eta_lock = 0.0
            if eta_lock > SOGLIA_LOCK_ABBANDONATO_SECONDI:
                with contextlib.suppress(OSError):
                    percorso_lock.unlink()
                continue
            if time.monotonic() > scadenza:
                raise TimeoutError(f"lock su {percorso_lock} non ottenuto entro {timeout_secondi}s")
            time.sleep(0.02)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            percorso_lock.unlink()


def aggiungi_riga_jsonl(
    percorso: Path,
    record: dict[str, Any],
    *,
    valida: Callable[[dict[str, Any]], list[str]] | None = None,
    timeout_lock_secondi: float = TIMEOUT_LOCK_SECONDI_PREDEFINITO,
) -> None:
    """Valida (se richiesto) e appende un record come riga JSON, sotto lock
    per serializzare scritture concorrenti multi-processo.

    Solleva ValueError se `valida` ritorna errori - nessuna scrittura avviene
    in quel caso. La validazione avviene PRIMA di acquisire il lock: e'
    intenzionale, un record invalido non deve mai contendere il lock con gli
    scrittori legittimi."""
    if valida is not None:
        errori = valida(record)
        if errori:
            raise ValueError("; ".join(errori))
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with _blocco(percorso, timeout_secondi=timeout_lock_secondi):
        _scrivi_riga(percorso, record)


def _scrivi_riga(percorso: Path, record: dict[str, Any]) -> None:
    with percorso.open("a", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        file.write("\n")
        file.flush()
        os.fsync(file.fileno())


def transazione_jsonl(
    percorso: Path,
    calcola_record: Callable[[], dict[str, Any] | None],
    *,
    valida: Callable[[dict[str, Any]], list[str]] | None = None,
    timeout_lock_secondi: float = TIMEOUT_LOCK_SECONDI_PREDEFINITO,
) -> dict[str, Any] | None:
    """Compare-and-set su un JSONL: esegue `calcola_record()` **sotto il lock
    del file**, cosi' che la lettura dello stato corrente, la verifica di una
    precondizione e l'append siano un'unica sezione critica serializzata fra
    processi (S14.3, docs/RFC_PIANO_STEP_POSSEDUTI.md).

    `calcola_record` deve leggere lo stato dall'interno (il lock e' gia' preso)
    e ritornare il record da appendere, oppure None se la precondizione non e'
    soddisfatta (in tal caso non si scrive nulla). Ritorna il record scritto o
    None."""
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with _blocco(percorso, timeout_secondi=timeout_lock_secondi):
        record = calcola_record()
        if record is None:
            return None
        if valida is not None:
            errori = valida(record)
            if errori:
                raise ValueError("; ".join(errori))
        _scrivi_riga(percorso, record)
        return record
