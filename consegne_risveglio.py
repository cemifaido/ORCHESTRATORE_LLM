#!/usr/bin/env python3
"""Stati di consegna del risveglio (PIANO_INDUSTRIALIZZAZIONE.md §15 Slice A,
docs/RFC_STATI_CONSEGNA_RISVEGLIO.md).

Supera il bit binario `notificato` di `risvegli_notificati.json` con una
macchina a stati per coppia `(agente, id_messaggio)`:

    in_attesa -> attenzione_richiamata -> acquisito_da_hook -> preso_in_carico
                          `-> chiuso_senza_consegna   (rinuncia del watcher)

Persistenza (tutta append-only, mai riscritture in place):
- `consegne_risveglio.jsonl`  : una riga per transizione scritta dal watcher.
- `hook_contesto.jsonl`       : una riga per coppia inclusa nel contesto emesso
                                dall'hook. L'hook resta di sola aggiunta.
- la bacheca stessa           : un messaggio dell'agente con
                                `correla_a = id_messaggio` prova `preso_in_carico`.

`risvegli_notificati.json` NON e' toccato qui: resta la cache calda del watcher
("questa coppia e' gia' stata gestita?"). Se la proiezione ha un bug, il watcher
si comporta comunque bene. Questo modulo e' additivo.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import scrittura_jsonl

RADICE = Path(__file__).resolve().parent

IN_ATTESA = "in_attesa"
ATTENZIONE_RICHIAMATA = "attenzione_richiamata"
ACQUISITO_DA_HOOK = "acquisito_da_hook"
PRESO_IN_CARICO = "preso_in_carico"
CHIUSO_SENZA_CONSEGNA = "chiuso_senza_consegna"

# Scala monotona in avanti. `chiuso_senza_consegna` NON e' nella scala: e'
# terminale per il watcher (raggiungibile solo da in_attesa/attenzione_richiamata)
# ma una prova esterna successiva (hook o bacheca) lo scavalca.
_AVANZAMENTO = {
    IN_ATTESA: 0,
    ATTENZIONE_RICHIAMATA: 1,
    ACQUISITO_DA_HOOK: 2,
    PRESO_IN_CARICO: 3,
}
STATI_VALIDI = frozenset({*_AVANZAMENTO, CHIUSO_SENZA_CONSEGNA})

_NOME_LOG = "consegne_risveglio.jsonl"
_NOME_HOOK_CONTESTO = "hook_contesto.jsonl"


def percorso_log(radice: Path = RADICE) -> Path:
    return radice / "dati_locali" / "orchestrazione" / _NOME_LOG


def percorso_hook_contesto(radice: Path = RADICE) -> Path:
    return radice / "dati_locali" / "orchestrazione" / _NOME_HOOK_CONTESTO


def _adesso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _leggi_jsonl(percorso: Path) -> list[dict[str, Any]]:
    if not percorso.exists():
        return []
    righe: list[dict[str, Any]] = []
    for riga in percorso.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if not riga:
            continue
        try:
            valore = json.loads(riga)
        except json.JSONDecodeError:
            continue  # una riga corrotta non deve far cadere la proiezione
        if isinstance(valore, dict):
            righe.append(valore)
    return righe


def _chiave(agente: str, id_messaggio: str) -> str:
    return f"{agente}:{id_messaggio}"


def registra_transizione(
    radice: Path,
    *,
    agente: str,
    id_messaggio: str,
    stato: str,
    origine: str,
    motivo: str | None = None,
    canale: str | None = None,
) -> dict[str, Any] | None:
    """Appende una transizione al log. Ritorna il record scritto, oppure None se
    lo stato non e' valido (non solleva: il watcher non deve cadere per questo).
    """
    if stato not in STATI_VALIDI:
        return None
    record = {
        "versione_schema": 1,
        "agente": agente,
        "id_messaggio": id_messaggio,
        "stato": stato,
        "motivo": motivo,
        "canale": canale,
        "origine": origine,
        "quando": _adesso(),
    }
    try:
        scrittura_jsonl.aggiungi_riga_jsonl(percorso_log(radice), record)
    except (OSError, TimeoutError):
        return None
    return record


def registra_reset(
    radice: Path, *, agente: str, id_messaggio: str, motivo: str | None = None
) -> dict[str, Any] | None:
    """Reset esplicito e umano di una coppia: la proiezione ignora tutto cio' che
    e' nel log PRIMA di questa riga (regola 4 della RFC). Una prova esterna
    successiva (hook, correla_a) resta comunque valida - il reset riporta indietro
    la vista del watcher, non la verita' del thread."""
    return registra_transizione(
        radice, agente=agente, id_messaggio=id_messaggio,
        stato=IN_ATTESA, origine="reset_umano", motivo=motivo,
    )


