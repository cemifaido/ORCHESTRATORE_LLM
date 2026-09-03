# Indice documentazione orchestratore LLM

Questo indice è il punto di ingresso per copiare o collegare la documentazione nel vault.

## Fondamenta

- [Presentazione semplice](PRESENTAZIONE_SEMPLICE.md) — due pagine senza dettagli tecnici, a cosa serve e quali sono i vantaggi: il documento pensato per divulgare il progetto a chi non l'ha seguito.
- [README](../README.md) — avvio rapido e componenti.
- [Guida semplice alla bacheca multi-agente](GUIDA_SEMPLICE_BACHECA_MULTIAGENTE.md) — spiegazione per non specialisti di cosa fa la bacheca, a cosa serve e come usarla.
- [Orchestrazione dei lavoratori](ORCHESTRAZIONE_LAVORATORI.md) — specifica operativa.
- [Conformità ToS della bacheca](CONFORMITA_TOS_BACHECA.md) — guardrail contrattuali e operativi per usare abbonamenti flat/IDE plugin senza trasformarli in API non ufficiali; sezione "Aggiornamento 2026-08-24" per l'automazione headless con canali ufficiali documentati.
- [Regole generali di programmazione](REGOLE_GENERALI_PROGRAMMAZIONE_DA_RISPETTARE_SEMPRE.MD) — regole obbligatorie importate come base del framework.
- [Proposta: riuso idee Weft](PROPOSTA_RIUSO_IDEE_WEFT.md) — origine comune di checkpoint ripristinabile, flusso dichiarato e postino: due idee di design (attesa umana come stato ripristinabile, workflow come dati validabili) prese dal linguaggio Weft senza adottarlo.
- [Proposta: riuso idee Amoeba](PROPOSTA_RIUSO_IDEE_AMOEBA.md) — Amoeba (multiplayer IDE commerciale) replica il posizionamento del progetto: non adottabile, ma da cui si estraggono il piano a passi posseduti (§14.3) e le note di codice ancorate (§14.1).

## Bacheca multi-agente

- [RFC Bacheca multi-agente](RFC_BACHECA_MULTIAGENTE.md) — disegno tecnico e stato dell'MVP della messaggistica strutturata fra Claude/Codex/Gemini/locale/umano senza API a pagamento.
- [RFC messaggio v2: checkpoint ripristinabile](RFC_MESSAGGIO_V2_RIPRESA.md) — campo `ripresa` sui checkpoint: l'attesa di un verdetto umano diventa uno stato ripristinabile, `approva`/`respingi` stampano da soli il prossimo passo previsto per l'esito ricevuto.
- [Esperimento Sveglia e Polling Asincrono](ESPERIMENTO_SVEGLIA_POLLING.md) — report storico dell'esperimento, chiuso con rimozione di endpoint, pulsanti e poller automatici (superato poi dal Postino, vedi sotto).

## Piano dichiarato e passi posseduti (S14.3)

- [RFC: piano dichiarato e passi posseduti](RFC_PIANO_STEP_POSSEDUTI.md) — bozza tecnica (Codex): campo opzionale `piano` su `messaggio.v1` proiettato da eventi; normalizzazione write_set/read_set; regola di overlap conservativa; compare-and-set atomico per `prendi-passo`/`offri-passo`. Slice (a) implementata (`bacheca_proiezioni.deriva_piano`, `piano_overlap.py`, `piano_comandi.py`); slice (b) — enforcement del dispatch — agganciata (`dashboard_risvegli` consulta `piano_overlap.valuta_dispatch_piano` prima di `postino.dispatch`, su collisione posta `segnalazione_conflitto` senza retry); slice (c) — widget "corsie" in dashboard (`/api/bacheca/piano`, `static/interfaccia.{js,css}`) — fatta 2026-09-02.
- [nota_codice.v1](../schema/nota_codice.v1.json) — post-it ancorati a un blocco di righe (S14.1): `ancora` percorso+range+hash, iniettati via hook (inclusa iniezione mirata per file via `PreToolUse`), marcati `da_rivedere` quando il codice si muove.

## Flusso dichiarato

- [Piano: flusso dichiarato](PIANO_FLUSSO_DICHIARATO.md) — il workflow standard (compito → gate → triage → registrazione → approvazione umana → chiusura), da prosa nelle istruzioni a dati validabili.
- [Flusso v1](../schema/flusso.v1.json) — schema dei passi di un flusso dichiarato (richiede/produce/richiede_opzionali, iniziale, irreversibile, approvazione_umana).
- [Flusso compito standard](../config/flussi/compito_standard.json) — il flusso reale del progetto, istanza validata dello schema sopra.

