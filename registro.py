#!/usr/bin/env python3
from __future__ import annotations

import argparse
import functools
import json
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

import console_utf8
import scrittura_jsonl


RADICE = Path(__file__).resolve().parent
PERCORSO_REGISTRO_PREDEFINITO = Path("dati_locali") / "orchestrazione" / "eventi.jsonl"
PERCORSO_SCHEMA_EVENTO = RADICE / "schema" / "evento.v1.json"
# Dispatch per versione (D14, revisione architetturale v3, 2026-08-27): stesso
# pattern gia' in uso in bacheca.py per messaggio v1/v2. Oggi un solo schema,
# ma il meccanismo di lettura duale e' gia' pronto - una v2 futura si aggiunge
# come voce del dizionario, senza toccare la logica di dispatch qui sotto ne'
# rompere gli eventi storici gia' scritti con versione_schema=1.
SCHEMI_EVENTO_PER_VERSIONE = {1: PERCORSO_SCHEMA_EVENTO}


@functools.lru_cache(maxsize=None)
def _schema_da_percorso(percorso: Path) -> str:
    """Testo canonico dello schema letto da disco, memoizzato per percorso: lo
    stesso file schema veniva riletto e riparsato una volta per ogni riga di
    eventi.jsonl / messaggi.jsonl."""
    return percorso.read_text(encoding="utf-8")


def carica_schema_evento(percorso: Path = PERCORSO_SCHEMA_EVENTO) -> dict[str, Any]:
    return json.loads(_schema_da_percorso(percorso))


def valori_ammessi(campo: str) -> list[str]:
    schema = carica_schema_evento()
    valore = schema["properties"][campo].get("enum")
    if not isinstance(valore, list):
        raise ValueError(f"il campo {campo} non espone enum nello schema")
    return [str(item) for item in valore]


def adesso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def lista_csv(valore: str) -> list[str]:
    if not valore:
        return []
    return [parte.strip() for parte in valore.split(",") if parte.strip()]


@functools.lru_cache(maxsize=None)
def _validatore_da_testo(schema_json: str) -> jsonschema.protocols.Validator:
    schema = json.loads(schema_json)
    classe = jsonschema.validators.validator_for(schema)
    classe.check_schema(schema)
    return classe(schema, format_checker=jsonschema.FormatChecker())


def validatore_per_schema(schema: dict[str, Any]) -> jsonschema.protocols.Validator:
    """Costruisce un validatore JSON Schema riutilizzabile per qualunque schema del
    progetto (evento, messaggio, flusso...), non solo per lo schema evento.

    Il validatore (e la meta-validazione ``check_schema``, ~25ms per schema draft
    2020-12) e' memoizzato sul testo canonico dello schema: senza cache veniva
    ricostruito da zero per ogni singola riga letta da eventi.jsonl / messaggi.jsonl,
    con un costo che cresceva linearmente col registro (centinaia di righe ->
    decine di secondi per una GET /api/bacheca, watcher e hook inclusi)."""
    return _validatore_da_testo(json.dumps(schema, sort_keys=True))


def messaggio_errore(errore: jsonschema.exceptions.ValidationError, dati: dict[str, Any]) -> str:
    """Traduce un errore jsonschema in un messaggio leggibile, per qualunque dato
    validato (evento del registro, messaggio della bacheca, ecc.)."""
    # I due casi piu' comuni restano in italiano per compatibilita' con l'uso esistente
    # (CLI e dashboard); gli altri usano il messaggio di jsonschema, con vera semantica
    # JSON Schema (union type, format, minimum, ecc.) al prezzo di un testo in inglese.
    if errore.validator == "required":
        mancanti = sorted(set(errore.validator_value) - set(dati))
        return "campi obbligatori mancanti: " + ", ".join(mancanti)
    if errore.validator == "additionalProperties":
        proprieta = errore.schema.get("properties", {})
        extra = sorted(set(dati) - set(proprieta))
        return "campi non previsti dallo schema: " + ", ".join(extra)
    campo = ".".join(str(parte) for parte in errore.absolute_path)
    return f"{campo}: {errore.message}" if campo else errore.message


