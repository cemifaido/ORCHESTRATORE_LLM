# Indice documentazione orchestratore LLM

Questo indice è il punto di ingresso per copiare o collegare la documentazione nel vault.

## Fondamenta

- [README](../README.md) — avvio rapido e componenti.
- [Orchestrazione dei lavoratori](ORCHESTRAZIONE_LAVORATORI.md) — specifica operativa.
- [Regole generali di programmazione](REGOLE_GENERALI_PROGRAMMAZIONE_DA_RISPETTARE_SEMPRE.MD) — regole obbligatorie importate come base del framework.

## Integrazioni opzionali

- [LiteLLM](INTEGRAZIONE_LITELLM.md) — gateway opzionale per provider LLM, costo misurato e token.

## Schemi

- [Evento v1](../schema/evento.v1.json) — riga JSONL del registro.
- [Compito v1](../schema/compito.v1.json) — stato runtime di un compito.

## Configurazione

- [Agenti esempio](../config/agenti.esempio.json)
- [Comandi esempio](../config/comandi.esempio.json)

## Script

- [registro.py](../registro.py) — append e validazione eventi.
- [sentinella.py](../sentinella.py) — esecuzione whitelistata dei gate.
- [genera_cruscotto.py](../genera_cruscotto.py) — riepilogo Markdown.
- [capoturno.py](../capoturno.py) — motore di orchestrazione reale (routing, agente, gate, rework).
- [instrada.py](../instrada.py) — suggerisce l'agente per un tipo di compito.
- [adattatori/litellm.py](../adattatori/litellm.py) — adapter opzionale LiteLLM (chiamate a pagamento e locali, estrazione testo/misurazione condivisa).
- [triage_locale.py](../triage_locale.py) — classificazione routine/escalation di un output a costo zero col modello locale.
- [commit_replay.py](../commit_replay.py) — correla un commit reale alla finestra di eventi del registro, per il replay in dashboard.
- [utility/installa_hook.py](../utility/installa_hook.py) — installa l'hook Git pre-commit del quality gate.
- [esempi/chiamata_agente_litellm.py](../esempi/chiamata_agente_litellm.py) — esempio eseguibile di chiamata LiteLLM con fallback mock.

## Note vault

- I dati runtime restano in `dati_locali/` e non vanno nel vault condiviso.
- I link sono relativi, quindi funzionano sia in repository sia in Obsidian.
- Le note progettuali nuove vanno aggiunte qui prima di diventare operative.
