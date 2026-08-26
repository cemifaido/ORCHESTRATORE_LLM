# Orchestrazione dei lavoratori — agenti AI, LLM locale e umano

**Stato**: specifica operativa iniziale (2026-07-03). Documento vivo.

Vedi anche: [Indice](INDEX.md) · [Regole generali di programmazione](REGOLE_GENERALI_PROGRAMMAZIONE_DA_RISPETTARE_SEMPRE.MD) · [Integrazione LiteLLM](INTEGRAZIONE_LITELLM.md) · [RFC Bacheca multi-agente](RFC_BACHECA_MULTIAGENTE.md) (bozza, evoluzione proposta della sincronizzazione asincrona descritta qui sotto) · [Conformità ToS della bacheca](CONFORMITA_TOS_BACHECA.md).

## Scopo

Coordinare più agenti AI, un LLM locale economico e un operatore umano su una sola base codice, senza ripetere contesto inutile e senza far sovrapporre i lavoratori.

Il valore non è il protocollo. Il valore è:

- ridurre il contesto riletto dagli agenti forti;
- instradare il compito al lavoratore più adatto;
- misurare costo, latenza, esito e rework;
- mantenere gate deterministici e veto umano sulle azioni importanti.

## Lavoratori

| Lavoratore | Forza | Limite | Quando usarlo |
|---|---|---|---|
| Gemini | Interfaccia, esperienza utente, CSS, prototipi rapidi | Meno affidabile su logica profonda e dati | Interfaccia, bozze visuali, idee |
| Claude | Architettura, servizi, dati, refactor | Meno spinto sull'estetica | Servizi, database, correttezza |
| Codex | Revisione puntigliosa, sicurezza, bug sottili | Lento e costoso | Revisione finale, sicurezza, concorrenza |
| Locale | Triage, sintesi, routing, sentinella | Non deve programmare | Gate, monitoraggio, riepiloghi |
| Umano | Giudizio, contesto, veto | Collo di bottiglia deliberato | Commit, merge, scelte irreversibili |

## Confini

- Gemini: interfaccia, CSS, prototipi.
- Claude: architettura, servizi, database, refactor.
- Codex: revisione, sicurezza, casi limite.
- Locale: registro, sentinella, sintesi, instradamento.
- Umano: approvazione e veto.

Nessun lavoratore modifica il dominio di un altro senza motivo esplicito.

## LLM locale

Il capofila operativo resta l'umano. Il LLM locale è una guardia di triage e
monitoraggio, non programmatore e non decisore finale.

Può:

- classificare un compito;
- suggerire regole extra da includere;
- riassumere output lunghi;
- proporre un lavoratore;
- registrare eventi;
- leggere lo stato dei gate.

Non può:

- modificare codice di produzione;
- lanciare comandi fuori whitelist;
- decidere che una regola core non serve;
- approvare commit, push, merge o cancellazioni.

## Registro

Il registro è un file JSONL append-only:

`dati_locali/orchestrazione/eventi.jsonl`

Ogni riga è validata da `schema/evento.v1.json` con la libreria `jsonschema` (Draft 2020-12 reale: type union, `format: date-time`, enum, ecc. — non un sottoinsieme fatto a mano). I due errori più comuni (campi obbligatori mancanti, campi non previsti) restano in messaggi italiani; gli altri usano il testo di `jsonschema` prefissato dal campo.

Un registro presente ma illeggibile (JSON corrotto o evento non conforme allo schema) non viene mai presentato come "nessun evento": sia la dashboard (`interfaccia.py`) sia `genera_cruscotto.py` mostrano esplicitamente quale progetto ha il registro corrotto e perché, invece di azzerare silenziosamente le statistiche.

I dati runtime non si committano: possono contenere path, costi, output e informazioni operative.

## Compiti

I compiti runtime stanno in:

`dati_locali/orchestrazione/compiti/*.json`

Schema: `schema/compito.v1.json`.

Stati:

`nuovo → pianificato → approvato → in_corso → da_rivedere → gate_in_corso → passato/fallito → accettato/respinto`

Campi minimi:

- `id_compito`;
- `proprietario`;
- `lease_fino`;
- `commit_base`;
- `file_modificati`.

## Sentinella

La sentinella esegue solo comandi dichiarati in `config/comandi.json` (se presente, altrimenti ripiega su `comandi.esempio.json`).

Ogni comando ha:

