# RFC — Bacheca multi-agente senza API a pagamento

**Stato**: MVP implementato e testato (`bacheca.py` + `tests/test_bacheca.py`,
125/125 test). Hook **verificati empiricamente e confermati funzionanti** per Claude
Code e Codex (sessioni fresche reali, non solo configurazione — vedi §9): l'iniezione
automatica del contesto dalla bacheca funziona senza intervento umano su entrambi.
Per Codex serve un'autorizzazione esplicita una tantum nell'IDE (Antigravity/Codex
extension chiede di approvare gli hook trovati la prima volta — un gate di sicurezza
atteso, non un difetto). Gemini/Antigravity non ancora verificato (Gemini bloccato
da quota al momento della verifica) — unico passo davvero ancora aperto sul lato
hook. **Aggiunto anche**: coordinamento cooperativo sui file (`occupati`/`prendi
--file-modificati`), interruzione/ripresa (`checkpoint`/`ripresa`/`emergenza`),
integrazione vera del modello locale (`sintetizza`), e un pannello "Bacheca" nella
dashboard esistente (`interfaccia.py`/`.html`) con feed live e replay animato.

**Da leggere insieme a**: [Indice](INDEX.md) ·
[Guida semplice alla bacheca multi-agente](GUIDA_SEMPLICE_BACHECA_MULTIAGENTE.md)
(stessa bacheca, spiegata senza i dettagli tecnici qui sotto) ·
[ORCHESTRAZIONE_LAVORATORI.md](ORCHESTRAZIONE_LAVORATORI.md)
(il meccanismo di sincronizzazione asincrona attuale, di cui questo documento è
un'evoluzione proposta, non un rimpiazzo) · [schema/messaggio.v1.json](../schema/messaggio.v1.json)
· [esempi/spike_dispatcher_locale.py](../esempi/spike_dispatcher_locale.py) ·
[CONFORMITA_TOS_BACHECA.md](CONFORMITA_TOS_BACHECA.md).

---

## 1. Obiettivo e motivazione

Il vincolo tassativo di partenza: coordinare Claude Code, Codex CLI e Gemini/Antigravity
sullo sviluppo di questo progetto **senza usare le rispettive API a pagamento**,
sfruttando invece gli abbonamenti flat già attivi tramite i plugin IDE, più un LLM
locale (llama-server, gratis, sempre acceso) come arbitro economico.

Oggi la sincronizzazione fra le tre sessioni interattive esiste già, ma è minimale:

- Ogni sessione legge `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` all'avvio (verificato per
  Claude Code, storicamente non verificato per gli altri due — vedi §4).
- Ognuno confronta il timestamp "Ultimo aggiornamento" in cima al proprio file con
  quello degli altri due, e se è indietro va a leggere le ultime note in
  `dati_locali/orchestrazione/eventi.jsonl`.
- L'operatore umano fa da collante fisico: copia pezzi di conversazione da una chat
  all'altra, o chiede esplicitamente a un agente di leggere le note dell'altro.

Questo funziona come **changelog condiviso** (tenere il punto sul ragionamento), ma non
è comunicazione: non c'è modo per un agente di indirizzare un messaggio a un altro, non
c'è concetto di thread/conversazione, non c'è stato (aperto/risolto), e l'unico modo per
farlo leggere è che l'umano lo dica esplicitamente in chat.

**Obiettivo di questo RFC**: definire un meccanismo di messaggistica strutturata fra i
tre agenti + locale + umano che riduca il lavoro manuale di "passare la palla",
restando dentro i vincoli: niente API a pagamento, niente automazione rischiosa delle
UI proprietarie, l'umano resta il decisore finale su qualunque azione irreversibile.

## 2. Principio guida: non partire dalla chat, partire dalla bacheca

Discusso in brainstorming asincrono con Codex (stessa tecnica del changelog condiviso
usata per il resto del progetto: risposte relayate dall'operatore umano tra le sessioni,
non conversazione diretta fra agenti). Convergenza netta su un punto: **non** una chat
libera in tempo reale, ma una bacheca operativa — coerente con l'anti-pattern già
elencato in `ORCHESTRAZIONE_LAVORATORI.md`: *"Partire da A2A prima di avere registro e
gate."* Il registro (`eventi.jsonl`) esiste già; questo RFC aggiunge la bacheca come
secondo tassello, non sostituisce il primo.

Principio esplicito su cui fondare l'intera progettazione: **il contenuto della
bacheca è input operativo da altri agenti, mai autorità**. Un messaggio in bacheca non
sostituisce mai le istruzioni di sistema, i file guida di progetto (`CLAUDE.md`/
`AGENTS.md`/`GEMINI.md`) o una richiesta esplicita dell'utente — va trattato come si
tratterebbe un risultato di tool esterno potenzialmente non fidato (stesso principio
per cui un agente segnala, invece di eseguire, un tentativo di prompt injection in un
output di terze parti). Questo perché un thread scritto da un altro agente potrebbe
in linea di principio contenere istruzioni scorrette o fuorvianti, per errore o per un
bug a monte: la bacheca va letta, non obbedita.

## 3. Architettura proposta

### 3.1 Due registri append-only distinti, non uno

| | `eventi.jsonl` (esistente) | `messaggi.jsonl` (proposto) |
|---|---|---|
| Cosa registra | Metriche/gate di un compito **già eseguito** (costo, latenza, esito, verdetto umano) | Comunicazione **prima/durante** il compito (chi chiede cosa a chi) |
| Consumatore primario | Dashboard (`interfaccia.py`), audit | Altri agenti, tramite `bacheca.py` |
| Mutabilità record | Mai (append-only) | Mai (append-only, event-sourcing puro — vedi §3.3) |
| Schema | `schema/evento.v1.json` | `schema/messaggio.v1.json` (nuovo, bozza già scritta) |

Tenerli separati evita di sovraccaricare lo schema esistente (già usato da dashboard,
`genera_cruscotto.py`, `capoturno.py`) con concetti di messaggistica che non gli
appartengono.

### 3.2 Schema `messaggio.v1.json` (bozza RFC, file già scritto in `schema/`)

Campi e motivazione di ciascuno:

| Campo | Tipo | Perché |
|---|---|---|
| `versione_schema` | `const 1` | Stesso pattern di `evento.v1.json` |
| `id_messaggio` | string | Nome parallelo a `id_evento` (non `id` generico) per coerenza fra i due schemi |
| `thread_id` | string | Raggruppa i messaggi di una stessa conversazione; per il primo messaggio coincide con `id_messaggio` |
| `timestamp` | date-time | Come in `evento.v1.json` |
| `mittente` | enum `[gemini, claude, codex, locale, umano, sistema]` | Stesso enum di `agente` in `evento.v1.json`, per coerenza |
| `destinatari` | array di enum (stesso set) | **Deciso** (v1): enumerazione esplicita, nessun valore "tutti" nello schema — vedi §7 per la motivazione |
| `tipo` | enum `[richiesta, risposta, domanda, sintesi, presa_in_carico, chiusura, annullamento, segnalazione_conflitto]` | Determina lo stato derivato del thread (vedi §3.3). `segnalazione_conflitto` è il tipo dedicato per quando il dispatcher locale rileva un conflitto (§6.2) — non va infilato come campo libero dentro `sintesi` |
| `testo` | string | Il contenuto — trattato come dato, non autorità (§2) |
| `file_modificati` | array di string | **Stesso nome** di `evento.v1.json` (non un nome diverso tipo "risorse"), per restare compatibili fra i due registri e permettere alla dashboard di trattarli come lo stesso concetto |
| `riferimenti` | array di string | Percorsi/URL di contesto che non sono file toccati (doc, altri thread, id_compito correlati) |
| `correla_a` | string o null | `id_messaggio` a cui questo risponde direttamente |
| `ttl_minuti` | integer o null | Significativo solo per `tipo=presa_in_carico`: lease non vincolante per ridurre collisioni fra agenti che lavorano sugli stessi file, non un lock reale. **Vincolo ora imposto dallo schema stesso** (non solo a parole): un `if/else` in `messaggio.v1.json` obbliga `ttl_minuti=null` per ogni tipo diverso da `presa_in_carico` |
| `verdetto_umano` | enum `[non_revisionato, approvato, respinto, modifiche_richieste]` | **Stesso enum** di `evento.v1.json`, campo ortogonale allo stato del thread (vedi §3.3). Il verdetto *corrente* del thread è l'ultimo `verdetto_umano != non_revisionato` nel thread (idealmente con `mittente=umano`), non il valore sull'ultimo record in assoluto |
| `metadati` | object, `additionalProperties: true`, default `{}` | Stesso pattern di `evento.v1.json`: dati diagnostici senza un campo dedicato (es. `fonte_hook`, `modello_locale`, `token_totali`, `severita'` di un conflitto) |

### 3.3 Event-sourcing puro: nessun campo di stato scritto nel record

Decisione presa in brainstorming (Codex) e confermata: coerente con come già funziona
`eventi.jsonl` (mai un record modificato in place, solo aggregazione a lettura — vedi
`registro.py:metriche()`). Lo stato di un thread **non è un campo**, si deriva
dall'ultimo messaggio pertinente:

- ultimo messaggio di tipo `richiesta`/`domanda`/`sintesi` senza seguito → **aperto**
- ultimo `presa_in_carico` → **preso in carico**
- ultimo `risposta` → **risposto**
- ultimo `chiusura` → **chiuso**
- ultimo `annullamento` → **annullato**

Correzione applicata rispetto a una prima bozza: **non** mescolare questo stato
operativo con `verdetto_umano` in un unico campo. Un thread può essere "risposto" e
allo stesso tempo "non_revisionato" da un umano — sono due assi distinti, esattamente
come già avviene in `evento.v1.json` fra `stato` ed `esito_gate`/`verdetto_umano`.

**Seconda correzione, emersa in revisione (Codex)**: "ultimo messaggio pertinente"
funziona per thread lineari (un destinatario), ma diventa ambiguo con più
destinatari. Se un thread è indirizzato a `claude` e `codex` e risponde solo Claude,
è "risposto" o resta "aperto" per Codex? Servono **due viste distinte**, non una:

- **stato thread globale** (quello elencato sopra): aperto/preso_in_carico/risposto/
  chiuso/annullato — utile per una vista d'insieme (es. `bacheca.py riepilogo`).
- **stato per destinatario**: per ogni agente X in `destinatari`, `X` è **pending**
  finché non ha inviato lui stesso un messaggio nel thread dopo l'ultima volta che è
  stato indirizzato, oppure il thread non è chiuso/annullato globalmente; altrimenti
  è **resolved**. Questa è la vista che conta per `bacheca.py prossimo --agente X`
  (§3.4) e per il trigger "un messaggio mi è indirizzato" (§3.6): un thread
  globalmente "risposto" da Claude può avere Codex ancora "pending".

### 3.4 `bacheca.py` — implementato e testato

Mirror strutturale di `registro.py` (stesso stile: `carica_schema_*`, `valida_*`,
`aggiungi_*`, `leggi_*`, riusando `_validatore_per_schema`/`_messaggio_errore`/
`adesso_utc`/`lista_csv` già presenti in `registro.py` invece di duplicarli). Comandi
CLI implementati (`tests/test_bacheca.py`, 125 test, più diversi giri manuali end-to-end):

```
python bacheca.py aggiungi --mittente claude --destinatari codex --tipo richiesta --testo "..."
python bacheca.py prossimo --agente codex [--formato hook]
python bacheca.py rispondi --correla-a <id_messaggio> --mittente codex --testo "..."
python bacheca.py prendi --thread-id <id> --agente codex --ttl-minuti 60 [--file-modificati bacheca.py] [--forza]
python bacheca.py occupati
python bacheca.py chiudi --thread-id <id> --mittente umano --testo "..."
python bacheca.py riepilogo
python bacheca.py valida
```

**Coordinamento cooperativo sui file, non un lock del filesystem** (emerso in
discussione: cosa succede se due agenti devono toccare lo stesso file?). Non c'è un
lock reale — la bacheca riduce il rischio, non lo elimina. `prendi --file-modificati X`
controlla se `X` è già in carico ad **un altro** agente tramite `file_occupati()`: un
file risulta occupato solo se il thread che lo reclama è ancora nello stato globale
"preso in carico" (una `risposta`/`chiusura` successiva rilascia già il claim da sola,
tramite `stato_thread` — nessun rilascio esplicito necessario) **e** il lease non è
scaduto (`timestamp + ttl_minuti`, confrontato timezone-aware in UTC con lo stesso
pattern già usato in `commit_replay.py`; un claim senza `ttl_minuti` non scade mai). Se
c'è una collisione, il comando si rifiuta (`exit 1`) e stampa un avviso, a meno di
`--forza` — che registra comunque il conflitto in `metadati.forzato_su_conflitto` e
`metadati.occupato_da`, per audit, invece di procedere in silenzio. `bacheca.py occupati`
mostra tutti i claim attivi non scaduti.