def registra_contesto_hook(
    radice: Path, coppie: list[tuple[str, str, str]]
) -> int:
    """`coppie` = [(agente, id_messaggio, thread_id), ...] incluse nel contesto
    emesso dall'hook. Scrive una riga per coppia non ancora presente. Ritorna il
    numero di righe scritte. Non solleva: un hook che fallisce qui deve comunque
    emettere il contesto.
    """
    if not coppie:
        return 0
    percorso = percorso_hook_contesto(radice)
    gia_viste = {
        _chiave(r["agente"], r["id_messaggio"])
        for r in _leggi_jsonl(percorso)
        if r.get("agente") and r.get("id_messaggio")
    }
    scritte = 0
    for agente, id_messaggio, thread_id in coppie:
        if _chiave(agente, id_messaggio) in gia_viste:
            continue
        record = {
            "versione_schema": 1,
            "agente": agente,
            "id_messaggio": id_messaggio,
            "thread_id": thread_id,
            "quando": _adesso(),
        }
        try:
            scrittura_jsonl.aggiungi_riga_jsonl(percorso, record)
            gia_viste.add(_chiave(agente, id_messaggio))
            scritte += 1
        except (OSError, TimeoutError):
            break
    return scritte


def _prove_bacheca(messaggi: list[dict[str, Any]]) -> set[str]:
    """Coppie (agente, id_messaggio) per cui esiste un messaggio dell'agente con
    `correla_a` = quell'id: prova diretta di `preso_in_carico`."""
    prove: set[str] = set()
    for m in messaggi:
        correla_a = m.get("correla_a")
        mittente = m.get("mittente")
        if correla_a and mittente:
            prove.add(_chiave(mittente, correla_a))
    return prove


def _stato_coppia(
    righe_log: list[dict[str, Any]],
    *,
    in_notificati: bool,
    ha_hook: bool,
    ha_prova_bacheca: bool,
) -> tuple[str, str | None]:
    if ha_prova_bacheca:
        return PRESO_IN_CARICO, None

    # Regola 4: un reset umano azzera tutto cio' che lo precede nel log, scollega
    # dalla cache legacy `notificati` e dal contesto hook precedente (l'umano dice
    # esplicitamente "trattala come nuova"). Solo la prova di bacheca (correla_a,
    # gestita sopra) sopravvive: quella e' un fatto, non una vista del watcher.
    ultimo_reset = max(
        (i for i, r in enumerate(righe_log) if r.get("origine") == "reset_umano"),
        default=-1,
    )
    if ultimo_reset >= 0:
        righe_log = righe_log[ultimo_reset + 1:]
        in_notificati = False
        ha_hook = False

    livello = ATTENZIONE_RICHIAMATA if in_notificati else IN_ATTESA
    motivo_chiuso: str | None = None
    for r in righe_log:
        stato = r.get("stato")
        if stato == CHIUSO_SENZA_CONSEGNA:
            if livello in (IN_ATTESA, ATTENZIONE_RICHIAMATA):
                motivo_chiuso = r.get("motivo")
        elif stato in _AVANZAMENTO and _AVANZAMENTO[stato] > _AVANZAMENTO[livello]:
            livello = stato
            motivo_chiuso = None  # un avanzamento reale supera una rinuncia precedente

    if ha_hook and _AVANZAMENTO[livello] < _AVANZAMENTO[ACQUISITO_DA_HOOK]:
        # l'agente ha dimostrabilmente visto il messaggio: scavalca anche una
        # rinuncia del watcher (regola 3 della RFC).
        return ACQUISITO_DA_HOOK, None

    if motivo_chiuso is not None:
        return CHIUSO_SENZA_CONSEGNA, motivo_chiuso
    return livello, None