- `cartella`;
- `argomenti`;
- `timeout_secondi`;
- `limite_output_caratteri`;
- `verifiche_connessione` (opzionale): array di URL o indirizzi (es. `["http://localhost:5173"]`) che devono essere raggiungibili via TCP prima di lanciare il test. Se offline, la Sentinella abortisce immediatamente l'avvio e registra `esito_gate` come `"errore_ambiente"`, evitando di calcolare un falso rework.

Non esiste esecuzione shell arbitraria.

Il quality gate minimo (lint, type check, complessità) è dichiarato come comandi whitelistati come gli altri: `controllo_lint` (ruff), `controllo_tipi` (mypy), `controllo_complessita` (xenon, soglie `--max-absolute C --max-modules B --max-average B`). Le dipendenze sono in `requirements-dev.txt`, separate da quelle di runtime.

La sentinella può anche registrare la classificazione dell'output ripetitivo:

```powershell
python .\sentinella.py test_servizi --id-compito "<id-compito>" --triage-locale
```

Con `--triage-locale` vengono scritti due eventi con lo stesso `id_compito`:

- evento gate: comando eseguito, codice, log salvato e hash dell'output;
- evento triage: `routine` o `escalation`, con `regole_incluse` pari a
  `triage_deterministico` se bastano pattern noti, oppure `triage_locale` se serve il
  modello locale.

Il pattern deterministico ha priorità su tutto per output noti (`OK`, codice 0 senza
segnali sospetti, `FAILED`/`ERROR` standard, timeout, errore ambiente). Il modello
locale viene chiamato solo per output ambigui o non strutturati. Se il modello locale
non è raggiungibile, il triage deve degradare a `escalation`, mai a falso successo.

### Hook Git Pre-commit
È possibile automatizzare l'esecuzione locale di Ruff, Mypy e Xenon prima di consentire un commit Git. Lo script di installazione si trova in [utility/installa_hook.py](file:///D:/Share/py/_ORCHESTRATORE_LLM/utility/installa_hook.py).

Per installarlo, esegui:
```powershell
python utility/installa_hook.py
```
Questo scriverà un file `.git/hooks/pre-commit` che bloccherà il commit se uno dei controlli fallisce, stampando i dettagli del fallimento in console.

## Routing

All'inizio il routing resta tabellare:

- `interfaccia` → Gemini;
- `servizi` / `database` → Claude;
- `revisione` / `sicurezza` → Codex;
- `monitoraggio` / `errore_test` → Locale;
- rischio alto → Umano prima.

Lo scoring automatico si aggiunge solo dopo aver raccolto dati veri.

## Sincronizzazione fra sessioni interattive (Claude/Gemini/Codex)

Claude Code, Gemini (antigravity-ide) e Codex lavorano su questo stesso progetto in
sessioni separate, senza conversazione condivisa in tempo reale. Sincronizzano in modo
asincrono attraverso il registro: ognuno legge le note degli eventi recenti all'inizio
di un compito e registra un evento (`--agente claude|gemini|codex`) alla fine. Istruzioni
dettagliate in `CLAUDE.md`, `GEMINI.md`, `AGENTS.md` (letti automaticamente dai
rispettivi strumenti — **verificato empiricamente** per Claude Code e Codex in
sessioni fresche reali; per antigravity-ide/Gemini resta da verificare, la prima
volta che apri una sessione controlla esplicitamente che l'abbia letto). Non è
sincronizzazione in tempo reale — è un changelog condiviso, lo stesso che vede
l'operatore umano nella dashboard.

Esiste anche un meccanismo più strutturato per la comunicazione fra agenti (non solo
changelog di audit, vera messaggistica con thread/destinatari/stato), con hook che
iniettano automaticamente il contesto rilevante all'avvio di una sessione — vedi
[RFC Bacheca multi-agente](RFC_BACHECA_MULTIAGENTE.md) e, in versione senza dettagli
tecnici, [Guida semplice alla bacheca multi-agente](GUIDA_SEMPLICE_BACHECA_MULTIAGENTE.md).

Un livello di automazione ulteriore, il **postino**, toglie anche il bisogno di
aprire una sessione perché l'hook scatti: quando c'è un messaggio pendente, un
processo in background lancia davvero l'agente giusto in headless (mai per
azioni irreversibili, sempre con tetti anti-loop e opt-in esplicito, spento di
default) — vedi [Guida: il postino e il dispatch headless](GUIDA_POSTINO_DISPATCH_HEADLESS.md).

