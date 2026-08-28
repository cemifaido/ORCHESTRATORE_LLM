"""Proiezioni pure del log event-sourced della bacheca.

Non leggono file, non stampano e non costruiscono messaggi: ricevono lo storico
gia' validato e ne derivano stato, destinatari pendenti, lease e riprese.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any


TIPI_APERTURA = {"richiesta", "domanda", "sintesi", "segnalazione_conflitto", "checkpoint"}

# Protocollo "passo" (decisione congiunta umano/Codex/Gemini, 2026-08-27, thread
# 5628be18): un livello di intento ADDIZIONALE sopra TIPI_APERTURA, mai
# sostitutivo - in assenza di marker il comportamento resta quello di sempre.
# Match solo sull'ULTIMA riga non vuota del messaggio, esatto e case-insensitive:
# mai una sottostringa nel corpo del testo (evita falsi positivi su "il prossimo
# passo e'..." in prosa). Il controllo di chiusura va valutato per primo perche'
# il suo pattern e' un prefisso testuale di quello di apertura.
_RIGA_PASSO_CHIUDI = re.compile(r"^[-–—]\s*passo\s+e\s+chiudo$", re.IGNORECASE)
_RIGA_PASSO = re.compile(r"^[-–—]\s*passo$", re.IGNORECASE)


def marker_intento(testo: str) -> str | None:
    """'chiudi' se l'ultima riga e' '- passo e chiudo', 'apri' se e' '- passo',
    None altrimenti (nessun marker riconosciuto: fallback su TIPI_APERTURA)."""
    righe = [r.strip() for r in (testo or "").splitlines() if r.strip()]
    if not righe:
        return None
    ultima = righe[-1]
    if _RIGA_PASSO_CHIUDI.match(ultima):
        return "chiudi"
    if _RIGA_PASSO.match(ultima):
        return "apri"
    return None


# Sottostringa (non riga intera) - usata solo per avvisare l'autore in scrittura,
# mai per decidere la pendenza: un marker quasi giusto non deve fallire muto
# (D-2026-08-28, dalla prova dal vivo del protocollo: Codex ha scritto il
# marker in coda alla stessa frase invece che su riga propria, ignorato dal
# parser rigido com'e' corretto, ma senza nessun avviso).
_SOTTOSTRINGA_MARKER = re.compile(r"[-–—]\s*passo(\s+e\s+chiudo)?", re.IGNORECASE)


def marker_quasi_riconosciuto(testo: str) -> bool:
    """True se l'ultima riga CONTIENE una sottostringa simile al marker ma non
    e' un match esatto (es. marker incollato a fine frase) - un probabile
    tentativo fallito, non una prosa qualunque che nomina 'passo'."""
    righe = [r.strip() for r in (testo or "").splitlines() if r.strip()]
    if not righe:
        return False
    ultima = righe[-1]
    if marker_intento(ultima) is not None:
        return False
    return bool(_SOTTOSTRINGA_MARKER.search(ultima))

# Fonte unica (D8, revisione architetturale v3, 2026-08-27): prima duplicata
# alla lettera in bacheca.py e bacheca_comandi.py, rischio di deriva silenziosa
# fra le due copie. Deve restare identico agli enum "mittente"/"agente" in
# schema/messaggio.v2.json e schema/evento.v1.json - vedi il test dedicato
# in tests/test_bacheca.py che confronta i tre.
AGENTI_VALIDI = ("gemini", "claude", "codex", "locale", "umano", "sistema")


def messaggi_del_thread(messaggi: list[dict[str, Any]], thread_id: str) -> list[dict[str, Any]]:
    rilevanti = [m for m in messaggi if m["thread_id"] == thread_id]
    rilevanti.sort(key=lambda m: m["timestamp"])
    return rilevanti


def partecipanti_thread(messaggi: list[dict[str, Any]], thread_id: str) -> set[str]:
    partecipanti: set[str] = set()
    for messaggio in messaggi_del_thread(messaggi, thread_id):
        partecipanti.add(messaggio["mittente"])
        partecipanti.update(messaggio["destinatari"])
    return partecipanti


def ultimo_rilevante(messaggi: list[dict[str, Any]], thread_id: str) -> dict[str, Any]:
    """Ultimo record che cambia lo stato globale, ignorando i checkpoint."""
    rilevanti = messaggi_del_thread(messaggi, thread_id)
    non_checkpoint = [m for m in rilevanti if m["tipo"] != "checkpoint"]
    return non_checkpoint[-1] if non_checkpoint else rilevanti[-1]


def stato_thread(messaggi: list[dict[str, Any]], thread_id: str) -> str:
    """Stato globale derivato dal solo storico, senza stato persistito."""
    if not messaggi_del_thread(messaggi, thread_id):
        return "inesistente"
    tipo = ultimo_rilevante(messaggi, thread_id)["tipo"]
    if tipo in TIPI_APERTURA:
        return "aperto"
    if tipo == "presa_in_carico":
        return "preso_in_carico"
    if tipo == "risposta":
        return "risposto"
    if tipo == "chiusura":
        return "chiuso"
    if tipo == "annullamento":
        return "annullato"
    return "sconosciuto"


def stato_per_destinatario(messaggi: list[dict[str, Any]], thread_id: str, agente: str) -> str:
    """Stato derivato per destinatario, con ordine stabile a parita' di timestamp."""
    rilevanti = messaggi_del_thread(messaggi, thread_id)
    if not rilevanti:
        return "inesistente"
    if stato_thread(messaggi, thread_id) in ("chiuso", "annullato"):
        return "resolved"

    indice_indirizzato_apertura: int | None = None
    indice_inviato: int | None = None
    for indice, messaggio in enumerate(rilevanti):
        if agente in messaggio["destinatari"]:
            marker = marker_intento(messaggio["testo"])
            if marker == "chiudi":
                # Override esplicito: chiude anche una pendenza aperta da un
                # messaggio precedente nello stesso thread, a prescindere dal tipo.
                indice_indirizzato_apertura = None
            elif marker == "apri" or messaggio["tipo"] in TIPI_APERTURA:
                indice_indirizzato_apertura = indice
        if messaggio["mittente"] == agente:
            indice_inviato = indice

    if indice_indirizzato_apertura is None:
        return "resolved"
    if indice_inviato is None:
        return "pending"
    return "pending" if indice_indirizzato_apertura > indice_inviato else "resolved"


