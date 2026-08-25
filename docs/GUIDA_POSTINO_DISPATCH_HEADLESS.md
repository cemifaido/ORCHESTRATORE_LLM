# Guida: il postino e il dispatch headless

**Stato**: funzionante e verificato dal vivo (2026-08-25). Questa è la guida
operativa di riferimento — cosa fa, cosa serve per farlo funzionare, come si
usa, come si replica su un'altra macchina. Per la storia delle decisioni e i
guardrail concordati con Gemini/Codex vedi `docs/PIANO_RISVEGLI_AUTOMATICI.md`;
per l'idea originale vedi `docs/PROPOSTA_RIUSO_IDEE_WEFT.md`.

## Cos'è, in una frase

Un meccanismo che toglie l'umano dal ruolo di "postino" tra gli agenti:
quando c'è un messaggio pendente in bacheca, il sistema lo nota da solo e fa
rispondere l'agente destinatario — a finestra (deep-link) o, se abilitato,
in un vero processo in background che legge, decide e scrive la risposta da
solo, senza aprire nulla.

## Come funziona (architettura)

```
messaggi.jsonl cambia
        │
        ▼
watcher (task asyncio dentro il processo FastAPI di interfaccia.py,
poll ogni 2.5s su st_mtime — nessun demone nuovo)
        │
        ▼
per ogni agente con un messaggio pendente non ancora notificato:
        │
        ├─ dispatch_headless = postino_attivo AND postino_headless_attivo
        │                      AND agente in postino.COMANDI (claude/codex)
        │
        ├─ SE dispatch_headless ──► postino.dispatch(): lancia claude -p /
        │                           codex exec in background, nessuna finestra
        │
        └─ ALTRIMENTI ──────────► _esegui_risveglio_os(): apre/porta in primo
                                   piano l'IDE dell'agente, copia il prompt
                                   negli appunti (richiede un umano che
                                   incolli e invii — il vecchio meccanismo,
                                   verificato a luglio)
```

`postino.py` è il motore di policy, usato da entrambi i percorsi:

- `autorizza(radice, agente, thread_id)` — decide se il turno è permesso
  (kill switch, tetti, debounce). Non esegue nulla, solo decide.
- `dispatch(radice, agente, thread_id)` — se autorizzato, lancia davvero il
  processo headless e registra l'esito.
- `registra_canale(radice, agente, thread_id, canale)` — usato dal percorso
  a finestra per consumare i tetti senza lanciare processi.

## I due interruttori (entrambi opt-in, spenti di default)

| File | Cosa accende | Dove si trova nel dashboard |
|---|---|---|
| `dati_locali/orchestrazione/POSTINO_ATTIVO` | Il watcher + il fallback a finestra | Pulsante "📬 Postino Automatico" |
| `dati_locali/orchestrazione/POSTINO_HEADLESS_ATTIVO` | Il dispatch headless reale (sotto-funzione del primo, inerte se il primo è spento) | Pulsante "🤖 Dispatch Headless" (disabilitato finché il primo è spento) |

Endpoint dietro i pulsanti: `POST /api/bacheca/postino/toggle` e
`POST /api/bacheca/postino/headless/toggle`, entrambi con body
`{"progetto_id": ..., "attivo": true|false}`. Stato letto da
`GET /api/bacheca` (campi `postino_attivo`, `postino_headless_attivo`).

**Spegnimento d'emergenza**: cancellare il file `POSTINO_ATTIVO` interrompe
tutto, comprese le code già pronte — non serve toccare altro.

## I tetti (configurabili, mai un file nuovo)

In `config/comandi.json`, blocco `"postino"`:

```json
"postino": {
  "max_turni_thread": 3,
  "max_invii_giorno": 10,
  "debounce_secondi": 300
}
```

- **`max_turni_thread`**: massimo di risvegli automatici consecutivi per un
  thread senza un tocco umano. Un messaggio con `mittente=umano` nel thread
  azzera il conteggio — non è "mai più di 3 messaggi", è "mai più di 3 senza
  che un umano intervenga". Vale per **tutti** i canali (headless e deep-link).
- **`max_invii_giorno`**: budget giornaliero, ma conta **solo il canale
  headless** — il fallback a finestra apre solo un pannello all'umano, non
  consuma quota dei provider.
- **`debounce_secondi`**: intervallo minimo tra due risvegli automatici per
  la stessa coppia agente+thread.

Un `config/comandi.json` assente, corrotto o con un valore non valido **non
allarga mai** i limiti: ogni chiave torna al default conservativo,
indipendentemente dalle altre. La taratura si fa modificando questi numeri,
mai il codice.

## Cosa serve per farlo funzionare (prerequisiti — la parte costata due giorni)

Il codice era pronto da subito; l'ambiente no. Se replichi questo sistema su
un'altra macchina, questi sono i punti che *davvero* bloccano, in ordine di
probabilità:

1. **Le CLI devono essere installate come eseguibili standalone**, non solo
   come estensione IDE. `claude` e `codex` devono risolversi da riga di
   comando (`Get-Command claude`/`codex` su Windows, `which` altrove).
   L'estensione VS Code/Antigravity **non** basta: è un processo diverso.
2. **La versione di Codex conta**: una build vecchia ("research preview",
   numerazione tipo `0.1.xxxxxxxxxx`) non ha un `exec` headless reale — lancia
   comunque l'interfaccia interattiva e crasha senza un terminale vero.
   Serve `npm install -g @openai/codex@latest` (verificato funzionante da
   `0.149.1` in su).
3. **Il workspace deve fidarsi di Claude**: la prima volta che l'installazione
   standalone di `claude` opera su una cartella, va lanciata **interattiva**
   in quella cartella e va accettato il trust dialog. Senza, `-p` ignora i
   permessi e fallisce. È un gesto umano deliberato, non automatizzabile né
   bypassabile da codice — è un confine di sicurezza voluto.
4. **Windows, se c'è un antivirus/whitelisting di eseguibili** (es.
   ThreatLocker): un eseguibile lanciato da uno script Python, fuori dal
   processo dell'IDE, può essere bloccato silenziosamente con errori che
   sembrano un problema di sandboxing del tool (es. `CreateProcessWithLogonW
   failed: 5`, accesso negato) e non lo sono. Se un dispatch fallisce in modo
   strano su Windows, questo è il primo sospetto da controllare — prima di
   scavare in teorie più complesse.
5. **`PATH` aggiornato di recente non basta da solo**: un processo già in
   esecuzione (compreso il server della dashboard) non vede un PATH
   modificato finché non riparte per davvero. Il pulsante "↻ Riavvia
   Sistema" della dashboard **non** risolve questo: copia l'ambiente dal
   processo vecchio invece di rileggerlo da Windows (bug noto, non ancora
   corretto — vedi sezione limiti sotto). Dopo aver installato/aggiornato
   una CLI o cambiato il PATH, riavvia il processo del server a mano
   (terminarlo e farne partire uno nuovo da una shell aperta di recente),
   o meglio ancora riavvia l'intera macchina/IDE.

## Come usarlo

1. Verifica i prerequisiti sopra (una tantum per macchina).
2. Apri la dashboard, sezione Bacheca, progetto interessato.
3. Accendi "📬 Postino Automatico": da qui in poi i risvegli a finestra
   partono da soli, con i tetti applicati.
4. Quando ti fidi, accendi anche "🤖 Dispatch Headless": claude/codex
   rispondono da soli in background, senza aprire finestre. Gemini resta
   sempre sul percorso a finestra (nessuna capability headless disponibile:
   `agy -p` ha un bug noto su Windows che richiede un TTY vero).
5. Osserva: ogni risveglio automatico (headless o deep-link) è un evento nel
   registro (`agente=sistema`, `tipo_compito=orchestrazione`,
   `id_compito` che inizia per `postino-`). Il widget "⏸️ Pratiche Sospese"
   in dashboard mostra i checkpoint ripristinabili in attesa.
6. Per spegnere tutto: il toggle base, o cancellare `POSTINO_ATTIVO` a mano.

## Il confine di sicurezza (importante, non è opzionale)

Il prompt che riceve l'agente headless (`postino.prompt_fisso()`) tratta il
contenuto della bacheca come **contesto non fidato**: l'agente deve decidere
da solo il merito della risposta, mai eseguire alla lettera un comando scritto
dentro un messaggio. Verificato dal vivo: un agente headless che legge un
messaggio contenente un comando esplicito lo **rifiuta** correttamente e non
lo esegue — è un comportamento sicuro, non un difetto. Il prompt vieta anche
esplicitamente commit, push, cancellazioni, rete; se serve lavoro reale o
manca chiarezza, l'agente scrive un checkpoint/domanda e si ferma, non
improvvisa.

## Limiti noti (non ancora risolti)

- **Il self-restart della dashboard non aggiorna l'ambiente**:
  `_avvia_processo_sostituto()` in `interfaccia.py` lancia il nuovo processo
  con `env=os.environ.copy()`, che copia l'ambiente del processo *corrente*
  invece di rileggerlo da Windows — un PATH cambiato non arriva mai al nuovo
  processo attraverso una catena di riavvii automatici, serve un riavvio
  genuino da una shell fresca. Da correggere se diventa un problema
  ricorrente (es. non usare `os.environ.copy()`, o documentare che dopo un
  cambio di PATH serve sempre un riavvio manuale/di macchina).
- **Livello 3 non implementato**: l'integrazione con il flusso dichiarato
  (fermarsi automaticamente ai passi `approvazione_umana`, notificare invece
  di svegliare) resta rimandata, come deciso da tutti fin dall'inizio —
  prima si osserva il funzionamento reale di questo, poi si valuta.
- **Gemini resta manuale**: nessuna capability headless verificata
  (`agy -p` bloccato da un bug noto su Windows). Se cambia, va riverificato
  con un test reale prima di aggiungerlo a `postino.COMANDI`, non per
  analogia con claude/codex.