Anche il modello locale (`triage_locale.py`) ora registra un evento (`--agente locale`,
`tipo_compito=monitoraggio`) per ogni classificazione: prima il suo lavoro spariva in
stdout, ora ha la stessa visibilità degli altri tre nella dashboard/registro.

Il registro non racconta solo cosa ha fatto un agente: quando l'operatore umano dà
un'approvazione esplicita e finale (tipicamente prima di un `git commit`, o comunque
prima di una decisione irreversibile), va registrato un evento separato
`--agente umano --verdetto-umano approvato --stato accettato`. Senza questo, il campo
`verdetto_umano` dello schema resterebbe sempre `non_revisionato`: il via libera
dell'umano è un fatto operativo quanto il lavoro dell'agente, non va perso. Non va fatto
per ogni messaggio (sarebbe rumore) — solo per un'approvazione concreta a un'azione con
effetto reale. Dettagli pratici (comando esatto) in `CLAUDE.md`/`GEMINI.md`/`AGENTS.md`.

**Chiuso (2026-08-25)**: il carattere accentato che appariva come `�` (es. "è" → `�`)
non era mai un token spezzato dal modello né un dato corrotto — verificato byte per
byte end-to-end (risposta HTTP di llama-server, testo estratto da litellm, scrittura e
rilettura su `messaggi.jsonl`: tutti UTF-8 corretto). La causa reale era `print()` su
un terminale Windows con codepage non-UTF-8 (`cp1252`), che sostituisce in silenzio i
caratteri non rappresentabili — un default della console di Windows, non un bug
dell'orchestratore né del modello. Fix: `sys.stdout.reconfigure(encoding="utf-8",
errors="replace")` a inizio dei `main()` di `triage_locale.py`/`sentinella.py`/
`bacheca.py`. Dettagli e riproduzione completa in
`docs/RFC_BACHECA_MULTIAGENTE.md` §6.4.

## Replay di un commit reale (demo)

Nello pannello **"🤝 Live Agent Handoff & Cooperazione"**, "Rivivi un commit reale" mostra un selettore di commit (`GET /api/commit/lista`, da `git log`, con hash/data/autore/messaggio) e un pulsante "🎬 Riproduci". Alla scelta, una card mostra i metadati del commit (hash breve, data, autore, messaggio) e `GET /api/commit/eventi?progetto_id=...&hash=...` (modulo `commit_replay.py`) calcola la finestra temporale del commit (tra il suo timestamp e quello del commit precedente, confrontati come date timezone-aware in UTC — non come stringhe, perché git usa il fuso locale e il registro usa sempre `Z`) e ritorna gli eventi del registro caduti in quella finestra. La dashboard li anima in sequenza sullo stesso diagramma SVG — inferendo la direzione linea-per-linea dall'ordine cronologico degli eventi (verde se passato, rossa se fallito/da rivedere) e chiudendo il ciclo verso il nodo "umano" a fine sequenza — poi mostra una statistica reale, non uno scenario finto:

- **percentuale di controlli di verifica gestiti gratis dal modello locale** sul totale (locale + eventuali revisioni/sicurezza fatte da un agente a pagamento nella stessa finestra) — varia per commit, non è mai fissa al 100%;
- **stima in $ del risparmio**, calcolata solo sui `token_totali` realmente misurati (metadati degli eventi `agente=locale`) moltiplicati per il prezzo pubblico di un modello di riferimento dichiarato (GPT-4o-mini, tariffa input, scelta conservativa) — mai un numero inventato.

Un commit senza eventi di verifica (es. solo lavoro conversazionale, costo sempre stimato/0) mostra correttamente "nessun controllo da cui stimare un risparmio": non si forza una percentuale quando non c'è nulla di comparabile.

## Metriche

Il cruscotto misura:

- costo stimato o misurato;
- latenza;
- esito gate;
- verdetto umano;
- rework;
- tipo compito;
- lavoratore.

Il rework non è dichiarato dall'agente. Si deduce da gate falliti, respingimenti umani o correzioni successive.

## LiteLLM opzionale

LiteLLM può essere usato come gateway per chiamate LLM e misurazione costo/token.
Resta un adapter: non sostituisce registro, gate, sentinella o verdetto umano.

Per un esempio pratico e funzionante di chiamata ed arricchimento dell'evento del registro con i costi reali misurati in USD, vedi lo script di esempio [esempi/chiamata_agente_litellm.py](file:///D:/Share/py/_ORCHESTRATORE_LLM/esempi/chiamata_agente_litellm.py).

Regola pratica:

- costo non disponibile -> `origine_costo=stimato`;
- costo restituito da LiteLLM -> `origine_costo=misurato`;
- dettagli tecnici -> `metadati.litellm`.

Specifica: `docs/INTEGRAZIONE_LITELLM.md`.

## Anti-pattern

- Cinque passaggi tra agenti per una modifica banale.
- Far programmare il LLM locale.
- Partire da A2A prima di avere registro e gate.
- Pilotare UI proprietarie o usare abbonamenti flat come API non ufficiali (vedi
  [Conformità ToS della bacheca](CONFORMITA_TOS_BACHECA.md)).
- Usare token rimasti come criterio principale di routing.
- Committare il registro runtime.

## Multi-Progetto

L'orchestratore centrale supporta l'aggregazione di più progetti contemporaneamente. L'elenco dei progetti monitorati viene memorizzato in `dati_locali/progetti.json`:

```json
{
  "progetti": [
    {
      "id": "orchestratore",
      "nome": "Orchestratore Centrale",
      "percorso": "D:\\Share\\py\\_ORCHESTRATORE_LLM"
    },
    {
      "id": "anita",
      "nome": "Progetto Esempio",
      "percorso": "D:\\Share\\py\\altro progetto\\0.6_app"
    }
  ]
}
```

Ogni progetto mantiene il proprio file `eventi.jsonl` isolato in `dati_locali/orchestrazione/eventi.jsonl` all'interno della cartella del proprio percorso. Il modulo `genera_cruscotto.py` ed il server web aggregano le letture di tutti i file di log rilevati.

## Integrazione Automatica

**I progetti target contengono solo dati e configurazione, mai codice dell'orchestratore.** `registro.py` e `sentinella.py` restano un'unica copia centrale in questa cartella; la dashboard li invoca sempre da qui, passando `--config`/`--registro` del progetto target e impostando `cwd` sul progetto target (cosi' `"cartella": "."` nei comandi risolve nel posto giusto). Un aggiornamento dell'orchestratore vale quindi per tutti i progetti integrati, senza dover ri-registrare nulla e senza il rischio di copie disallineate.

Quando un progetto viene registrato tramite l'interfaccia, l'integrazione esegue:
1. Creazione delle cartelle di runtime `dati_locali/orchestrazione/` nel percorso di destinazione.
2. Copia degli schemi `schema/evento.v1.json` e `schema/compito.v1.json` come riferimento locale (documentazione): la validazione vera avviene sempre nell'orchestratore centrale con il proprio schema, non con questa copia.
3. Copia dei file di configurazione di esempio `config/comandi.esempio.json` e `config/agenti.esempio.json` se non già presenti.
4. Aggiornamento automatico del file `.gitignore` del progetto target per escludere i file dati/config gestiti dall'orchestratore, prevenendo commit indesiderati nei repository dei singoli progetti.

Nei progetti integrati prima di questo cambiamento possono restare copie storiche di `registro.py`/`sentinella.py`/`genera_cruscotto.py`/`requirements-orchestratore.txt`: non vengono più usate dalla dashboard (che chiama sempre lo script centrale) e possono essere cancellate manualmente quando comodo, non serve un'azione immediata.

## Interfaccia Web (Dashboard)

Avvio quotidiano consigliato: `.\avvia_dashboard.ps1` (non avvia una seconda copia se la dashboard è già attiva sulla porta, poi apre il browser).

**Struttura dei file** (dal 2026-08-25, revisione di sicurezza — `interfaccia.html`
era un monolite di ~3391 righe, L5 del rilievo): `interfaccia.html` resta solo lo
scheletro HTML; CSS e JS vivono in `static/interfaccia.css` e `static/interfaccia.js`,
serviti da FastAPI via `app.mount("/static", ...)`. Estrazione pura (nessuna riga
di logica modificata), verificata con la suite di test, `node --check` sul JS e un
avvio reale della dashboard. Se modifichi lo stile o il comportamento della
dashboard, i file da toccare sono questi due, non più `interfaccia.html`.

**Autenticazione su bind non-loopback** (stesso giorno, C1 del rilievo): per
default (`ORCHESTRATORE_HOST=127.0.0.1`) nessun cambiamento, nessuna chiave
richiesta. Se `ORCHESTRATORE_HOST` viene impostato a un indirizzo non-loopback,
il processo si rifiuta di avviarsi finché non è impostata anche
`ORCHESTRATORE_API_KEY`: con la chiave impostata, ogni richiesta deve presentare
l'header `X-Orchestratore-Key` con lo stesso valore.

**Uso dichiarato: solo rete aziendale con accesso diretto, niente accesso remoto**
(decisione umana, revisione sicurezza v3/NEW-1, 2026-08-26): l'header
`X-Orchestratore-Key` non è utilizzabile da un browser normale (non può impostare
header custom sulla richiesta iniziale), quindi non è una soluzione di login per
accesso via browser — resta valido solo per client/API. Piuttosto che costruire
subito una sessione/cookie di login nell'app, la decisione presa è: il bind resta
`127.0.0.1` (loopback) come default e unico scenario supportato oggi, l'uso è
sempre locale sulla stessa macchina o su rete aziendale fidata con accesso diretto
alla porta. **Accesso remoto non è nei piani immediati**: se in futuro servisse
davvero, la direzione concordata (Codex/Gemini/Claude, bacheca thread `4b5d75f5`)
è un reverse proxy dedicato con TLS e autenticazione browser-compatibile davanti
alla dashboard, non una login implementata dentro `interfaccia.py` — punto lasciato
esplicitamente in backlog, non implementato.

**CSRF residuo su bind loopback** (M8 del rilievo, revisione sicurezza v3): con
`ORCHESTRATORE_HOST=127.0.0.1` (default) nessuna richiesta all'API porta o
richiede l'header `X-Orchestratore-Key`, quindi una pagina web malevola aperta
nello stesso browser sulla stessa macchina potrebbe far partire richieste verso
`http://127.0.0.1:8095/...` senza che l'utente se ne accorga (CSRF classico:
l'origine della richiesta non viene verificata). Rischio accettato oggi,
coerente con l'uso dichiarato (rete aziendale con accesso diretto, singolo
utente fidato per macchina, non un servizio multi-utente esposto): se in
futuro la macchina diventasse condivisa fra più persone, la mitigazione
minima è un token locale per-sessione verificato lato server (non solo
l'header statico attuale, pensato per client/API, non per isolare utenti
della stessa macchina) — non implementato, stesso backlog di NEW-1.

