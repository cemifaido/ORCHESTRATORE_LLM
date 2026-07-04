#!/usr/bin/env python3
# ruff: noqa: E402
"""Esempio di integrazione di un agente AI con l'adattatore LiteLLM dell'orchestratore.

Questo script dimostra come:
1. Effettuare una chiamata completamento tramite l'adapter (con fallback mock se litellm non è installato).
2. Estrarre la misurazione dei token e del costo stimato in USD.
3. Arricchire l'evento dell'orchestratore con i metadati LiteLLM impostando origine_costo='misurato'.
4. Registrare l'evento nel file eventi.jsonl.

Esecuzione:
    python esempi/chiamata_agente_litellm.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Aggiunge la radice del progetto al path per poter importare registro e adattatori
RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

import registro
from adattatori import litellm


def main() -> int:
    percorso_registro = RADICE / "dati_locali" / "orchestrazione" / "eventi.jsonl"

    # 1. Definiamo i dettagli del compito e i messaggi dell'agente
    id_compito = "refactoring-esempio"
    modello = "openai/gpt-4o-mini"
    messaggi = [
        {"role": "system", "content": "Sei un assistente programmatore."},
        {"role": "user", "content": "Spiega brevemente cos'è un quality gate."},
    ]

    print(f"Avvio completamento con modello '{modello}'...")

    # 2. Eseguiamo la chiamata tramite l'adapter
    try:
        # Se litellm è installato ed è configurata la chiave, questa chiamata
        # contatterà il provider reale.
        risposta, misurazione = litellm.completamento(
            modello=modello,
            messaggi=messaggi,
            temperature=0.2,
        )
        print("LiteLLM ha risposto con successo.")
    except Exception as errore:
        # Fallback di simulazione in locale se LiteLLM non è installato
        # o se mancano le API key per lo sviluppo locale
        print(f"Nota (chiamata simulata per sviluppo): {errore}")

        # Mock della risposta tipica restituita da LiteLLM
        contenuto_spiegazione = (
            "Un quality gate è un punto di controllo formale che verifica che il codice soddisfi "
            "determinati standard di qualità (es. test verdi, assenza di bug, bassa complessità) "
            "prima di essere integrato o promosso a un ambiente successivo."
        )
        risposta_mock = {
            "id": "chatcmpl-mock123",
            "object": "chat.completion",
            "created": 1677858242,
            "model": modello,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": contenuto_spiegazione
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 45,
                "total_tokens": 165
            },
            "response_cost": 0.00033
        }
        misurazione = litellm.estrai_misurazione(risposta_mock, modello=modello)
        print("Generata risposta mock di fallback.")

    # 3. Costruiamo l'evento base dell'orchestratore per questo compito
    evento_base = {
        "versione_schema": 1,
        "id_evento": "fittizio",  # Verrà sovrascritto in aggiungi_evento se vuoto, oppure lo generiamo
        "timestamp": registro.adesso_utc(),
        "id_compito": id_compito,
        "agente": "gemini",  # L'agente che sta eseguendo il lavoro
        "tipo_compito": "servizi",
        "stato": "passato",
        "esito_gate": "superato",
        "verdetto_umano": "non_revisionato",
        "costo_stimato_usd": 0.0,
        "origine_costo": "stimato",
        "latenza_ms": 340,
        "regole_incluse": ["mock_test"],
        "file_modificati": ["esempi/chiamata_agente_litellm.py"],
        "note": "Chiamata di prova del quality gate ed adapter LiteLLM",
    }

    # 4. Arricchiamo l'evento con la misurazione dei costi effettivi di LiteLLM
    evento_arricchito = litellm.arricchisci_evento(evento_base, misurazione)

    # 5. Salviamo l'evento nel registro del progetto
    # Rimuoviamo l'id fittizio per farlo rigenerare univoco a registro.py
    if "id_evento" in evento_arricchito:
        import uuid
        evento_arricchito["id_evento"] = str(uuid.uuid4())

    registro.aggiungi_evento(percorso_registro, evento_arricchito)

    print("\n=== EVENTO REGISTRATO NEL LOG ===")
    print(json.dumps(evento_arricchito, ensure_ascii=False, indent=2))
    print("=================================")
    print(f"Registro aggiornato in: {percorso_registro}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