Scelta deliberata di scope: **niente integrazione con `git status`/diff** per questo
controllo — aggiungerebbe complessità reale (normalizzazione path, stato del working
tree) per un guadagno marginale rispetto ai claim già dichiarati in bacheca. Da
riconsiderare solo se emerge un bisogno concreto in uso.

### 3.4bis Interruzione e ripresa: checkpoint, ripresa, emergenza

Domanda emersa in uso: se bisogna spegnere tutto a metà di una o più lavorazioni,
cosa succede, e come si riprende? La bacheca (append-only) non perde nulla di già
scritto — il rischio è solo ciò che non è ancora stato scritto (ragionamento rimasto
nella chat di un agente, modifiche non salvate, decisioni non annotate). Tre comandi
coprono i due casi (interruzione pianificata vs. emergenza):

- **`bacheca.py checkpoint --thread-id <id> --agente X --obiettivo ... --stato-attuale
  ... --file-modificati ... --manca ... --test ... --rischi ... --prossimo-passo
  ...`**: annotazione strutturata di avanzamento a metà lavoro. Non chiude il thread.
  **Deliberatamente trasparente allo stato globale**: `stato_thread` lo ignora
  tramite `_ultimo_rilevante` (un checkpoint non deve far tornare "aperto" un thread
  già preso in carico), ma i suoi destinatari possono comunque risultare "pending"
  (`tipo=checkpoint` è nell'insieme `TIPI_APERTURA` per questo asse) — due
  meccanismi indipendenti, non uno che esclude l'altro, così un checkpoint resta
  visibile via hook alla ripresa senza alterare lo stato derivato.
- **`bacheca.py ripresa`**: vista pensata per quando si riaccende — thread ancora
  aperti/in carico, lease scaduti evidenziati, file con lease attivo, promemoria di
  controllare anche `git status`/`git diff` per modifiche non ancora registrate in
  bacheca. Non decide nulla al posto dell'umano.
- **`bacheca.py emergenza [--testo "..."]`**: per quando non c'è tempo di chiudere
  bene. Scrive un solo checkpoint (mittente `umano`, indirizzato a tutti gli agenti)
  in bacheca, cattura `git status --short` (best-effort: se git fallisce lo annota e
  prosegue comunque, il checkpoint in bacheca non deve dipendere da git), salva
  tutto in `dati_locali/orchestrazione/ultimo_checkpoint_emergenza.txt` ed elenca i
  thread ancora da riprendere. Nessun parametro obbligatorio: la regola in
  emergenza è "non provare a finire bene, lascia un segnale minimo ma chiaro".

Bug reale trovato scrivendo i test di questi comandi, non solo teorico: il confronto
per stabilire se un destinatario è "pending" usava i timestamp come stringhe con
`>` stretto, ma `adesso_utc()` ha precisione al secondo — messaggi scritti nello
stesso secondo (frequente con scritture ravvicinate, non solo nei test) avevano
timestamp identici, e il confronto sbagliava silenziosamente verso "resolved".
Corretto usando la posizione nella lista ordinata (`_messaggi_del_thread` ordina già
in modo stabile) invece della stringa del timestamp — coperto da un test di
regressione dedicato.

`prossimo --agente X --formato hook` è il comando pensato per essere chiamato **dagli
hook** dei tre strumenti (§4): deve produrre un output compatto (vincolo tecnico reale,
non solo buona pratica — vedi limite di 10.000 caratteri in §4) contenente solo i
thread aperti/presi in carico rilevanti per quell'agente (vista **per destinatario**,
non stato globale del thread — vedi §3.3).

**Comandi ergonomici dedicati all'umano** (proposti in revisione, Codex, implementati):
i comandi sopra sono generici (validi per qualunque `mittente`), ma per l'uso
dell'umano dentro una conversazione con uno degli agenti servono scorciatoie corte,
non l'aggiungi completo con tutti i flag. Sono zucchero sintattico sopra
`aggiungi`/`chiudi`, non comandi nuovi con semantica propria:

```
python bacheca.py chiedi --a codex --testo "Rivedi l'RFC"          # = aggiungi --mittente umano --tipo richiesta
python bacheca.py chiedi --a claude,gemini --testo "Criticate X"   # destinatari multipli
python bacheca.py stato                                            # riepilogo lo stato globale + "aspetta te" per destinatario
python bacheca.py thread <id>                                      # cronologia completa di un thread
python bacheca.py approva --thread-id <id> --testo "Procedi"       # = chiudi + verdetto_umano=approvato
python bacheca.py respingi --thread-id <id> --testo "..."          # = chiudi + verdetto_umano=respinto
```

**Deciso** (risolve il punto prima aperto in §7): `bacheca.py approva` scrive il
verdetto solo nel *thread* (`messaggi.jsonl`) — serve agli agenti per sapere "l'umano
ha approvato questo thread, potete procedere". Questo **non** genera automaticamente
un evento in `eventi.jsonl`: i due registri restano disaccoppiati, con criteri
d'uso distinti:

- `bacheca.py approva --thread-id <id>` → sempre, ogni volta che l'umano chiude un
  thread operativo con esito positivo (consumatore: gli altri agenti).
- `registro.py aggiungi --agente umano --verdetto-umano approvato` → **solo** quando
  l'approvazione riguarda un'azione materiale e irreversibile (commit, push,
  cancellazione, merge, decisione architetturale importante) — stesso criterio già
  in uso oggi, non un criterio nuovo (consumatore: audit/dashboard).