def proietta(
    radice: Path,
    messaggi: list[dict[str, Any]],
    *,
    notificati: dict[str, list[str]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Stato corrente di ogni coppia `(agente, id_messaggio)` nota, come
    `{"<agente>:<id>": {"agente", "id_messaggio", "stato", "motivo"}}`.

    `notificati` e' il blocco `notificati` di `risvegli_notificati.json` (cache
    legacy): una coppia presente li' ma assente dal log vale
    `attenzione_richiamata` (il watcher se n'era occupato).
    """
    notificati = notificati or {}
    log = _leggi_jsonl(percorso_log(radice))
    hook = _leggi_jsonl(percorso_hook_contesto(radice))
    prove = _prove_bacheca(messaggi)

    log_per_coppia: dict[str, list[dict[str, Any]]] = {}
    for r in log:
        if r.get("agente") and r.get("id_messaggio"):
            log_per_coppia.setdefault(_chiave(r["agente"], r["id_messaggio"]), []).append(r)
    hook_coppie = {
        _chiave(r["agente"], r["id_messaggio"])
        for r in hook
        if r.get("agente") and r.get("id_messaggio")
    }
    notificati_coppie = {
        _chiave(agente, idm) for agente, ids in notificati.items() for idm in ids
    }

    tutte = set(log_per_coppia) | hook_coppie | notificati_coppie | prove
    risultato: dict[str, dict[str, Any]] = {}
    for chiave in tutte:
        agente, _, id_messaggio = chiave.partition(":")
        stato, motivo = _stato_coppia(
            log_per_coppia.get(chiave, []),
            in_notificati=chiave in notificati_coppie,
            ha_hook=chiave in hook_coppie,
            ha_prova_bacheca=chiave in prove,
        )
        risultato[chiave] = {
            "agente": agente,
            "id_messaggio": id_messaggio,
            "stato": stato,
            "motivo": motivo,
        }
    return risultato


def rigenera_notificati(
    radice: Path, messaggi: list[dict[str, Any]]
) -> dict[str, list[str]]:
    """Ricostruisce il blocco `notificati` di `risvegli_notificati.json` dalla
    proiezione: una coppia che non e' piu' `in_attesa` (il watcher l'ha gestita,
    o e' stata consegnata) risulta notificata. Il log JSONL e' la fonte di
    verita'; questa e' la cache derivata (Gemini, RFC domanda 5).

    Ritorna il nuovo blocco `notificati`. NON scrive il file: il chiamante lo
    fa sotto la stessa transazione con cui aggiorna il resto dello stato.
    """
    proiezione = proietta(radice, messaggi, notificati=None)
    nuovo: dict[str, list[str]] = {}
    for v in proiezione.values():
        if v["stato"] != IN_ATTESA:
            nuovo.setdefault(v["agente"], []).append(v["id_messaggio"])
    return {agente: sorted(set(ids)) for agente, ids in nuovo.items()}


def stato_coppia(
    radice: Path,
    messaggi: list[dict[str, Any]],
    agente: str,
    id_messaggio: str,
    *,
    notificati: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    proiezione = proietta(radice, messaggi, notificati=notificati)
    return proiezione.get(
        _chiave(agente, id_messaggio),
        {"agente": agente, "id_messaggio": id_messaggio, "stato": IN_ATTESA, "motivo": None},
    )


def notificati_da_disco(radice: Path) -> dict[str, list[str]]:
    percorso = radice / "dati_locali" / "orchestrazione" / "risvegli_notificati.json"
    if not percorso.exists():
        return {}
    try:
        return json.loads(percorso.read_text(encoding="utf-8")).get("notificati", {})
    except (OSError, json.JSONDecodeError):
        return {}


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stati di consegna del risveglio.")
    parser.add_argument("--radice", type=Path, default=RADICE)
    sotto = parser.add_subparsers(dest="comando", required=True)
    sotto.add_parser("elenco", help="Stato di consegna di ogni coppia nota")
    p_reset = sotto.add_parser("reset", help="Reset umano di una coppia (agente, id_messaggio)")
    p_reset.add_argument("--agente", required=True)
    p_reset.add_argument("--id-messaggio", required=True)
    p_reset.add_argument("--motivo", default=None)
    sotto.add_parser(
        "rigenera-cache", help="Riscrive il blocco notificati di risvegli_notificati.json dal log"
    )
    args = parser.parse_args(argv)

    import bacheca

    messaggi, _errore = bacheca.leggi_messaggi_progetto(args.radice)

    if args.comando == "reset":
        record = registra_reset(
            args.radice, agente=args.agente, id_messaggio=args.id_messaggio, motivo=args.motivo,
        )
        print(json.dumps(record, ensure_ascii=False) if record else "reset non scritto")
        return 0 if record else 1

    if args.comando == "rigenera-cache":
        nuovo = rigenera_notificati(args.radice, messaggi)
        percorso = args.radice / "dati_locali" / "orchestrazione" / "risvegli_notificati.json"
        stato = {"versione_schema": 1, "notificati": nuovo}
        if percorso.exists():
            try:
                esistente = json.loads(percorso.read_text(encoding="utf-8"))
                if isinstance(esistente, dict):
                    esistente["notificati"] = nuovo
                    stato = esistente
            except (OSError, json.JSONDecodeError):
                pass
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(json.dumps(stato, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(nuovo, ensure_ascii=False))
        return 0

    proiezione = proietta(args.radice, messaggi, notificati=notificati_da_disco(args.radice))
    for chiave in sorted(proiezione):
        v = proiezione[chiave]
        riga = f"{v['agente']:8} {v['id_messaggio'][:12]}  {v['stato']}"
        if v["motivo"]:
            riga += f"  ({v['motivo']})"
        print(riga)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
