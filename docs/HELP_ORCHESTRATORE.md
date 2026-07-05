# Guida Rapida Operativa — Orchestratore LLM

Questa guida spiega come configurare, utilizzare e monitorare l'Orchestratore LLM sui tuoi progetti.

---

## 1. Avvio del Server Web (Dashboard Visiva)

Per l'uso quotidiano, lo script di avvio controlla se la dashboard è già attiva (non ne avvia una seconda copia) e apre il browser da solo:

```powershell
# Eseguire all'interno della cartella _ORCHESTRATORE_LLM
.\avvia_dashboard.ps1
```

In alternativa, avvio manuale diretto (utile per vedere i log in console mentre gira):

```powershell
python .\interfaccia.py
```

* Il server si avvierà all'indirizzo: **`http://127.0.0.1:8095`**
* Offre la visualizzazione dei grafici Chart.js su esecuzioni/rework e tempo LLM per agente, la timeline aggregata e il terminale per lanciare la sentinella.

**Bottone "⟲ Riavvia Sistema"**: uvicorn non ricarica mai il codice modificato su disco (nessun `--reload`), quindi dopo aver aggiornato `interfaccia.py`/`registro.py`/`sentinella.py` la dashboard resterebbe silenziosamente disallineata dal codice finché il processo non viene riavviato a mano. Questo bottone chiede conferma, avvia un nuovo processo (che ricarica tutto da disco) e termina quello vecchio non appena il nuovo ha preso la porta; la pagina si ricarica da sola quando il nuovo processo risponde. Da usare dopo ogni modifica al codice dell'orchestratore, invece di cercare e uccidere il processo manualmente.

---

## 2. Monitorare e Integrare un Progetto

Per iniziare a gestire un nuovo progetto (es. `mio_progetto`):
1. Apri la dashboard web all'indirizzo sopra indicato.
2. Compila il modulo **Integra e Monitora Nuovo Progetto**:
   - **Nome**: Nome identificativo (es. `Mio Progetto Backend`)
   - **Percorso Cartella**: Percorso assoluto su disco (es. `D:/Share/py/mio_progetto`)
3. Fai clic su **Esegui Integrazione**.