Il server `interfaccia.py` (FastAPI/Uvicorn, porta `8095`) offre un'interfaccia di monitoraggio visiva ad alto impatto grafico (dark theme, glassmorphic layout) basata su:
- **Grafici Chart.js**: Visualizzazione di esecuzioni/rework e ripartizione del tempo LLM cumulato per ogni lavoratore.
- **Selettore Progetti**: Form per inserire il percorso assoluto e nome di una nuova cartella per effettuarne l'integrazione ed il monitoraggio automatico.
- **Pannello Sentinella**: Console web interattiva per lanciare comandi deterministici whitelistati (es. pytest, git status) su un determinato progetto in un subprocesso isolato, visualizzandone il log di ritorno.
- **Live Agent Handoff & Cooperazione**: pannello per riprodurre in modalità replay un commit reale (vedi [Replay di un commit reale](#replay-di-un-commit-reale-demo)) oppure un thread della bacheca multi-agente (pulsante "▶ Rivivi" nel pannello Bacheca), con diagramma SVG animato e console che mostrano la sequenza temporale degli eventi.
- **Bacheca Multi-Agente** (vedi [RFC Bacheca multi-agente](RFC_BACHECA_MULTIAGENTE.md)): pannello di sola visualizzazione per `dati_locali/orchestrazione/messaggi.jsonl` — tabella thread con stato/chi aspetta/verdetto umano, banner per i conflitti segnalati, file attualmente in carico, drill-down della cronologia al click. Include un feed live opzionale (pulsante Avvia/Ferma, poll ogni 5s solo dei messaggi nuovi) e il replay animato descritto sopra. Nessuna azione da qui (approvare/chiudere/assegnare restano CLI, `bacheca.py`).
- **Riavvio Sistema**: `POST /api/sistema/riavvia` avvia un nuovo processo `interfaccia.py` (che ricarica il codice corrente da disco) e termina quello in esecuzione non appena il nuovo ha preso la porta (`__main__` ritenta il bind per ~10s in caso di sovrapposizione). Necessario perché uvicorn non ricarica mai i moduli modificati: senza riavvio, la dashboard resta silenziosamente disallineata dal codice sorgente.
- **Tempo Elaborazione LLM Cumulato**: la dashboard usa `latenza_ms` aggregata per mostrare il tempo di elaborazione per agente/progetto. I costi restano nel registro e nelle API per audit/LiteLLM, ma non sono più una tile primaria della dashboard.
