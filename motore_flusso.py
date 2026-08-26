"""Derivazione pura e fail-safe dello stato di un flusso dichiarato.

Questo modulo non avvia agenti, gate o commit: interpreta soltanto le prove
append-only gia' presenti nella bacheca e nel registro.
"""
from __future__ import annotations

from collections import deque
from typing import Any, TypedDict


class StatoFlusso(TypedDict):
    """DTO stabile, consumabile dalla UI senza euristiche."""

    stato: str
    fase: str | None
    passi_completati: list[str]
    passi_abilitati: list[str]
    prove: list[str]
    artefatti_mancanti: dict[str, list[str]]
    diagnostica: list[str]


def _passi_per_id(flusso: dict[str, Any]) -> dict[str, dict[str, Any]]:
    passi = flusso.get("passi")
    if not isinstance(passi, list):
        raise ValueError("flusso senza lista passi")
    per_id = {passo["id"]: passo for passo in passi if isinstance(passo, dict) and isinstance(passo.get("id"), str)}
    if len(per_id) != len(passi):
        raise ValueError("id passo mancanti o duplicati")
    return per_id


def _grafo(per_id: dict[str, dict[str, Any]]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    produttore = _produttori(per_id)
    predecessori: dict[str, set[str]] = {identita: set() for identita in per_id}
    for identita, passo in per_id.items():
        for artefatto in passo.get("richiede", []) + passo.get("richiede_opzionali", []):
            if artefatto in produttore:
                predecessori[identita].add(produttore[artefatto])
    successori: dict[str, set[str]] = {identita: set() for identita in per_id}
    for identita, precedenti in predecessori.items():
        for precedente in precedenti:
            successori[precedente].add(identita)
    return predecessori, successori


def _produttori(per_id: dict[str, dict[str, Any]]) -> dict[str, str]:
    produttore: dict[str, str] = {}
    for identita, passo in per_id.items():
        for artefatto in passo.get("produce", []):
            if artefatto in produttore:
                raise ValueError(f"produttore ambiguo: {artefatto}")
            produttore[artefatto] = identita
    return produttore


def _ordine_topologico(predecessori: dict[str, set[str]], successori: dict[str, set[str]]) -> list[str]:
    rimanenti = {identita: set(precedenti) for identita, precedenti in predecessori.items()}
    coda = deque(sorted(identita for identita, precedenti in rimanenti.items() if not precedenti))
    ordine: list[str] = []
    while coda:
        identita = coda.popleft()
        ordine.append(identita)
        for successore in sorted(successori[identita]):
            rimanenti[successore].remove(identita)
            if not rimanenti[successore]:
                coda.append(successore)
    if len(ordine) != len(rimanenti):
        raise ValueError("ciclo nel flusso")

    return ordine


def compila_flusso(flusso: dict[str, Any]) -> dict[str, Any]:
    """Indicizza il DAG in un formato stabile per validatore e motore."""
    per_id = _passi_per_id(flusso)
    predecessori, successori = _grafo(per_id)
    ordine = _ordine_topologico(predecessori, successori)
    predecessori_obbligatori = {
        identita: {
            produttore
            for artefatto in passo.get("richiede", [])
            for produttore in [
                next(
                    (candidato for candidato, altro_passo in per_id.items() if artefatto in altro_passo.get("produce", [])),
                    None,
                )
            ]
            if produttore is not None
        }
        for identita, passo in per_id.items()
    }
    return {
        "passi": per_id,
        "ordine": ordine,
        "predecessori": predecessori,
        "predecessori_obbligatori": predecessori_obbligatori,
        "successori": successori,
    }


def _verdetto_bacheca(messaggi: list[dict[str, Any]], thread_id: str) -> str:
    verdetto = "non_revisionato"
    for messaggio in messaggi:
        if messaggio.get("thread_id") == thread_id and messaggio.get("verdetto_umano") not in (None, "non_revisionato"):
            verdetto = str(messaggio["verdetto_umano"])
    return verdetto


def _thread_chiuso(messaggi: list[dict[str, Any]], thread_id: str) -> bool:
    del_thread = [m for m in messaggi if m.get("thread_id") == thread_id]
    return bool(del_thread and del_thread[-1].get("tipo") in {"chiusura", "annullamento"})


def _prove(eventi: list[dict[str, Any]], messaggi: list[dict[str, Any]], thread_id: str) -> set[str]:
    correlati = [evento for evento in eventi if evento.get("thread_id") == thread_id]
    prove: set[str] = set()
    controlli = {
        "file_modificati": lambda evento: bool(evento.get("file_modificati")),
        "esito_gate": lambda evento: evento.get("esito_gate") not in (None, "non_eseguito"),
        "classificazione_triage": lambda evento: any("triage" in str(regola) for regola in evento.get("regole_incluse", [])),
        "evento_registro": lambda evento: evento.get("agente") in {"claude", "codex", "gemini"},
        "commit": _ha_prova_commit,
    }
    prove.update(nome for nome, controllo in controlli.items() if any(controllo(evento) for evento in correlati))
    if _ha_prova_verdetto(correlati, messaggi, thread_id):
        prove.add("verdetto_umano")
    return prove


def _ha_prova_commit(evento: dict[str, Any]) -> bool:
    metadati = evento.get("metadati")
    flusso = metadati.get("flusso") if isinstance(metadati, dict) else None
    return "commit" in evento.get("artefatti_flusso", []) and isinstance(flusso, dict) and bool(flusso.get("commit_hash"))


def _ha_prova_verdetto(correlati: list[dict[str, Any]], messaggi: list[dict[str, Any]], thread_id: str) -> bool:
    verdetto = _verdetto_bacheca(messaggi, thread_id)
    umano_coerente = any(evento.get("agente") == "umano" and evento.get("verdetto_umano") == verdetto for evento in correlati)
    return verdetto == "approvato" and umano_coerente


def _dto(
    stato: str,
    *,
    fase: str | None = None,
    completati: list[str] | None = None,
    abilitati: list[str] | None = None,
    prove: set[str] | None = None,
    mancanti: dict[str, list[str]] | None = None,
    diagnostica: list[str] | None = None,
) -> StatoFlusso:
    return {
        "stato": stato,
        "fase": fase,
        "passi_completati": completati or [],
        "passi_abilitati": abilitati or [],
        "prove": sorted(prove or set()),
        "artefatti_mancanti": mancanti or {},
        "diagnostica": diagnostica or [],
    }


def _valuta_passo(
    compilato: dict[str, Any], identita: str, prove: set[str], completati: list[str], thread_chiuso: bool,
) -> tuple[bool, bool, list[str]]:
    passo = compilato["passi"][identita]
    assenti = sorted(set(passo.get("richiede", [])) - prove)
    abilitato = not assenti and compilato["predecessori_obbligatori"][identita].issubset(completati)
    prodotti = set(passo.get("produce", []))
    completato = abilitato and (prodotti.issubset(prove) if prodotti else thread_chiuso)
    return abilitato, completato, assenti or sorted(prodotti - prove)


def _avanzamento(compilato: dict[str, Any], prove: set[str], chiuso: bool) -> tuple[list[str], list[str], dict[str, list[str]]]:
    completati: list[str] = []
    abilitati: list[str] = []
    mancanti: dict[str, list[str]] = {}
    for identita in compilato["ordine"]:
        abilitato, completato, assenti = _valuta_passo(compilato, identita, prove, completati, chiuso)
        if abilitato:
            abilitati.append(identita)
        if completato:
            completati.append(identita)
        else:
            mancanti[identita] = assenti
    return completati, abilitati, mancanti


def _fase_attiva(compilato: dict[str, Any], completati: list[str], abilitati: list[str]) -> str | None:
    for identita in compilato["ordine"]:
        if not compilato["passi"][identita].get("opzionale") and identita not in completati and identita in abilitati:
            return identita
    return None


def deriva_stato(flusso: dict[str, Any], eventi: list[dict[str, Any]], messaggi: list[dict[str, Any]], thread_id: str) -> StatoFlusso:
    """Deriva un DTO per la UI esclusivamente da evidenze correlate.

    Dati incoerenti non vengono mai trasformati in un avanzamento: il chiamante
    riceve ``incoerente`` con la ragione leggibile.
    """
    try:
        compilato = compila_flusso(flusso)
    except ValueError as errore:
        return _dto("invalido", diagnostica=[str(errore)])
    prove = _prove(eventi, messaggi, thread_id)
    chiuso = _thread_chiuso(messaggi, thread_id)
    completati, abilitati, mancanti = _avanzamento(compilato, prove, chiuso)
    if chiuso and "chiusura" not in completati:
        return _dto(
            "incoerente", completati=completati, abilitati=abilitati, prove=prove,
            mancanti=mancanti,
            diagnostica=["thread chiuso con prerequisiti del flusso mancanti"],
        )
    fase = _fase_attiva(compilato, completati, abilitati)
    if fase:
        return _dto("attivo", fase=fase, completati=completati, abilitati=abilitati, prove=prove, mancanti=mancanti)
    return _dto("completato", completati=completati, abilitati=abilitati, prove=prove, mancanti=mancanti)