## Postino (risvegli automatici)

- [Guida: il postino e il dispatch headless](GUIDA_POSTINO_DISPATCH_HEADLESS.md) — **guida operativa di riferimento**: come funziona, prerequisiti per farlo funzionare, come usarlo, come replicarlo su un'altra macchina.
- [Piano: risvegli automatici](PIANO_RISVEGLI_AUTOMATICI.md) — storia delle decisioni e guardrail concordati con Gemini/Codex (tetti, capability provate non presunte, canali ufficiali).
- [RFC: stati di consegna del risveglio](RFC_STATI_CONSEGNA_RISVEGLIO.md) — specifica approvata e implementata (§15 Slice A): superare il bit binario `notificato` con `in_attesa` → `attenzione_richiamata` → `acquisito_da_hook` → `preso_in_carico` (+ terminale `chiuso_senza_consegna`); eventi in `consegne_risveglio.jsonl` append-only (unica fonte di verità), `risvegli_notificati.json` degrada a cache proiettata, hook in `hook_contesto.jsonl` separato, prova di `preso_in_carico` via `correla_a` (esteso `bacheca.py prendi`) o provenienza.
- [RFC: server MCP locale](RFC_SERVER_MCP_LOCALE.md) — specifica approvata e implementata (§15 Slice B): server stdio per-sessione che espone bacheca/piano/note come 8 tool tipizzati chiamando le funzioni di dominio (mai subprocess CLI), così gli agenti rispondono senza sillabare comandi di shell. Non riporta Gemini nel dispatch headless (risponde a tool call, non avvia turni). Implementata sia in lettura che in scrittura (`mcp_orchestratore.py`, `bacheca_scritture.py`, `config/mcp.esempio.json`). Smoke 3/3 client PASS (Claude Code, Codex CLI, Antigravity).
- [verifica_aggiornamenti_cli.py](../verifica_aggiornamenti_cli.py) — controllo settimanale (Attività Pianificata Windows) delle versioni di claude/codex/agy, riassunto note di rilascio col modello locale, notifica in bacheca; mai un aggiornamento automatico senza verdetto umano.

## Integrazioni opzionali

- [LiteLLM](INTEGRAZIONE_LITELLM.md) — gateway opzionale per provider LLM, costo misurato e token.

## Schemi

- [Evento v1](../schema/evento.v1.json) — riga JSONL del registro.
- [Compito v1](../schema/compito.v1.json) — stato runtime di un compito.
- [Messaggio v1](../schema/messaggio.v1.json) — riga JSONL della bacheca multi-agente, in uso da `bacheca.py` ([RFC Bacheca multi-agente](RFC_BACHECA_MULTIAGENTE.md)); dal 2026-08-31 include il campo opzionale `piano` ([RFC piano](RFC_PIANO_STEP_POSSEDUTI.md)), retrocompatibile.
- [Messaggio v2](../schema/messaggio.v2.json) — v1 congelata più il campo `ripresa` sui checkpoint ([RFC messaggio v2](RFC_MESSAGGIO_V2_RIPRESA.md)); il lettore instrada per versione, nessuna migrazione dello storico.
- [Flusso v1](../schema/flusso.v1.json) — passi di un flusso dichiarato ([Piano: flusso dichiarato](PIANO_FLUSSO_DICHIARATO.md)).

## Configurazione

- [Comandi esempio](../config/comandi.esempio.json)

## Script

