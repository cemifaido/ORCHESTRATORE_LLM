# Indice documentazione orchestratore LLM

Questo indice è il punto di ingresso per copiare o collegare la documentazione nel vault.

## Fondamenta

- [README](../README.md) — avvio rapido e componenti.
- [Guida semplice alla bacheca multi-agente](GUIDA_SEMPLICE_BACHECA_MULTIAGENTE.md) — spiegazione per non specialisti di cosa fa la bacheca, a cosa serve e come usarla.
- [Orchestrazione dei lavoratori](ORCHESTRAZIONE_LAVORATORI.md) — specifica operativa.
- [Conformità ToS della bacheca](CONFORMITA_TOS_BACHECA.md) — guardrail contrattuali e operativi per usare abbonamenti flat/IDE plugin senza trasformarli in API non ufficiali.
- [Regole generali di programmazione](REGOLE_GENERALI_PROGRAMMAZIONE_DA_RISPETTARE_SEMPRE.MD) — regole obbligatorie importate come base del framework.

## Bacheca multi-agente

- [RFC Bacheca multi-agente](RFC_BACHECA_MULTIAGENTE.md) — disegno tecnico e stato dell'MVP della messaggistica strutturata fra Claude/Codex/Gemini/locale/umano senza API a pagamento.
- [Esperimento Sveglia e Polling Asincrono](ESPERIMENTO_SVEGLIA_POLLING.md) — report storico dell'esperimento, chiuso con rimozione di endpoint, pulsanti e poller automatici.

## Integrazioni opzionali

- [LiteLLM](INTEGRAZIONE_LITELLM.md) — gateway opzionale per provider LLM, costo misurato e token.

## Schemi

- [Evento v1](../schema/evento.v1.json) — riga JSONL del registro.
- [Compito v1](../schema/compito.v1.json) — stato runtime di un compito.
- [Messaggio v1](../schema/messaggio.v1.json) — riga JSONL della bacheca multi-agente, in uso da `bacheca.py` ([RFC Bacheca multi-agente](RFC_BACHECA_MULTIAGENTE.md)).

## Configurazione

- [Agenti esempio](../config/agenti.esempio.json)
- [Comandi esempio](../config/comandi.esempio.json)

## Script

- [registro.py](../registro.py) — append e validazione eventi.
- [sentinella.py](../sentinella.py) — esecuzione whitelistata dei gate.
- [genera_cruscotto.py](../genera_cruscotto.py) — riepilogo Markdown.
- [capoturno.py](../capoturno.py) — motore di orchestrazione reale (routing, agente, gate, rework).
- [bacheca.py](../bacheca.py) — CLI della bacheca multi-agente (messaggi, thread, prossimi lavori, prese in carico, approvazioni).
- [instrada.py](../instrada.py) — suggerisce l'agente per un tipo di compito.
- [adattatori/litellm.py](../adattatori/litellm.py) — adapter opzionale LiteLLM (chiamate a pagamento e locali, estrazione testo/misurazione condivisa).
- [triage_locale.py](../triage_locale.py) — classificazione routine/escalation di un output a costo zero col modello locale.
- [commit_replay.py](../commit_replay.py) — correla un commit reale alla finestra di eventi del registro, per il replay in dashboard.
- [utility/installa_hook.py](../utility/installa_hook.py) — installa l'hook Git pre-commit del quality gate.
- [esempi/chiamata_agente_litellm.py](../esempi/chiamata_agente_litellm.py) — esempio eseguibile di chiamata LiteLLM con fallback mock.
- [esempi/spike_dispatcher_locale.py](../esempi/spike_dispatcher_locale.py) — spike usa-e-getta: valuta se il modello locale regge il ruolo di dispatcher (sintesi/instradamento/conflitti) per la [RFC Bacheca multi-agente](RFC_BACHECA_MULTIAGENTE.md).

## Note vault

- I dati runtime restano in `dati_locali/` e non vanno nel vault condiviso.
- I link sono relativi, quindi funzionano sia in repository sia in Obsidian.
- Le note progettuali nuove vanno aggiunte qui prima di diventare operative.