Il sistema eseguirà in automatico le seguenti operazioni nella cartella di destinazione:
- Creazione di `dati_locali/orchestrazione/`
- Copia degli schemi `schema/evento.v1.json` e `schema/compito.v1.json` come riferimento locale (solo documentazione: la validazione vera avviene sempre nell'orchestratore centrale)
- Copia delle configurazioni template `config/comandi.esempio.json` e `config/agenti.esempio.json`
- Aggiornamento del `.gitignore` del progetto target per escludere questi file dati/config gestiti dall'orchestratore

**Nota importante**: i progetti target contengono solo dati e configurazione, mai il codice dell'orchestratore. `registro.py` e `sentinella.py` **non vengono più copiati** nel progetto: restano un'unica installazione centrale in questa cartella, e la dashboard li invoca sempre da qui (passando `--config`/`--registro` del progetto target e impostando la cartella di lavoro su di esso). Un aggiornamento dell'orchestratore vale quindi subito per tutti i progetti integrati, senza bisogno di ri-registrarli.

---

## 3. Registrazione Manuale di un Evento (CLI)

Se un agente (o tu stesso) completa un lavoro su un progetto, puoi registrare l'evento nel registro locale del progetto:

```powershell
python .\registro.py aggiungi `
  --id-compito "task-102" `
  --agente "claude" `
  --tipo-compito "database" `
  --stato "da_rivedere" `
  --costo-stimato-usd 0.0150 `
  --latenza-ms 4500 `
  --regole-incluse "sicurezza,transazioni" `
  --note "Refactoring chiavi esterne tabelle"
```

* Il comando convalida l'evento rispetto a `schema/evento.v1.json` con `jsonschema`.
* Scrive in modalità append-only su `dati_locali/orchestrazione/eventi.jsonl`.

---

## 4. Esecuzione dei Gate in Sicurezza (Sentinella)

La sentinella esegue un comando di test o controllo e ne logga l'esito nel registro come agente `locale`.
I comandi eseguibili devono essere dichiarati nella whitelist in `config/comandi.esempio.json` (rinominabile in `comandi.json` per uso reale).

Esempio di comando whitelistato:
```json
"test_servizi": {
  "cartella": ".",
  "argomenti": [".venv/Scripts/python.exe", "-m", "pytest", "tests"],
  "timeout_secondi": 300,
  "limite_output_caratteri": 60000
}
```

Per lanciare la sentinella via CLI **sull'orchestratore stesso** (dalla cartella `_ORCHESTRATORE_LLM`):
```powershell
python .\sentinella.py test_servizi --id-compito "task-102"
```

Per far classificare anche l'output ripetitivo senza leggerlo a mano:
```powershell
python .\sentinella.py test_servizi --id-compito "task-102" --triage-locale
```

Con `--triage-locale` la sentinella registra due eventi sullo stesso `id_compito`:
il gate (`esito_gate=superato|fallito|timeout|errore_ambiente`) e il triage locale
(`routine|escalation`). Per output ovvi usa pattern deterministici; chiama il modello
locale solo per output non strutturati, warning ambigui o errori non riconoscibili.

Per lanciare un comando su un **altro progetto integrato**, la sentinella non è più presente nella sua cartella: si usa il Pannello Sentinella della dashboard (sezione 1), che internamente invoca sempre lo script centrale con `--config`/`--registro` puntati al progetto scelto. In alternativa, dalla cartella `_ORCHESTRATORE_LLM`:
```powershell
python .\sentinella.py test_servizi `
  --config "D:\percorso\mio_progetto\config\comandi.json" `
  --registro "D:\percorso\mio_progetto\dati_locali\orchestrazione\eventi.jsonl" `
  --triage-locale
```
(i comandi con `"cartella": "."` nel file `comandi.json` risolvono rispetto alla cwd del processo, non al percorso del progetto: lanciando così da `_ORCHESTRATORE_LLM` serve impostare `cd` sul progetto target prima, cosa che la dashboard fa già in automatico.)

* La sentinella lancia il comando in modo isolato (`shell=False`, directory confinata, timeout rigido).
* Tronca l'output se supera il limite caratteri per non intasare i log.
* Registra l'esito (`esito_gate`: `"superato"` o `"fallito"`) nel registro degli eventi.
* Il pannello Sentinella della dashboard usa automaticamente `--triage-locale`.

---

## 5. Come viene calcolato il Rework

Il tasso di rework di un agente **non è mai auto-dichiarato** per evitare valutazioni viziate. Viene dedotto deterministicamente dagli eventi successivi dello stesso `id_compito` tramite una macchina a stati:

1. Un agente (es. `gemini`) cambia lo stato del compito a `"da_rivedere"` o `"gate_in_corso"`.
2. Se l'evento successivo di quel compito ha:
   - `esito_gate` = `"fallito"` (segnalato da `sentinella.py` / agente `locale`), OPPURE
   - `verdetto_umano` = `"respinto"` (segnalato dall'operatore `umano`), OPPURE
   - `stato` = `"fallito"` o `"respinto"`.
3. Allora quell'agente (in questo caso `gemini`) subisce un incremento di **+1 Rework Totale**.

---

## 6. Lanciare un Compito Reale (Capoturno)

Il pannello **"🤝 Live Agent Handoff & Cooperazione"** della dashboard lancia `capoturno.py`: un motore che fa scrivere del codice reale a un agente (Gemini/Claude via LiteLLM), lo applica sul progetto target e lo valida con la sentinella, ripetendo in automatico se il gate fallisce.

Passi:
1. **Progetto Target**: scegli tra i progetti già integrati (sezione 2). Attenzione: se il compito riguarda *questa dashboard* (es. modificare `interfaccia.html`), il progetto giusto è "Orchestratore Centrale", non un altro progetto monitorato.
2. **Tipo Compito**: determina l'agente suggerito dal routing (es. `servizi` → Claude, `interfaccia` → Gemini). Nota: quando l'agente è `gemini`, il modello reale chiamato è `openai/gpt-4o-mini` (serve `OPENAI_API_KEY`, non una chiave Google) — è un'etichettatura da correggere, non ancora fatto.
3. **File Target**: percorso relativo al progetto dove scrivere il codice (es. `esempi/test_codice.py`). Se non esiste viene creato. Obbligatorio: il motore non sceglie da solo il file, gestisce un solo file per compito.
4. **Livello Rischio**: se scegli `alto`, il browser chiede una conferma esplicita in più prima di inviare la richiesta (riepilogo del compito). Non è ancora una sospensione lato server: chi lancia il compito dal form è già l'umano che approva.
5. **Descrizione Compito**: prompt in linguaggio naturale di cosa deve fare l'agente.
6. Clic su **"▶ Lancia Compito Reale"**: il diagramma SVG si anima seguendo i passaggi reali (chi sta lavorando, se sta fallendo un gate, se c'è stato un failover), e la console mostra i messaggi passo-passo.

A fine esecuzione, l'evento (`passato`, `fallito` o `errore_ambiente`) viene scritto nel registro **del progetto target**, mai in quello dell'orchestratore.

**Requisito**: serve `pip install litellm` e una chiave API valida per il provider usato (variabile d'ambiente, mai nel codice) **disponibile al processo della dashboard**: se hai impostato la chiave dopo aver avviato `interfaccia.py`, riavvialo (bottone "⟲ Riavvia Sistema") perché la erediti. Senza LiteLLM installato o senza crediti/chiave validi, il compito termina con `stato=errore_ambiente` — è il comportamento atteso, non un errore del framework: significa "manca l'infrastruttura per procedere", non "l'agente ha scritto codice sbagliato".

Specifica completa: `docs/ORCHESTRAZIONE_LAVORATORI.md` (sezione Capoturno).

---

## 7. Rivivere un Commit Reale (Replay Demo)

Nello stesso pannello "🤝 Live Agent Handoff & Cooperazione", il blocco "Rivivi un commit reale" mostra un selettore con gli ultimi commit del progetto selezionato (hash, data, autore, messaggio — letti da `git log`, non inventati).

Passi:
1. Scegli un commit dal menu a tendina: una card mostra hash breve, data, autore e messaggio del commit scelto.
2. Clic su **"🎬 Riproduci"**: la dashboard calcola la finestra temporale tra questo commit e il precedente, recupera gli eventi reali del registro caduti in quella finestra e li anima in sequenza sul diagramma SVG — con le linee che seguono la direzione cronologica reale tra gli agenti (verdi se l'esito è passato, rosse se fallito/da rivedere) e si chiudono verso il nodo "umano" a fine sequenza.
3. Al termine viene mostrata una stima onesta di risparmio: percentuale di controlli di verifica gestiti gratis dal modello locale sul totale (varia per commit, non è mai un numero fisso), e una stima in $ calcolata solo sui token realmente misurati negli eventi `agente=locale`, moltiplicati per il prezzo pubblico di un modello di riferimento dichiarato (GPT-4o-mini, tariffa input). Un commit senza eventi di verifica mostra correttamente "nessun controllo da cui stimare un risparmio", invece di forzare una percentuale a caso.

Utile per dimostrare (a te stesso o a terzi) cosa è successo davvero durante un commit, senza scenari finti o numeri inventati.

Specifica completa: `docs/ORCHESTRAZIONE_LAVORATORI.md` (sezione "Replay di un commit reale").

---

## 8. Bacheca Multi-Agente (messaggistica fra Claude/Codex/Gemini/locale/umano)

Oltre al registro (audit di cosa è stato fatto), c'è una bacheca separata per la
comunicazione asincrona fra agenti prima/durante il lavoro:
`dati_locali/orchestrazione/messaggi.jsonl`, gestita da `bacheca.py` (CLI) e da un
pannello dedicato nella dashboard.

**Da riga di comando**, i comandi più comuni:
```powershell
python bacheca.py chiedi --a codex --testo "Obiettivo: ... Contesto: ... Output atteso: ... Vincoli: ..."
python bacheca.py stato
python bacheca.py prossimo --agente claude
python bacheca.py approva --thread-id <id> --testo "Va bene, procedi."
```
Guida completa senza dettagli tecnici: `docs/GUIDA_SEMPLICE_BACHECA_MULTIAGENTE.md`.
Disegno tecnico completo: `docs/RFC_BACHECA_MULTIAGENTE.md`.

**Nella dashboard**, il pannello "🗂️ Bacheca Multi-Agente" (sopra la Timeline
eventi) mostra: tabella dei thread con stato e chi aspetta, banner se c'è un
conflitto segnalato, file attualmente in carico, cronologia al click su un thread.
Solo visualizzazione — approvare/chiudere/assegnare restano comandi CLI.

Due funzioni in più nel pannello:
- **Attività live**: box che si aggiorna da solo ogni 5s (solo i messaggi nuovi),
  va avviato con il pulsante "▶ Avvia" — non parte mai da solo.
- **▶ Rivivi**: riproduce animatamente la cronologia di un thread nel pannello
  "Live Agent Handoff" (stesso meccanismo del replay di un commit reale, §7 sopra).

**Hook automatici**: se configurati (`.claude/settings.json`, `.codex/hooks.json`),
Claude Code e Codex leggono da soli i messaggi in sospeso all'avvio di una sessione
o all'invio di un prompt — verificato che funziona davvero, non solo in teoria.
Gemini/Antigravity per ora resta manuale (`bacheca.py prossimo --agente gemini`).
