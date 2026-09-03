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
- Copia della configurazione template `config/comandi.esempio.json`
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

## 6. Rivivere un Commit Reale (Replay Demo)

Nello pannello **"🤝 Live Agent Handoff & Cooperazione"**, il blocco "Rivivi un commit reale" mostra un selettore con gli ultimi commit del progetto selezionato (hash, data, autore, messaggio — letti da `git log`, non inventati).

Passi:
1. Scegli un commit dal menu a tendina: una card mostra hash breve, data, autore e messaggio del commit scelto.
2. Clic su **"🎬 Riproduci"**: la dashboard calcola la finestra temporale tra questo commit e il precedente, recupera gli eventi reali del registro caduti in quella finestra e li anima in sequenza sul diagramma SVG — con le linee che seguono la direzione cronologica reale tra gli agenti (verdi se l'esito è passato, rosse se fallito/da rivedere) e si chiudono verso il nodo "umano" a fine sequenza.
3. Al termine viene mostrata una stima onesta di risparmio: percentuale di controlli di verifica gestiti gratis dal modello locale sul totale (varia per commit, non è mai un numero fisso), e una stima in $ calcolata solo sui token realmente misurati negli eventi `agente=locale`, moltiplicati per il prezzo pubblico di un modello di riferimento dichiarato (GPT-4o-mini, tariffa input). Un commit senza eventi di verifica mostra correttamente "nessun controllo da cui stimare un risparmio", invece di forzare una percentuale a caso.

Utile per dimostrare (a te stesso o a terzi) cosa è successo davvero durante un commit, senza scenari finti o numeri inventati.

Specifica completa: `docs/ORCHESTRAZIONE_LAVORATORI.md` (sezione "Replay di un commit reale").

---

## 7. Bacheca Multi-Agente (messaggistica fra Claude/Codex/Gemini/locale/umano)

Oltre al registro (audit di cosa è stato fatto), c'è una bacheca separata per la
comunicazione asincrona fra agenti prima/durante il lavoro:
`dati_locali/orchestrazione/messaggi.jsonl`, gestita da `bacheca.py` (CLI) e da un
pannello dedicato nella dashboard.

**Da riga di comando**, i comandi più comuni:
```powershell
python bacheca.py chiedi --a codex --testo "Obiettivo: ... Contesto: ... Output atteso: ... Vincoli: ..."
python bacheca.py stato
python bacheca.py thread <id>       # nota: l'ID del thread va indicato come argomento posizionale (senza --thread-id)
python bacheca.py prossimo --agente claude
python bacheca.py rispondi --correla-a <id> --mittente claude --testo "..."
python bacheca.py prendi --thread-id <id> --agente codex --correla-a <id-del-risveglio>
python bacheca.py approva --thread-id <id> --testo "Va bene, procedi."
```
Guida completa senza dettagli tecnici: `docs/GUIDA_SEMPLICE_BACHECA_MULTIAGENTE.md`.
Disegno tecnico completo: `docs/RFC_BACHECA_MULTIAGENTE.md`.

**Piano a corsie su un thread** (`docs/RFC_PIANO_STEP_POSSEDUTI.md`): quando più
agenti lavorano insieme, si dichiara chi tocca cosa con `write_set` disgiunti.
```powershell
python bacheca.py piano crea-passo --thread-id <id> --piano-id P --passo-id build --descrizione "..." --attore claude --write-set "src/x.py,tests/test_x.py"
python bacheca.py piano prendi-passo --thread-id <id> --passo-id build --attore claude
python bacheca.py piano offri-passo --thread-id <id> --passo-id build --attore claude --a codex
python bacheca.py piano mostra --thread-id <id>
```
Se chi crea il passo è anche chi lo lavora, `crea-passo --proprietario claude` lo
fa nascere già `in_corso` (crea + prende in un colpo), risparmiando il
`prendi-passo`.
Prima di un dispatch automatico il watcher blocca un passo che si sovrappone a
uno già in corso e apre una `segnalazione_conflitto` (avviso, non blocco per
l'umano).

**Nella dashboard**, il pannello "🗂️ Bacheca Multi-Agente" (sopra la Timeline
eventi) mostra: tabella dei thread con stato e chi aspetta, banner se c'è un
conflitto segnalato, file attualmente in carico, cronologia al click su un thread.
Solo visualizzazione — approvare/chiudere/assegnare restano comandi CLI.

Due funzioni in più nel pannello:
- **Attività live**: box che si aggiorna da solo ogni 5s (solo i messaggi nuovi),
  va avviato con il pulsante "▶ Avvia" — non parte mai da solo.
- **▶ Rivivi**: riproduce animatamente la cronologia di un thread nel pannello
  "Live Agent Handoff" (stesso meccanismo del replay di un commit reale, §6 sopra).

**Hook automatici**: se configurati (`.claude/settings.json`, `.codex/hooks.json`,
`.agents/hooks.json` per Antigravity), tutti e tre gli agenti ricevono i messaggi
in sospeso nel contesto all'avvio di una sessione o all'invio di un prompt —
verificato dal vivo. Quando l'hook include un messaggio nel contesto, lo stato di
consegna di quella coppia passa a `acquisito_da_hook` (vedi §9).

**Note di codice mirate**: su Claude Code un hook `PreToolUse`
(`note_codice.py hook --pre-tool-use`, matcher `Edit|Write|MultiEdit|NotebookEdit`)
inietta, *appena prima* di una modifica, le sole note ancorate a quel file —
non l'elenco intero. A inizio sessione resta il dump panoramico di tutte le note
(`bacheca.py prossimo --formato hook`). Una nota è sempre contesto, mai
istruzione; un errore dell'hook non blocca la modifica.

**Server MCP** (`docs/RFC_SERVER_MCP_LOCALE.md`): oltre agli hook (mono-direzionali),
`mcp_orchestratore.py` espone la bacheca come tool nativi. Con la config del
client (`config/mcp.esempio.json`), l'agente chiama `bacheca_pendenti`,
`bacheca_thread`, `piano_stato`, `note_codice_elenco` (lettura) e
`bacheca_rispondi`, `bacheca_prendi`, `piano_prendi_passo`, `piano_offri_passo`
(scrittura idempotente) senza sillabare comandi di shell. Non fa partire turni:
risponde a tool call dentro un turno già in corso.

---

## 8. Il postino: risvegli automatici, anche a sessione chiusa

Tutto il punto 7 sopra richiede comunque che tu apra una sessione perché l'hook
scatti. Il postino va oltre: quando c'è un messaggio pendente in bacheca, un
processo in background lancia davvero l'agente giusto (`claude -p`, `codex exec`),
che legge, decide e scrive la risposta da solo — nessun pannello da aprire.
Per Gemini il dispatch headless (`agy -p`) è **degradato su Windows**: il postino
ricade sul risveglio OS (focus finestra + prompt negli appunti).

Non ci sono più i due vecchi interruttori: c'è **un profilo operativo per
progetto**, dal menu della dashboard — `standard` (nessuna automazione, default),
`brainstorming` (risposta headless in bacheca, ritmo largo), `super`/`smodata`
(anche scrittura file, mai Git). Un thread non riceve più di
`MAX_HOP_HEADLESS_CONSECUTIVI` risvegli automatici consecutivi senza un tuo
intervento; un dispatch che fallisce non fa ritentare all'infinito (ricade sul
risveglio OS o rinuncia dopo pochi tentativi); un risveglio OS ha un cooldown.

Per design l'agente svegliato dal postino in `standard`/`brainstorming` può solo
leggere/rispondere in bacheca — mai commit, push, cancellazioni o rete. In
`super`/`smodata` può anche scrivere file (per Claude con perimetro `enforced`,
per Codex/Gemini `prompt_only`). Esiste una modalità **revisione** attivabile
solo su richiesta esplicita (mai dal watcher): allarga il perimetro a
diff/log/gate di sola lettura, mai a scrittura.

Guida operativa completa: `docs/GUIDA_POSTINO_DISPATCH_HEADLESS.md`.

---

## 9. Stati di consegna e identità dei processi

**Stati di consegna** (`docs/RFC_STATI_CONSEGNA_RISVEGLIO.md`): un risveglio non è
una consegna. Per ogni coppia `(agente, messaggio)` c'è una progressione —
`in_attesa` → `attenzione_richiamata` (il watcher ha agito) → `acquisito_da_hook`
(l'agente l'ha visto nel contesto) → `preso_in_carico` (ha risposto con
`correla_a` che punta al risveglio) — più il terminale `chiuso_senza_consegna`.
La dashboard mostra lo stato accanto a ogni destinatario in attesa.

```powershell
python consegne_risveglio.py elenco          # stato di ogni coppia nota
python consegne_risveglio.py reset --agente gemini --id-messaggio <id>
python consegne_risveglio.py rigenera-cache  # ricostruisce risvegli_notificati.json dal log
```

**Identità dei processi**: su Windows i PID si riciclano in fretta.
`dashboard_os.stato_processo` verifica la tupla PID + istante di creazione +
percorso dell'eseguibile e ritorna `vivo` / `morto` / `non_verificabile`
(fail-closed): un PID che combacia ma con un altro istante di creazione è un
processo diverso, trattato come morto.
