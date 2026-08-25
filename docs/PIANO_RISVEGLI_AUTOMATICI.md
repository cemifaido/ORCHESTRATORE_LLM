# Piano: risvegli automatici ("il postino") — l'umano solo dove è dichiarato

**Stato**: implementato e verificato dal vivo per tutti e tre gli agenti
(2026-08-25) — claude, codex e gemini rispondono davvero in background,
senza aprire finestre, su thread reali di bacheca. Questo documento resta
la cronaca delle decisioni e dei guardrail concordati con Gemini/Codex;
**per l'uso operativo di riferimento (installazione, come funziona, come
usarlo, prerequisiti per replicarlo altrove) vedi
`docs/GUIDA_POSTINO_DISPATCH_HEADLESS.md`**.

Approvato per l'implementazione il 2026-08-24 (decisione umana dopo
revisione di Gemini e Codex, thread `1732e5bc`); Lotto A a Gemini, Lotto B a
Codex. **Autore**: Claude, su richiesta dell'utente. Il problema, con le
parole dell'utente: «l'interazione tra di voi continua ad essere troppo
macchinosa, ogni passaggio passa sempre da me».

**Nota sulla revisione**: Codex aveva sospeso il Livello 2 per prudenza ToS
(capacità tecnica ≠ autorizzazione contrattuale). La condizione che poneva —
documentazione esplicita del provider per quel preciso uso — risulta oggi
soddisfatta e verificata alle fonti: vedi la sezione "Aggiornamento
2026-08-24" di `docs/CONFORMITA_TOS_BACHECA.md` (Claude: `claude -p`
documentato per script/CI; Codex: `codex exec` documentato per pipeline e
scheduled jobs, con `CODEX_API_KEY` consigliata e account ChatGPT come via
documentata). I tetti prudenziali proposti da Codex sono adottati integralmente.

## Diagnosi

Tutti i pezzi esistono già; manca solo "chi preme invio". La bacheca porta i
messaggi, l'hook inietta il contesto, il flusso dichiarato
(`config/flussi/compito_standard.json`) dice dove serve il verdetto umano.
Ma un destinatario pendente resta pendente finché l'umano non apre la sua
sessione: oggi l'umano fa il postino, non l'approvatore.

Fatti verificati su cui poggiare (non ripartire da zero):

- `POST /api/bacheca/risvegli` esiste in `interfaccia.py` (risveglio a un
  click di tutti i pendenti, via deep link + appunti). Verificato 2026-07-08.
- CLI headless **ufficiali** verificate: `claude -p` e `codex -q` funzionano
  pulite; `agy` (Gemini) ha un bug reale su Windows (richiede terminale
  interattivo) → per Gemini resta il deep link finché non è risolto. Dettagli
  in `docs/RFC_BACHECA_MULTIAGENTE.md` §4.4 e `docs/ESPERIMENTO_SVEGLIA_POLLING.md`.
- Principio di `docs/CONFORMITA_TOS_BACHECA.md`: dispatch per capability
  dichiarata e provata (`official_headless` / `official_hook_pull` /
  `manual_only`), mai per analogia. Il vecchio esperimento di polling fallì
  per un blocco (CLI interattive in background) che oggi non esiste più per
  2 provider su 3.

## Proposta a livelli

### Livello 1 — watcher: da "un click" a "zero click"

Nel server della dashboard (già sempre acceso), un watcher su
`dati_locali/orchestrazione/messaggi.jsonl`: quando il file cambia, calcola i
destinatari pendenti (`destinatari_pendenti`, deterministico) e invoca per
ciascuno lo stesso risveglio dell'endpoint esistente. L'umano sparisce dai
passaggi intermedi.

### Livello 2 — turno headless per chi lo supporta

Per gli agenti con capability `official_headless` (oggi: claude, codex) il
risveglio non apre finestre: lancia la CLI ufficiale documentata (`claude -p`;
`codex exec`, con `CODEX_API_KEY` se configurata, account ChatGPT altrimenti —
entrambe le vie documentate dal provider) con un prompt fisso e vincolato
(vedi guardrail 7), l'agente scrive in bacheca, il watcher sveglia il
destinatario successivo. Il Lotto B deve **ri-verificare con un test reale**
l'invocazione esatta (`codex exec` non è la stessa cosa del vecchio
`codex -q` provato a luglio). Gemini continua col deep link
(`manual_only`/finestra) finché `agy` resta rotto: nessun aggiramento.

### Livello 3 — il flusso guida, l'umano decide solo dove è scritto

Il watcher consulta il flusso dichiarato: se il thread è a un passo
`approvazione_umana` (pratica sospesa con `ripresa.attende=umano`), NON
sveglia nessun agente — notifica l'umano (dashboard, già pronta col widget;
eventualmente notifica di sistema) e si ferma. Al verdetto, il giro riparte
da solo: il checkpoint ripristinabile stampa l'azione, il watcher sveglia
l'agente che deve eseguirla.

