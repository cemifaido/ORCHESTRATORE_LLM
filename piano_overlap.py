#!/usr/bin/env python3
"""Normalizzazione dei set di file e regola di collisione fra passi del piano
(S14.3 slice a / piece 2). Vedi docs/RFC_PIANO_STEP_POSSEDUTI.md, sezioni
"Contratto dei set di file" e "Regola di overlap".

Solo calcolo puro: nessuna lettura del disco, nessun enforcement del dispatch
(l'aggancio arriva in piece 3 / slice b). Semantica conservativa e fail-closed:
puo' produrre un falso positivo (blocco), mai un falso via libera.
"""
from __future__ import annotations

import re

# Un set con anche un solo elemento non deterministico e' interamente
# non_dispatchabile: il sistema non invia il lavoro in automatico.
DISGIUNTO = "disgiunto"
OVERLAP_O_INDETERMINATO = "overlap_o_indeterminato"

# Glob portabili ammessi: solo '*', '?', '**' per componente. Tutto il resto
# (brace expansion, extglob, negazioni, variabili, output di shell) e' ambiguo.
_CARATTERI_AMBIGUI = re.compile(r"[{}\[\]!$`()|~]")
_WILDCARD = re.compile(r"[*?]")


def _componente_ambigua(comp: str) -> bool:
    if _CARATTERI_AMBIGUI.search(comp):
        return True
    # '**' solo come componente intero; '*'/'?' liberi dentro un componente.
    return "**" in comp and comp != "**"


def normalizza_set(patterns: object) -> list[str] | None:
    """Normalizza una lista di path/glob relativi alla root del repo.

    Ritorna la lista normalizzata (path POSIX, case-folded per il profilo
    Windows v1), oppure None se un elemento e' assoluto, risale con '..', e'
    vuoto, usa separatori ambigui o un glob non portabile -> il chiamante tratta
    l'intero set come 'non_dispatchabile'.
    """
    if not isinstance(patterns, list):
        return None
    fuori: list[str] = []
    for grezzo in patterns:
        if not isinstance(grezzo, str) or not grezzo.strip():
            return None
        p = grezzo.strip().replace("\\", "/")
        if p.startswith("/") or re.match(r"^[A-Za-z]:", p) or p.startswith("//"):
            return None
        componenti = [c for c in p.split("/") if c != ""]  # comprime '//'
        if not componenti or any(c in (".", "..") for c in componenti):
            return None
        if any(_componente_ambigua(c) for c in componenti):
            return None
        fuori.append("/".join(c.lower() for c in componenti))
    return sorted(set(fuori))


def _prefissi_provano_disgiunzione(p: str, q: str) -> bool:
    """True solo se i prefissi letterali di p e q divergono PRIMA del primo
    componente con wildcard. In tutti gli altri casi (wildcard sovrapponibili,
    '**', pattern che finisce prima di un mismatch) non si puo' provare la
    disgiunzione -> False (conservativo)."""
    cp, cq = p.split("/"), q.split("/")
    for a, b in zip(cp, cq):
        a_wild, b_wild = bool(_WILDCARD.search(a)) or a == "**", bool(_WILDCARD.search(b)) or b == "**"
        if a_wild or b_wild:
            return False  # da qui in poi non e' piu' letterale: indeterminato
        if a != b:
            return True  # due componenti letterali diversi: sicuramente disgiunti
    # un pattern e' prefisso dell'altro sui componenti letterali comuni:
    # non si puo' escludere che si sovrappongano (es. 'a' e 'a/b')
    return False


def interseca(set1: list[str], set2: list[str]) -> str:
    for p in set1:
        for q in set2:
            if not _prefissi_provano_disgiunzione(p, q):
                return OVERLAP_O_INDETERMINATO
    return DISGIUNTO


def valuta_collisione(
    candidato: dict[str, object], passi_in_corso: list[dict[str, object]]
) -> dict[str, object]:
    """Decide se il passo `candidato` puo' essere dispatchato dato l'insieme dei
    passi gia' `in_corso` (anche di altri operatori dello stesso ruolo).

    Ritorna {"esito": "consentito" | "bloccato" | "non_dispatchabile", ...}.
    non_dispatchabile e bloccato NON attivano un retry automatico: il chiamante
    registra un evento e chiede una decisione (set esplicito o umano).
    """
    c_write = normalizza_set(candidato.get("write_set"))
    if c_write is None:
        return {"esito": "non_dispatchabile", "motivo": "write_set_non_deterministico"}
    c_read = normalizza_set(candidato.get("read_set") or [])
    if c_read is None:
        return {"esito": "non_dispatchabile", "motivo": "read_set_non_deterministico"}

    for attivo in passi_in_corso:
        a_write = normalizza_set(attivo.get("write_set"))
        if a_write is None:
            return {
                "esito": "non_dispatchabile", "motivo": "passo_attivo_non_deterministico",
                "passo": attivo.get("id"),
            }
        a_read = normalizza_set(attivo.get("read_set") or []) or []
        for insieme_c, insieme_a, coppia in (
            (c_write, a_write, "write_x_write"),
            (c_write, a_read, "write_x_read"),
            (c_read, a_write, "read_x_write"),
        ):
            if interseca(insieme_c, insieme_a) != DISGIUNTO:
                return {
                    "esito": "bloccato", "motivo": coppia, "passo": attivo.get("id"),
                    "proprietario": attivo.get("proprietario"),
                    "write_set_attivo": a_write, "write_set_candidato": c_write,
                }
    return {"esito": "consentito"}
