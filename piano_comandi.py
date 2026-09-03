#!/usr/bin/env python3
"""Comandi del piano dichiarato (S14.3 slice a / piece 3).
Vedi docs/RFC_PIANO_STEP_POSSEDUTI.md, sezione "prendi-passo, offri-passo e
compare-and-set".

`prendi_passo` / `approva_handoff` fanno un compare-and-set atomico: lettura
dello stato, verifica della precondizione e append avvengono nella stessa
sezione critica serializzata dal lock del file (scrittura_jsonl.transazione_jsonl).
Due agenti che tentano lo stesso passo: il secondo legge lo stato gia'
aggiornato e la sua precondizione fallisce - nessun doppio possesso.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import scrittura_jsonl
from bacheca_proiezioni import deriva_piano, messaggi_del_thread

_ATTORI = ("gemini", "claude", "codex", "umano")


def _lista(valore: object) -> list[str]:
    if not valore:
        return []
    if isinstance(valore, str):
        return [p.strip() for p in valore.split(",") if p.strip()]
    if isinstance(valore, (list, tuple)):
        return [str(v) for v in valore]
    return [str(valore)]


def _chiavi_idempotenza_thread(messaggi: list[dict[str, Any]], thread_id: str) -> set[str]:
    return {
        m["piano"]["idempotency_key"]
        for m in messaggi_del_thread(messaggi, thread_id)
        if isinstance(m.get("piano"), dict) and m["piano"].get("idempotency_key")
    }


def crea_passo(
    percorso_bacheca: Path,
    *,
    piano_id: str,
    passo_id: str,
    descrizione: str,
    attore: str,
    proprietario: str | None = None,
    write_set: object = (),
    read_set: object = (),
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Aggiunge un passo al piano di un thread. Il thread deve gia' esistere se
    thread_id e' dato; altrimenti apre un thread nuovo (thread_id = id_messaggio).

    Con `proprietario` il passo nasce gia' `in_corso` assegnato a lui (crea +
    prende in un colpo): senza questo, un `crea_passo` con proprietario ma
    `non_iniziato` resterebbe bloccato - `prendi_passo` rifiuta i passi che hanno
    gia' un proprietario e nessun altro comando li porta a `in_corso`."""
    import bacheca
    messaggi = bacheca.leggi_messaggi(percorso_bacheca)
    if thread_id is not None:
        bacheca._richiedi_thread_esistente(messaggi, thread_id)
    campi: dict[str, Any] = {"descrizione": descrizione}
    if proprietario is not None:
        campi["proprietario"] = proprietario
        campi["stato"] = "in_corso"
    if write_set:
        campi["write_set"] = _lista(write_set)
    if read_set:
        campi["read_set"] = _lista(read_set)
    messaggio = bacheca.costruisci_messaggio(
        mittente=attore, destinatari=[a for a in _ATTORI if a != attore] or ["umano"],
        tipo="richiesta" if thread_id is None else "risposta",
        testo=f"[piano] crea passo {passo_id}: {descrizione}", thread_id=thread_id,
        piano={
            "azione": "crea_passo", "piano_id": piano_id, "passo_id": passo_id,
            "attore": attore, "idempotency_key": str(uuid.uuid4()), "campi": campi,
        },
    )
    bacheca.aggiungi_messaggio(percorso_bacheca, messaggio)
    return messaggio


def _cas_transizione(
    percorso_bacheca: Path,
    thread_id: str,
    passo_id: str,
    attore: str,
    idempotency_key: str,
    costruisci_evento: Any,
) -> dict[str, Any]:
    """Sezione critica comune a prendi_passo / approva_handoff: sotto il lock
    del file legge la proiezione, verifica la precondizione tramite
    `costruisci_evento(piano, passo)` (che ritorna il dict `piano` oppure una
    tupla ('rifiuto', motivo)), e appende il messaggio."""
    import bacheca
    esito: dict[str, Any] = {}

    def calcola() -> dict[str, Any] | None:
        messaggi = bacheca.leggi_messaggi(percorso_bacheca)
        if idempotency_key in _chiavi_idempotenza_thread(messaggi, thread_id):
            esito.update(esito="gia_applicato", idempotency_key=idempotency_key)
            return None
        piano = deriva_piano(messaggi, thread_id)
        if piano is None:
            esito.update(esito="nessun_piano")
            return None
        passo = piano["passi"].get(passo_id)
        if passo is None:
            esito.update(esito="passo_assente")
            return None
        evento = costruisci_evento(piano, passo)
        if isinstance(evento, tuple):
            esito.update(esito=evento[0], motivo=evento[1] if len(evento) > 1 else None)
            return None
        evento["idempotency_key"] = idempotency_key
        return bacheca.costruisci_messaggio(
            mittente=attore, destinatari=[a for a in _ATTORI if a != attore] or ["umano"],
            tipo="risposta", testo=f"[piano] {evento['azione']} {passo_id}",
            thread_id=thread_id, piano=evento,
        )

    scritto = scrittura_jsonl.transazione_jsonl(
        percorso_bacheca, calcola, valida=bacheca.valida_messaggio,
    )
    if scritto is not None:
        esito.update(esito="ok", messaggio=scritto)
    return esito