Non ogni `approva` in bacheca genera un evento umano in `eventi.jsonl`: solo quelle
"materiali". Un thread che chiude una semplice consultazione ("va bene questo
naming?") non ha bisogno di un evento di audit; una decisione che sblocca un commit
sì — restano due atti distinti, anche se a volte coincidono nello stesso momento.

Due correzioni di parsing emerse dallo spike (§6): la normalizzazione case-insensitive
dei nomi agente (`Gemini` → `gemini`) è **fatta** (`bacheca.py:normalizza_agente`,
testata). Il modello locale che a volte restituisce `"conflitto": "null"` come
stringa invece di `null` JSON resta **da gestire quando esisterà** un comando che
integra davvero il dispatcher locale (es. un futuro `bacheca.py sintetizza`) — non
ancora scritto: `bacheca.py` oggi copre solo i comandi umani/agente, non ancora
un'integrazione diretta con `adattatori/litellm.py`.

### 3.5 Flusso di lavoro end-to-end (esempio concreto)

Scenario passo per passo, per rendere concreto come si incastrano bacheca e hook:

1. Claude, in sessione interattiva, apre un thread:
   `bacheca.py aggiungi --mittente claude --destinatari codex --tipo richiesta --testo "Rivedi X"`.
   Questo scrive un record in `messaggi.jsonl`. **Nient'altro succede subito** — non
   c'è push, nessuno "sveglia" Codex.
2. Il thread resta derivato come "aperto" (§3.3) finché qualcuno non lo prende in
   carico o risponde.
3. Più avanti, quando l'utente apre (di sua iniziativa) una sessione Codex, l'hook
   `SessionStart`/`UserPromptSubmit` (§4) esegue
   `bacheca.py prossimo --agente codex --formato hook`: l'output (i thread aperti
   indirizzati a codex, compatto) viene iniettato come `additionalContext` nel
   contesto di Codex. Codex "vede" la richiesta senza che l'utente gliela debba
   incollare a mano — questo è il punto in cui si guadagna rispetto a oggi.
4. Codex risponde all'utente in conversazione e, se fa un'azione reale, scrive sia un
   evento in `eventi.jsonl` (metrica del compito) sia una risposta in bacheca:
   `bacheca.py rispondi --correla-a <id_messaggio> --mittente codex --testo "..."`.
5. Il thread deriva ora stato "risposto". Se serve un'ulteriore iterazione (es.
   Claude deve integrare il feedback), il ciclo si ripete nel verso opposto.
6. Solo se c'è un'azione irreversibile (commit, merge, cancellazione, decisione
   architetturale) interviene un evento umano esplicito
   (`--agente umano --verdetto-umano approvato`) — esattamente il meccanismo già in
   uso oggi per `eventi.jsonl`, non uno nuovo.

Nota importante su questo esempio: ogni passo richiede comunque che **l'utente apra
la sessione di sua iniziativa** (punto 3) — resta un meccanismo pull, non una vera
attivazione automatica (§4.1). Il guadagno è togliere il copia-incolla manuale del
contesto, non eliminare l'apertura delle sessioni.

### 3.6 Il canale "umano": control plane, non quarto agente in chat continua

Domanda diretta a cui rispondere prima di scrivere codice: la bacheca è una chat
condivisa dove l'utente vede passare tutto e deve autorizzare? **No** — e il modo più
preciso di dirlo (formulazione emersa in revisione, Codex): **l'umano è il control
plane del sistema, non un quarto agente che partecipa a una chat continua.** Il
canale ufficiale per l'umano resta comunque la bacheca (`mittente=umano`, stessi
record, stesso schema) — ma l'umano non deve scrivere JSON a mano né comandi lunghi:
gli serve un'ergonomia dedicata sopra `bacheca.py` (i comandi `chiedi`/`stato`/
`thread`/`approva`/`respingi` di §3.4), non un'interfaccia parallela.

**Non esiste, e non è l'obiettivo, una chat stile WhatsApp.** Oggi l'unico modo di
vedere lo stato della bacheca è `bacheca.py stato`/`bacheca.py thread <id>` da riga
di comando. Una vista dashboard minima (non il cockpit completo) è comunque parte
del perimetro v1 — vedi §9, ridimensionato rispetto a una prima stesura che la
rimandava del tutto.

**L'utente non deve autorizzare ogni messaggio che passa.** Il flusso
richiesta/risposta/domanda/sintesi fra agenti è pensato per essere autonomo, sullo
stesso principio già in uso per `eventi.jsonl`: nessuno rilegge ogni singola nota in
tempo reale, è un changelog da consultare quando serve — non un flusso da presidiare
riga per riga. Imporre un'approvazione umana per ogni messaggio vanificherebbe
l'obiettivo stesso di questo RFC. **L'autorizzazione esplicita resta riservata alle
azioni irreversibili**: commit, push, cancellazioni, decisioni architetturali
importanti — stesso principio di sempre, non un meccanismo nuovo.

**Trigger di notifica push (desktop, non chat)** — ampliati in revisione da due a
quattro, tutto il resto resta pull (consultabile quando comodo):

1. un messaggio con `destinatari` che include esplicitamente `umano`;
2. un **conflitto rilevato** dal dispatcher locale (`tipo=segnalazione_conflitto`,
   §6.2) — il caso per cui vale di più interrompere, non farlo scoprire per caso;
3. un **gate di approvazione richiesto** (un thread arriva a un punto in cui, per
   convenzione di workflow, serve un via libera esplicito prima di proseguire — es.
   fine implementazione, prima di un merge);
4. un **lease scaduto** (`ttl_minuti` di una `presa_in_carico` superato) su un
   lavoro segnalato come importante — segnale di possibile stallo/abbandono da non
   scoprire solo per caso.

**Come dovrebbe interagire l'umano in pratica**, in sintesi (revisione, Codex):
aprire un intento ("voglio implementare X"); decidere il routing, o chiedere al
locale di proporlo; leggere la *sintesi* prodotta dal locale, non l'intero thread
grezzo, salvo quando serve approfondire; farsi interrompere solo su conflitto o
scelta importante (i 4 trigger sopra); approvare solo le azioni irreversibili.

Riepilogo architetturale del canale umano in una riga:
`Dashboard/CLI (chiedi/approva) → bacheca` · `Hook agenti → leggono ciò che li
riguarda` · `Locale → sintetizza e segnala conflitti` · `Notifica → richiama l'umano
solo sui 4 trigger, mai altrimenti`.

### 3.7 Come l'umano assegna un obiettivo durevole (finché resta lui a deciderli)

Domanda pratica: finché è l'umano a dare gli obiettivi (non ancora delegati al
routing automatico), come li comunica agli agenti senza tornare al copia-incolla
manuale? Regola operativa: **la chat con un agente serve per lavorare, la bacheca
serve per assegnare e sincronizzare.** Qualunque obiettivo che deve sopravvivere a un
cambio di agente/sessione va scritto in bacheca come messaggio `mittente=umano` una
sola volta, non ripetuto a mano in ogni chat — è la stessa idea del "control plane"
di §3.6, applicata al momento in cui l'obiettivo nasce, non solo a come viene
approvato.