- [registro.py](../registro.py) — append e validazione eventi.
- [sentinella.py](../sentinella.py) — esecuzione whitelistata dei gate.
- [genera_cruscotto.py](../genera_cruscotto.py) — riepilogo Markdown.
- [bacheca.py](../bacheca.py) — CLI della bacheca multi-agente (messaggi, thread, prossimi lavori, prese in carico, approvazioni, checkpoint ripristinabili v2, sottocomando `piano` per i passi posseduti S14.3).
- [postino.py](../postino.py) — motore di policy e dispatch headless del [Postino](GUIDA_POSTINO_DISPATCH_HEADLESS.md): `autorizza`/`dispatch`/`registra_canale`.
- [valida_flussi.py](../valida_flussi.py) — validatore read-only dei [flussi dichiarati](PIANO_FLUSSO_DICHIARATO.md).
- [adattatori/litellm.py](../adattatori/litellm.py) — adapter opzionale LiteLLM (chiamate a pagamento e locali, estrazione testo/misurazione condivisa).
- [triage_locale.py](../triage_locale.py) — classificazione routine/escalation di un output a costo zero col modello locale.
- [note_codice.py](../note_codice.py) — note di codice ancorate (S14.1): `aggiungi`/`elenco`/`verifica`/`hook`; stato derivato dall'hash del blocco.
- [mcp_orchestratore.py](../mcp_orchestratore.py) — server MCP locale stdio (§15 Slice B): 8 tool tipizzati che chiamano le funzioni di dominio — lettura (`bacheca_pendenti`/`bacheca_thread`/`piano_stato`/`note_codice_elenco`) + scrittura di coordinamento (`bacheca_rispondi`/`bacheca_prendi`/`piano_prendi_passo`/`piano_offri_passo`). Loop JSON-RPC 2.0 senza dipendenze. Config: `config/mcp.esempio.json`. Smoke 3/3 client.
- [bacheca_scritture.py](../bacheca_scritture.py) — scritture idempotenti in bacheca per l'MCP (§15 Slice B): `rispondi`/`prendi` con contratto `(mittente, thread_id, operazione, chiave)` — controllo+append sotto un lock, stessa chiave+payload → `gia_applicato`, payload diverso → `conflitto`.
- [consegne_risveglio.py](../consegne_risveglio.py) — stati di consegna del risveglio (§15 Slice A): log append-only `consegne_risveglio.jsonl` + `hook_contesto.jsonl`, proiezione `in_attesa → attenzione_richiamata → acquisito_da_hook → preso_in_carico` (+ `chiuso_senza_consegna`); `risvegli_notificati.json` resta cache (`rigenera_notificati` la ricostruisce dal log). Agganciato in `dashboard_risvegli` (watcher), `bacheca_comandi` (hook) e nel DTO della bacheca (`consegna_per_agente`). CLI: `elenco` / `reset` / `rigenera-cache`.
- [piano_overlap.py](../piano_overlap.py) — normalizzazione set di file + regola di collisione fra passi del piano (S14.3), calcolo puro fail-closed; `valuta_dispatch_piano` è il gancio che `dashboard_risvegli` consulta prima del dispatch (slice b).
- [piano_comandi.py](../piano_comandi.py) — comandi `bacheca.py piano` (crea/prendi/offri-passo, approva-handoff) con compare-and-set atomico. `crea-passo --proprietario` fa nascere il passo già `in_corso`.
- [contesa_tree.py](../contesa_tree.py) — controllo pre-dispatch della contesa sul working tree ("80% leggero" di §15 Slice C, worktree differiti): se `git status` mostra modifiche non committate sui file del `write_set` dell'agente, `postino.dispatch` torna `tree_conteso` (niente CLI, niente retry). Fail-open senza git o senza piano dichiarato. Log append-only `contese.jsonl`.
- [console_utf8.py](../console_utf8.py) — forzatura centralizzata di stdout/stderr/stdin in UTF-8 con fallback di rimpiazzo su Windows.
- [blocco_file.py](../blocco_file.py) — lock a file condiviso con timeout e gestione lock abbandonati per bacheca e risvegli.
- [scrittura_jsonl.py](../scrittura_jsonl.py) — transazione di scrittura append-only sicura con lock a file, validazione schema e fsync.
- [commit_replay.py](../commit_replay.py) — correla un commit reale alla finestra di eventi del registro, per il replay in dashboard.
- [utility/installa_hook.py](../utility/installa_hook.py) — installa l'hook Git pre-commit del quality gate.
- [esempi/chiamata_agente_litellm.py](../esempi/chiamata_agente_litellm.py) — esempio eseguibile di chiamata LiteLLM con fallback mock.
- [esempi/spike_dispatcher_locale.py](../esempi/spike_dispatcher_locale.py) — spike usa-e-getta: valuta se il modello locale regge il ruolo di dispatcher (sintesi/instradamento/conflitti) per la [RFC Bacheca multi-agente](RFC_BACHECA_MULTIAGENTE.md).

## Note vault

- I dati runtime restano in `dati_locali/` e non vanno nel vault condiviso.
- I link sono relativi, quindi funzionano sia in repository sia in Obsidian.
- Le note progettuali nuove vanno aggiunte qui prima di diventare operative.
