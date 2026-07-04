#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RADICE = Path(__file__).resolve().parent
PERCORSO_REGISTRO_PREDEFINITO = Path("dati_locali") / "orchestrazione" / "eventi.jsonl"
PERCORSO_SCHEMA_EVENTO = RADICE / "schema" / "evento.v1.json"


def carica_schema_evento(percorso: Path = PERCORSO_SCHEMA_EVENTO) -> dict[str, Any]:
    return json.loads(percorso.read_text(encoding="utf-8"))


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


def _tipo_valido(valore: Any, tipo_schema: str) -> bool:
    if tipo_schema == "string":
        return isinstance(valore, str)
    if tipo_schema == "integer":
        return isinstance(valore, int) and not isinstance(valore, bool)
    if tipo_schema == "number":
        return isinstance(valore, (int, float)) and not isinstance(valore, bool)
    if tipo_schema == "array":
        return isinstance(valore, list)
    if tipo_schema == "object":
        return isinstance(valore, dict)
    return True


def _valida_valore(campo: str, valore: Any, regola: dict[str, Any]) -> list[str]:
    errori: list[str] = []
    if "const" in regola and valore != regola["const"]:
        errori.append(f"{campo} deve essere {regola['const']!r}")
    tipo = regola.get("type")
    if isinstance(tipo, str) and not _tipo_valido(valore, tipo):
        errori.append(f"{campo} deve essere di tipo {tipo}")
    if "enum" in regola and valore not in regola["enum"]:
        errori.append(f"{campo} non valido: {valore!r}")
    if isinstance(valore, (int, float)) and "minimum" in regola and valore < regola["minimum"]:
        errori.append(f"{campo} deve essere >= {regola['minimum']}")
    if isinstance(valore, str) and "minLength" in regola and len(valore) < regola["minLength"]:
        errori.append(f"{campo} deve avere almeno {regola['minLength']} caratteri")
    if isinstance(valore, list) and regola.get("items", {}).get("type") == "string":
        if not all(isinstance(item, str) for item in valore):
            errori.append(f"{campo} deve contenere solo stringhe")
    return errori


def valida_evento(evento: dict[str, Any], schema: dict[str, Any] | None = None) -> list[str]:
    schema = schema or carica_schema_evento()
    proprieta = schema.get("properties", {})
    obbligatori = set(schema.get("required", []))
    errori: list[str] = []

    mancanti = sorted(obbligatori - set(evento))
    if mancanti:
        errori.append("campi obbligatori mancanti: " + ", ".join(mancanti))

    if schema.get("additionalProperties") is False:
        extra = sorted(set(evento) - set(proprieta))
        if extra:
            errori.append("campi non previsti dallo schema: " + ", ".join(extra))

    for campo, valore in evento.items():
        regola = proprieta.get(campo)
        if not isinstance(regola, dict):
            continue
        errori.extend(_valida_valore(campo, valore, regola))
    return errori


def aggiungi_evento(percorso: Path, evento: dict[str, Any]) -> None:
    errori = valida_evento(evento)
    if errori:
        raise ValueError("; ".join(errori))
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with percorso.open("a", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(evento, ensure_ascii=False, sort_keys=True))
        file.write("\n")


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


def leggi_eventi_progetto(percorso_progetto: Path) -> list[dict[str, Any]]:
    percorso_eventi = percorso_progetto / "dati_locali" / "orchestrazione" / "eventi.jsonl"
    if not percorso_eventi.exists():
        return []
    try:
        return leggi_eventi(percorso_eventi)
    except Exception:
        return []


def statistiche_progetto(p_id: str, p_nome: str, p_path: Path, eventi_progetto: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "nome": p_nome,
        "percorso": str(p_path),
        "esecuzioni": len(eventi_progetto),
        "costo": sum(float(ev.get("costo_stimato_usd") or 0.0) for ev in eventi_progetto),
        "latenza": sum(int(ev.get("latenza_ms") or 0) for ev in eventi_progetto),
        "rework": sum(1 for ev in eventi_progetto if evento_indica_rework(ev)),
        "id": p_id,
    }


def carica_eventi_multi_progetto(progetti: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Legge gli eventi di piu progetti, li etichetta e calcola le statistiche per progetto."""
    tutti_eventi: list[dict[str, Any]] = []
    progetto_stats: dict[str, dict[str, Any]] = {}
    for proj in progetti:
        p_id, p_nome, p_path = proj["id"], proj["nome"], Path(proj["percorso"])
        eventi_progetto = leggi_eventi_progetto(p_path)
        for evento in eventi_progetto:
            evento["_progetto_nome"] = p_nome
            evento["_progetto_id"] = p_id
        tutti_eventi.extend(eventi_progetto)
        progetto_stats[p_id] = statistiche_progetto(p_id, p_nome, p_path, eventi_progetto)
    return tutti_eventi, progetto_stats


def costruisci_evento(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "versione_schema": 1,
        "id_evento": args.id_evento or str(uuid.uuid4()),
        "timestamp": args.timestamp or adesso_utc(),
        "id_compito": args.id_compito,
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
    parser = argparse.ArgumentParser(description="Registro append-only dell'orchestratore LLM")
    parser.add_argument("--registro", default=str(PERCORSO_REGISTRO_PREDEFINITO))
    sotto = parser.add_subparsers(dest="comando", required=True)

    aggiungi = sotto.add_parser("aggiungi", help="Aggiunge un evento al registro")
    aggiungi.add_argument("--id-evento", default="")
    aggiungi.add_argument("--timestamp", default="")
    aggiungi.add_argument("--id-compito", required=True)
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
