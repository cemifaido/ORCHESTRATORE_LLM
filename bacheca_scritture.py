#!/usr/bin/env python3
"""Scritture idempotenti in bacheca per il server MCP (PIANO §15 Slice B,
docs/RFC_SERVER_MCP_LOCALE.md, sezione "Concorrenza").

Contratto di idempotenza (revisione Codex, obbligatorio per ogni scrittura):
- chiave con scope `(mittente, thread_id, operazione, idempotency_key)`;
- controllo E append avvengono sotto UN solo lock (`scrittura_jsonl.transazione_jsonl`);
- stessa chiave + stesso payload  -> {"esito": "gia_applicato", "id_messaggio": <originale>}
- stessa chiave + payload diverso -> {"esito": "conflitto", "id_messaggio": <originale>}
- chiave nuova -> si scrive, {"esito": "ok", "messaggio": <record>}

Un client MCP puo' ritentare una tool call (timeout, riconnessione): con la
stessa `idempotency_key` non produce un doppione. Se il client non fornisce una
chiave se ne genera una nuova (la chiamata e' allora "sempre nuova", cioe' non
retry-safe - responsabilita' del client fornire una chiave stabile).

Questo modulo usa `transazione_jsonl` direttamente, NON `bacheca.aggiungi_messaggio`
(che prende gia' il lock e non e' reentrante).
"""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, Callable

import bacheca
import scrittura_jsonl

_OPERAZIONI = ("rispondi", "prendi")


def _payload_sha256(operazione: str, *parti: Any) -> str:
    grezzo = json.dumps([operazione, *parti], ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(grezzo.encode("utf-8")).hexdigest()


def _idempotenza_di(messaggio: dict[str, Any]) -> dict[str, Any] | None:
    idem = messaggio.get("metadati", {}).get("idempotenza")
    return idem if isinstance(idem, dict) else None


def _scrivi_idempotente(
    percorso: Path,
    *,
    mittente: str,
    thread_id: str,
    operazione: str,
    idempotency_key: str,
    payload_sha256: str,
    costruisci: Callable[[list[dict[str, Any]]], dict[str, Any]],
) -> dict[str, Any]:
    """Sezione critica: sotto il lock del file, cerca una scrittura precedente
    con la stessa chiave/scope, altrimenti costruisce e appende il nuovo record."""
    esito: dict[str, Any] = {}

    def calcola() -> dict[str, Any] | None:
        messaggi = bacheca.leggi_messaggi(percorso)
        for m in messaggi:
            if m.get("thread_id") != thread_id or m.get("mittente") != mittente:
                continue
            idem = _idempotenza_di(m)
            if not idem or idem.get("chiave") != idempotency_key or idem.get("operazione") != operazione:
                continue
            if idem.get("payload_sha256") == payload_sha256:
                esito.update(esito="gia_applicato", id_messaggio=m["id_messaggio"])
            else:
                esito.update(esito="conflitto", id_messaggio=m["id_messaggio"])
            return None
        return costruisci(messaggi)

    scritto = scrittura_jsonl.transazione_jsonl(percorso, calcola, valida=bacheca.valida_messaggio)
    if scritto is not None:
        esito.update(esito="ok", messaggio=scritto)
    return esito


def _metadati_idempotenza(operazione: str, chiave: str, payload_sha256: str) -> dict[str, Any]:
    return {"idempotenza": {"chiave": chiave, "operazione": operazione, "payload_sha256": payload_sha256}}


def rispondi(
    percorso: Path,
    *,
    thread_id: str,
    mittente: str,
    testo: str,
    correla_a: str | None = None,
    destinatari: list[str] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Appende una `risposta` a un thread esistente. Vedi contratto in cima."""
    messaggi = bacheca.leggi_messaggi(percorso)
    if not any(m["thread_id"] == thread_id for m in messaggi):
        return {"esito": "thread_inesistente", "thread_id": thread_id}
    chiave = idempotency_key or str(uuid.uuid4())
    dst = destinatari or bacheca._default_destinatari(messaggi, thread_id, mittente)
    payload = _payload_sha256("rispondi", testo, correla_a, sorted(dst))

    def costruisci(_messaggi: list[dict[str, Any]]) -> dict[str, Any]:
        return bacheca.costruisci_messaggio(
            mittente=mittente, destinatari=dst, tipo="risposta", testo=testo,
            thread_id=thread_id, correla_a=correla_a,
            metadati=_metadati_idempotenza("rispondi", chiave, payload),
        )

    return _scrivi_idempotente(
        percorso, mittente=mittente, thread_id=thread_id, operazione="rispondi",
        idempotency_key=chiave, payload_sha256=payload, costruisci=costruisci,
    )


def prendi(
    percorso: Path,
    *,
    thread_id: str,
    agente: str,
    correla_a: str | None = None,
    destinatari: list[str] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Appende una `presa_in_carico` a un thread esistente. `correla_a` collega
    la presa al risveglio (prova di consegna, RFC stati di consegna)."""
    messaggi = bacheca.leggi_messaggi(percorso)
    if not any(m["thread_id"] == thread_id for m in messaggi):
        return {"esito": "thread_inesistente", "thread_id": thread_id}
    if correla_a is not None and not any(m["id_messaggio"] == correla_a for m in messaggi):
        return {"esito": "correla_a_inesistente", "correla_a": correla_a}
    chiave = idempotency_key or str(uuid.uuid4())
    dst = destinatari or bacheca._default_destinatari(messaggi, thread_id, agente)
    payload = _payload_sha256("prendi", correla_a, sorted(dst))

    def costruisci(_messaggi: list[dict[str, Any]]) -> dict[str, Any]:
        return bacheca.costruisci_messaggio(
            mittente=agente, destinatari=dst, tipo="presa_in_carico",
            testo=f"{agente} ha preso in carico il thread", thread_id=thread_id,
            correla_a=correla_a,
            metadati=_metadati_idempotenza("prendi", chiave, payload),
        )

    return _scrivi_idempotente(
        percorso, mittente=agente, thread_id=thread_id, operazione="prendi",
        idempotency_key=chiave, payload_sha256=payload, costruisci=costruisci,
    )
