# Squadra (Orchestratore LLM)

Struttura operativa riutilizzabile per coordinare più agenti AI commerciali (Claude, Codex, Gemini), un LLM locale economico gratuito e un operatore umano su qualunque base codice — **senza costi API a consumo**, sfruttando gli abbonamenti flat già attivi.

> *Per una panoramica sintetica e divulgativa senza dettagli tecnici, consulta la guida: [docs/PRESENTAZIONE_SEMPLICE.md](docs/PRESENTAZIONE_SEMPLICE.md).*

Il principio guida è semplice:

> il valore non è far parlare gli agenti; il valore è ridurre il contesto riletto ogni volta, instradare meglio, misurare costo/resa e svegliare il lavoratore giusto solo quando serve.

---

## Componenti Principali

- `bacheca.py` — **Bacheca multi-agente**: messaggistica asincrona strutturata tra Claude, Codex, Gemini, modello locale e umano su file append-only, senza API a pagamento (vedi `docs/RFC_BACHECA_MULTIAGENTE.md` e `docs/GUIDA_SEMPLICE_BACHECA_MULTIAGENTE.md`).
- `postino.py` — **Dispatch headless automatico**: sveglia ed esegue in background l'agente destinatario (Claude, Codex, Gemini) per i thread pendenti, con sandbox restrittive e controlli anti-loop (vedi `docs/GUIDA_POSTINO_DISPATCH_HEADLESS.md`).
- `commit_replay.py` — **Ricostruzione & Replay Commit**: calcola la finestra temporale e le interazioni reali collegate a ciascun commit Git, stimando il risparmio economico ottenuto grazie al modello locale gratuito.
- `interfaccia.py` & `interfaccia.html` — **Dashboard Web**: visualizzatore in tempo reale con:
  - **Diagramma di cooperazione SVG radiale**: con il **Gestore Squadra** (infrastruttura) al centro che anima visivamente i passaggi di consegna e le interazioni tra tutti i membri del team.
  - **Custom Commit Picker a 2 righe**: per selezionare e rivivere la sequenza reale di eventi che ha portato a ciascun commit.
  - **Live Handoff Console** e monitoraggio pratiche sospese / conflitti.
- `registro.py` — appende e valida (con `jsonschema`) eventi nel registro JSONL (`eventi.jsonl`).
- `sentinella.py` — esegue solo comandi dichiarati in whitelist e registra l'esito del quality gate.
- `triage_locale.py` — guardia automatica locale (llama-server) per classificare output di test e build senza consumare token cloud.
- `capoturno.py` — motore di orchestrazione: instrada, gestisce patch e fallback automatico.
- `verifica_aggiornamenti_cli.py` — controllo periodico delle versioni delle CLI (claude/codex/agy) con sintesi delle note di rilascio tramite LLM locale e notifica in bacheca.

---

## Avvio rapido

Avviare la dashboard web per l'uso quotidiano (apre automaticamente il browser su `http://127.0.0.1:8095`):

```powershell
.\avvia_dashboard.ps1
```

Controllare la bacheca per il proprio agente (es. Gemini):

```powershell
.\pull gemini
```

Aggiungere un evento nel registro:

```powershell
python .\registro.py aggiungi --id-compito prova --agente codex --tipo-compito revisione --stato accettato --esito-gate superato --verdetto-umano approvato --note "prima prova"
```

Validare la bacheca e il registro:

```powershell
python .\bacheca.py valida
python .\registro.py valida
```

Eseguire un gate con triage della sentinella locale:

```powershell
python .\sentinella.py test_servizi --id-compito "<id-compito>" --triage-locale
```

---

## Test & Quality Gate

Tutti i test usano la suite standard (270 test unitari e di integrazione):

```powershell
py -3.14 -m pytest
```

Quality gate per linting, type-checking e complessità ciclomatica:

```powershell
python -m ruff check .
python -m mypy .
python -m xenon --max-absolute C --max-modules B --max-average B .
```

---

## Regole Fondamentali del Framework

1. **Nessun costo API a consumo**: gli agenti commerciali operano tramite sessioni interattive o CLI headless con abbonamenti flat esistenti.
2. **Il modello locale non tocca il codice di produzione**: fa solo da guardia e triage economico sugli output ripetitivi.
3. **Azioni irreversibili sempre all'umano**: commit, push, merge, deploy e cancellazioni richiedono esplicito verdetto umano.
4. **Append-only & Tracciabilità**: registro e bacheca sono immutabili e verificabili.
5. **Sentinella a perimetro chiuso**: vengono eseguiti solo i comandi dichiarati in whitelist.

Per la mappa documentale completa, consulta [docs/INDEX.md](docs/INDEX.md) e la guida [docs/ORCHESTRAZIONE_LAVORATORI.md](docs/ORCHESTRAZIONE_LAVORATORI.md).
