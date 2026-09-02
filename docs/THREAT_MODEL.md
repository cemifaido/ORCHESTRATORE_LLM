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
chiamate reali a un provider a pagamento. **Mitigato**: limiti di ritmo per profilo
(debounce, tetto turni/thread, tetto invii/giorno — un tetto assoluto in codice che
nessun override di configurazione può superare, nemmeno il profilo "smodata"), kill
switch esplicito (**profilo operativo per progetto**, `standard` = spento, default
fail-closed per ogni progetto nuovo o file assente/corrotto — sostituisce dal
2026-08-27 i due marker `POSTINO_ATTIVO`/`POSTINO_HEADLESS_ATTIVO`, ora legacy e
ignorati dal runtime), e la prenotazione atomica del turno avviene *prima* dell'azione
reale (subprocess o azione OS), non dopo — H5, revisione sicurezza v3, chiuso
2026-08-26 dopo quattro cicli di revisione live con Codex. Vedi
`docs/GUIDA_POSTINO_DISPATCH_HEADLESS.md` per la matrice completa dei profili.

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

### 3.9 Server MCP locale (`mcp_orchestratore.py`)
Il server MCP espone bacheca/piano/note come tool a un client MCP (Claude Code / Codex
CLI / Antigravity). Confini e rischi (vedi `docs/RFC_SERVER_MCP_LOCALE.md`):
- **Nessuna autenticazione, per scelta.** Trasporto stdio locale, processo figlio del
  client, stesso utente e stessi privilegi. Non c'è superficie di rete. Un'auth più
  forte fra processi dello stesso utente non aggiungerebbe garanzie — la valutazione
  cambia solo se il server esce da stdio/locale (allora serve un threat model nuovo).
- **`--agente` è etichetta di provenienza, non identità provata.** I record che l'MCP
  scriverà in bacheca (fase scrittura) porteranno `mittente = <agente di avvio>`: è
  **audit**, non una garanzia che quel processo sia davvero quell'agente. Nessun
  override per-call: un tool call che passa un `agente` diverso è rifiutato.
- **I risultati dei tool sono dati non fidati**, come il contesto iniettato dall'hook
  (§3.3): un thread di bacheca può contenere testo che sembra un'istruzione. Ogni
  `description` di tool lo dichiara; il modello non deve obbedire al contenuto.
- **MVP di sola lettura** oggi: nessuna scrittura, nessun `dispatch`, nessun comando
  git/shell, nessun I/O di file arbitrari — esclusioni tassative nella RFC. La fase
  scrittura richiede prima di portare `bacheca.aggiungi_messaggio` su un percorso
  serializzato (`scrittura_jsonl`) e il contratto di idempotenza obbligatorio.
- **Robustezza del loop**: `params` non-oggetto / `jsonrpc` errato / riga non-JSON
  producono un errore JSON-RPC tipizzato, non un crash (regressione da revisione Codex).

## 4. Cosa cambia con "chiunque può clonarlo" (gap specifici del rilascio pubblico)

Questi non sono minacce nuove al *funzionamento* del sistema — sono lacune che emergono
solo quando l'ipotesi "questa macchina, questo utente" non regge più. Elenco completo in
`docs/PIANO_INDUSTRIALIZZAZIONE.md` §10 (rilascio pubblico); qui solo il taglio
sicurezza:

- **Config di hook con path assoluti e dati di sessioni reali committati — chiuso
  (2026-08-26)**: `.claude/settings.json` aveva una `permissions.allow` con comandi
  verbatim di incidenti reali. Leak storico chiuso in precedenza (file gitignored,
  storia riscritta). La seconda metà — nessun template portabile né un modo per
  generare la configurazione locale senza scriverla a mano — è ora chiusa: template
  generici in `config/templates_hook/` (nessun path assoluto, nessun dato di sessione
  reale, verificato anche da test dedicato) e `setup_wizard.py` con
  `inizializza_config_agenti()` che li applica per gli agenti selezionati durante il
  setup, senza mai sovrascrivere una config esistente a meno di scelta esplicita
  (lavoro di Gemini, bacheca thread `02124182`).