def valida_evento(evento: dict[str, Any], schema: dict[str, Any] | None = None) -> list[str]:
    if schema is None:
        versione = evento.get("versione_schema")
        percorso_schema = SCHEMI_EVENTO_PER_VERSIONE.get(versione) if isinstance(versione, int) else None
        if percorso_schema is None:
            return [
                f"versione_schema non supportata: {versione!r} "
                f"(ammesse: {sorted(SCHEMI_EVENTO_PER_VERSIONE)})"
            ]
        schema = carica_schema_evento(percorso_schema)
    validatore = validatore_per_schema(schema)
    errori = sorted(validatore.iter_errors(evento), key=lambda e: list(e.absolute_path))
    return [messaggio_errore(errore, evento) for errore in errori]


def aggiungi_evento(percorso: Path, evento: dict[str, Any]) -> None:
    """Append serializzato (lock di file + fsync) - stesso contratto di
    `bacheca.aggiungi_messaggio` (rilievo review v4 N9: prima era un `open("a")`
    nudo, lost-update possibile fra scrittori concorrenti su Windows)."""
    scrittura_jsonl.aggiungi_riga_jsonl(percorso, evento, valida=valida_evento)


def leggi_eventi(percorso: Path) -> list[dict[str, Any]]:
    if not percorso.exists():
        return []
    eventi: list[dict[str, Any]] = []
    with percorso.open("r", encoding="utf-8") as file:
        for numero_riga, riga in enumerate(file, start=1):
            riga = riga.strip()
            if not riga:
                continue
            try:
                evento = json.loads(riga)
            except json.JSONDecodeError as errore:
                raise ValueError(f"JSON non valido alla riga {numero_riga}: {errore}") from errore
            errori = valida_evento(evento)
            if errori:
                raise ValueError(f"evento non valido alla riga {numero_riga}: {'; '.join(errori)}")
            eventi.append(evento)
    return eventi


def evento_indica_rework(evento: dict[str, Any]) -> bool:
    return evento.get("esito_gate") == "fallito" or evento.get("verdetto_umano") == "respinto"


def media_voto(somma: int, conteggio: int) -> float | None:
    return round(somma / conteggio, 2) if conteggio else None


