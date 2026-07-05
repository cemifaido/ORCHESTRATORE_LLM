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
  RPA o keystroke injection.
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
- non si devono inviare segreti o dati sensibili a servizi non pagati/non protetti.

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
