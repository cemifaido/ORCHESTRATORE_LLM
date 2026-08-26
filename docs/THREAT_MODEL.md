# Threat model

**Stato**: bozza (step 2 del piano di rilascio open-source, `docs/PIANO_INDUSTRIALIZZAZIONE.md`
§8). Autore iniziale: Claude, su richiesta dell'umano — segue lo step 1 (inventario, chiuso
2026-08-26). Da rivedere con Codex e Gemini prima di considerarlo chiuso, stesso schema
usato per l'inventario (bacheca thread `89b5d378`).

**Scopo di questo documento**: non introduce protezioni nuove — consolida in un unico
posto le difese già costruite (e verificate) durante le due revisioni di sicurezza di
questa sessione, e distingue esplicitamente cosa cambia quando il progetto passa da "uso
di un solo utente fidato" a "chiunque può clonarlo". Il gate di sicurezza per uno scenario
multiutente/azienda (§7 del piano) resta un passo successivo, fuori scopo qui.

## 1. Asset da proteggere

- **La macchina dell'utente**: file system, credenziali dei provider LLM (chiavi API,
  sessioni OAuth), altri progetti presenti sulla stessa macchina.
- **L'integrità del registro/bacheca** (`eventi.jsonl`/`messaggi.jsonl`): sono log
  append-only usati come base di fiducia per decisioni (rate limit, audit, coordinamento
  fra agenti) — una scrittura persa o corrotta non è solo un bug estetico.
- **Il budget/costo**: chiamate reali a provider a pagamento (dispatch headless,
  litellm), possono costare denaro se non limitate.
- **La fiducia dell'operatore umano**: nessuna azione irreversibile (commit, push,
  cancellazioni) deve avvenire senza un passaggio umano esplicito.

## 2. Attori e confini di fiducia

| Attore | Fidato? | Note |
|---|---|---|
| L'utente umano alla tastiera | Sì | Ha accesso completo per design (dashboard loopback, CLI locali). |
| Gli agenti LLM (Claude/Codex/Gemini) in sessione interattiva | Parzialmente | Eseguono codice/comandi per conto dell'utente, ma dentro i vincoli della sentinella/postino, non con privilegi arbitrari. |
| Il contenuto dei messaggi in bacheca (testo scritto da un agente o dall'umano) | **No** | Può contenere testo che assomiglia a istruzioni (prompt injection) — vedi §3.3. |
| `config/comandi.json` di un progetto integrato | **No** | Dato di configurazione non firmato — vedi §3.1. |
| Un altro processo/utente sulla stessa macchina | Parzialmente | Vedi CSRF su bind loopback, §3.2. |
| Un contributor esterno (dopo il rilascio pubblico) | **No**, finché non revisionato | Fuori scopo per questo step — politica di contribuzione è nel backlog §7 del piano. |

## 3. Minacce e mitigazioni esistenti (verificate in questa sessione)

### 3.1 Esecuzione di comandi arbitrari via `comandi.json`
Un `config/comandi.json` malevolo (o solo malformato) potrebbe far girare un binario
arbitrario fuori dalla cartella del progetto. **Mitigato, con un prerequisito esplicito**:
`sentinella.py` limita sia *quale binario* può girare (`ESEGUIBILI_AMMESSI`, allowlist)
sia *dove* (`radice_progetto` obbligatoria, containment check) — C2, revisione sicurezza
v3, chiuso 2026-08-26. Questo presuppone che la radice del progetto e `comandi.json`
stesso siano scrivibili solo dall'utente fidato (revisione Codex): se un attaccante ha
già scrittura nella radice, o può introdurre un symlink/reparse point che punta fuori
dalla radice consentita, l'allowlist da sola non è un confine di sicurezza completo — il
containment check va sempre accompagnato da quel prerequisito, non trattato come
sufficiente in ogni scenario di compromissione.

### 3.2 CSRF su bind loopback
Con `ORCHESTRATORE_HOST=127.0.0.1` (default) nessuna richiesta all'API richiede
autenticazione: una pagina malevola nello stesso browser potrebbe far partire richieste
verso la dashboard. **Accettato come rischio residuo** per l'uso dichiarato (singolo
utente per macchina) — documentato in `docs/ORCHESTRAZIONE_LAVORATORI.md` (M8). Mitigazione
futura (token locale per-sessione) solo se la macchina diventa condivisa fra più persone.

