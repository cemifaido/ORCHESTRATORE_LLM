# Guida Rapida Operativa — Orchestratore LLM

Questa guida spiega come configurare, utilizzare e monitorare l'Orchestratore LLM sui tuoi progetti.

---

## 1. Avvio del Server Web (Dashboard Visiva)

Per avviare la console grafica premium di controllo:

```powershell
# Eseguire all'interno della cartella _ORCHESTRATORE_LLM
.venv\Scripts\python.exe .\interfaccia.py
```

* Il server si avvierà all'indirizzo: **`http://127.0.0.1:8095`**
* Offre la visualizzazione dei grafici Chart.js dei costi e del tasso di rework per agente, la timeline aggregata e il terminale per lanciare la sentinella.

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

* Il comando convalida l'evento rispetto alle definizioni di `VALORI` ed ai tipi richiesti.
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

Per lanciare un comando su un **altro progetto integrato**, la sentinella non è più presente nella sua cartella: si usa il Pannello Sentinella della dashboard (sezione 1), che internamente invoca sempre lo script centrale con `--config`/`--registro` puntati al progetto scelto. In alternativa, dalla cartella `_ORCHESTRATORE_LLM`:
```powershell
python .\sentinella.py test_servizi `
  --config "D:\percorso\mio_progetto\config\comandi.json" `
  --registro "D:\percorso\mio_progetto\dati_locali\orchestrazione\eventi.jsonl"
```
(i comandi con `"cartella": "."` nel file `comandi.json` risolvono rispetto alla cwd del processo, non al percorso del progetto: lanciando così da `_ORCHESTRATORE_LLM` serve impostare `cd` sul progetto target prima, cosa che la dashboard fa già in automatico.)

* La sentinella lancia il comando in modo isolato (`shell=False`, directory confinata, timeout rigido).
* Tronca l'output se supera il limite caratteri per non intasare i log.
* Registra l'esito (`esito_gate`: `"superato"` o `"fallito"`) nel registro degli eventi.

---

## 5. Come viene calcolato il Rework

Il tasso di rework di un agente **non è mai auto-dichiarato** per evitare valutazioni viziate. Viene dedotto deterministicamente dagli eventi successivi dello stesso `id_compito` tramite una macchina a stati:

1. Un agente (es. `gemini`) cambia lo stato del compito a `"da_rivedere"` o `"gate_in_corso"`.
2. Se l'evento successivo di quel compito ha:
   - `esito_gate` = `"fallito"` (segnalato da `sentinella.py` / agente `locale`), OPPURE
   - `verdetto_umano` = `"respinto"` (segnalato dall'operatore `umano`), OPPURE
   - `stato` = `"fallito"` o `"respinto"`.
3. Allora quell'agente (in questo caso `gemini`) subisce un incremento di **+1 Rework Totale**.