Tre pattern d'uso, tutti già coperti dal `tipo` esistente (nessun nuovo valore di
enum, solo convenzione su come li usa l'umano):

```
# incarico diretto (tipo=richiesta, un destinatario)
python bacheca.py chiedi --a claude --testo "..."

# consultazione / review (tipo=domanda)
python bacheca.py chiedi --a codex --tipo domanda --testo "Ci sono rischi in Y?"

# broadcast controllato (destinatari multipli, enumerati per esteso — §7)
python bacheca.py chiedi --a claude,codex,gemini --testo "Criticate questa RFC prima dell'implementazione"
```

**Template consigliato per il campo `testo`** (convenzione, non vincolo di schema —
`testo` resta libero): quattro parti, sempre le stesse, perché l'agente che lo riceve
via hook non ha altro contesto a cui appoggiarsi:

```
Obiettivo: ...
Contesto: ...
Output atteso: ...
Vincoli: ...
```

Esempio concreto:

```
python bacheca.py chiedi --a claude --testo "Obiettivo: implementare bacheca.py.
Contesto: seguire docs/RFC_BACHECA_MULTIAGENTE.md. Output atteso: CLI funzionante
con aggiungi/prossimo/rispondi/prendi/chiudi/riepilogo/valida. Vincoli: niente
dashboard, niente hook reali in questa fase, test minimi su schema e proiezione
stato."
```

Conseguenza pratica di questa regola: l'umano continua a parlare normalmente con
Claude/Codex/Gemini in chat per il lavoro del momento, ma smette di essere lui il
"copiatore di contesto" fra le sessioni — quel ruolo lo assorbe la bacheca. L'umano
resta il product owner che apre thread, assegna, consulta, approva e chiude — non un
postino che porta a mano lo stesso messaggio in tre chat diverse.

Se l'obiettivo evolve **dopo** essere stato postato (es. la conversazione con un
agente lo raffina), il messaggio originale non va riscritto — è append-only, come
tutto il resto (§3.3). L'aggiornamento va loggato come nuovo messaggio correlato
(`correla_a` che punta all'`id_messaggio` originale, `tipo=sintesi` o una nuova
`richiesta`), non lasciato divergere in silenzio fra bacheca e chat.

## 4. Meccanismo di attivazione: pull via hook, non push

### 4.1 Perché il polling da solo non basta

Il polling del file (`messaggi.jsonl` o una futura bacheca) per rilevare un
cambiamento è economicamente quasi gratis: un controllo di mtime/hash ogni 1-2 secondi
è un semplice `stat()`, non una chiamata LLM. **Non è quello il collo di bottiglia.**

