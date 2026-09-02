# RFC (bozza) — Server MCP locale per bacheca, piano e registro

**Stato:** bozza approvata da Gemini (2026-09-02, thread `fb8338d2`). In attesa
della revisione Codex e del verdetto umano prima del codice.
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
| Root del repo | Fissata all'avvio: `--radice <path>` oppure `ORCHESTRATORE_RADICE`, fallback a `Path(__file__).parent`. Il server **non** accetta un path di progetto per-call: una sessione = un repo. |
| Come agisce | Importa e chiama **funzioni di dominio** (`bacheca_proiezioni`, `bacheca` write helper, `piano_comandi`, `note_codice`, `registro`). **Mai** `subprocess` verso `bacheca.py`/`registro.py`. |
| Atomicità | Riusa i lock esistenti: `piano_comandi` fa già CAS via `scrittura_jsonl.transazione_jsonl`; le scritture in bacheca passano per `scrittura_jsonl`. Il server non introduce un secondo meccanismo di lock. |
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
- **`agente` dichiarato, non provato.** In stdio locale il client *è* l'agente;
  il server prende l'identità dall'argomento di avvio, non da un tool call. Un
  tool call che passa un `agente` diverso è rifiutato con errore, non
  silenziosamente accettato.

## Concorrenza

Scenari simultanei possibili:

- più server MCP (uno per sessione client) che scrivono lo stesso `messaggi.jsonl`;
- il watcher della dashboard che scrive `segnalazione_conflitto` / stati di consegna;
- una CLI `bacheca.py` lanciata a mano.

Tutti passano per `scrittura_jsonl` (lock su file, `O_CREAT|O_EXCL`, soglia lock
abbandonato). `piano_prendi_passo` è già serializzato da
`scrittura_jsonl.transazione_jsonl` dentro `piano_comandi`. Il server **non**
aggiunge lock propri: se lo facesse, avrebbe due gerarchie di lock e un possibile
deadlock.

**Idempotenza delle scritture.** Un client MCP può ritentare una tool call (timeout,
riconnessione). `piano_*` hanno già `idempotency_key`. Per `bacheca_rispondi` /
`bacheca_prendi` si aggiunge una `idempotency_key` opzionale: il server, sotto lo
stesso lock della scrittura, controlla se un messaggio del thread la porta già in
`metadati.idempotency_key` e in tal caso ritorna `{esito: "gia_applicato"}` senza
scrivere.

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

## File nuovi previsti

- `mcp_orchestratore.py` — il server. Sottile: registra i tool, mappa
  argomenti → funzione di dominio → risultato. Nessuna logica di business propria.
- `config/mcp.esempio.json` — config di esempio per un client MCP (comando,
  args `--radice`/`--agente`), sul modello di `config/comandi.esempio.json`. Il
  file reale con i path assoluti di questa macchina resta gitignored.
- Voce in `docs/INDEX.md`.

## Testing

- **Unit** — per ogni tool: argomento valido → chiama la funzione di dominio
  giusta con i parametri giusti → mappa il risultato; argomento non valido →
  errore tipizzato, nessuna scrittura.
- **Idempotenza** — stessa `idempotency_key` due volte → una sola riga.
- **Concorrenza** — due «server» nello stesso processo di test che scrivono lo
  stesso file → N righe valide (riusa il guardrail di `test_scrittura_jsonl`).
- **Smoke stdio** — avvio del server come subprocess, `initialize` + `tools/list`
  + una `tools/call` di lettura, verifica della risposta JSON-RPC.
- **Trust** — un `bacheca_thread` che restituisce un messaggio con testo
  «istruzione»: verifica che il server lo passi come contenuto e non lo
  interpreti (il server non interpreta comunque nulla, ma il test fissa il
  contratto).

## Fasi

1. **RFC approvata** (questo documento) — Gemini ok, manca Codex + verdetto umano.
   Supporto MCP stdio dei tre client: confermato da Gemini (vedi in cima), da
   riprovare con una config reale in Fase 2.
2. **`bacheca.py prendi --correla-a`** — FATTO (commit `3387866`, Slice A). L'MCP
   `bacheca_prendi` lo riusa e basta.
3. **MVP di sola lettura** — `bacheca_pendenti`, `bacheca_thread`, `piano_stato`,
   `note_codice_elenco`. Nessuna scrittura. Si prova con Claude Code per una
   settimana: gli agenti leggono lo stato via tool invece che via hook?
4. **Scrittura** — `bacheca_rispondi`, `bacheca_prendi` (con `correla_a`),
   `piano_prendi_passo`, `piano_offri_passo`.
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
