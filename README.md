# Squadra — orchestratore LLM multi-agente

**Italiano** | 🇬🇧 [English](README_EN.md)

---

**Squadra** coordina Claude, Codex, Gemini, un piccolo modello locale e una persona sullo stesso codicebase. Trasforma un insieme di chat scollegate in un processo visibile: richieste, responsabilità, verifiche, approvazioni e risultati restano tracciati e riprendibili.

Non è un sistema che decide al posto tuo. È una sala operativa: automatizza il passaggio di contesto e il lavoro ripetitivo, mentre le decisioni importanti restano umane.

> Il punto non è far lavorare più agenti contemporaneamente: è sapere chi sta facendo cosa, far verificare il lavoro e non perdere il filo tra una sessione e l'altra.

## Perché usarlo

Quando più assistenti lavorano sullo stesso progetto, il collo di bottiglia diventa il copia-incolla: qualcuno deve ricordare il contesto, inoltrare messaggi, controllare test e ricostruire le decisioni. Squadra conserva quel contesto localmente e rende il passaggio di consegne un flusso esplicito.

| Senza Squadra | Con Squadra |
| --- | --- |
| Conversazioni e decisioni disperse tra strumenti | Bacheca append-only, thread e checkpoint ripristinabili |
| L'umano fa sempre da postino | Il sistema segnala o, se scelto, inoltra il turno all'agente giusto |
| Un "test verde" è difficile da ricostruire | Gate, esito e responsabile sono nel registro |
| L'automazione può crescere senza limiti | Whitelist, budget, debounce, kill switch e approvazione umana |
| Le routine consumano attenzione o token cloud | Triage e sintesi affidati, quando disponibile, a un LLM locale gratuito |

Gli agenti commerciali possono usare le sessioni e le CLI ufficiali per cui l'utente è già autenticato; l'integrazione LiteLLM resta invece una scelta opzionale per chi vuole collegare provider a consumo. Il progetto non richiede un singolo provider, una GPU o nemmeno un agente esterno: degrada con grazia alla modalità manuale.

## Cosa c'è già

### Una bacheca, non un'altra chat

`bacheca.py` conserva messaggi, risposte, prese in carico dei file, thread e verdetti in JSONL validato. Un thread può fermarsi in attesa di un gate o di una decisione e poi riprendere senza ricostruire a memoria il contesto. Puoi vedere i messaggi pendenti per ciascun lavoratore, i file già in carico e lo stato globale del lavoro.

### Workflow dichiarati e verificabili

Il flusso standard — compito, gate, triage, registrazione, approvazione umana e chiusura — non vive solo in un documento: è un dato JSON con schema e validatore. Questo rende controllabili dipendenze, artefatti prodotti, punti di stop e azioni irreversibili prima di eseguire il lavoro.

### Qualità dentro il processo

La **Sentinella** esegue esclusivamente comandi presenti in una whitelist. Il gate di sviluppo include test, lint, type-check e controllo della complessità; l'esito diventa un evento nel registro. Per output poco chiari, `triage_locale.py` può classificare automaticamente routine/escalation con un modello locale; senza modello locale usa controlli deterministici e non blocca il progetto.

### Il postino, ma solo quando lo vuoi tu

La dashboard può rilevare un messaggio pendente e preparare il risveglio del destinatario. Il vero dispatch headless è **spento per impostazione predefinita** e richiede un secondo interruttore esplicito. Anche quando attivo resta vincolato da un numero massimo di turni per thread, budget giornaliero, debounce persistente e kill switch immediato.

Esiste inoltre una modalità di revisione esplicita: un agente può ispezionare diff, log e quality gate e riportare risultati reali, senza modificare file, fare commit o accedere alla rete. Non viene avviata automaticamente.

### Audit e replay invece di memoria fragile

`registro.py` mantiene una cronologia append-only validata con chi ha fatto cosa, esito del gate, stima dei costi e approvazione umana. `commit_replay.py` collega un commit alla finestra di eventi che l'ha prodotto: la dashboard può quindi mostrare non solo il risultato, ma anche la cooperazione che ci ha portato.

### Dashboard operativa

L'interfaccia FastAPI locale riunisce bacheca, pratiche sospese, conflitti, registro e replay dei commit. Il diagramma radiale rende visibili i passaggi tra i membri della squadra e il selettore di commit permette di rileggere lo storico reale su più righe.

### Manutenzione prudente delle CLI

