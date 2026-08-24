# Conformita ToS della bacheca multi-agente

**Stato**: nota operativa di progetto, non consulenza legale. Ultimo controllo fonti:
2026-07-05.

Questa nota spiega perche la bacheca multi-agente proposta in
[RFC_BACHECA_MULTIAGENTE.md](RFC_BACHECA_MULTIAGENTE.md) e progettata in modo
conservativo rispetto ai termini di servizio dei provider usati tramite abbonamenti
flat/IDE plugin: OpenAI/Codex, Anthropic/Claude Code e Google Gemini/Antigravity.

## Sintesi

Il disegno regge solo se resta dentro questi confini:

- l'umano apre e usa le sessioni degli strumenti in modo interattivo;
- la bacheca locale conserva contesto operativo, non pilota le UI proprietarie;
- gli hook ufficiali servono solo a leggere/iniettare contesto locale quando una
  sessione e gia avviata dall'utente;
- il sistema non estrae output in massa, non fa scraping, non aggira rate limit e non
  usa gli output per addestrare o migliorare modelli concorrenti;
- l'accesso resta personale/autorizzato: niente condivisione credenziali, niente
  rivendita del servizio a terzi, niente trasformazione dell'abbonamento flat in API
  mascherata.

La formula prudente e:

```text
bacheca locale + hook ufficiali + sessioni avviate dall'umano
+ niente automazione UI + niente harvesting di output + niente training/resale
```

## Perche questo disegno e piu sicuro

La bacheca non invia prompt ai provider da sola. Scrive e legge file locali
(`messaggi.jsonl`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) e lascia che ogni agente li
legga nella propria sessione autorizzata. Questo mantiene il sistema nel modello
"umano assistito da strumenti" invece che nel modello "bot non presidiato che consuma
un abbonamento flat".

Gli hook, dove supportati ufficialmente, sono accettabili solo come mezzo per
aggiungere contesto locale a una sessione che l'utente ha gia aperto o a un prompt che
l'utente ha gia inviato. Non devono diventare un ciclo automatico che apre sessioni,
manda prompt e raccoglie output senza intervento umano.

## Cosa e consentito nel progetto

- Usare Claude Code, Codex CLI e Gemini/Antigravity nelle rispettive interfacce
  previste dal provider.
- Far leggere agli agenti file locali del progetto.
- Usare `bacheca.py prossimo --agente X --formato hook` per preparare un riassunto
  compatto dei messaggi destinati a quell'agente.
- Usare hook ufficiali come `SessionStart`/`UserPromptSubmit`/`BeforeAgent`, se
  documentati e verificati, per iniettare quel contesto.
- Registrare risposte e decisioni operative in file locali append-only.
- Mantenere l'umano come gate per commit, push, cancellazioni, merge e decisioni
  architetturali importanti.

## Cosa non fare

