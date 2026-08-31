# Proposta: riuso di idee di Amoeba nell'orchestratore

**Stato**: proposta aperta alla revisione degli altri agenti, non decisa.
**Autore**: Claude, su richiesta dell'utente (2026-08-28).
**Origine**: analisi di [Amoeba](https://useamoeba.com/) ("World's first
multiplayer IDE"). Stesso pattern del documento su
[Weft](PROPOSTA_RIUSO_IDEE_WEFT.md): il giudizio complessivo NON è "usiamo
Amoeba", è "rubiamo idee di design e le realizziamo con i mezzi che abbiamo".

**Giudizio complessivo su Amoeba**: prodotto commerciale chiuso (download
Electron macOS/Windows, prezzo flat per team in arrivo, non open-source), che
costruisce quasi esattamente le §4-5 del nostro piano di industrializzazione:
coordinamento multi-agente su repo condiviso, riuso degli abbonamenti senza
markup ("never sits between you and your provider's bill"), collision
prevention, ownership, governance dashboard ("Mission Control"), "Brain"
locale con opzione self-hosted per l'enterprise. **Non adottabile**: è un IDE,
e adottarlo butterebbe via il nostro punto di forza (CLI/hook-based,
agent-agnostic, non-IDE — coordina gli strumenti che usi già). Ma è anche
**validazione di mercato** (qualcuno ha preso soldi per farlo) e va annotato
in §4 come dato concreto sul "chi lo comprerebbe". Non risolve il problema
`agy` headless: nessuna menzione di CLI/API/headless, verosimilmente stesso
limite di Antigravity.

## Le idee che valgono

Dalle pagine `docs/concepts/*` e `docs/collaboration/live-sessions` di Amoeba,
citazioni testuali:

1. **Piano condiviso con step posseduti.** *"A session ... has exactly one
   branch and one plan, shared by everyone in it."* *"Steps have owners and
   statuses everyone can see"*; i pari possono *"select steps and offer to take
   them"*. Lavoro non posseduto = trasferimento immediato; lavoro iniziato =
   serve l'ok del proprietario.
2. **Collisione attiva, non passiva.** Non lock di file: *"task-level ownership
   and live state awareness ... your agent knows what every peer agent is
   doing"*. Se un agente punta a un task già coperto *"stops, shows their
   progress, and offers the safe move: join their session, or take only the
   steps that are provably unstarted"*. Regola: *"Provably safe splits happen
   automatically with a passive notice to the other side. Anything started or
   assigned always asks first. Nothing is ever silently duplicated."*
3. **"Brain": note strutturate ancorate a file e commit.** *"The Brain keeps
   short, structured notes pinned to specific files and commits: decisions,
   gotchas, conventions."* E — dettaglio che ci manca — *"Git flags notes when
   code moves, prompting rewrites to maintain accuracy."*
4. **Il lavoro è di una persona, mai di un agente.** *"Work is assigned to
   people, never to agents. A person holds work; their agent executes it."*
   Con *"visible account sponsorship before execution"*.

## Cosa abbiamo già (per non reinventarlo)

- **Bacheca event-sourced** = il substrato di "live state awareness" (chi
  aspetta cosa, chi ha preso in carico, dove sono i conflitti).
- **Lease sui file** (`bacheca.py prendi --file-modificati`) = collisione
  *rilevata*, e da `705d395` un lease per-agente sul dispatch + tetto di hop.
- **`motore_flusso.py`** = deriva la *fase* di un thread da prove reali
  (eventi correlati per `thread_id`) — un abbozzo di "plan".
- **`registro` `verdetto_umano`** + `agente=umano` = l'approvazione umana come
  fatto registrato.
- **Dashboard** = una "Mission Control" parziale.
- **`dashboard_freschezza`** (impronta blake2b dei moduli, rilevamento
  disallineamento) = la macchina per "flag quando il codice si muove".

## I buchi rispetto alle 4 idee

- **(a) Collisione passiva, non attiva.** Il lease dice *dopo* che un file è
  in carico. Non c'è il gesto "prima di iniziare, controlla se il lavoro è
  coperto e offri una mossa sicura". Il costo di non averlo si è visto il
  2026-08-28: Codex e Gemini hanno reagito entrambi allo stesso thread veloce,
  il ping-pong Fase 0. `705d395` ha messo il lease, non il comportamento.
- **(b) Nessun "piano con step posseduti" di prima classe.** Oggi la divisione
  del lavoro (task A/B/C ai tre agenti) l'ha scritta l'umano in prosa in un
  messaggio bacheca. Nessuno la verifica, nessuno la aggiorna, nessuno può
  "offrire di prendere" lo step 3.
- **(c) Nessuna nota ancorata al codice.** `docs/`, memoria, CLAUDE.md: niente
  è appuntato a `file:funzione`/`file:range` in modo da comparire quando un
  agente sta per toccare quell'area, né viene segnalato stantio quando quella
  funzione si sposta.
- **(d) Identità per ruolo, non per persona.** `agente` è
  `claude|codex|gemini|umano` — un ruolo. Due operatori sulla stessa "claude"
  collidono (già annotato in §10 del piano, "multi-operatore con account
  propri").

## Proposta 1 — Piano dichiarato con step posseduti + regola di collisione attiva

Le idee 1 e 2 sono un'unica proposta coerente: dare al thread un **piano** che
sia un oggetto condiviso, e una **regola** su chi può agire su cosa.

- Al thread (schema messaggio v2 o campo opzionale) si aggiunge un tipo
  `piano` con una lista di `passi`, ognuno: `id`, `descrizione` (una frase),
  `proprietario` (`nil` | agente | umano), `stato`
  (`non_iniziato` | `in_corso` | `fatto` | `bloccato`), `write_set` atteso
  (file/glob). Il piano è append-only come tutto il resto: si "modifica" un
  passo aggiungendo un evento `passo_aggiornato`, non riscrivendo.
- `bacheca.py` nuovo sottocomando `offri-passo` / `prendi-passo`: un agente
  può **offrire di prendere** un passo `non_iniziato` (trasferimento
  immediato con avviso passivo all'autore del piano) o `in_corso` di un altro
  (richiede conferma del proprietario o dell'umano). Ricalca *"select steps
  and offer to take them"* di Amoeba.
- **Regola di collisione attiva**, applicata dal watcher/postino prima di
  dispatchare e da `prompt_fisso` come istruzione all'agente:
  - passo `non_iniziato` e `write_set` che non si sovrappone a nessun passo
    `in_corso` → si può procedere, con avviso passivo in bacheca;
  - passo `in_corso` di un altro, o `write_set` sovrapposto → **non si
    dispatcha / non si agisce**: si posta una nota "coperto da <passo/agente>,
    serve join o decisione umana". *"Anything started or assigned always asks
    first. Nothing is ever silently duplicated."*
- Beneficio diretto: è la versione concreta dei guardrail DEC.3 di §13
  (`max_hop`, "niente duplicazione silenziosa") e il fix reale del
  ping-pong/doppia-reazione, non una toppa sui timeout.
- Nessun motore nuovo: il piano **descrive e vincola il dispatch**, non
  esegue. L'esecuzione resta agli agenti.

Costo stimato: `schema/messaggio.v2.json` (o campo v1 opzionale) +
`bacheca.py` (serializzazione, `offri-passo`/`prendi-passo`, calcolo
sovrapposizioni write_set) + un check in `dashboard_risvegli` /
`postino.dispatch` + `prompt_fisso` + test. La dashboard può poi disegnare il
piano dal JSON (già allineato al punto 3 del piano di industrializzazione).

## Proposta 2 — Note di codice ancorate ("Brain povero")

L'idea 3 con i mezzi che abbiamo:

- Un file `dati_locali/orchestrazione/note_codice.jsonl` (append-only,
  gitignorato come gli altri dati locali): ogni nota ha `ancora`
  (`percorso` + `simbolo` opzionale, es. `postino.py::_blocco_stato`, o
  `percorso` + range di righe), `testo` (breve: decisione, gotcha,
  convenzione), `autore`, `creata_il`, e `impronta_ancora` (blake2b del
  blocco ancorato, riusando la macchina di `dashboard_freschezza`).
- L'hook `SessionStart`/`UserPromptSubmit`, o un check in `sentinella`,
  inietta le note la cui ancora è nei file che l'agente sta per toccare —
  non tutte, solo quelle rilevanti all'area di lavoro. È il "core snello +
  doc on-demand" della discussione sui token, in versione granulare.
- Quando l'`impronta_ancora` non combacia più (il codice si è mosso), la
  nota viene marcata `da_rivedere` e segnalata all'autore — *"Git flags
  notes when code moves"*. Non si cancella da sola: una nota stantia è un
  fatto, non spazzatura.
- Sostituisce le annotazioni sparse in `docs/` e nei commenti per i "gotcha
  locali" (es. la nota su `_blocco_stato` / `SOGLIA_LOCK_ABBANDONATO`,
  la CWD di `sentinella.py`, l'autocrlf che fa scattare l'auto-riavvio).

Costo stimato: uno schema `schema/nota_codice.v1.json` + un modulo
`note_codice.py` (append, query per file, verifica impronta) + aggancio
all'hook + test. Nessun demone.

## Cosa NON si propone

- **Adottare Amoeba** o qualunque IDE/runtime di coordinamento esterno:
  lock-in su un prodotto chiuso, contro il principio "zero dipendenze
  a pagamento/fragili" e contro il posizionamento non-IDE.
- **Un motore di esecuzione del piano**: il piano dichiarato **descrive e
  vincola**, non esegue. Come per il flusso dichiarato (Weft).
- **Identità per-persona ora**: la idea 4 è giusta ma si sovrappone a
  D2/D4-D14 e al lavoro multi-operatore già rimandato in §10; va con lo
  stesso cerimoniale, non in questa proposta. Qui si annota solo che la
  formulazione di Amoeba ("una persona possiede il lavoro, il suo agente lo
  esegue", "visible account sponsorship") è il bersaglio giusto quando ci si
  torna.
- **Toccare il registro eventi**: resta l'audit trail, invariato.

## Requisiti dalla revisione (2026-08-31, bacheca `fedf15e7`)

Codex e Gemini hanno rivisto entrambe le proposte e sono favorevoli. Questi
requisiti sono vincolanti — la proposta diventa spec, non solo idea.

### Proposta 1 — requisiti (Codex)

1. **Campo `piano` opzionale su `messaggio.v1`**, validato da schema,
   **proiettato da eventi append-only**. Niente `messaggio.v2` né migrazione
   finché il primo slice non è provato.
2. **Ogni passo**: `id` immutabile; `thread_id` / `repo` / `branch` espliciti;
   `proprietario` e attore dell'aggiornamento come campi **separati**;
   `versione` (o precondizione di stato) + `idempotency_key`.
   `prendi-passo` / `offri-passo` fanno **compare-and-set atomico** sulla
   `versione`: due agenti non possono acquisire lo stesso passo.
3. **`write_set` normalizzato**: path relativo alla root del repo, separatori e
   case normalizzati per Windows; match glob **conservativo**. `write_set`
   mancante, dinamico o ambiguo ⇒ **niente dispatch automatico**, serve
   chiarimento o l'umano. Campo `read_set` distinto: leggere in comune è
   lecito, scrivere no — la sovrapposizione che blocca è write∩write e
   write∩read, mai read∩read.
4. **Enforcement server-side** in `postino` / `dashboard_risvegli` e nei
   sottocomandi `bacheca`. Il prompt (`prompt_fisso`) e la dashboard sono
   **solo spiegazione/visibilità, mai fonte di autorità**. Il motivo del
   diniego è registrato come evento; **nessun retry automatico** (aggancia il
   fix retry-loop di §14.2).
5. **Handoff di un passo `in_corso`**: proposta + approvazione esplicita del
   proprietario o dell'umano. **Mai** trasferimento implicito da timeout.
   (Un passo `non_iniziato` senza proprietario: trasferimento immediato con
   avviso passivo.)
6. **Ordine di costruzione**: (a) modello + `piano` in bacheca, calcolo overlap,
   test di concorrenza/idempotenza; (b) enforcement nel dispatch; (c) UI
   checklist e bottoni — **solo dopo**.

### Proposta 1 — UX (Gemini)

- Widget "Corsie/Checklist" per thread con piano: passi ordinati, badge stato
  (`non_iniziato`/`in_corso`/`fatto`/`bloccato`) + badge proprietario. **I badge
  derivano SOLO dalla proiezione validata degli eventi, mai da stato locale
  della UI** (Codex).
- Sovrapposizioni `write_set` evidenziate in ambra/rosso **prima** che scatti il
  blocco, col motivo esplicito ("Passo 2 fermo: write_set sovrapposto su
  `postino.py` con Passo 1 di Claude"). Distinguere sempre **avviso** da
  **blocco**.
- Bottoni human-in-the-loop che **non sono azioni dirette**: "Riassegna passo" →
  crea una proposta; "Approva handoff" → registra un consenso una-tantum;
  "Forza sblocco" → richiede motivazione + approvazione umana esplicita, con
  audit.

### Proposta 2 — requisiti (Codex + Gemini)

- **Ancora = `file` + `range` di righe + `hash` del contenuto del blocco**. Il
  `simbolo` (es. `postino.py::_blocco_stato`) è **solo descrittivo**: il
  resolving dei simboli è fragile, non ci si basa per l'aggancio.
- Una **nota stantia resta visibile** e non viene **mai** reiniettata
  automaticamente come istruzione (una nota `da_rivedere` è contesto "attento,
  questo potrebbe non valere più", non un ordine).
- Azione "Aggiorna impronta" nella UI ⇒ **obbliga a rivedere il testo** della
  nota, non solo a ricalcolare l'hash — altrimenti si certifica alla cieca una
  conoscenza vecchia.
- Widget "Knowledge Base / Gotcha" in dashboard, note raggruppate per
  file/modulo; warning evidente quando `hash_ancora` non combacia.

## Ordine e verifica (aggiornato 2026-08-31)

Priorità capovolta rispetto alla bozza: **la Proposta 2 (note di codice) è
ASAP** per decisione dell'umano.

1. **Proposta 2 — note di codice** (§14.1 del piano). Schema + modulo + verifica
   impronta + aggancio hook + prime note reali migrate. Test: serializzazione,
   query per area, transizione `attiva`→`da_rivedere`.
2. **Proposta 1 — piano + collisione attiva** (§14.3 del piano). Nell'ordine di
   Codex: modello+overlap+test → enforcement dispatch → UI. Ogni incremento
   passa dal gate (`sentinella.py`) e viene registrato.

Nessuna dipendenza fra le due; la 2 è più piccola e va per prima.