def prendi_passo(
    percorso_bacheca: Path, thread_id: str, passo_id: str, attore: str,
    *, idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Acquisisce un passo non_iniziato e senza proprietario. CAS sulla versione."""
    key = idempotency_key or str(uuid.uuid4())

    def costruisci(piano: dict[str, Any], passo: dict[str, Any]) -> Any:
        if passo["proprietario"] is not None or passo["stato"] != "non_iniziato":
            return ("non_acquisibile", f"passo {passo['stato']}, proprietario {passo['proprietario']}")
        return {
            "azione": "aggiorna_passo", "piano_id": piano["piano_id"], "passo_id": passo_id,
            "attore": attore,
            "precondizione": {"versione": passo["versione"], "stato": "non_iniziato"},
            "campi": {"proprietario": attore, "stato": "in_corso"},
        }

    return _cas_transizione(percorso_bacheca, thread_id, passo_id, attore, key, costruisci)


def offri_passo(
    percorso_bacheca: Path, thread_id: str, passo_id: str, attore: str, a: str,
) -> dict[str, Any]:
    """Se il passo e' in_corso: propone un handoff (non trasferisce). Se e'
    non_iniziato senza proprietario: delega a prendi_passo per conto di `a`."""
    key = str(uuid.uuid4())

    def costruisci(piano: dict[str, Any], passo: dict[str, Any]) -> Any:
        if passo["stato"] == "non_iniziato" and passo["proprietario"] is None:
            return {
                "azione": "aggiorna_passo", "piano_id": piano["piano_id"], "passo_id": passo_id,
                "attore": attore,
                "precondizione": {"versione": passo["versione"], "stato": "non_iniziato"},
                "campi": {"proprietario": a, "stato": "in_corso"},
            }
        if passo["stato"] != "in_corso":
            return ("non_offribile", f"passo {passo['stato']}")
        return {
            "azione": "proponi_handoff", "piano_id": piano["piano_id"], "passo_id": passo_id,
            "attore": attore, "precondizione": {"versione": passo["versione"], "stato": "in_corso"},
            "campi": {"proprietario": a},
        }

    return _cas_transizione(percorso_bacheca, thread_id, passo_id, attore, key, costruisci)


def approva_handoff(
    percorso_bacheca: Path, thread_id: str, passo_id: str, attore: str,
) -> dict[str, Any]:
    """Approva un handoff aperto. Solo il proprietario attuale o umano. CAS."""
    key = str(uuid.uuid4())

    def costruisci(piano: dict[str, Any], passo: dict[str, Any]) -> Any:
        aperto = next((h for h in piano["handoff_aperti"] if h["passo_id"] == passo_id), None)
        if aperto is None:
            return ("nessun_handoff_aperto",)
        if attore not in (passo["proprietario"], "umano"):
            return ("non_autorizzato", f"solo {passo['proprietario']} o umano")
        return {
            "azione": "approva_handoff", "piano_id": piano["piano_id"], "passo_id": passo_id,
            "attore": attore,
            "precondizione": {"versione": passo["versione"], "stato": passo["stato"]},
            "campi": {},
        }

    return _cas_transizione(percorso_bacheca, thread_id, passo_id, attore, key, costruisci)


def mostra_piano(percorso_bacheca: Path, thread_id: str) -> dict[str, Any] | None:
    import bacheca
    return deriva_piano(bacheca.leggi_messaggi(percorso_bacheca), thread_id)
