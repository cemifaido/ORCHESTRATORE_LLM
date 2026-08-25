# Orchestratore LLM

Struttura operativa riutilizzabile per coordinare agenti AI, un LLM locale economico e un operatore umano su qualunque base codice.

Il principio è semplice:

> il valore non è far parlare gli agenti; il valore è ridurre il contesto riletto ogni volta, instradare meglio, misurare costo/resa e svegliare il lavoratore giusto solo quando serve.

## Componenti

- `registro.py` — appende e valida (con `jsonschema`) eventi nel registro JSONL.
- `genera_cruscotto.py` — genera un cruscotto Markdown dal registro.
- `sentinella.py` — esegue solo comandi dichiarati in whitelist e registra l'esito.
- `capoturno.py` — motore di orchestrazione reale: instrada, chiama l'agente via LiteLLM, scrive la patch, valida con la sentinella e fa rework/failover automatico (vedi `docs/ORCHESTRAZIONE_LAVORATORI.md#capoturno`).
- `instrada.py` — suggerisce l'agente più adatto per un tipo di compito.
- `bacheca.py` — bacheca multi-agente: messaggistica strutturata fra Claude/Codex/Gemini/locale/umano senza API a pagamento (vedi `docs/RFC_BACHECA_MULTIAGENTE.md`).
- `postino.py` — dispatch headless automatico per i thread pendenti in bacheca: lancia davvero l'agente giusto in background (mai per azioni irreversibili, tetti anti-loop, spento di default) — vedi `docs/GUIDA_POSTINO_DISPATCH_HEADLESS.md`.
- `verifica_aggiornamenti_cli.py` — controllo periodico delle versioni di claude/codex/agy, riassunto delle note di rilascio col modello locale, notifica in bacheca; mai un aggiornamento senza verdetto umano.
- `schema/` — schemi versionati per eventi, compiti e messaggi della bacheca.
- `config/` — esempi di configurazione per agenti e comandi ammessi.
- `adattatori/` — integrazioni opzionali, importate solo quando servono.
- `utility/installa_hook.py` — installa un hook Git pre-commit che lancia il quality gate.
- `esempi/` — script eseguibili di riferimento (es. chiamata LiteLLM con fallback mock).
- `dati_locali/` — dati runtime ignorati da Git.

## Avvio rapido

Avviare la dashboard per l'uso quotidiano (non avvia una seconda copia se è già attiva, apre il browser):

```powershell
.\avvia_dashboard.ps1
```

Aggiungere un evento:

```powershell
python .\registro.py aggiungi --id-compito prova --agente codex --tipo-compito revisione --stato accettato --esito-gate superato --verdetto-umano approvato --note "prima prova"
```

Validare il registro:

```powershell
python .\registro.py valida
```

Generare il cruscotto:

```powershell
python .\genera_cruscotto.py
```

Eseguire un comando whitelistato:

```powershell
python .\sentinella.py stato_git
```

Eseguire un gate con guardia locale:

```powershell
python .\sentinella.py test_servizi --id-compito "<id-compito>" --triage-locale
```

La sentinella registra sempre l'evento del gate. Con `--triage-locale` aggiunge un
secondo evento `agente=locale` sullo stesso `id_compito`: per output ovvi usa pattern
deterministici, per output ambigui chiama il modello locale.

## Test

I test usano solo `unittest` della libreria standard:

```powershell
python -B -m unittest discover -s tests -v
```

Coprono validazione schema, rifiuto dei campi extra, rework derivato, sentinella whitelistata e adapter LiteLLM opzionale.

## Quality gate

Lint, type check e controllo complessità sono in `requirements-dev.txt` (non servono a runtime):

```powershell
pip install -r requirements-dev.txt
python -m ruff check .
python -m mypy .
python -m xenon --max-absolute C --max-modules B --max-average B .
```

Sono richiamabili anche come comandi whitelistati dalla sentinella: `controllo_lint`, `controllo_tipi`, `controllo_complessita` (vedi `config/comandi.json`).

## Regole non negoziabili

1. Il LLM locale non modifica codice di produzione.
2. Commit, push, merge e azioni irreversibili restano all'umano.
3. Il registro reale resta in `dati_locali/` e non si committa.
4. La sentinella esegue solo comandi dichiarati in `config/comandi.esempio.json`.
5. Il rework non è auto-dichiarato dall'agente: deriva da gate deterministici e verdetto umano.
6. Il capofila operativo resta l'umano: il modello locale fa solo guardia su output ripetitivi.

La mappa documentale è in `docs/INDEX.md`; la specifica operativa completa è in `docs/ORCHESTRAZIONE_LAVORATORI.md`.
La bacheca multi-agente senza API a pagamento (`bacheca.py`, implementata e testata, hook verificati per Claude Code e Codex) è documentata in `docs/RFC_BACHECA_MULTIAGENTE.md` (tecnico) e `docs/GUIDA_SEMPLICE_BACHECA_MULTIAGENTE.md` (senza dettagli tecnici). Il postino (`postino.py`, dispatch headless automatico anche per Gemini, verificato dal vivo) è documentato in `docs/GUIDA_POSTINO_DISPATCH_HEADLESS.md`.
