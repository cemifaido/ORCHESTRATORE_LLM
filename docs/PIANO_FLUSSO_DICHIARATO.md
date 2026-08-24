# Piano operativo: flusso dichiarato (Proposta 2, idee Weft)

**Stato**: assegnazione in corso via bacheca (2026-08-24). Coordinatore: Claude.
**Prerequisito soddisfatto**: pilota Proposta 1 committato (`1d1e0f1`) con
approvazione di Gemini, Codex e verdetto umano — come da ordine concordato in
`docs/PROPOSTA_RIUSO_IDEE_WEFT.md`.

## Obiettivo

Il workflow standard (compito → gate → triage → registrazione → approvazione
umana → chiusura), oggi prosa in CLAUDE.md/GEMINI.md/AGENTS.md, diventa dati
validabili: un file di flusso + uno schema + un validatore, e la dashboard lo
disegna dai dati. Nessun motore di esecuzione: il flusso descrive e valida,
l'esecuzione resta agli agenti (non-obiettivo esplicito della proposta).

## Lotti e assegnatari

### Lotto 0 — bozza del flusso di riferimento (Claude, FATTO)

`config/flussi/compito_standard.json`: la conoscenza oggi in prosa, trascritta
in dati. **È una bozza senza schema**: serve a dare a Codex un caso concreto da
modellare e a Gemini un dato reale su cui disegnare. Codex ha piena facoltà di
rimodellarla quando definisce lo schema.

### Lotto 1 — schema e validatore (Codex, thread bacheca dedicato)

- `schema/flusso.v1.json` (draft 2020-12, `additionalProperties: false`,
  versionato come `messaggio.v*.json`).
- Validatore con controlli strutturali: id dei passi univoci, passi orfani
  (mai raggiunti), `richiede` senza un passo che lo produca, produzioni mai
  consumate, passo `irreversibile: true` senza approvazione umana a monte.
  Collocazione a scelta di Codex (sottocomando di `sentinella.py` o script
  dedicato), purché invocabile da CLI e con exit code 0/1.
- Test in `tests/`, gate completo (unittest + ruff + mypy).

### Lotto 2 — dashboard (Gemini, thread bacheca dedicato, dopo/in parallelo)

- Stepper read-only del flusso in `interfaccia.py`/`interfaccia.html`:
  consuma `config/flussi/*.json`, evidenzia la fase corrente di un
  thread/compito. Può partire in mock sulla bozza del Lotto 0 e allinearsi
  allo schema di Codex appena pubblicato; HTML/CSS leggero, nessuna
  dipendenza JS pesante (vincolo posto da Gemini stesso).
- Widget "pratiche sospese": i checkpoint con `ripresa` (v2, già committati)
  in attesa di verdetto, con l'azione prevista per esito. Read-only.

### Coordinamento

- Ogni lotto vive nel suo thread bacheca; presa in carico con `prendi` e
  `--file-modificati` (lease sui file), avanzamento con `checkpoint`.
- Conflitti o dubbi di perimetro: segnalarli sul thread, decide l'umano.
- Chiusura di ogni lotto: gate verde dichiarato sul thread + revisione
  incrociata (Codex rivede il lotto 2 per rigore, Gemini il lotto 1 per
  consumabilità dalla dashboard), poi verdetto umano per il commit — stesso
  cerimoniale del pilota, che ha funzionato.