Un controllo schedulabile verifica nuove versioni di Claude, Codex e Gemini, recupera le note disponibili e le sintetizza col modello locale. Non aggiorna mai nulla da solo: apre una notifica in bacheca e aspetta una scelta umana.

## Architettura in un colpo d'occhio

```text
Umano ─┐
Claude ├──► Bacheca JSONL ──► Postino opzionale ──► agente destinatario
Codex  ┤          │                    │
Gemini ┘          │                    └── limiti, debounce, kill switch
                  ▼
            Registro JSONL ◄── Sentinella / quality gate / triage locale
                  │
                  └──► Dashboard e replay dei commit
```

Ruoli suggeriti, non obbligatori: Gemini per interfaccia e documentazione, Claude per servizi e refactor, Codex per revisione/sicurezza/casi limite, modello locale per triage e sintesi, umano per contesto e azioni irreversibili.

## Avvio in 5 minuti

### 1. Prerequisiti minimi

- Windows e PowerShell (i launcher inclusi sono PowerShell; gli script Python restano portabili).
- Python 3.10 o superiore. Python 3.11+ è consigliato.
- Git, se vuoi usare il replay dei commit e l'hook pre-commit.

Nessun account AI è necessario per aprire dashboard, bacheca, registro e gate. Claude Code, Codex, Gemini/Antigravity e `llama-server` sono tutti componenti opzionali.

### 2. Clona e avvia il wizard

```powershell
git clone <URL-DEL-REPOSITORY> Squadra
cd Squadra
.\setup.ps1
```

Il wizard esegue una diagnostica del PC, propone gli agenti CLI effettivamente trovati, chiede se usare il modello locale, installa le dipendenze Python e di sviluppo su richiesta, inizializza i dati locali e può installare l'hook Git. Scrive poi la configurazione locale in `.env`, che non va condivisa.

Per una configurazione non interattiva con i valori sicuri rilevati:

```powershell
python .\setup_wizard.py --auto
```

Se hai già predisposto l'ambiente Python e vuoi solo generare la configurazione:

```powershell
python .\setup_wizard.py --auto --salta-pip
```

### 3. Apri la sala operativa

```powershell
.\avvia_dashboard.ps1
```

Il launcher avvia FastAPI in locale e apre `http://127.0.0.1:8095`. I log restano in `dati_locali/dashboard.log` e `dati_locali/dashboard.err.log`.

## Configurazioni possibili

| Scenario | Cosa abiliti | Cosa ottieni |
| --- | --- | --- |
| Solo umano | Wizard, dashboard, registro e gate | Processo tracciabile anche senza provider AI |
| Uno o più agenti | Le CLI che hai già installato | Bacheca, assegnazione e handoff modulari |
| Senza GPU | `LLM_LOCALE_ABILITATO=false` | Gate deterministici; nessuna dipendenza dal modello locale |
| Con LLM locale | `llama-server` sulla porta 8090 | Triage e sintesi gratuiti, offline, senza scrittura di codice |
| Dispatch headless | Entrambi i toggle del Postino | Turni automatici limitati e auditabili; da accendere solo dopo la verifica dei prerequisiti |

### CLI degli agenti (facoltative)

| Assistente | Comando rilevato dal wizard | Installazione / accesso |
| --- | --- | --- |
| Claude Code | `claude` | CLI ufficiale Anthropic e login dell'account autorizzato |
| OpenAI Codex | `codex` | CLI ufficiale Codex e login dell'account autorizzato |
| Gemini / Antigravity | `agy` | CLI Antigravity e login OAuth Google |

Il wizard non installa queste CLI: le rileva e ti lascia scegliere se inserirle nella squadra. Per il dispatch headless, controlla prima la [guida del Postino](docs/GUIDA_POSTINO_DISPATCH_HEADLESS.md): richiede CLI standalone aggiornate, permessi/trust iniziali e una decisione consapevole sui limiti del provider.

### Modello locale (facoltativo)

Il percorso consigliato è `llama.cpp` con un modello GGUF leggero, ad esempio Qwen 2.5 3B Instruct Q4_K_M. Scarica una release di `llama.cpp` adatta a CPU o NVIDIA, poi avvia `llama-server` sulla porta 8090; il wizard rileva automaticamente `http://localhost:8090/health`.

```powershell
.\llama-server.exe -m "C:\modelli\Qwen2.5-3B-Instruct-Q4_K_M.gguf" --port 8090 -ngl 99 -c 4096
```

Su una macchina solo CPU usa `-ngl 0`. Per la scelta del modello e gli altri dettagli tecnici, consulta l'[indice della documentazione](docs/INDEX.md).