def metriche(eventi: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    statistiche: defaultdict[str, dict[str, float | int]] = defaultdict(lambda: {
        "esecuzioni": 0, "costo": 0.0, "latenza": 0, "rework": 0,
        "voto_q_somma": 0, "voto_q_n": 0, "voto_v_somma": 0, "voto_v_n": 0,
    })
    for evento in eventi:
        agente = evento["agente"]
        statistiche[agente]["esecuzioni"] += 1
        statistiche[agente]["costo"] += float(evento.get("costo_stimato_usd") or 0.0)
        statistiche[agente]["latenza"] += int(evento.get("latenza_ms") or 0)
        if evento_indica_rework(evento):
            statistiche[agente]["rework"] += 1
        vq = evento.get("voto_qualita")
        if isinstance(vq, int) and not isinstance(vq, bool):
            statistiche[agente]["voto_q_somma"] += vq
            statistiche[agente]["voto_q_n"] += 1
        vv = evento.get("voto_velocita")
        if isinstance(vv, int) and not isinstance(vv, bool):
            statistiche[agente]["voto_v_somma"] += vv
            statistiche[agente]["voto_v_n"] += 1
    return statistiche


LIVELLI_ARCHITETTURALI = ("database", "backend", "frontend")

# tipo_compito -> livello architetturale (per il cruscotto "quota lavoro per agente").
# interfaccia/database hanno un livello proprio univoco; le categorie trasversali
# (revisione, sicurezza, monitoraggio, orchestrazione, documentazione, errore_test,
# sconosciuto) non hanno un livello unico: in questo progetto sono quasi sempre
# infrastruttura/logica interna, quindi confluiscono in "backend" per default.
MAPPA_LIVELLO_TIPO_COMPITO: dict[str, str] = {
    "interfaccia": "frontend",
    "database": "database",
    "servizi": "backend",
    "errore_test": "backend",
    "revisione": "backend",
    "sicurezza": "backend",
    "monitoraggio": "backend",
    "orchestrazione": "backend",
    "documentazione": "backend",
    "sconosciuto": "backend",
}


def metriche_per_livello(eventi: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Ripartisce gli eventi di ciascun agente per livello architetturale
    (database/backend/frontend), dedotto da tipo_compito tramite
    MAPPA_LIVELLO_TIPO_COMPITO. Conta esecuzioni, non costo: e' una misura di
    "quanto lavoro", non "quanto e' costato" (vedi metriche())."""
    statistiche: defaultdict[str, dict[str, int]] = defaultdict(
        lambda: {livello: 0 for livello in LIVELLI_ARCHITETTURALI}
    )
    for evento in eventi:
        agente = evento["agente"]
        livello = MAPPA_LIVELLO_TIPO_COMPITO.get(evento.get("tipo_compito", "sconosciuto"), "backend")
        statistiche[agente][livello] += 1
    return statistiche


def leggi_eventi_progetto(percorso_progetto: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Legge gli eventi di un progetto. Ritorna (eventi, errore): errore e' None solo se
    il registro non esiste ancora (progetto nuovo) o e' stato letto senza problemi. Un
    registro presente ma corrotto NON deve sembrare un progetto senza eventi: l'errore va
    riportato a chi chiama, non inghiottito, perche' questo e' uno strumento di controllo."""
    percorso_eventi = percorso_progetto / "dati_locali" / "orchestrazione" / "eventi.jsonl"
    if not percorso_eventi.exists():
        return [], None
    try:
        return leggi_eventi(percorso_eventi), None
    except Exception as errore:
        return [], f"registro corrotto ({percorso_eventi}): {errore}"


def statistiche_progetto(
    p_id: str, p_nome: str, p_path: Path, eventi_progetto: list[dict[str, Any]], errore: str | None = None
) -> dict[str, Any]:
    stat = {
        "nome": p_nome,
        "percorso": str(p_path),
        "esecuzioni": len(eventi_progetto),
        "costo": sum(float(ev.get("costo_stimato_usd") or 0.0) for ev in eventi_progetto),
        "latenza": sum(int(ev.get("latenza_ms") or 0) for ev in eventi_progetto),
        "rework": sum(1 for ev in eventi_progetto if evento_indica_rework(ev)),
        "id": p_id,
    }
    if errore:
        stat["errore"] = errore
    return stat


def carica_eventi_multi_progetto(progetti: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Legge gli eventi di piu progetti, li etichetta e calcola le statistiche per progetto.
    Un progetto con registro corrotto contribuisce 0 eventi alle aggregazioni ma la sua voce
    in progetto_stats porta il campo "errore": non deve sparire nel conteggio globale."""
    tutti_eventi: list[dict[str, Any]] = []
    progetto_stats: dict[str, dict[str, Any]] = {}
    for proj in progetti:
        p_id, p_nome, p_path = proj["id"], proj["nome"], Path(proj["percorso"])
        eventi_progetto, errore = leggi_eventi_progetto(p_path)
        for evento in eventi_progetto:
            evento["_progetto_nome"] = p_nome
            evento["_progetto_id"] = p_id
        tutti_eventi.extend(eventi_progetto)
        progetto_stats[p_id] = statistiche_progetto(p_id, p_nome, p_path, eventi_progetto, errore)
    return tutti_eventi, progetto_stats


def costruisci_evento(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "versione_schema": 1,
        "id_evento": args.id_evento or str(uuid.uuid4()),
        "timestamp": args.timestamp or adesso_utc(),
        "id_compito": args.id_compito,
        **({"thread_id": args.thread_id} if getattr(args, "thread_id", "") else {}),
        "agente": args.agente,
        "tipo_compito": args.tipo_compito,
        "stato": args.stato,
        "esito_gate": args.esito_gate,
        "verdetto_umano": args.verdetto_umano,
        "costo_stimato_usd": args.costo_stimato_usd,
        "origine_costo": args.origine_costo,
        "latenza_ms": args.latenza_ms,
        "regole_incluse": lista_csv(args.regole_incluse),
        "file_modificati": lista_csv(args.file_modificati),
        "artefatti_flusso": lista_csv(getattr(args, "artefatti_flusso", "")),
        "voto_qualita": getattr(args, "voto_qualita", None),
        "voto_velocita": getattr(args, "voto_velocita", None),
        "note": args.note,
        "metadati": {},
    }


def comando_aggiungi(args: argparse.Namespace) -> int:
    evento = costruisci_evento(args)
    aggiungi_evento(Path(args.registro), evento)
    print(json.dumps(evento, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def comando_valida(args: argparse.Namespace) -> int:
    eventi = leggi_eventi(Path(args.registro))
    print(f"registro valido: {len(eventi)} eventi")
    return 0


def comando_riepilogo(args: argparse.Namespace) -> int:
    eventi = leggi_eventi(Path(args.registro))
    dati = metriche(eventi)
    print("| Agente | Esecuzioni | Costo USD | Latenza ms | Rework | Qualità | Velocità |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for agente, riga in sorted(dati.items()):
        q = media_voto(int(riga["voto_q_somma"]), int(riga["voto_q_n"]))
        v = media_voto(int(riga["voto_v_somma"]), int(riga["voto_v_n"]))
        print(
            f"| {agente} | {riga['esecuzioni']} | {riga['costo']:.4f} | {riga['latenza']} | "
            f"{riga['rework']} | {q if q is not None else '—'} | {v if v is not None else '—'} |"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    console_utf8.forza_console_utf8()  # `note` libera ristampata a video su console Windows
    parser = argparse.ArgumentParser(description="Registro append-only dell'orchestratore LLM")
    parser.add_argument("--registro", default=str(PERCORSO_REGISTRO_PREDEFINITO))
    sotto = parser.add_subparsers(dest="comando", required=True)

    aggiungi = sotto.add_parser("aggiungi", help="Aggiunge un evento al registro")
    aggiungi.add_argument("--id-evento", default="")
    aggiungi.add_argument("--timestamp", default="")
    aggiungi.add_argument("--id-compito", required=True)
    aggiungi.add_argument("--thread-id", default="", help="UUID del thread bacheca correlato (opzionale)")
    aggiungi.add_argument("--agente", choices=valori_ammessi("agente"), required=True)
    aggiungi.add_argument("--tipo-compito", choices=valori_ammessi("tipo_compito"), required=True)
    aggiungi.add_argument("--stato", choices=valori_ammessi("stato"), required=True)
    aggiungi.add_argument("--esito-gate", choices=valori_ammessi("esito_gate"), default="non_eseguito")
    aggiungi.add_argument("--verdetto-umano", choices=valori_ammessi("verdetto_umano"), default="non_revisionato")
    aggiungi.add_argument("--costo-stimato-usd", type=float, default=0.0)
    aggiungi.add_argument("--origine-costo", choices=valori_ammessi("origine_costo"), default="stimato")
    aggiungi.add_argument("--latenza-ms", type=int, default=0)
    aggiungi.add_argument("--regole-incluse", default="")
    aggiungi.add_argument("--file-modificati", default="")
    aggiungi.add_argument("--artefatti-flusso", default="", help="artefatti runtime aggiuntivi, separati da virgole")
    aggiungi.add_argument("--voto-qualita", type=int, choices=[1, 2, 3, 4, 5], default=None)
    aggiungi.add_argument("--voto-velocita", type=int, choices=[1, 2, 3, 4, 5], default=None)
    aggiungi.add_argument("--note", default="")
    aggiungi.set_defaults(funzione=comando_aggiungi)

    valida = sotto.add_parser("valida", help="Valida tutto il registro")
    valida.set_defaults(funzione=comando_valida)

    riepilogo = sotto.add_parser("riepilogo", help="Mostra metriche sintetiche")
    riepilogo.set_defaults(funzione=comando_riepilogo)

    args = parser.parse_args(argv)
    try:
        return args.funzione(args)
    except Exception as errore:
        print(f"errore: {errore}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