### 3.3 Prompt injection via contenuto della bacheca
Il testo di un messaggio (scritto da un agente o recuperato da fonti esterne) potrebbe
contenere frasi che sembrano istruzioni rivolte al modello che lo riassume/dispatcha
("ignora le istruzioni precedenti", ecc.). **Ridotto, non azzerato** (revisione Codex —
delimitatori e istruzione di sistema sono difesa in profondità, non una mitigazione
assoluta): ogni prompt che include contenuto di bacheca lo delimita esplicitamente
(`<<<INIZIO_THREAD>>>`/`<<<FINE_THREAD>>>` in `bacheca_sintesi.py`,
`<<<INIZIO_CRONOLOGIA>>>`/`<<<FINE_CRONOLOGIA>>>` in `dashboard_risvegli.py`) e il prompt
di sistema istruisce esplicitamente a trattare quel contenuto come dato da riassumere, mai
come comando da eseguire. Resta possibile un riassunto o un dispatch semanticamente
influenzato dal testo iniettato: il contenuto della bacheca resta **non fidato** e non può
mai conferire autorità (es. autorizzare da solo un'azione irreversibile) — solo un umano
o un evento del registro verificato possono farlo.

### 3.4 Automazione fuori controllo / costi non limitati
Il dispatch headless (postino) potrebbe, senza limiti, generare un numero illimitato di
chiamate reali a un provider a pagamento. **Mitigato**: `LIMITI_PREDEFINITI` (debounce
300s per coppia agente+thread, tetto 3 turni per thread, tetto 10 invii/giorno),
kill-switch esplicito (`POSTINO_ATTIVO`/`POSTINO_HEADLESS_ATTIVO`, default **spento**,
fail-closed), e la prenotazione atomica del turno avviene *prima* dell'azione reale
(subprocess o azione OS), non dopo — H5, revisione sicurezza v3, chiuso 2026-08-26 dopo
quattro cicli di revisione live con Codex.

### 3.5 Race condition su stato condiviso
Scritture concorrenti su `postino_stato.json`/`eventi.jsonl`/`messaggi.jsonl` potrebbero
perdere aggiornamenti (lost update). **Mitigato**: lock a file (`os.O_CREAT | os.O_EXCL`,
atomico sia su Windows sia POSIX) più scrittura atomica (`tempfile` + `os.replace`), con
soglia di abbandono del lock indipendente dal timeout del chiamante (bug corretto
2026-08-26 sia in `postino.py` sia nel nuovo contratto condiviso `scrittura_jsonl.py`).

### 3.6 Path traversal / SSRF
- La cartella di lavoro di un comando sentinella deve stare dentro la radice del
  progetto (stesso meccanismo di 3.1, con lo stesso prerequisito: radice/config scrivibili
  solo dall'utente fidato — un attaccante che può introdurre un symlink/reparse point
  fuori dalla radice non è coperto solo dal containment check).
- Le sonde di rete (`verifiche_connessione`) sono ristrette a host locali/loopback,
  per evitare port-scanning di rete interna tramite un `comandi.json` malevolo (M5).

### 3.7 Segreti nei log
L'output catturato da un comando potrebbe contenere per errore una chiave API stampata
a schermo. **Mitigato, non garantito**: `sentinella.redigi_segreti()` pattern-matcha e
redige chiavi/token dai formati **noti** (`sk-...`, `AIza...`, header Bearer, coppie
chiave=valore comuni) prima di salvare il log (L1) — un segreto in un formato non
riconosciuto passa comunque. Regola operativa: il log non va mai trattato come un canale
sicuro solo perché esiste la redazione; resta un rischio residuo da tenere presente
soprattutto in una release clonabile da chiunque, dove il set di provider/formati di
chiave in uso non è più prevedibile come su questa singola installazione.

### 3.8 Parsing fragile di risposte LLM
Il vecchio pattern `testo.index('{')...testo.rindex('}')` per estrarre JSON da una
risposta del modello si rompeva con oggetti annidati o testo spurio dopo il JSON — non
uno scenario di attacco diretto, ma un punto dove un input malformato (anche innocuo)
produceva un comportamento indefinito. **Mitigato**: `estrai_primo_oggetto_json()` usa
`json.JSONDecodeError`/`raw_decode` invece di ricerca di stringa (M3).

## 4. Cosa cambia con "chiunque può clonarlo" (gap specifici del rilascio pubblico)

Questi non sono minacce nuove al *funzionamento* del sistema — sono lacune che emergono
solo quando l'ipotesi "questa macchina, questo utente" non regge più. Elenco completo in
`docs/PIANO_INDUSTRIALIZZAZIONE.md` §10 (rilascio pubblico); qui solo il taglio
sicurezza:

- **Config di hook con path assoluti e dati di sessioni reali committati**
  (`.claude/settings.json` aveva una `permissions.allow` con comandi verbatim di
  incidenti reali) — per un fork di terzi questo non è solo "non funziona", è un file
  che non dovrebbe essere distribuito così com'è. Serve un template portabile o un
  comando di init che generi la configurazione locale, mai committata.
- **Manifest di capability implementato ma non collegato al runtime** (proposta di
  Codex, Step 3 del piano chiuso il 2026-08-26 — nota aggiornata dopo revisione Codex
  del 2026-08-26 sul gap rimasto): `schema/capability.v1.json` +
  `valida_capability.py` + `config/capability_catalogo.json` esistono e sono
  testati, con `default deny` (verified richiesto per `automatica`) e scadenza a
  90 giorni imposti come invarianti del validatore. **Ma è un controllo
  strutturale offline, non enforcement a runtime**: nessun punto del codice
  (`postino.py`, `sentinella.py`, `registro.py`, dispatch) legge il catalogo
  prima di agire — l'unico modo in cui l'invariante protegge davvero qualcosa
  oggi è se un umano esegue `valida_capability.py` e legge l'esito. Finché non
  esiste una lettura runtime fail-closed del catalogo prima di ogni azione
  automatica, non va descritto né percepito come un gate di sicurezza attivo:
  è un audit strutturale, non un enforcement. Implementare la lettura runtime
  fail-closed è un item futuro esplicito, da fare prima di qualunque
  installer/configuratore automatico che si affidi al catalogo per decidere
  cosa è sicuro eseguire.
- **Adapter Windows-only presentati come impliciti, non come capability opzionale**
  (`dashboard_os.py`): corretto avere un adapter Windows-specifico, ma un nuovo utente
  su un sistema non supportato deve vedere un degrado esplicito, non un fallimento
  silenzioso o un'assunzione implicita che "ovviamente" gira solo su Windows.
- **Hook Gemini/Antigravity**: fino a poco fa dichiarato implicitamente funzionante
  ma mai verificato — vedi `docs/PIANO_INDUSTRIALIZZAZIONE.md` §10, chiuso 2026-08-26
  con verifica di specifica + log diagnostico per la conferma empirica nel tempo. Lezione
  generale per il manifest di cui sopra: non dichiarare mai una capability "funzionante"
  senza prova.
- **Nessuna SBOM/lockfile o policy sulle dipendenze** (revisione Codex): per un clone
  pubblico, sapere esattamente quali versioni di `fastapi`/`uvicorn`/`pydantic`/
  `jsonschema`/`rfc3339-validator`/`litellm` sono verificate (non solo dichiarate in
  `requirements*.txt` senza pin) diventa parte della superficie di fiducia — un utente
  esterno non ha il contesto implicito di questa installazione per giudicare se una
  versione è sicura.

## 5. Esplicitamente fuori scopo per questo step

Rimandato al gate "prima del multiutente/azienda" (§7 del piano, non iniziato):
separazione per progetto/tenant, ACL e autorizzazione multi-persona, retention/
cancellazione/export dei dati, integrità crittografica e rotazione del log append-only,
provenance dei contenuti, consenso e diritti sui dati. Nessuno di questi blocca un
rilascio open-source a singolo utente — bloccano solo l'uso aziendale/condiviso, una
decisione ancora non presa (§7).

## 6. Criteri di uscita proposti (Codex, bacheca thread `89b5d378`)

- Scansione di file tracciati **e** storia git per path assoluti, ID utente/home,
  identificativi di thread/messaggi reali, marker `TEST_*` residui.
- Un clone pulito, su una macchina senza nessun client AI installato **e senza i loro
  hook/config locali residui** (revisione Codex: non basta verificare l'assenza dei
  client, va verificata anche l'assenza di configurazione locale pre-esistente che
  altrimenti maschererebbe un problema di generalizzazione), con il core
  (registro/bacheca/sentinella/dashboard) funzionante in modalità manuale.
- Una matrice di capability che riporti esplicitamente `enabled`/`manual_only`/
  `unavailable` invece di degradare in silenzio.
