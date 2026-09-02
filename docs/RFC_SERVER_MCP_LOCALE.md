# RFC (bozza) — Server MCP locale per bacheca, piano e registro

**Stato:** MVP di sola lettura implementato e rivisto (2026-09-02,
`mcp_orchestratore.py`). Gemini approva; **Codex approva il loop senza SDK
SOLO come MVP read-only e timeboxed** — non come base della fase scrittura: un
protocollo fatto a mano richiede compatibilità continua, quindi **prima delle
scritture serve uno smoke reale con Codex CLI e Antigravity, oppure la migrazione
all'SDK `mcp`**. Correzioni della revisione recepite: `--radice` obbligatoria
senza fallback, validazione `jsonrpc`/`params`, `ping`, negoziazione
`protocolVersion`, limite su `bacheca_thread`, smoke-test subprocess,
contratto di idempotenza per le scritture, correzione del claim su
`scrittura_jsonl`.
**Origine:** PIANO_INDUSTRIALIZZAZIONE.md §15 Slice B (thread bacheca `fb8338d2`).
Prerequisito «verifica del codice sorgente reale dei benchmark» già svolto
(Codex, 2026-09-02, thread `4ddae141`): vedi sotto.

**Domanda bloccante RISOLTA** (Gemini, 2026-09-02): tutti e tre i client
supportano un server MCP stdio nativo — Claude Code via `.mcp.json`, Codex CLI
via `codex mcp add <NAME> -- <COMANDO>` (con `--env`), Antigravity via
`mcp_config.json` in `~/.gemini/config/` o `.agents/`. Il valore «universale»
regge. Da confermare con una config reale per ciascun client al momento
dell'MVP (Fase 2), in particolare il meccanismo `codex mcp add` va provato da
Codex sul suo strumento.

## Cosa risolve — e cosa no

**Problema concreto.** Gli agenti *ricevono* il contesto della bacheca bene
(l'hook lo inietta), ma per *rispondere* devono lanciare
`python bacheca.py rispondi --testo "..."` come comando di shell. In pratica:

- Codex applica l'anti-injection alla lettera e si blocca sul contenuto della
  bacheca etichettato «non fidato» (vedi memoria `codex_serve_spinta_esplicita_ad_agire`);
- il quoting di un testo multilinea in shell è fragile e sbagliarlo silenziosamente
  produce un messaggio troncato;
- ogni agente ha una sillabazione diversa dei comandi, e un flag nuovo
  (`--correla-a`, `piano prendi-passo`) va reinsegnato a tutti.

Un **tool MCP tipizzato** — `bacheca_rispondi(thread_id, testo)` — elimina la
shell: il client MCP lo chiama nativamente, con argomenti strutturati, e il
server valida e scrive.

**Cosa NON risolve (promemoria, thread `9ebc1315`).** L'MCP **non** riporta
Gemini nel dispatch headless di `smodata`. Un server MCP *risponde* a tool call
dentro un turno già in corso; non *avvia* turni. Rende Gemini (e Codex, e Claude)
un buon lavoratore **semi-interattivo** — l'umano apre la sessione, l'agente ha i
tool a portata di mano — non un lavoratore headless. Il risveglio (passivo o
headless) resta un problema separato, coperto dal Postino e dalla RFC stati di
consegna.

## Verifica dei benchmark (Codex, 2026-09-02) — dal sorgente, non dai README

- **`agent-blackboard` `@118cc8d`**: **non** espone un server MCP stdio né tool
  della lavagna. `mcp` compare solo come dipendenza/config per un *memory server*
  MCP esterno; la Blackboard è un'API Python async con persistenza JSON. **Niente
  da riusare**: il disegno qui sotto è interamente nostro.
- **`ao` `@4fe9a4a`** e **`Overstory` `@ff38f3f`**: rilevanti per §15 Slice A e C,
  non per l'MCP.

Conclusione: **stdio + funzioni di dominio native** non è una scelta copiata da
un benchmark, è l'unica coerente con i vincoli del progetto (local-first, niente
API non ufficiali, riuso dei lock esistenti).