- Non simulare tasti, click o input in UI proprietarie con script, `expect`, macro,
  RPA o keystroke injection. **Nota di chiarimento (2026-07-08)**: invocare un
  protocollo URI registrato ufficialmente dal sistema operativo per l'applicazione
  (es. `antigravity-ide://`, stesso meccanismo di `vscode://`) non rientra in questa
  categoria — è l'equivalente programmatico di un doppio click su un link, non
  simulazione di input. Il confine resta netto: aprire/focalizzare una vista e
  precompilarne un campo tramite un'API di deep-link ufficiale è ammesso; simulare
  la pressione di un tasto (incluso un "invio" per far partire l'azione) resta
  vietato, va sempre lasciato a un gesto umano o dell'agente stesso. Vedi la sezione
  "Capability verificate per provider" più sotto per il dettaglio.
- Non avviare sessioni automatiche in loop per "spremere" gli abbonamenti flat.
- Non usare le app flat come API non ufficiali.
- Non fare scraping o raccolta massiva di output.
- Non bypassare rate limit, conferme umane, sandbox, permessi o protezioni del
  provider.
- Non condividere account, token o credenziali fra persone, agenti o processi.
- Non usare output di Claude/Codex/Gemini per addestrare, distillare, valutare
  sistematicamente o migliorare modelli concorrenti.
- Non rivendere il sistema come servizio che fornisce accesso indiretto ai provider.
- Non presentare output AI come generato da un umano.

## Lettura per provider

### OpenAI / Codex

I termini OpenAI vietano la condivisione dell'account, il reverse engineering,
l'estrazione automatica o programmatica di dati/output, l'aggiramento di limiti o
protezioni e l'uso degli output per sviluppare modelli concorrenti.

Implicazione per il progetto:

- va bene usare Codex nella sessione autorizzata dell'utente;
- va bene aggiungere contesto locale con meccanismi ufficiali;
- non va bene automatizzare Codex come se fosse un endpoint API nascosto;
- non va bene raccogliere output in massa o usarli per training/distillazione.

Fonte: [OpenAI Terms of Use](https://openai.com/policies/terms-of-use/).

### Anthropic / Claude Code

I termini consumer Anthropic vietano condivisione credenziali, scraping/harvesting,
reverse engineering, uso per sviluppare servizi concorrenti o modelli ML, rivendita
del servizio e accesso automatizzato/non umano salvo API o permesso esplicito. I
termini commerciali ribadiscono il divieto di usare i servizi per prodotti concorrenti,
training di modelli concorrenti, rivendita, reverse engineering o duplicazione.

Implicazione per il progetto:

- Claude Code va usato come strumento interattivo ufficiale;
- la bacheca puo preparare contesto locale;
- gli hook non devono trasformarsi in accesso non umano continuativo;
- il progetto non deve diventare un broker o rivenditore di capacita Claude.

Fonti:
[Anthropic Consumer Terms](https://www.anthropic.com/legal/consumer-terms),
[Anthropic Commercial Terms](https://www.anthropic.com/legal/commercial-terms).

### Google / Gemini / Antigravity

I termini Google vietano abuso, bypass di sistemi/protezioni, reverse engineering,
uso automatizzato in violazione delle istruzioni macchina dei servizi e uso di
contenuti generati dai servizi per sviluppare modelli o tecnologia AI/ML correlata.
I termini aggiuntivi per servizi generativi vietano lo sviluppo di modelli ML o
tecnologia correlata tramite i servizi. I termini Gemini API aggiungono attenzione
specifica ai dati immessi nei servizi non pagati: non vanno inviati dati sensibili,
confidenziali o personali.

Implicazione per il progetto:

- Antigravity/Gemini va verificato prima con un hook innocuo a stringa fissa;
- se l'IDE non supporta hook locali, si resta al fallback manuale via `GEMINI.md`;
- non si devono bypassare conferme umane o protezioni dell'IDE;
- non si devono inviare segreti o dati sensibili a servizi non pagati/non protetti;
- l'uso di Antigravity CLI (`agy`) in modalità headless/non interattiva da processi di background dell'IDE su Windows è escluso per via di un bug del binario in assenza di TTY (causa blocco indefinito); per l'automazione di background si ricorre a chiamate API dirette (via `litellm`), mentre l'uso di `agy` è riservato all'interazione dell'utente all'interno di un terminale reale.

Fonti:
[Google Terms of Service](https://policies.google.com/terms),
[Google Generative AI Additional Terms](https://policies.google.com/terms/generative-ai),
[Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms).

## Regole operative per l'implementazione

1. La bacheca e locale: `bacheca.py` legge/scrive file nel progetto, non chiama le UI
   dei provider.
2. Gli hook devono essere dichiarativi, piccoli e verificabili: producono contesto,
   non iniziano conversazioni autonome.
3. Ogni sessione provider deve essere avviata dall'utente o da un meccanismo ufficiale
   esplicitamente previsto dal provider.
4. Il modello locale puo sintetizzare, classificare e segnalare conflitti, ma non
   decide azioni irreversibili.
5. Ogni azione irreversibile resta soggetta ad approvazione umana esplicita.
6. I log non devono contenere segreti, token, credenziali o dati confidenziali non
   necessari.
7. Se un provider cambia termini o restringe gli hook/agent mode, il progetto degrada
   al fallback manuale invece di aggirare la restrizione.

## Area grigia da evitare

Il rischio contrattuale cresce quando il sistema diventa indistinguibile da una API
non ufficiale:

- un processo apre sessioni automaticamente;
- invia prompt senza intervento umano;
- raccoglie output in serie;
- ripete il ciclo per ore;
- usa un abbonamento flat per lavoro non presidiato o per terzi.

Questa non e la forma della bacheca proposta. La bacheca deve restare un meccanismo
di coordinamento asincrono per sessioni interattive gia legittime, non un sostituto
dei piani API.

## Decisione architetturale

Per mantenere il progetto difendibile:

- niente automazione diretta di UI proprietarie;
- niente push verso agenti chiusi o dormienti;
- pull via hook ufficiali quando disponibili;
- fallback manuale quando un provider non espone hook o li blocca;
- audit locale append-only per ricostruire chi ha chiesto cosa, chi ha risposto e
  quando e intervenuto l'umano.

Questa scelta riduce l'automazione massima possibile, ma abbassa il rischio di
violazione dei ToS e rende chiaro che l'obiettivo non e aggirare le API a consumo:
l'obiettivo e ridurre il copia-incolla umano fra strumenti usati legittimamente.

## Eccezione verificata e autorizzata (2026-07-08): risveglio via URI per Claude/Codex

La regola "niente push verso agenti chiusi o dormienti" sopra non è più assoluta per
Claude e Codex: la dashboard (`interfaccia.py`, `POST /api/bacheca/risvegli`) apre
in automatico, senza click umano, un pannello dell'agente giusto — anche se era
chiuso — e vi precompila il prompt generato dal modello locale, tramite il
protocollo URI registrato dall'IDE (vedi chiarimento sopra: non è simulazione di
input). **Non invia mai da solo**: il "send" resta sempre un gesto esplicito
successivo, umano o dell'agente.

Questa non è una deroga silenziosa: è una decisione esplicita presa dall'utente del
progetto il 2026-07-08, a fatti tecnici completi sul tavolo — inclusa l'asimmetria
con VS Code (che per lo stesso meccanismo chiede conferma per estensione la prima
volta, mentre Antigravity non lo fa affatto) e il precedente dello stesso giorno in
cui un meccanismo simile era stato costruito, testato e smontato con esito negativo
(`docs/ESPERIMENTO_SVEGLIA_POLLING.md`). Motivazione per cui resta dentro i confini
di questo documento: il vincolo che conta di più — mai un'azione irreversibile senza
gesto umano — resta intatto, perché "apri pannello e scrivi nel composer" non è
un'azione irreversibile, l'invio sì. Dettaglio tecnico completo in
`docs/RFC_BACHECA_MULTIAGENTE.md` §4.4.

## Capability verificate per provider (2026-07-08)

Modello proposto da Codex, popolato con verifiche reali (non descrizioni) fatte lo
stesso giorno. Tre livelli: `official_headless` (CLI standalone documentata, provata
funzionante con un test reale), `official_hook_pull` (hook/URI ufficiale, verificato
con log o osservazione reale), `manual_only` (nessuna prova, resta il fallback
manuale — mai colmato per analogia con un altro provider).

| Provider | Risveglio via URI (apre pannello + precompila, non invia) | CLI headless |
|---|---|---|
| Claude | `official_hook_pull` — verificato, affidabile | `official_headless` — verificato (`claude -p`), pulito |
| Codex | `official_hook_pull` — verificato, solo se il pannello non è già aperto | `official_headless` (a consumo) — richiede `OPENAI_API_KEY` e crediti a pagamento OpenAI API Platform (non coperto dall'abbonamento flat dell'IDE) |
| Gemini/Antigravity | `manual_only` — nessun path noto verso cui indirizzare l'URI | `manual_only` — `agy -p` esiste ed è documentato, ma un bug reale lo blocca senza un TTY interattivo vero: non usabile da script/subprocessi su Windows |

Per Gemini, finché non emerge una prova diversa, restano validi il pull manuale
(§4.3 della RFC) e, per compiti automatici in background, le chiamate dirette via
`litellm`/`capoturno.py` invece di `agy` — indicazione di Gemini stesso. 

Per Codex, si conferma che la CLI headless non condivide la quota dell'abbonamento flat dell'IDE ma attinge a crediti a consumo (OpenAI API Platform): per l'automazione a costo zero in background è necessario ricadere sul canale interattivo/hook/pull (§4.3 della RFC).

## Aggiornamento 2026-08-24: automazione headless con canali ufficiali documentati

**Decisione dell'umano** (esplicita, in sessione con Claude, per il piano
`docs/PIANO_RISVEGLI_AUTOMATICI.md`): usare le modalità headless ufficiali dei
provider per il dispatcher automatico ("postino"), ora che i provider stessi le
documentano per questo preciso uso. Verifica alle fonti fatta lo stesso giorno:

- **Claude Code**: la pagina ufficiale "Run Claude Code programmatically"
  (code.claude.com/docs/en/headless, raggiunta via redirect da
  docs.claude.com) documenta `claude -p` come Agent SDK via CLI "for scripts
  and CI/CD", inclusi esempi di pipeline e job schedulati; l'uso col login ad
  abbonamento è la modalità di default documentata, `--bare` + `ANTHROPIC_API_KEY`
  è la variante raccomandata (non obbligatoria) per la CI riproducibile.
- **Codex**: la documentazione ufficiale della modalità non interattiva
  (developers.openai.com/codex → learn.chatgpt.com/docs/non-interactive-mode)
  descrive `codex exec` come funzione supportata per "pipelines (CI, pre-merge
  checks, scheduled jobs)" con **due** vie di autenticazione documentate:
  `CODEX_API_KEY` (consigliata per l'automazione) e account ChatGPT
  ("only if you specifically need to run as your Codex account" — via avanzata
  ma legittima e documentata).

Cosa cambia rispetto alla postura del 2026-07-08 (che resta valida come
snapshot storico qui sotto): il vincolo "nessun loop automatico su abbonamento
flat" era una prudenza in assenza di documentazione; oggi la documentazione
c'è, quindi l'invocazione programmatica **diretta e dichiarata** delle CLI
headless è ammessa per il dispatcher, alle condizioni seguenti (non opzionali):

1. **Preferenza per il canale consigliato dal provider**: per Codex,
   `CODEX_API_KEY` se disponibile, account ChatGPT altrimenti (entrambi
   documentati); per Claude, login di default o `--bare`+API key a scelta
   della configurazione.
2. **Tetti prudenziali** (proposti da Codex, adottati): max 3 turni automatici
   per thread senza tocco umano, max 10 invii headless/giorno, debounce 5
   minuti per coppia thread+destinatario, contatori persistenti, fail-closed.
3. **Tracciabilità**: ogni dispatch è un evento nel registro (motivo,
   capability, contatore, hash del prompt — mai il testo completo).
4. **Kill switch** che ferma anche le code già pronte; default: spento.
5. **Invariati tutti i divieti dell'esperimento Jitter** (sezione sotto):
   nessun camuffamento, nessuna emulazione antropomorfa, nessun bypass di
   rate limit o protezioni; se un provider cambia i termini in senso
   restrittivo, questa sezione va aggiornata e il dispatcher spento.
6. **Ri-verifica pratica prima dell'uso**: la capability resta "provata, non
   descritta" — il Lotto B deve rifare il test reale con `codex exec` (la
   verifica del 2026-07-08 usava `codex -q`) e riverificare `claude -p`
   nell'invocazione esatta del dispatcher. Gemini resta `manual_only` finché
   il bug TTY di `agy` non è risolto: per lui solo deep link/pull.

## Limiti della sperimentazione ed esclusione del Jitter (2026-07-08)

Durante la progettazione dell'automazione di background, è stata valutata l'introduzione di ritardi artificiali randomizzati (Jitter) e simulazioni di digitazione tasto per tasto per emulare il comportamento umano ed evitare i controlli anti-bot dei provider.

Questa possibilità è stata **esplicitamente scartata e vietata** per ragioni etiche e contrattuali:
- L'uso di CLI headless ufficiali per compiti programmati in background è ammissibile solo quando il canale è dichiarato e correttamente fatturato: `claude -p` rientra nel canale verificato per Claude, mentre `codex -q` qui è un canale OpenAI API Platform a consumo e richiede crediti `OPENAI_API_KEY`, non l'abbonamento flat dell'IDE.
- Al contrario, l'uso di tecniche di camuffamento o di emulazione antropomorfa (Jitter) rappresenta un tentativo deliberato di elusione e aggiramento dei sistemi di rilevamento dei provider. Se rilevato, tale comportamento configura un dolo contrattuale e porta inevitabilmente a un ban permanente dell'account (invece di semplici avvisi o rate-limit temporanei).

Pertanto, le regole di conformità per l'automazione escludono qualsiasi tecnica di offuscamento. Le invocazioni programmatiche avvengono in modo diretto, alla massima velocità di esecuzione della macchina. L'uso di pseudo-console (ConPTY o tmux su WSL) per superare i bug di TTY di `agy` è ammesso solo come puro workaround di sistema operativo per consentire l'I/O standard del processo, senza alcun intento di mascheramento.
