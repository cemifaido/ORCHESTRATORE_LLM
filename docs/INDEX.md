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
- [adattatori/litellm.py](../adattatori/litellm.py) — adapter opzionale LiteLLM.

## Note vault

- I dati runtime restano in `dati_locali/` e non vanno nel vault condiviso.
- I link sono relativi, quindi funzionano sia in repository sia in Obsidian.
- Le note progettuali nuove vanno aggiunte qui prima di diventare operative.
