#!/usr/bin/env python3
"""Validatore read-only dei flussi dichiarati dell'orchestratore."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

import motore_flusso


RADICE = Path(__file__).resolve().parent
PERCORSO_SCHEMA_PREDEFINITO = RADICE / "schema" / "flusso.v1.json"
PERCORSO_FLUSSO_PREDEFINITO = RADICE / "config" / "flussi" / "compito_standard.json"

Grafo = dict[str, set[str]]
Mappa = dict[str, list[str]]


def carica_json(percorso: Path) -> Any:
    return json.loads(percorso.read_text(encoding="utf-8"))


def _formato_errore(errore: Any) -> str:
    percorso = ".".join(str(parte) for parte in errore.absolute_path) or "radice"
    return f"{percorso}: {errore.message}"


def _errori_schema(dati: Any, schema: dict[str, Any]) -> list[str]:
    validatore = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        _formato_errore(errore)
        for errore in sorted(validatore.iter_errors(dati), key=lambda e: list(e.absolute_path))
    ]


def _indicizza_passi(passi: list[Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    per_id: dict[str, dict[str, Any]] = {}
    errori: list[str] = []
    for passo in passi:
        if not isinstance(passo, dict) or not isinstance(passo.get("id"), str):
            continue
        identita = passo["id"]
        if identita in per_id:
            errori.append(f"id passo duplicato: {identita!r}")
        else:
            per_id[identita] = passo
    return per_id, errori


def _mappa_artefatti(per_id: dict[str, dict[str, Any]]) -> tuple[Mappa, Mappa, Mappa, list[str]]:
    produttori: Mappa = defaultdict(list)
    consumatori: Mappa = defaultdict(list)
    consumatori_opzionali: Mappa = defaultdict(list)
    errori: list[str] = []
    for identita, passo in per_id.items():
        for artefatto in passo["produce"]:
            produttori[artefatto].append(identita)
        for artefatto in passo["richiede"]:
            consumatori[artefatto].append(identita)
        for artefatto in passo.get("richiede_opzionali", []):
            consumatori_opzionali[artefatto].append(identita)
        sovrapposti = set(passo["richiede"]).intersection(passo.get("richiede_opzionali", []))
        if sovrapposti:
            errori.append(f"passo {identita!r}: artefatti sia obbligatori sia opzionali: {', '.join(sorted(sovrapposti))}")
    return produttori, consumatori, consumatori_opzionali, errori


def _errore_produttore(per_id: dict[str, dict[str, Any]], produttori: Mappa, artefatto: str, utilizzatori: list[str], opzionale: bool) -> str | None:
    etichetta = "artefatto opzionale" if opzionale else "artefatto"
    if not produttori.get(artefatto):
        return f"{etichetta} richiesto senza produttore: {artefatto!r} (richiesto da {', '.join(utilizzatori)})"
    if len(produttori[artefatto]) > 1:
        return f"{etichetta} con produttori ambigui: {artefatto!r} ({', '.join(produttori[artefatto])})"
    produttore_opzionale = bool(per_id[produttori[artefatto][0]].get("opzionale"))
    if not opzionale and produttore_opzionale:
        return f"artefatto obbligatorio prodotto da passo opzionale: {artefatto!r} (usa richiede_opzionali)"
    if opzionale and not produttore_opzionale:
        return f"artefatto opzionale prodotto da passo non opzionale: {artefatto!r}"
    return None


def _errori_dipendenze(per_id: dict[str, dict[str, Any]], produttori: Mappa, consumatori: Mappa, consumatori_opzionali: Mappa) -> list[str]:
    errori: list[str] = []
    for opzionale, mappa in ((False, consumatori), (True, consumatori_opzionali)):
        for artefatto, utilizzatori in sorted(mappa.items()):
            errore = _errore_produttore(per_id, produttori, artefatto, utilizzatori, opzionale)
            if errore:
                errori.append(errore)
    for artefatto, produttori_artefatto in sorted(produttori.items()):
        consumato = consumatori.get(artefatto) or consumatori_opzionali.get(artefatto)
        tutti_opzionali = all(per_id[p].get("opzionale") for p in produttori_artefatto)
        if not consumato and not tutti_opzionali:
            errori.append(f"artefatto prodotto ma mai consumato: {artefatto!r} (prodotto da {', '.join(produttori_artefatto)})")
    return errori


def _grafo(per_id: dict[str, dict[str, Any]], produttori: Mappa, consumatori: Mappa, consumatori_opzionali: Mappa) -> tuple[Grafo, Grafo]:
    successori: Grafo = {identita: set() for identita in per_id}
    predecessori: Grafo = {identita: set() for identita in per_id}
    for artefatto in set(consumatori).union(consumatori_opzionali):
        utilizzatori = consumatori[artefatto] + consumatori_opzionali[artefatto]
        for produttore in produttori.get(artefatto, []):
            for utilizzatore in utilizzatori:
                if produttore != utilizzatore:
                    successori[produttore].add(utilizzatore)
                    predecessori[utilizzatore].add(produttore)
    return successori, predecessori


def _raggiungibili(iniziali: list[str], successori: Grafo) -> set[str]:
    raggiunti: set[str] = set(iniziali)
    coda = deque(iniziali)
    while coda:
        corrente = coda.popleft()
        for successore in successori[corrente]:
            if successore not in raggiunti:
                raggiunti.add(successore)
                coda.append(successore)
    return raggiunti


def _errori_raggiungibilita(per_id: dict[str, dict[str, Any]], successori: Grafo, predecessori: Grafo) -> list[str]:
    errori: list[str] = []
    iniziali = [identita for identita, passo in per_id.items() if passo["iniziale"]]
    if len(iniziali) != 1:
        errori.append(f"il flusso deve dichiarare esattamente un passo iniziale (trovati: {len(iniziali)})")
    for identita in iniziali:
        if predecessori[identita]:
            errori.append(f"passo iniziale con predecessori: {identita!r}")
    for identita in sorted(set(per_id) - _raggiungibili(iniziali, successori)):
        errori.append(f"passo orfano/non raggiungibile: {identita!r}")
    return errori


def _antenati(identita: str, predecessori: Grafo) -> set[str]:
    antenati: set[str] = set()
    coda = deque(predecessori[identita])
    while coda:
        predecessore = coda.popleft()
        if predecessore in antenati:
            continue
        antenati.add(predecessore)
        coda.extend(predecessori[predecessore])
    return antenati


def _errori_irreversibili(per_id: dict[str, dict[str, Any]], predecessori: Grafo) -> list[str]:
    errori: list[str] = []
    approvazioni = {identita for identita, passo in per_id.items() if passo.get("approvazione_umana") is True}
    for identita, passo in per_id.items():
        if passo["irreversibile"] and not approvazioni.intersection(_antenati(identita, predecessori)):
            errori.append(f"passo irreversibile senza approvazione umana a monte: {identita!r}")
    return errori


def valida_flusso(dati: Any, schema: dict[str, Any]) -> list[str]:
    """Ritorna gli errori dello schema e delle invarianti tra passi."""
    errori = _errori_schema(dati, schema)
    if errori or not isinstance(dati, dict) or not isinstance(dati.get("passi"), list):
        return errori

    per_id, errori = _indicizza_passi(dati["passi"])
    if len(per_id) != len(dati["passi"]):
        return errori

    produttori, consumatori, consumatori_opzionali, errori_sovrapposizioni = _mappa_artefatti(per_id)
    errori.extend(errori_sovrapposizioni)
    errori.extend(_errori_dipendenze(per_id, produttori, consumatori, consumatori_opzionali))

    successori, predecessori = _grafo(per_id, produttori, consumatori, consumatori_opzionali)
    errori.extend(_errori_raggiungibilita(per_id, successori, predecessori))
    errori.extend(_errori_irreversibili(per_id, predecessori))
    try:
        motore_flusso.compila_flusso(dati)
    except ValueError as errore:
        errori.append(f"flusso non compilabile: {errore}")
    return errori


def valida_file(percorso_flusso: Path, percorso_schema: Path = PERCORSO_SCHEMA_PREDEFINITO) -> list[str]:
    try:
        dati = carica_json(percorso_flusso)
    except (OSError, json.JSONDecodeError) as errore:
        return [f"impossibile leggere il flusso {percorso_flusso}: {errore}"]
    try:
        schema = carica_json(percorso_schema)
    except (OSError, json.JSONDecodeError) as errore:
        return [f"impossibile leggere lo schema {percorso_schema}: {errore}"]
    return valida_flusso(dati, schema)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida un flusso dichiarato (read-only).")
    parser.add_argument("flusso", nargs="?", type=Path, default=PERCORSO_FLUSSO_PREDEFINITO)
    parser.add_argument("--schema", type=Path, default=PERCORSO_SCHEMA_PREDEFINITO)
    args = parser.parse_args(argv)
    errori = valida_file(args.flusso, args.schema)
    if errori:
        for errore in errori:
            print(f"errore: {errore}", file=sys.stderr)
        return 1
    print(f"flusso valido: {args.flusso}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