def destinatari_pendenti(messaggi: list[dict[str, Any]], thread_id: str) -> list[str]:
    if not messaggi_del_thread(messaggi, thread_id):
        return []
    return sorted(
        agente for agente in partecipanti_thread(messaggi, thread_id)
        if stato_per_destinatario(messaggi, thread_id, agente) == "pending"
    )


def verdetto_umano_corrente(messaggi: list[dict[str, Any]], thread_id: str) -> str:
    for messaggio in reversed(messaggi_del_thread(messaggi, thread_id)):
        if messaggio["verdetto_umano"] != "non_revisionato":
            return messaggio["verdetto_umano"]
    return "non_revisionato"


def checkpoint_ripristinabile_attivo(
    messaggi: list[dict[str, Any]], thread_id: str
) -> dict[str, Any] | None:
    attivo: dict[str, Any] | None = None
    for messaggio in messaggi_del_thread(messaggi, thread_id):
        if messaggio["tipo"] == "checkpoint" and messaggio.get("ripresa"):
            attivo = messaggio
        elif messaggio["tipo"] in ("chiusura", "annullamento"):
            attivo = None
    return attivo


def riprese_pronte(messaggi: list[dict[str, Any]], agente: str) -> list[dict[str, Any]]:
    risultato: list[dict[str, Any]] = []
    for thread_id in sorted({m["thread_id"] for m in messaggi}):
        attivo: dict[str, Any] | None = None
        pronto: dict[str, Any] | None = None
        for messaggio in messaggi_del_thread(messaggi, thread_id):
            if messaggio["tipo"] == "checkpoint" and messaggio.get("ripresa"):
                attivo = messaggio
                pronto = None
            elif messaggio["tipo"] in ("chiusura", "annullamento"):
                if (
                    messaggio["tipo"] == "chiusura"
                    and messaggio["verdetto_umano"] != "non_revisionato"
                    and attivo is not None
                    and attivo["ripresa"]["attende"] == "umano"
                    and attivo["mittente"] == agente
                ):
                    pronto = {
                        "checkpoint": attivo,
                        "verdetto": messaggio["verdetto_umano"],
                        "azione": attivo["ripresa"]["azioni_per_esito"].get(messaggio["verdetto_umano"]),
                    }
                attivo = None
            elif messaggio["mittente"] == agente and pronto is not None:
                pronto = None
        if pronto is not None:
            risultato.append(pronto)
    return risultato


def a_utc(timestamp_iso: str) -> datetime:
    normalizzato = timestamp_iso.replace("Z", "+00:00")
    valore = datetime.fromisoformat(normalizzato)
    if valore.tzinfo is None:
        valore = valore.replace(tzinfo=timezone.utc)
    return valore.astimezone(timezone.utc)


def file_occupati(
    messaggi: list[dict[str, Any]], adesso: datetime | None = None
) -> dict[str, dict[str, Any]]:
    adesso = adesso or datetime.now(timezone.utc)
    per_thread: dict[str, list[dict[str, Any]]] = {}
    for messaggio in messaggi:
        per_thread.setdefault(messaggio["thread_id"], []).append(messaggio)

    occupati: dict[str, dict[str, Any]] = {}
    for thread_id in per_thread:
        if stato_thread(messaggi, thread_id) != "preso_in_carico":
            continue
        ultimo = ultimo_rilevante(messaggi, thread_id)
        scadenza = None
        if ultimo["ttl_minuti"] is not None:
            scadenza = a_utc(ultimo["timestamp"]) + timedelta(minutes=ultimo["ttl_minuti"])
            if scadenza < adesso:
                continue
        for file_modificato in ultimo["file_modificati"]:
            occupati[file_modificato] = {
                "agente": ultimo["mittente"],
                "thread_id": thread_id,
                "scadenza": scadenza,
            }
    return occupati


def messaggi_aperti_per(messaggi: list[dict[str, Any]], agente: str) -> list[dict[str, Any]]:
    thread_ids = {m["thread_id"] for m in messaggi}
    risultato = [
        messaggi_del_thread(messaggi, thread_id)[-1]
        for thread_id in thread_ids
        if stato_per_destinatario(messaggi, thread_id, agente) == "pending"
    ]
    risultato.sort(key=lambda messaggio: messaggio["timestamp"])
    return risultato
