#!/usr/bin/env python3
"""Spike usa-e-getta: il modello locale regge un ruolo di "dispatcher" (sintesi di
un thread multi-agente + prossimo destinatario + conflitti) o solo la
classificazione binaria che gia' fa `triage_locale.py`?

Non scrive nulla nel registro ne' in una futura bacheca: e' solo un test di
fattibilita' prima di costruire `bacheca.py` (vedi il piano concordato in sessione).
Se il modello fallisce sistematicamente su questi 3 thread di prova, il ruolo del
locale nella bacheca va ridimensionato, non forzato.

Esecuzione:
    python esempi/spike_dispatcher_locale.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from adattatori import litellm  # noqa: E402

PROMPT_SISTEMA = (
    "Sei un dispatcher di messaggistica tecnica tra agenti AI (claude, codex, gemini) "
    "e un umano. Ricevi la cronologia di un thread e devi SOLO analizzarla, non agire. "
    "Rispondi ESCLUSIVAMENTE con un oggetto JSON, senza altro testo, con tre chiavi: "
    '"sintesi" (una frase breve in italiano su cosa dice il thread), '
    '"prossimo_destinatario" (chi tra claude/codex/gemini/umano dovrebbe rispondere ora, '
    'oppure "nessuno" se il thread e\' chiuso), '
    '"conflitto" (null se non ce n\'e\' uno, altrimenti una frase breve che lo descrive). '
    "Un conflitto e' quando due mittenti affermano fatti incompatibili sulla STESSA cosa "
    "concreta (stesso file, stesso test, stesso stato di una funzionalita'): non basta "
    "che stiano semplicemente discutendo o siano in disaccordo su un'opinione."
)

# Esempio one-shot: un thread diverso da quelli di test, per insegnare al modello COME
# si riconosce un conflitto (fatti incompatibili sulla stessa cosa) senza rivelargli la
# risposta corretta sui thread che poi valutiamo davvero.
ESEMPIO_THREAD_CONFLITTO = (
    "[claude -> umano] (risposta) Ho verificato che test_login passa in locale con Python 3.11.\n"
    "[codex -> umano] (risposta) Ho eseguito lo stesso test_login e fallisce con un TypeError in Python 3.11."
)
ESEMPIO_OUTPUT_CONFLITTO = {
    "sintesi": "Claude e Codex riportano esiti opposti sullo stesso test nello stesso ambiente.",
    "prossimo_destinatario": "umano",
    "conflitto": "Claude dice che test_login passa, Codex dice che fallisce con un TypeError: stesso test, stesso ambiente, esiti incompatibili.",
}

# Thread di prova in stile schema/messaggio.v1.json (solo i campi rilevanti per il
# dispatcher: mittente, destinatari, tipo, testo — timestamp/id omessi, non servono
# al modello per questo giudizio).

THREAD_APERTO_SENZA_RISPOSTA: list[dict[str, Any]] = [
    {
        "mittente": "claude",
        "destinatari": ["codex"],
        "tipo": "richiesta",
        "testo": "Rivedi la bozza di schema/messaggio.v1.json per naming e casi limite prima che la usiamo in bacheca.py.",
    },
    {
        "mittente": "codex",
        "destinatari": ["claude"],
        "tipo": "domanda",
        "testo": "Il campo destinatari deve supportare un valore 'tutti' per il broadcast o enumeriamo sempre gli agenti per esteso?",
    },
]

THREAD_CHIUSO: list[dict[str, Any]] = [
    {
        "mittente": "umano",
        "destinatari": ["claude"],
        "tipo": "richiesta",
        "testo": "Togli dalla dashboard tutta la logica di conversione USD->EUR, non ci serve piu' mostrare il costo.",
    },
    {
        "mittente": "claude",
        "destinatari": ["umano"],
        "tipo": "risposta",
        "testo": "Fatto: rimossa la tile costo, il grafico a torta dei costi e la logica di fetch/cache del tasso di cambio.",
    },
    {
        "mittente": "umano",
        "destinatari": ["claude"],
        "tipo": "chiusura",
        "testo": "Confermato, va bene cosi'.",
    },
]

THREAD_CON_CONFLITTO: list[dict[str, Any]] = [
    {
        "mittente": "umano",
        "destinatari": ["claude", "gemini"],
        "tipo": "richiesta",
        "testo": "Serve una card 'costo per progetto' nella dashboard multi-progetto.",
    },
    {
        "mittente": "claude",
        "destinatari": ["gemini", "umano"],
        "tipo": "risposta",
        "testo": (
            "Ho tolto tutta la logica di costo/EUR nell'ultimo commit perche' era "
            "diventata codice morto: non aggiungerei una nuova card di costo ora "
            "senza confermare che serva ancora."
        ),
    },
    {
        "mittente": "gemini",
        "destinatari": ["claude", "umano"],
        "tipo": "risposta",
        "testo": "Io ho gia' iniziato lato frontend assumendo che il costo fosse ancora disponibile: procedo o mi fermo?",
    },
]

THREAD_DI_PROVA: list[tuple[str, list[dict[str, Any]]]] = [
    ("aperto_senza_risposta", THREAD_APERTO_SENZA_RISPOSTA),
    ("chiuso", THREAD_CHIUSO),
    ("con_conflitto", THREAD_CON_CONFLITTO),
]


def formatta_thread(messaggi: list[dict[str, Any]]) -> str:
    righe = []
    for m in messaggi:
        destinatari = ", ".join(m["destinatari"])
        righe.append(f"[{m['mittente']} -> {destinatari}] ({m['tipo']}) {m['testo']}")
    return "\n".join(righe)


def valuta_thread(nome: str, messaggi: list[dict[str, Any]], modello: str | None = None) -> dict[str, Any]:
    testo_thread = formatta_thread(messaggi)
    messaggi_prompt = [
        {"role": "system", "content": PROMPT_SISTEMA},
        {"role": "user", "content": f"Thread da analizzare:\n{ESEMPIO_THREAD_CONFLITTO}"},
        {"role": "assistant", "content": json.dumps(ESEMPIO_OUTPUT_CONFLITTO, ensure_ascii=False)},
        {"role": "user", "content": f"Thread da analizzare:\n{testo_thread}"},
    ]
    parametri: dict[str, Any] = {"messaggi": messaggi_prompt, "max_tokens": 200, "temperature": 0.0}
    if modello:
        parametri["modello"] = modello
    try:
        risposta, misurazione = litellm.completamento_locale(**parametri)
    except Exception as errore:
        return {"thread": nome, "ok": False, "errore": f"modello locale non raggiungibile: {errore}"}

    testo = litellm.testo_da_risposta(risposta)
    try:
        inizio = testo.index("{")
        fine = testo.rindex("}") + 1
        dati = json.loads(testo[inizio:fine])
        richieste = {"sintesi", "prossimo_destinatario", "conflitto"}
        mancanti = richieste - set(dati)
        if mancanti:
            raise ValueError(f"chiavi mancanti nella risposta: {mancanti}")
        return {"thread": nome, "ok": True, "risultato": dati, "token_totali": misurazione.token_totali}
    except Exception as errore:
        return {
            "thread": nome,
            "ok": False,
            "errore": f"risposta non interpretabile: {errore}",
            "testo_grezzo": testo[:300],
        }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Spike dispatcher locale")
    parser.add_argument(
        "--modello",
        default=None,
        help="Nome modello servito da llama-server (default: quello di adattatori/litellm.py)",
    )
    args = parser.parse_args()

    esiti = []
    for nome, messaggi in THREAD_DI_PROVA:
        print(f"\n=== Thread: {nome} ===")
        print(formatta_thread(messaggi))
        esito = valuta_thread(nome, messaggi, modello=args.modello)
        print("--- Risposta del modello locale ---")
        print(json.dumps(esito, ensure_ascii=False, indent=2))
        esiti.append(esito)

    riusciti = sum(1 for e in esiti if e["ok"])
    print(f"\n{riusciti}/{len(esiti)} thread analizzati con JSON valido e chiavi complete.")
    print("Il giudizio su sintesi/instradamento/conflitto sensati resta manuale (vedi piano).")
    return 0 if riusciti == len(esiti) else 1


if __name__ == "__main__":
    raise SystemExit(main())