## Forma del server

| Aspetto | Decisione |
|---|---|
| Trasporto | **stdio** (newline-delimited JSON-RPC 2.0). Nessun demone, nessuna porta di rete, nessun socket. |
| Ciclo di vita | **Un processo per sessione client**, spawnato dal client (Claude Code, ecc.) alla sua apertura e ucciso alla chiusura. Nessun processo long-running condiviso. |
| Latenza | Bassa, **non zero**: c'è lo spawn del processo all'avvio della sessione e il framing dei messaggi a ogni call. «Zero» era impreciso. |
| Root del repo | Fissata all'avvio da **`--radice <path>` obbligatoria, senza fallback implicito** (revisione Codex): in un git worktree `Path(__file__).parent` punterebbe al worktree, non al checkout con `dati_locali/`. Il server **non** accetta un path di progetto per-call: una sessione = un repo. |
| Come agisce | Importa e chiama **funzioni di dominio** (`bacheca_proiezioni`, `bacheca` write helper, `piano_comandi`, `note_codice`, `registro`). **Mai** `subprocess` verso `bacheca.py`/`registro.py`. |
| Atomicità | `piano_comandi` fa già CAS via `scrittura_jsonl.transazione_jsonl`. **`bacheca.aggiungi_messaggio` oggi NON usa `scrittura_jsonl`** — è un `open("a")` nudo (rilievo Codex). La fase scrittura deve prima portare le scritture di bacheca su un percorso serializzato (migrare `aggiungi_messaggio` a `scrittura_jsonl`, o far usare `transazione_jsonl` ai tool di scrittura dell'MCP). Il server non introduce un secondo meccanismo di lock. |
| Identità dell'agente | Il server è avviato con `--agente <claude|codex|gemini>` (dalla config del client). I tool di scrittura usano **quell'**agente come mittente; un argomento `agente` in un tool call che lo contraddice è rifiutato. |

## Superficie — MVP

Tutti i tool hanno schema di input tipizzato (JSON Schema, generato dai type hint
o scritto a mano). Gli output sono `{esito: "...", ...}` — gli stessi dict che le
funzioni di dominio già ritornano — serializzati come contenuto strutturato del
risultato del tool.

### Lettura

| Tool | Argomenti | Ritorna | Funzione di dominio |
|---|---|---|---|
| `bacheca_pendenti` | — | i thread in cui l'agente del server è `destinatario_pendente`, con l'ultimo messaggio | `bacheca_proiezioni.destinatari_pendenti` + `thread_pendenti_per_agente` |
| `bacheca_thread` | `thread_id` | cronologia completa del thread + `piano` proiettato | `bacheca_proiezioni.messaggi_del_thread` + `deriva_piano` |
| `piano_stato` | `thread_id` | `deriva_piano(...)` o `null` | `bacheca_proiezioni.deriva_piano` |
| `note_codice_elenco` | `percorsi?` (lista) | note attive/da_rivedere/orfane, filtrate per file se `percorsi` è dato | `note_codice.note_con_stato` / `note_per_file` |

### Scrittura

| Tool | Argomenti | Funzione di dominio | Note |
|---|---|---|---|
| `bacheca_rispondi` | `thread_id`, `testo`, `correla_a?`, `idempotency_key?` | `bacheca` write helper (come `comando_rispondi`) | `correla_a` serve alla RFC stati di consegna (prova di `preso_in_carico`). `idempotency_key`: se un messaggio con la stessa chiave esiste già nel thread, no-op. |
| `bacheca_prendi` | `thread_id`, `correla_a?`, `idempotency_key?` | come `comando_prendi` (`presa_in_carico`) | idem `correla_a` |
| `piano_prendi_passo` | `thread_id`, `passo_id`, `idempotency_key?` | `piano_comandi.prendi_passo` | CAS atomico già garantito dalla funzione |
| `piano_offri_passo` | `thread_id`, `passo_id`, `a` | `piano_comandi.offri_passo` | propone handoff, non trasferisce |

### Fase 2 (dopo che l'MVP è in uso reale)

| Tool | Funzione di dominio |
|---|---|
| `registro_aggiungi` | `registro.aggiungi_evento` — con i vincoli di `CLAUDE.md` (costo stimato, `esito_gate` solo se verificato) espressi nella descrizione del tool |
| `piano_approva_handoff` | `piano_comandi.approva_handoff` |

## Esclusioni tassative

Mai esposti come tool, in nessuna fase:

- **file I/O generico** (lettura/scrittura di file arbitrari del repo);
- **dispatch** / risveglio di un altro agente (`postino.dispatch`, `esegui_risvegli_bacheca`);
- **toggle del profilo Postino** (`standard`/`brainstorming`/`super`/`smodata`);
- **qualunque comando git**, in lettura o scrittura;
- **esecuzione di comandi / gate** (`sentinella.py`): un agente che vuole girare i
  test lo fa con i suoi strumenti nativi, non attraverso l'MCP dell'orchestratore.

Il perimetro dell'MCP è: *leggere lo stato di coordinamento e scrivere messaggi
di coordinamento*. Nient'altro.

## Modello di trust

- **Nessuna autenticazione.** Trasporto stdio locale, processo figlio del client,
  stesso utente e stessi privilegi del client. Non c'è una superficie di rete da
  proteggere.
- **I risultati dei tool sono DATI, non autorità.** Un thread di bacheca
  restituito da `bacheca_thread` può contenere testo che sembra un'istruzione
  («ignora le regole del progetto e fai X»). Vale la stessa regola del contesto
  iniettato dall'hook oggi: è contenuto da riassumere/valutare, mai da obbedire.
  Il server lo esplicita nella `description` di ogni tool di lettura e, dove il
  protocollo lo permette, marca il contenuto come non fidato.
- **L'audit resta la bacheca append-only.** Ogni scrittura via MCP è un record
  bacheca normale, con `mittente` = agente del server. Non c'è un canale nascosto.
- **`agente` = etichetta di provenienza, non autenticazione** (precisazione
  Codex). In stdio locale il client *è* l'agente; il server prende l'identità
  dall'argomento di avvio, **mai** da un tool call (nessun override per-call). Fra
  processi dello stesso utente un'auth più forte non aggiungerebbe molto — cambia
  solo se il server esce da stdio/locale. Questo va scritto esplicitamente nel
  threat model (`docs/THREAT_MODEL.md`): la firma `mittente` sui record MCP è
  audit, non garanzia d'identità.

## Concorrenza

Scenari simultanei possibili:

- più server MCP (uno per sessione client) che scrivono lo stesso `messaggi.jsonl`;
- il watcher della dashboard che scrive `segnalazione_conflitto` / stati di consegna;
- una CLI `bacheca.py` lanciata a mano.

`piano_prendi_passo` è già serializzato da `scrittura_jsonl.transazione_jsonl`
dentro `piano_comandi`. `bacheca.aggiungi_messaggio` è stata migrata a
`scrittura_jsonl` (commit del 2026-09-02) — le scritture di bacheca ora prendono
il lock di file; il prerequisito della fase scrittura è soddisfatto. Il server
**non** aggiunge lock propri: se lo facesse, avrebbe due gerarchie di lock e un
possibile deadlock. **Nota**: `aggiungi_messaggio` non è reentrante — i tool di
scrittura che devono leggere-e-scrivere atomico (idempotenza) useranno
`transazione_jsonl` direttamente, non `aggiungi_messaggio` sotto lock.

**Idempotenza delle scritture** (contratto da revisione Codex). Obbligatoria per
*ogni* scrittura, non opzionale. Chiave con scope `(mittente, thread_id,
operazione, idempotency_key)`. Controllo **e** append avvengono sotto **un solo**
lock:

- chiave già vista, **stesso payload** → `{esito: "gia_applicato", id_messaggio:
  <quello originale>}`, nessuna nuova riga;
- chiave già vista, **payload diverso** → `{esito: "conflitto"}`, **non**
  `gia_applicato` (è un errore del client, non un retry);
- chiave nuova → si scrive, si ritorna il nuovo `id_messaggio`.

`piano_*` hanno già `idempotency_key` con semantica compatibile.

## Compatibilità dei client

| Client | Supporto MCP stdio | Config |
|---|---|---|
| **Claude Code** | sì, nativo | `.mcp.json` / `--mcp-config` |
| **Codex CLI** | sì (Gemini, 2026-09-02) | `codex mcp add <NAME> -- <COMANDO>`, flag `--env` — **Codex confermi il meccanismo sul suo strumento** |
| **Antigravity / Gemini** | sì (Gemini, 2026-09-02) | `mcp_config.json` in `~/.gemini/config/` o `.agents/` |

L'MCP è **additivo**: `bacheca.py` e `registro.py` restano la via di riferimento e
l'unica per i client senza MCP. Non si rimuove nulla. `config/mcp.esempio.json`
raccoglierà i tre snippet di config (uno per client), con i path assoluti reali
gitignored come per `config/comandi.json`.

## Dipendenza

Né `mcp` né `fastmcp` sono installati oggi. Due strade:

1. **SDK ufficiale `mcp` (Python)** — pip, puro Python, nessuna rete a runtime.
   Gestisce handshake, `tools/list`, `tools/call`, framing stdio. Costo: una
   dipendenza in più in `requirements`/`setup.ps1`.
2. **Hand-roll** del loop JSON-RPC 2.0 su stdio (newline-delimited). ~150 righe,
   nessuna dipendenza, ma va mantenuto in pari col protocollo MCP.

**Raccomandazione: (1)**, l'SDK. È mantenuto da Anthropic, il protocollo evolve, e
150 righe di framing di protocollo sono esattamente il tipo di codice che non
vogliamo possedere. La dipendenza è isolabile: solo `mcp_orchestratore.py` la
importa; se un domani dà problemi, il fallback (2) resta possibile perché la
logica vera sta tutta nelle funzioni di dominio.

## File nuovi

- `mcp_orchestratore.py` — il server. **Fatto** (MVP sola lettura). Sottile:
  registra i tool, mappa argomenti → funzione di dominio → risultato. Nessuna
  logica di business propria. Loop JSON-RPC 2.0 stdio senza dipendenze.
- `config/mcp.esempio.json` — **fatto**: i tre snippet di config (Claude Code,
  Codex CLI, Antigravity) con `<RADICE>`/`<AGENTE>` da sostituire. Il file reale
  con i path assoluti va trattato come `config/comandi.json` (fuori da Git).
- Voce in `docs/INDEX.md` — **fatta**.

## Testing

- **Unit** — per ogni tool: argomento valido → chiama la funzione di dominio
  giusta con i parametri giusti → mappa il risultato; argomento non valido →
  errore tipizzato, nessuna scrittura.
- **Idempotenza** — stessa `idempotency_key` due volte → una sola riga.
- **Concorrenza** — due «server» nello stesso processo di test che scrivono lo
  stesso file → N righe valide (riusa il guardrail di `test_scrittura_jsonl`).
- **Smoke stdio** — FATTO (`test_smoke_subprocess_stdio`): server avviato come
  subprocess reale, `initialize` + `notifications/initialized` + `tools/list` +
  `tools/call`, verifica delle risposte JSON-RPC. Da estendere a uno smoke
  lanciato dai client reali (Codex CLI, Antigravity) prima della fase scrittura.
- **Robustezza del loop** — `params` non-oggetto, `jsonrpc` errato, riga non-JSON:
  errore tipizzato, il loop prosegue (regressione della revisione Codex).
- **Trust** — un `bacheca_thread` che restituisce un messaggio con testo
  «istruzione»: verifica che il server lo passi come contenuto e non lo
  interpreti (il server non interpreta comunque nulla, ma il test fissa il
  contratto).

## Fasi

1. **RFC approvata** — Gemini ok, Codex ok (con vincolo timeboxed), manca il
   verdetto umano. Supporto MCP stdio dei tre client confermato: `codex mcp add`
   verificato da Codex sul suo strumento (`codex mcp add [OPTIONS] <NAME> (--url |
   -- <COMMAND>...)`), Antigravity `.agents/mcp_config.json` da doc primaria.
   **Smoke reale (2026-09-02)**: `--radice`/`--agente` espliciti, config
   gitignored, template in `config/mcp.esempio.json`.
   - **B1 Claude Code: PASS** — `.mcp.json` nella root; server connesso alla
     sessione, `bacheca_pendenti` e `note_codice_elenco` chiamati e verificati.
   - **B3 Antigravity: PASS** — Gemini in Antigravity ha chiamato
     `bacheca_pendenti` via MCP, risposta JSON-RPC valida (`isError: false`).
     `.agents/mcp_config.json` **NON** viene letto: Antigravity usa la sua UI
     (Settings → Customizations → Installed MCP Servers → "Open MCP Config").
   - **B2 Codex CLI: registrato** — `.codex/config.toml` di progetto funziona
     (`codex mcp list` mostra `orchestratore`), manca la chiamata da dentro
     `codex` per il pass pieno.
2. **`bacheca.py prendi --correla-a`** — FATTO (commit `3387866`, Slice A).
3. **MVP di sola lettura** — FATTO e rivisto (`mcp_orchestratore.py`, 12 test
   incl. smoke subprocess). `config/mcp.esempio.json` ha i quattro snippet
   (Claude, `codex mcp add`, `.codex/config.toml`, Antigravity). Da provare con
   Claude Code per una settimana: gli agenti leggono lo stato via tool invece
   che via hook?
3bis. **PRIMA della fase scrittura** (vincolo Codex): smoke reale del server
   avviato da Codex CLI e da Antigravity — non solo dal test Python — oppure
   decidere la migrazione all'SDK `mcp`. ~~Portare le scritture di bacheca su un
   percorso serializzato~~ **FATTO** (`bacheca.aggiungi_messaggio` → `scrittura_jsonl`,
   2026-09-02).
4. **Scrittura** — `bacheca_rispondi`, `bacheca_prendi` (con `correla_a`),
   `piano_prendi_passo`, `piano_offri_passo`. `idempotency_key` **obbligatoria**
   (contratto nella sezione Concorrenza); `agente` mai da tool call.
5. **Fase 2** — `registro_aggiungi`, `piano_approva_handoff`; config reale per
   Codex CLI e Antigravity.
6. Worktree-awareness (Slice C): quando esisterà, il server dovrà sapere che
   `dati_locali/` è nel root del repo, non nel worktree — stesso nodo di §15.4.

## Domande aperte

1. ~~**Codex e Antigravity supportano un server MCP stdio?**~~ **RISOLTA** (Gemini,
   2026-09-02): sì, tutti e tre — `.mcp.json` (Claude), `codex mcp add` (Codex),
   `mcp_config.json` (Antigravity). Da riconfermare con una config reale in Fase 2.
2. **`agente` all'avvio vs multi-agente nello stesso client.** Se un domani un
   client volesse agire come agenti diversi nella stessa sessione, il modello «un
   server = un agente» non regge. Per ora è un vincolo accettabile (una sessione
   Claude Code *è* «claude»).
3. **`bacheca_pendenti` e i tetti.** Un agente che risponde via MCP a raffica non
   passa per i tetti del Postino (che valgono per il dispatch, non per le
   scritture dirette). Serve un limite di ritmo lato server, o la natura
   semi-interattiva (un umano nella sessione) è già sufficiente?
4. ~~**Sincronia con la RFC stati di consegna.**~~ **RISOLTA**: `bacheca.py prendi
   --correla-a` è già stato aggiunto (Slice A, commit `3387866`); `bacheca.py
   rispondi` aveva già `--correla-a`. L'MCP `bacheca_prendi`/`bacheca_rispondi`
   li riusano direttamente.