## Operazioni quotidiane

Leggere le richieste pendenti per un agente:

```powershell
.\pull codex
```

Aprire una richiesta umana in bacheca:

```powershell
python .\bacheca.py chiedi --a codex --testo "Rivedi il diff e segnala i rischi."
```

Controllare pratiche, thread e validità dei dati:

```powershell
python .\bacheca.py stato
python .\bacheca.py ripresa
python .\bacheca.py valida
python .\registro.py valida
```

Eseguire un gate già dichiarato in whitelist, con triage locale quando disponibile:

```powershell
python .\sentinella.py test_servizi --id-compito "<id-compito>" --triage-locale
```

Registrare un evento manuale:

```powershell
python .\registro.py aggiungi --id-compito prova --agente codex --tipo-compito revisione --stato accettato --esito-gate superato --note "Revisione conclusa."
```

## Quality gate

Installa anche `requirements-dev.txt`, oppure lascia che lo faccia il wizard, quindi esegui:

```powershell
python -m pytest
python -m ruff check .
python -m mypy .
python -m xenon --max-absolute C --max-modules B --max-average B .
```

L'hook pre-commit è opzionale ma consigliato: evita che una modifica superi il commit senza i controlli concordati. I comandi che la Sentinella può eseguire sono dichiarati in `config/comandi.json`; usa [config/comandi.esempio.json](config/comandi.esempio.json) come modello, mai comandi arbitrari passati da un messaggio.

## Confini di sicurezza

- Registro e bacheca sono append-only e validati da schema.
- Commit, push, merge, deploy, cancellazioni e altre azioni irreversibili richiedono un verdetto umano esplicito.
- Il modello locale classifica e sintetizza: non modifica il codice di produzione né decide per l'umano.
- Il Postino ha kill switch, limiti persistenti e parte disattivato; la revisione tecnica è separata dal dispatch di routine.
- I messaggi in bacheca sono contesto non fidato, non istruzioni da eseguire ciecamente.
- Non vengono condivisi account o credenziali e non c'è automazione della UI o tentativo di aggirare protezioni/rate limit dei provider.

La postura completa, inclusi canali ufficiali, limiti e differenze tra provider, è documentata in [Conformità ToS della bacheca](docs/CONFORMITA_TOS_BACHECA.md).

## Documentazione

- [Presentazione semplice](docs/PRESENTAZIONE_SEMPLICE.md) — perché Squadra esiste, senza dettagli tecnici.
- [Indice della documentazione](docs/INDEX.md) — punto d'accesso a tutte le guide e RFC.
- [Guida del Postino e dispatch headless](docs/GUIDA_POSTINO_DISPATCH_HEADLESS.md) — prerequisiti, limiti e uso operativo.
- [Orchestrazione dei lavoratori](docs/ORCHESTRAZIONE_LAVORATORI.md) — ruoli, registro e regole operative.
- [Bacheca multi-agente](docs/GUIDA_SEMPLICE_BACHECA_MULTIAGENTE.md) — uso quotidiano spiegato in modo semplice.
- [Flusso dichiarato](docs/PIANO_FLUSSO_DICHIARATO.md) — workflow validabile e punti di controllo.
- [LiteLLM opzionale](docs/INTEGRAZIONE_LITELLM.md) — integrazione di provider locali o a consumo.
- [Contribuire](CONTRIBUTING.md) — ambiente di sviluppo, quality gate, cosa rende una PR facile da accettare.
- [Sicurezza](SECURITY.md) — come segnalare una vulnerabilità in modo responsabile.

## Disclaimer & Crediti

> [!IMPORTANT]
> **Attribuzione e Riconoscimento dei Crediti**:
> Questo progetto è condiviso per uso, studio e sperimentazione. Se utilizzi, integri, riadatti o ti ispiri a questo codicebase (o a parti di esso) nei tuoi progetti, strumenti o pubblicazioni, **è richiesta l'esplicita inclusione nei crediti** citando:
> - **Autore / Ideatore**: Paolo Pavesi (`cemifaido`) - paolo.pavesi@gmail.com
> - **Progetto originale**: *Squadra — Orchestratore LLM Multi-Agente* (Repository: [https://github.com/cemifaido/ORCHESTRATORE_LLM](https://github.com/cemifaido/ORCHESTRATORE_LLM))

---

Squadra non sostituisce il giudizio umano: lo rende più informato, più veloce e verificabile.