Il problema è cosa succede dopo aver rilevato un messaggio nuovo: se la sessione di
Codex/Claude/Gemini non è aperta, non c'è nessuno lì che lo legga — il poller può solo
notificare l'umano, non far ripartire da sola una conversazione in un terminale/IDE
fermo. Farla "svegliare da sola" richiederebbe simulare input in un'interfaccia
proprietaria — l'automazione fragile e a rischio ToS che questo progetto evita
esplicitamente (vedi anche l'anti-pattern generale del non pilotare UI di terze parti).

### 4.2 Hook verificati sui tre strumenti (con fonti dirette, non solo a parola)

Verificato tramite fetch diretto delle pagine di documentazione ufficiali (non solo
fidandosi della ricerca fatta da Codex/Gemini in brainstorming — controllato
indipendentemente prima di darlo per buono):

| Strumento | Evento "inizio sessione" | Evento "prima di processare un prompt" | File di configurazione | Iniezione contesto |
|---|---|---|---|---|
| **Claude Code** | `SessionStart` | `UserPromptSubmit` | `settings.json` (con altri eventi: `InstructionsLoaded`, `FileChanged`, `PreToolUse`/`PostToolUse`, `PreCompact`, `SubagentStart`, ecc. — set molto più ricco del previsto) | `hookSpecificOutput.additionalContext`, incapsulato come "system reminder", **limite 10.000 caratteri** oltre cui viene scritto su file con solo anteprima |
| **Codex CLI** | `SessionStart` | `UserPromptSubmit` | `~/.codex/hooks.json` o `<repo>/.codex/hooks.json` (anche `config.toml` inline) | `hookSpecificOutput.additionalContext`, o testo semplice su stdout come "developer context" |
| **Gemini CLI / Antigravity** | `SessionStart` | `BeforeAgent` (nome diverso, stessa funzione — scatta dopo l'invio del prompt, prima del planning loop) | `.gemini/settings.json` (progetto) / `~/.gemini/config/settings.json` (utente) | `additionalContext` con semantica per evento (`BeforeAgent`: appeso al prompt solo per quel turno; `SessionStart`: iniettato come primo turno) |

Fonti verificate direttamente: `code.claude.com/docs/en/hooks`,
`developers.openai.com/codex/hooks`, `developers.googleblog.com` (post ufficiale
gennaio 2026) + `geminicli.com/docs/hooks/reference/` (linkata dal blog Google stesso
come documentazione ufficiale, nonostante il dominio non sia google.com).

**Correzione strutturale rispetto alla prima bozza di configurazione proposta**: il
JSON di `settings.json` non è un array piatto di hook — c'è un livello di nesting in
più, un array di gruppi-per-matcher ciascuno con un proprio array `hooks` interno:

```json
{
  "hooks": {
    "BeforeAgent": [
      {
        "matcher": "*",
        "hooks": [
          { "name": "leggi-bacheca", "type": "command", "command": "python bacheca.py prossimo --agente gemini --formato hook" }
        ]
      }
    ]
  }
}
```

Stessa forma (matcher + hooks annidati) su Claude Code. Da verificare quando si scrive
davvero la configurazione, non assumere la forma più semplice.

### 4.3 Limite noto e non ancora chiuso: Antigravity IDE vs Gemini CLI open-source

Tutto quanto sopra per Gemini è documentato per **Gemini CLI**, il progetto
open-source. Antigravity (l'IDE) ne è basato, ma non è garantito che l'IDE esponga o
rispetti la stessa configurazione `.gemini/settings.json` — potrebbe avere una
superficie di configurazione diversa, sandbox più stringenti (build commerciali spesso
bloccano l'esecuzione di comandi locali arbitrari per sicurezza), o canali diversi
(variabili d'ambiente, estensioni interne). Verifica pratica ancora da fare sulla
macchina reale, sensori concreti da cercare:

1. Presenza di una cartella `.gemini/` generata automaticamente o riconoscimento di
   `GEMINI.md` a livello di workspace.
2. Comportamento del sistema al salvataggio di un `.gemini/settings.json` con il
   nesting corretto del `matcher`.
3. Log di errore/blocco di sicurezza nella console sviluppatori dell'IDE quando
   l'agente tenta di invocare un comando esterno (`type: "command"`).

**Per v1, questo va trattato come ipotesi, non come fondazione del disegno** (rafforzato
in revisione, Codex): il requisito minimo per Gemini resta `GEMINI.md` +
`bacheca.py prossimo --agente gemini` letto manualmente a inizio sessione — l'hook
`BeforeAgent` è un "best effort", da aggiungere se e quando verificato sulla macchina
reale, mai un presupposto per far funzionare il resto del disegno. Claude Code e
Codex, con gli hook già verificati (§4.2), non hanno bisogno di questo fallback.

## 5. Cosa NON fare: automazione diretta delle UI proprietarie

Discusso e scartato esplicitamente. Pilotare le sessioni interattive di Claude
Code/Codex/Antigravity via script che simulano tasti (pty/expect, keystroke
injection) per farle "reagire" senza un umano che apre la sessione:

- è fragile (si rompe a ogni aggiornamento dei tool);
- rischia di urtare i termini di servizio degli abbonamenti flat, pensati per uso
  interattivo personale, non per automazione non presidiata prolungata;
- non aggiunge nulla che il meccanismo a hook (§4) non dia già, restando dentro un
  uso legittimo di ogni sessione.

La motivazione contrattuale completa e il set di guardrail operativi sono nella nota
[Conformità ToS della bacheca](CONFORMITA_TOS_BACHECA.md): la bacheca deve restare un
coordinamento locale per sessioni interattive legittime, non una API non ufficiale
costruita sopra abbonamenti flat.

## 6. Ruolo del modello locale: ridimensionato dopo lo spike sperimentale

### 6.1 Cosa NON deve fare

**`prossimo_destinatario` non va chiesto al modello.** Si deriva deterministicamente
dalla vista per destinatario (§3.3): per ogni agente si guarda se ha ancora messaggi
pending dopo l'ultima volta in cui è stato indirizzato. Zero ambiguità, zero chiamata
LLM, e lo spike ha mostrato che il modello sbaglia comunque questo compito in almeno
una configurazione testata (vedi tabella §6.3) — motivo in più, non contrario, a
tenerlo fuori dal locale.

### 6.2 Cosa può fare, ma solo con un prompt adeguato

Sintesi del thread e rilevamento conflitti — **ma il rilevamento conflitti fallisce
sistematicamente senza un esempio one-shot nel prompt** che mostri concretamente cosa
si intende per "conflitto" (due mittenti che affermano fatti incompatibili sulla
stessa cosa concreta, non una semplice discussione/disaccordo di opinione). Con la
sola definizione astratta nel prompt di sistema, 0 modelli su 3 testati rilevavano un
conflitto esplicito nel thread di prova; con un esempio one-shot, 2 modelli su 3 lo
rilevano su tutti i thread di prova.

**Come va scritto il conflitto in bacheca** (revisione, Codex): quando il dispatcher
locale rileva un conflitto, non deve scriverlo come campo libero dentro un messaggio
`sintesi` — va scritto come messaggio di tipo dedicato `segnalazione_conflitto` (già
aggiunto all'enum di `messaggio.v1.json`, §3.2), con `destinatari` che includa
`umano`. Un tipo esplicito, invece di testo libero da interpretare, è ciò che
permette a dashboard/notifiche di filtrarlo in modo affidabile (§3.6, trigger 2).

### 6.3 Risultati sperimentali completi

Metodologia: script a perdere `esempi/spike_dispatcher_locale.py`, 3 thread di prova
hardcoded (uno aperto senza risposta, uno chiuso, uno con conflitto esplicito fra due
agenti su uno stesso fatto concreto — la presenza/assenza della logica di costo nella
dashboard), stesso prompt di sistema per ogni test, `temperature=0.0`.

| Modello | Quantizzazione | Senza esempio nel prompt | Con esempio one-shot |
|---|---|---|---|
| Qwen 2.5 7B Instruct | Q3_K_M | Instradamento invertito, conflitto **non rilevato** | Conflitto rilevato ✅, instradamento **ancora invertito** ❌ |
| Qwen 2.5 7B Instruct | Q4_K_M | Identico al Q3 (nessun miglioramento da sola quantizzazione) | Tutto corretto ✅✅✅ |
| Llama 3.1 8B Instruct | Q4_K_M | Non testato in questa configurazione | Tutto corretto ✅✅✅ |

Conclusioni tratte da questi dati:

1. **La quantizzazione da sola non basta** (Q3→Q4 senza esempio: nessun cambiamento).
2. **Il prompt è la leva decisiva**, non il modello: lo stesso Qwen Q4_K_M passa da
   "debole" a "corretto su tutto" solo aggiungendo un esempio.
3. **Q3_K_M resta debole solo sul compito che comunque non gli deleghiamo**
   (instradamento) — sui due compiti che restano davvero al locale (sintesi,
   conflitto) è alla pari con Q4_K_M e Llama 3.1 una volta dato l'esempio.
4. **Nessun vantaggio deciso di Llama 3.1 su Qwen**: stessa classe di grandezza,
   stesso risultato con lo stesso prompt. Non c'è motivo di introdurre una seconda
   famiglia di modello da mantenere.
5. **Il conteggio token non differenzia i modelli** (~576-602 token medi per
   risposta su tutti e tre, con esempio): il numero di token dipende dal testo del
   prompt e dal tokenizer di ciascun modello, non dalla quantizzazione o dai
   parametri — e qui il costo è comunque $0 (locale), quindi non è nemmeno un segnale
   economico da ottimizzare.

**Raccomandazione**: Qwen 2.5 7B Instruct **Q3_K_M** come modello di default per il
ruolo di dispatcher — più leggero, stesse prestazioni di Q4_K_M/Llama 3.1 sui compiti
che gli restano assegnati, offload GPU migliore sulla scheda da 6GB disponibile (24
layer su GPU contro i 18 stimati per Q4_K_M). Q4_K_M/Llama 3.1 restano un'opzione se in
futuro emergessero thread più complessi di questi 3 di prova dove serva più margine di
ragionamento — non misurato, solo un'ipotesi plausibile da riverificare se necessario.

### 6.4 Bug noto: caratteri accentati UTF-8 corrotti

Presente identicamente su **tutti e tre** i modelli testati (Qwen Q3_K_M, Qwen
Q4_K_M, Llama 3.1 8B Q4_K_M) — stesso sintomo esatto (es. "è" → `�`) su due famiglie di
modelli e tokenizer completamente diversi, servite dallo stesso `llama-server.exe`.
Questo è un indizio forte, non ancora confermato, che la causa **non è il modello**
(come ipotizzato nella nota preesistente in `ORCHESTRAZIONE_LAVORATORI.md`) ma
qualcosa di condiviso a valle nel pipeline — più probabilmente un mismatch di encoding
fra la risposta HTTP di `llama-server` e il lato Python/Windows che la legge (un
mismatch cp1252/UTF-8 è un problema comune su Windows). **Da investigare
separatamente**, non blocca il resto di questo design: il bug altera solo
occasionalmente il testo libero (`sintesi`/`conflitto`), mai la struttura JSON o
l'esito booleano di un campo.

**Ricetta pratica per quando qualcuno la investiga** (non fatto ora, solo annotato):
salvare sempre JSON strutturato dal dispatcher, mai decisioni basate sul testo libero
accentato (già coerente col design: instradamento è deterministico, non testuale);
riprodurre con un prompt che forzi accenti nella risposta per isolare il caso;
forzare `encoding="utf-8"` in ogni lettura/scrittura lato Python; controllare gli
header/il decoding della risposta HTTP di `llama-server` prima di sospettare ancora
il modello.

## 7. Punti aperti, non ancora decisi

- ~~`destinatari` con valore "tutti"~~ — **deciso**: enumerazione esplicita in v1,
  niente sentinel nello schema (converge Claude e Codex in revisione: con 4-6 agenti
  possibili l'enumerazione è già breve, e un valore speciale creerebbe due modi di
  dire la stessa cosa, ambiguo su se includa `locale`/`sistema`). Resta possibile
  come **comodità solo a livello di CLI** (`bacheca.py chiedi --a tutti` che espande
  internamente l'elenco completo prima di scrivere il record), mai come valore
  salvato nello schema.
- ~~Relazione fra `verdetto_umano` in bacheca e l'evento umano in `eventi.jsonl`~~ —
  **deciso** (§3.4): registri disaccoppiati, `bacheca.py approva` per il thread,
  evento `eventi.jsonl` riservato solo alle approvazioni materiali/irreversibili.
- **Rilevamento conflitti su scala**: lo spike ha validato solo 3 thread scritti a
  mano. Non sappiamo ancora se l'esempio one-shot generalizza a conflitti diversi da
  quello testato. **Non è un blocco da risolvere prima di procedere**: il design
  tratta già il locale come un segnalatore (`segnalazione_conflitto`), mai un
  decisore — in v1 un conflitto è un allarme per l'umano, non una sentenza, quindi un
  falso negativo su un caso sfumato degrada silenziosamente a "l'umano non viene
  avvisato", non a una decisione sbagliata presa in autonomia dal sistema.
- **Bug di encoding UTF-8** (§6.4): causa non confermata; ricetta di indagine
  annotata, non ancora eseguita.
- **Verifica empirica hook su Antigravity IDE** (§4.3): non ancora fatta sulla
  macchina reale. Test minimo proposto, **eseguibile fin da subito senza aspettare
  `bacheca.py`**: un hook `BeforeAgent` in `.gemini/settings.json` che stampa una
  stringa fissa e innocua (non serve chiamare `bacheca.py prossimo` per verificare se
  il meccanismo di iniezione funziona affatto). Solo dopo, se funziona, si collega
  davvero a `bacheca.py prossimo --agente gemini --formato hook`.
- **Revisione dello schema da parte di Gemini**: non ancora fatta. Questo documento e
  `schema/messaggio.v1.json` sono pensati per essere un punto di partenza concreto da
  criticare, non una versione finale.

## 8. Infrastruttura locale toccata per questi esperimenti (progetto `un altro progetto locale`)

Hardware di riferimento: NVIDIA Quadro RTX 3000, 6GB VRAM, Intel i7-9850H, 32GB RAM.

Motore di inferenza: **llama-server** (llama.cpp), non Ollama. Motivazione:
integrazione già esistente e tarata su questa GPU in due progetti (`un altro progetto locale` e,
tramite `adattatori/litellm.py`, l'orchestratore), con controllo fine su
`--n-gpu-layers`/`--ctx-size`/`--cache-type-k/v`/`--flash-attn`/`--parallel` per
ciascun modello. Passare a Ollama richiederebbe rifare questa tarazione senza
risolvere nessuno dei problemi reali trovati (che sono di prompt/modello, non di
motore di inferenza), e l'unico vantaggio tipico di Ollama — cambiare modello con un
comando — è già coperto dal meccanismo di selezione descritto sotto.

File modificati/aggiunti in `D:\Share\py\altro-progetto\0.6_app\` (fuori dall'orchestratore,
esplicitamente autorizzato):

| File | Modifica |
|---|---|
| `download_models.ps1` | Aggiunte due entry (Qwen 7B Q4_K_M in 2 parti, Llama 3.1 8B Q4_K_M), refactoring in funzione `Save-Parte` per supportare modelli multi-file, nuovo flag `-SkipConfirm` per uso non interattivo |
| `start_dbunico.bat` | Menu di selezione modello esteso da 4 a 6 voci (aggiunte Qwen 7B Q4_K_M e Llama 3.1 8B Q4_K_M) |
| `start_llama_only.ps1` (nuovo) | Avvia solo `llama-server.exe` (stessi parametri di `start.ps1`), senza FastAPI/Vite/indicizzazione — per sperimentare rapidamente cambiando modello |
| `start_llama_only.bat` (nuovo) | Stesso menu di selezione modello di `start_dbunico.bat`, senza i menu di chat/indicizzazione non pertinenti |

GPU layers assegnati per modello (6GB VRAM):

| Modello | Quantizzazione | `--n-gpu-layers` | Misurato / stimato |
|---|---|---|---|
| Qwen 2.5 VL 7B | Q4_K_M | 999 (tutti) | Preesistente, funzionante |
| Qwen 2.5 3B | Q4_K_M | 999 (tutti) | Preesistente, funzionante |
| Qwen 2.5 7B | Q3_K_M | 24 | Preesistente, funzionante |
| Qwen 2.5 7B | Q4_K_M | 18 | **Stimato** per proporzione rispetto al Q3_K_M, confermato nessun OOM in avvio reale durante gli esperimenti |
| Llama 3.1 8B | Q4_K_M | 15 | **Stimato**, confermato nessun OOM in avvio reale (log: "Quadro RTX 3000, 6143 MiB, 5107 MiB free" all'avvio) |

## 9. Stato di avanzamento e cosa resta da fare

Aggiornato più volte durante l'implementazione — questo documento non è più un
piano, riflette cosa è stato costruito davvero, in ordine cronologico:

1. **Fatto**: `bacheca.py` scritto secondo il disegno in §3.4 — schema, stato
   globale e per destinatario, comandi generici e umani. Bug reali trovati e
   corretti in corso d'opera: derivazione dello stato per destinatario (confronto
   timestamp a parità di secondo, corretto usando la posizione nella lista invece
   della stringa), eredità di `thread_id` da `correla_a` in `aggiungi` (prima ne
   apriva uno nuovo per sbaglio).
2. **Fatto e VERIFICATO EMPIRICAMENTE**: `.claude/settings.json` e
   `.codex/hooks.json` configurati con `SessionStart`/`UserPromptSubmit` →
   `bacheca.py prossimo --agente X --formato hook --evento <nome>`. Confermato in
   sessioni fresche reali: Claude Code inietta il contesto da solo; Codex lo stesso,
   dopo un'autorizzazione umana esplicita una tantum richiesta dall'IDE per gli
   hook trovati in un repository (gate di sicurezza atteso, non un difetto).
   `.gemini/settings.json` ha solo l'hook di test a stringa fissa (§4.3), **ancora
   da verificare** (Gemini bloccato da quota al momento del test) e non ancora
   collegato a `bacheca.py` — unico passo davvero bloccante rimasto sul lato hook.
3. **Fatto**: `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` aggiornati con l'istruzione
   esplicita di controllare la bacheca, fallback quando gli hook non scattano.
4. **Fatto**: coordinamento cooperativo sui file — `file_occupati()` (claim attivi
   non scaduti, rilascio automatico via `stato_thread` su risposta/chiusura,
   confronto timezone-aware come in `commit_replay.py`), `--file-modificati`/
   `--forza` su `prendi` con blocco su collisione salvo autorizzazione esplicita
   (tracciata in `metadati`), comando `occupati`. Deliberatamente fuori scope:
   integrazione con `git status`/diff.
5. **Fatto**: interruzione/ripresa — tipo `checkpoint` (trasparente allo stato
   globale via `_ultimo_rilevante`, ma rende comunque "pending" i suoi destinatari:
   due assi indipendenti), comandi `checkpoint`/`ripresa`/`emergenza` (quest'ultimo
   cattura `git status --short` best-effort, scrive un checkpoint broadcast e un
   file di snapshot, senza parametri obbligatori).
6. **Fatto**: `bacheca.py sintetizza --thread-id <id> [--modello ...]`, l'unico
   comando che chiama il modello locale (`adattatori/litellm.py`), stesso
   prompt/esempio one-shot validato nello spike (§6). Scrive sempre come
   `mittente=locale`: `segnalazione_conflitto` (a `umano` + partecipanti) se rileva
   un conflitto, altrimenti `sintesi`. `prossimo_destinatario` resta deterministico,
   mai chiesto al modello (§6.1). Verificato con mock e con una chiamata reale a
   Qwen 7B Q3_K_M sullo stesso thread di conflitto dello spike: rilevato
   correttamente.
7. **Fatto**: pannello **"🗂️ Bacheca Multi-Agente"** nella dashboard esistente
   (`interfaccia.py`/`interfaccia.html`, non una dashboard separata — riusa
   selettore multi-progetto, tema, framework già presenti). Contiene:
   - tabella thread (stato, ultimo mittente, chi aspetta, verdetto umano) con badge
     colorati e riga evidenziata per i conflitti segnalati, più banner in cima se
     ce ne sono di attivi;
   - elenco file attualmente in carico (da `occupati`);
   - drill-down della cronologia di un thread al click su una riga;
   - **feed live**: box che si aggiorna da solo ogni 5s aggiungendo solo i
     messaggi nuovi mai mostrati (nuovo endpoint `GET /api/bacheca/feed`),
     attivabile/disattivabile con un pulsante Avvia/Ferma — non parte da solo
     all'apertura della pagina, va richiesto esplicitamente;
   - pulsante **"▶ Rivivi"** per riprodurre animatamente un thread nel pannello
     "Live Agent Handoff" esistente (stesso meccanismo già usato per il replay di
     un commit reale, `passoSuccessivo`/`simTimer`, intervallo fisso 1.8s) — con
     una differenza voluta: **niente linee fra coppie arbitrarie di agenti** (il
     diagramma SVG ha percorsi fissi disegnati per il flusso di `capoturno.py`, non
     un grafo libero), solo il nodo di chi sta scrivendo che pulsa, più il log
     testuale con mittente/destinatari/tipo/testo.
   Nuovo helper difensivo `bacheca.leggi_messaggi_progetto()` (mirror di
   `registro.leggi_eventi_progetto()`) perché una bacheca corrotta non deve far
   cadere l'intera dashboard. Suite a 125/125 test (solo backend/route toccati dai
   test; il frontend è verificato a vista).
8. **Da fare**: revisione di questo documento e dello schema da parte di Gemini —
   non ancora avvenuta.
9. **Da fare**: verifica empirica dell'hook Antigravity/Gemini (§4.3), rimandata a
   quando Gemini non sarà più bloccato da quota.

Punto 2 (hook Gemini/Antigravity) e punto 8 (revisione Gemini) restano gli unici
passi davvero aperti — tutto il resto in questa lista è stato costruito, testato e
verificato (a mano, con mock, o entrambi) durante questa sessione di lavoro.