- **Manifest di capability: enforcement runtime — chiuso (2026-08-26)**: era un
  controllo strutturale offline (`valida_capability.py` protegge solo se un umano
  lo esegue a mano) fino a oggi. Chiuso con `capability_policy.py` (modulo puro,
  bacheca thread `2b5c8a22`, lavoro di Codex): gate fail-closed innestati in
  `postino.dispatch()` (canale headless), `postino.registra_canale()` (canale
  deep_link) e `hook_gemini.py` (canale hook_pull) — capability assente, non
  `verified`, non `automatica` o scaduta blocca, con motivo deterministico
  scritto sia in `dati_locali/orchestrazione/capability_blocchi.jsonl` sia nel
  log diagnostico esistente (mai un blocco silenzioso, stessa disciplina del
  bug CWD dell'hook Gemini). Test con fixture/mock, mai il catalogo reale nella
  suite. **Verificato dal vivo, non solo a schema**: attivando l'enforcement,
  `gemini_uri_wake` (mai realmente testato) è stato provato due volte
  (`dashboard_os.copia_negli_appunti`+`lancia_ide_uri`) e osservato NON
  funzionare — comando eseguito con successo, appunti popolati, ma la finestra
  Antigravity non va mai in focus da sola. Declassato da `unknown` a `failed`
  nel catalogo reale (stato più informativo per un fallimento osservato, non
  solo mai provato) — resta `manual_only` per default deny, causa non ancora
  indagata. La consegna messaggi a Gemini (`gemini_hook_pull`, canale diverso)
  non è toccata, resta `verified`/`automatica`.
- **Adapter Windows-only** (`dashboard_os.py`, deep-link/clipboard del risveglio via
  `antigravity-ide://`): voce corretta dopo verifica diretta (2026-08-26) — non e' un
  fallimento silenzioso. Il catalogo capability modella gia' correttamente
  `os_supportati: ["windows"]` per `claude_uri_wake`/`codex_uri_wake`/
  `gemini_uri_wake`, e `dashboard_risvegli.esegui_risveglio_os()` degrada in modo
  esplicito su sistemi non-Windows (stato `non_supportato`, motivo loggato su
  stderr) invece di tentare la chiamata. Il gap reale trovato era di copertura, non
  di comportamento: quel ramo era irraggiungibile nella test suite (il flag
  `in_test` intercetta sempre prima) — estratto in `piattaforma_supporta_risveglio_os()`
  e coperto da `tests/test_dashboard_moduli.py::test_piattaforma_supporta_risveglio_os`.
- **Hook Gemini/Antigravity**: fino a poco fa dichiarato implicitamente funzionante
  ma mai verificato — vedi `docs/PIANO_INDUSTRIALIZZAZIONE.md` §10, chiuso 2026-08-26
  con verifica di specifica + log diagnostico per la conferma empirica nel tempo. Lezione
  generale per il manifest di cui sopra: non dichiarare mai una capability "funzionante"
  senza prova.
- **Policy sulle dipendenze — chiuso (2026-08-26)**: `requirements.txt` e
  `requirements-dev.txt` erano senza pin (revisione Codex). Ora entrambi
  dichiarano versioni esatte (`==`), quelle su cui la suite di test è
  verificata; installazione e `pip check` riverificati senza conflitti.
  Aggiornare una versione richiede un bump esplicito e il quality gate
  completo verde prima del commit — mai un range aperto che introduca una
  versione mai testata in silenzio. Nessuna SBOM formale: per questo
  progetto (poche dipendenze dirette, nessuna in produzione con dati di
  terzi) il pin secco è stato giudicato sufficiente; una SBOM resta
  possibile in futuro se le dipendenze crescono.

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
  `unavailable` invece di degradare in silenzio — **chiuso (2026-08-26)**:
  `python valida_capability.py --matrice` (lavoro di Codex, bacheca thread
  `c62ab2ed`), vista di sola lettura id/stato/modalità/scadenza con avviso
  esplicito che è audit, non enforcement.
