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
- `setup_wizard.py` / `setup.ps1` — wizard interattivo per la configurazione guidata dell'ambiente, installazione dipendenze e rilevamento modulare delle risorse (funziona con qualsiasi sottoinsieme di agenti, con o senza GPU).
- `capoturno.py` — motore di orchestrazione: instrada, gestisce patch e fallback automatico.
- `verifica_aggiornamenti_cli.py` — controllo periodico delle versioni delle CLI (claude/codex/agy) con sintesi delle note di rilascio tramite LLM locale e notifica in bacheca.

---

## Guida all'Installazione & Prerequisiti

### 1. Prerequisiti di Sistema
Prima di iniziare, assicurati di avere installato sul tuo computer:
- **Python >= 3.10** (raccomandato Python 3.11, 3.12, 3.13 o 3.14).
- **Git** per la gestione del repository e dei branch.
- **Node.js** (opzionale, necessario solo se intendi installare le CLI di Claude o Codex via `npm`).

---

### 2. Account e Strumenti Assistenti AI (Opzionali e Modulari)
Squadra è pensata per funzionare con **qualsiasi combinazione di assistenti**: puoi usarne tre, due, uno solo, o lavorare solo con l'operatore umano e il modello locale.

| Assistente | Tool CLI | Come si installa | Account / Login richiesto |
|---|---|---|---|
| **Claude Code** | `claude` | `npm install -g @anthropic-ai/claude-code` | Abbonamento Anthropic (Claude Pro/Team/Max) con login una tantum `claude` |
| **OpenAI Codex** | `codex` | `npm install -g @openai/codex` | Abbonamento OpenAI (ChatGPT Plus/Team) con login una tantum `codex` |
| **Google Gemini** | `agy` | `irm https://antigravity.google/cli/install.ps1 \| iex` | Account Google con login OAuth una tantum `agy models` |
| **Modello Locale** | `llama-server` | Binario `llama.cpp` + modello `.gguf` (es. Qwen 2.5 3B) | **Nessun account, 100% gratuito e offline** (se non hai GPU dedicata, il wizard disattiva l'LLM e usa triage deterministico) |

---

### 3. Procedura Passo-Passo per Partire

#### Passo 1: Copiare o Clonare il Progetto
Scarica o clona il repository nella cartella desiderata:
```powershell
git clone <URL_REPOSITORY> _ORCHESTRATORE_LLM
cd _ORCHESTRATORE_LLM
```

#### Passo 2: Eseguire il Setup Wizard Guidato
Avvia il wizard di configurazione (esegue la diagnosi, chiede quali agenti abilitare, installa le dipendenze e genera il file `.env` locale):

```powershell
.\setup.ps1
```
*(oppure `python setup_wizard.py`)*

Durante il wizard ti verrà chiesto:
1. Quali assistenti abilitare tra quelli presenti sul tuo PC.
2. Se disponi di una GPU per il modello locale o se preferisci la modalità leggera senza GPU.
3. Se desideri installare automaticamente le dipendenze Python (`requirements.txt` e `requirements-dev.txt`).
4. La porta della Dashboard web (default `8095`).
5. Se installare l'hook Git pre-commit per il controllo automatico di qualità.

#### Passo 3: Avvio della Dashboard
Al termine del setup, avvia la console operativa:

```powershell
.\avvia_dashboard.ps1
```
Il browser si aprirà automaticamente su `http://127.0.0.1:8095`.

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
