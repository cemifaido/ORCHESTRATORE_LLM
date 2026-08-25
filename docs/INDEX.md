# Indice documentazione orchestratore LLM

Questo indice è il punto di ingresso per copiare o collegare la documentazione nel vault.

## Fondamenta

- [README](../README.md) — avvio rapido e componenti.
- [Guida semplice alla bacheca multi-agente](GUIDA_SEMPLICE_BACHECA_MULTIAGENTE.md) — spiegazione per non specialisti di cosa fa la bacheca, a cosa serve e come usarla.
- [Orchestrazione dei lavoratori](ORCHESTRAZIONE_LAVORATORI.md) — specifica operativa.
- [Conformità ToS della bacheca](CONFORMITA_TOS_BACHECA.md) — guardrail contrattuali e operativi per usare abbonamenti flat/IDE plugin senza trasformarli in API non ufficiali; sezione "Aggiornamento 2026-08-24" per l'automazione headless con canali ufficiali documentati.
- [Regole generali di programmazione](REGOLE_GENERALI_PROGRAMMAZIONE_DA_RISPETTARE_SEMPRE.MD) — regole obbligatorie importate come base del framework.
- [Proposta: riuso idee Weft](PROPOSTA_RIUSO_IDEE_WEFT.md) — origine comune di checkpoint ripristinabile, flusso dichiarato e postino: due idee di design (attesa umana come stato ripristinabile, workflow come dati validabili) prese dal linguaggio Weft senza adottarlo.

## Bacheca multi-agente

- [RFC Bacheca multi-agente](RFC_BACHECA_MULTIAGENTE.md) — disegno tecnico e stato dell'MVP della messaggistica strutturata fra Claude/Codex/Gemini/locale/umano senza API a pagamento.
- [RFC messaggio v2: checkpoint ripristinabile](RFC_MESSAGGIO_V2_RIPRESA.md) — campo `ripresa` sui checkpoint: l'attesa di un verdetto umano diventa uno stato ripristinabile, `approva`/`respingi` stampano da soli il prossimo passo previsto per l'esito ricevuto.
- [Esperimento Sveglia e Polling Asincrono](ESPERIMENTO_SVEGLIA_POLLING.md) — report storico dell'esperimento, chiuso con rimozione di endpoint, pulsanti e poller automatici (superato poi dal Postino, vedi sotto).

## Flusso dichiarato

- [Piano: flusso dichiarato](PIANO_FLUSSO_DICHIARATO.md) — il workflow standard (compito → gate → triage → registrazione → approvazione umana → chiusura), da prosa nelle istruzioni a dati validabili.
- [Flusso v1](../schema/flusso.v1.json) — schema dei passi di un flusso dichiarato (richiede/produce/richiede_opzionali, iniziale, irreversibile, approvazione_umana).
- [Flusso compito standard](../config/flussi/compito_standard.json) — il flusso reale del progetto, istanza validata dello schema sopra.

## Postino (risvegli automatici)

- [Guida: il postino e il dispatch headless](GUIDA_POSTINO_DISPATCH_HEADLESS.md) — **guida operativa di riferimento**: come funziona, prerequisiti per farlo funzionare, come usarlo, come replicarlo su un'altra macchina.
- [Piano: risvegli automatici](PIANO_RISVEGLI_AUTOMATICI.md) — storia delle decisioni e guardrail concordati con Gemini/Codex (tetti, capability provate non presunte, canali ufficiali).

## Integrazioni opzionali

- [LiteLLM](INTEGRAZIONE_LITELLM.md) — gateway opzionale per provider LLM, costo misurato e token.

## Schemi

- [Evento v1](../schema/evento.v1.json) — riga JSONL del registro.
- [Compito v1](../schema/compito.v1.json) — stato runtime di un compito.
- [Messaggio v1](../schema/messaggio.v1.json) — riga JSONL della bacheca multi-agente, in uso da `bacheca.py` ([RFC Bacheca multi-agente](RFC_BACHECA_MULTIAGENTE.md)).
- [Messaggio v2](../schema/messaggio.v2.json) — v1 congelata più il campo `ripresa` sui checkpoint ([RFC messaggio v2](RFC_MESSAGGIO_V2_RIPRESA.md)); il lettore instrada per versione, nessuna migrazione dello storico.
- [Flusso v1](../schema/flusso.v1.json) — passi di un flusso dichiarato ([Piano: flusso dichiarato](PIANO_FLUSSO_DICHIARATO.md)).

## Configurazione

- [Agenti esempio](../config/agenti.esempio.json)
- [Comandi esempio](../config/comandi.esempio.json)

## Script

- [registro.py](../registro.py) — append e validazione eventi.
- [sentinella.py](../sentinella.py) — esecuzione whitelistata dei gate.
- [genera_cruscotto.py](../genera_cruscotto.py) — riepilogo Markdown.
- [capoturno.py](../capoturno.py) — motore di orchestrazione reale (routing, agente, gate, rework).
- [bacheca.py](../bacheca.py) — CLI della bacheca multi-agente (messaggi, thread, prossimi lavori, prese in carico, approvazioni, checkpoint ripristinabili v2).
- [postino.py](../postino.py) — motore di policy e dispatch headless del [Postino](GUIDA_POSTINO_DISPATCH_HEADLESS.md): `autorizza`/`dispatch`/`registra_canale`.
- [valida_flussi.py](../valida_flussi.py) — validatore read-only dei [flussi dichiarati](PIANO_FLUSSO_DICHIARATO.md).
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