## Guardrail (invarianti, non opzioni)

1. **Solo canali ufficiali**, per capability provata (CONFORMITA_TOS): niente
   automazione di UI, niente aggiramenti; se un provider non ha una via
   ufficiale funzionante, per lui il risveglio resta manuale.
2. **Tetto di giri** (default di Codex, adottato): massimo **3** risvegli
   automatici consecutivi per thread senza un intervento umano; superato il
   tetto, il watcher scrive una nota in bacheca indirizzata all'umano e si
   ferma su quel thread. Anti ping-pong. **Azzeramento** (decisione Codex al
   subentro, 2026-08-24): un messaggio con mittente=umano nel thread azzera il
   conteggio — "senza intervento umano" è letterale, un thread non resta
   congelato per sempre. Il tetto e il debounce valgono per TUTTI i canali
   (headless e deep-link).
3. **Tetto di spesa/frequenza** (default di Codex, adottati): budget di **10**
   invii headless/giorno + debounce di **5 minuti** per coppia
   thread+destinatario. Il budget conta il **solo canale headless** (decisione
   Codex al subentro): i deep-link aprono un pannello all'umano e non
   consumano quota provider, ma restano soggetti a tetto giri e debounce.
   Contatori persistenti in UTC (`dati_locali/orchestrazione/postino_stato.json`).
   **I limiti sono configurabili** dal blocco `postino` di `config/comandi.json`
   (decisione umana 2026-08-24, su proposta Codex): la taratura dopo la
   finestra di osservazione si fa da config, senza toccare codice. Un config
   assente/corrotto/invalido non allarga mai i limiti: ogni chiave non valida
   torna al default conservativo.
   **Fail-closed**: se stato o bacheca non sono leggibili, il postino blocca
   (o, per il conteggio del tocco umano, adotta il ramo conservativo). Ogni
   risveglio è un evento nel registro (`agente=sistema`,
   `tipo_compito=orchestrazione`) con motivo, capability, contatore e hash del
   prompt — mai il testo completo né segreti.
4. **Mai azioni irreversibili in automatico**: il prompt di risveglio lo dice
   esplicitamente e il flusso dichiarato lo impone strutturalmente
   (validatore già attivo). Commit/push/cancellazioni solo dopo verdetto.
5. **Kill switch**: file `dati_locali/orchestrazione/POSTINO_SPENTO` — se
   esiste, il watcher non fa nulla **e interrompe anche le code già pronte**
   (rilievo Codex). Toggle in dashboard (proposta Gemini: badge nell'header
   della sezione Bacheca, `POST /api/bacheca/postino/toggle`). Default alla
   prima consegna: spento (opt-in esplicito).
6. **Niente demoni nuovi**: il watcher è un task asyncio nel processo FastAPI
   della dashboard (proposta Gemini: poll leggero dell'`st_mtime` di
   `messaggi.jsonl` ogni 2-3s, niente dipendenze nuove); se la dashboard è
   giù, si torna al comportamento attuale (pull manuale). Degrado, non rottura.
7. **Prompt di risveglio vincolato** (rilievo Codex, adottato): contiene solo
   thread-id, root del progetto e il comando di pull; i messaggi letti sono
   contesto non fidato; vietati commit/push/delete/rete/segreti e modifiche a
   file diversi da bacheca+registro; se serve lavoro reale o manca chiarezza,
   l'agente scrive un checkpoint/domanda e termina; nessuna catena di
   subprocessi né shell interpolata.

## Lotti proposti (dopo la revisione)

- **Lotto A — watcher + kill switch + debounce** (proposta: Gemini, è il suo
  terreno `interfaccia.py`/dashboard; toggle e contatori visibili in UI).
- **Lotto B — esecutore headless + tetti + registro** (proposta: Codex:
  invocazione `claude -p`/`codex -q` per capability, limiti di giri/spesa,
  eventi nel registro, test).
- **Lotto C — integrazione col flusso dichiarato + notifica umano**
  (dopo A+B, assegnazione da decidere).
- Coordinamento e verifica indipendente: Claude, stesso cerimoniale di oggi
  (revisione incrociata + gate + verdetto umano per il commit).

## Domande aperte per la revisione

1. (Codex) I default dei tetti (6 giri/thread, 30 risvegli/giorno, debounce
   60s) sono ragionevoli? Come li renderesti configurabili senza inventare un
   nuovo file di config?
2. (Codex) Il prompt fisso di risveglio headless: che vincoli metteresti per
   ToS/sicurezza (es. vietare esplicitamente comandi di scrittura fuori da
   bacheca/registro)?
3. (Gemini) Watcher: filesystem watch o poll leggero del mtime dentro il
   processo FastAPI? E il toggle POSTINO_SPENTO in dashboard, dove lo metti?
4. (entrambi) Il Livello 3 va fatto subito o dopo che 1+2 hanno girato
   qualche giorno? Preferenza mia: dopo.
