# Regole Generali di Programmazione da Rispettare Sempre

## Scopo

Questo documento e il mantra operativo per programmare in modo ordinato, riusabile e verificabile.
Vale per questo progetto e per i prossimi: quando nasce un dubbio su dove mettere una cosa, quanto
spingere un refactor, come testare o come scrivere nomi e testi, si parte da qui.

La regola principale e semplice: il codice deve essere facile da capire, modificare, testare e
buttare via quando non serve piu. Ogni scelta tecnica deve aiutare almeno uno di questi obiettivi.

## Principi non negoziabili

- Capire prima di cambiare: leggere il flusso esistente, i contratti e i test prima di intervenire.
- Separare responsabilita: dominio, I/O, UI, persistenza, configurazione e generazione output non
  devono mescolarsi senza motivo.
- Preferire funzioni pure: se una regola puo stare in una funzione senza effetti collaterali, deve
  stare li.
- Rendere espliciti i contratti: input, output, errori, default e limiti devono essere visibili nel
  codice o nei test.
- Non fare refactor al buio: prima caratterizzare il comportamento, poi modificarlo.
- Non fare big bang: cambiare poco, verificare spesso, lasciare una traccia leggibile.
- Non nascondere complessita: se una cosa e complessa, darle un nome, isolarla e testarla.
- Automatizzare cio che si ripete: test, lint, formattazione, build e controlli devono stare in
  comandi ripetibili.
- Usare l'italiano per i nomi di qualunque cosa: file, cartelle, moduli, funzioni, classi, variabili,
  test, etichette, documenti e messaggi. Fanno eccezione solo API esterne, librerie, protocolli,
  standard tecnici e convenzioni obbligate dal framework.
  **Applicare con criterio (regola per il NUOVO, non retroattiva)**: vale soprattutto per nuovo
  dominio, nuovi documenti, nuovi test e nuovi moduli interni. NON rinominare codice esistente,
  API/route pubbliche, componenti Vue, funzioni gia esposte o convenzioni FastAPI/Python solo per
  uniformare: il costo (rotture, diff enormi, contratti pubblici) supera il beneficio estetico.
- Documentare decisioni, non ovvieta: i commenti spiegano perche, non riscrivono il codice in prosa.
- Il codice morto va rimosso: duplicati, esperimenti e workaround scaduti diventano debito reale.
- Tracciabilita dei TODO: i commenti `TODO` o `FIXME` sono ammessi solo se indicano chiaramente l'azione da fare (es. `# TODO: estrarre in una funzione pura quando si aggiunge il supporto a X`).
- Niente codice commentato: non committare mai blocchi di codice commentati "per sicurezza". La cronologia di Git e lo strumento preposto a recuperare il codice passato.

## Dove mettere le cose

Ogni file deve avere una ragione chiara per esistere. Se non si riesce a descriverla in una frase,
probabilmente il modulo sta facendo troppo.

| Cosa | Dove va | Regola |
|---|---|---|
| Modelli e tipi di dominio | `nucleo/` o modulo equivalente | Nessuna dipendenza da UI, rete o filesystem non necessario |
| Regole di dominio | `nucleo/` | Funzioni pure o servizi piccoli, testabili in isolamento |
| Generazione output | `generatori/` o modulo dedicato | Riceve dati gia validati, non decide il dominio |
| Interfaccia utente | `interfaccia/` o interfaccia | Orchestrazione e stato vista, non logica di dominio nascosta |
| Accesso dati | `archivi/`, `depositi/`, `database/` o equivalente | Un solo punto per query, mapping e transazioni |
| Client esterni | `client_esterni/`, `integrazioni/` o equivalente | Timeout, retry, errori e mock chiaramente gestiti |
| Configurazione | `configurazione/`, `.env`, file dedicati | Nessun segreto hardcoded |
| Script operativi | `strumenti/`, `script/` o `componenti_aggiuntivi/` | Idempotenti quando possibile, documentati se pericolosi |
| Test | `tests/` | Specchio del comportamento, non discarica di prove manuali |
| Documentazione tecnica | `documentazione/` o `docs/` per convenzione | Contratti, architettura, procedure e decisioni |
| Artefatti generati | `build/`, `dist/`, `release/`, `tmp/`, `dati_locali/` | Fuori dal sorgente e ignorati da Git se rigenerabili |

Regola pratica: se un modulo deve importare "verso l'alto" per funzionare, l'architettura sta
probabilmente invertendo le responsabilita.

## Bibbia dei file

I file sono parte dell'architettura. Una struttura disordinata rende fragile anche codice corretto.

### Regole generali

- Ogni file deve avere un proprietario logico: dominio, UI, test, script, documento, configurazione,
  asset o artefatto.
- La root del progetto deve restare leggibile: pochi file essenziali, niente accumulo operativo.
- I file generati devono stare in cartelle generate (`build/`, `dist/`, `release/`, `tmp/`,
  `dati_locali/`) e non mescolarsi al sorgente.
- I file temporanei devono essere ignorati da Git e cancellabili senza perdere conoscenza.
- I file sensibili non devono stare nel repository, nemmeno "solo per prova".
- Gli asset statici devono stare in una cartella esplicita (`assets/`, `static/`, `resources/`) e
  avere nomi descrittivi.
- Le fixture di test devono stare in `tests/fixtures/` o cartella equivalente, piccole e anonime.
- Le esportazioni manuali devono avere una cartella dedicata e una regola di conservazione.
- Ogni cartella non ovvia deve avere un README o essere citata nella documentazione architetturale.

### Nomi dei file

- Il nome deve descrivere il contenuto, non la storia: evitare `nuovo`, `finale`, `finalissimo`,
  `prova`, `backup2`.
- I nomi devono essere in italiano, salvo nomi imposti da framework, linguaggi, protocolli o API
  esterne.
- Usare suffissi espliciti per varianti reali: `_test`, `_fixture`, `_migrazione`, `_modello`,
  `_adattatore`, `_archivio`.
- Usare date solo per artefatti storici o backup, nel formato ordinabile `YYYY-MM-DD`.
- Evitare spazi nei nomi dei file quando devono essere usati da script o build.
- Non duplicare lo stesso concetto in file quasi uguali: estrarre configurazione o funzione comune.
- I file obsoleti vanno rimossi o spostati in una cartella `archivio/` documentata, non lasciati in
  mezzo al codice vivo.

### Cosa entra in Git

Entra in Git:

- codice sorgente
- test e fixture minime
- configurazioni non segrete
- template necessari alla build
- documentazione
- script ripetibili
- migrazioni database

Non entra in Git:

- password, token, chiavi, database reali, dump privati
- cache, virtualenv, output di build, log, screenshot temporanei
- file esportati rigenerabili
- backup locali
- dataset non bonificati

### File grandi

- Prima di aggiungere un file grande, chiedersi se e sorgente o artefatto.
- Se e rigenerabile, non va committato.
- Se e necessario, documentare origine, licenza, dimensione e motivo.
- Se cambia spesso, valutare storage esterno o procedura di download controllata.

## Confini architetturali

- Il dominio non conosce la UI.
- Il dominio non conosce il formato di visualizzazione finale, salvo DTO espliciti.
- La UI puo chiamare servizi applicativi, ma non deve contenere algoritmi lunghi.
- I generatori producono output; non devono correggere silenziosamente dati sbagliati.
- L'accesso a rete, database, filesystem e processi esterni deve stare ai bordi.
- Le funzioni di parsing devono restituire strutture chiare, non dizionari casuali.
- Gli errori devono essere rappresentati come eccezioni specifiche, result object o messaggi
  validati; mai come `print` dispersi.
- Le dipendenze globali vanno ridotte: passare configurazioni e servizi quando serve.
- Sanitizzazione ai confini: qualsiasi dato proveniente dall'esterno (input utente, clipboard, importazione file, API) deve essere validato e sanificato al confine (es. nella UI o nei parser) prima di entrare nel dominio o essere scritto nel database.
- Fail-fast sui contratti di input: se un input viola un tipo o un vincolo strutturale non aggirabile, l'applicazione deve sollevare un errore immediato anziche procedere con dati parziali o corrotti.

## Grammatica del codice

La grammatica del codice e il modo in cui nomi, file, funzioni e messaggi raccontano il sistema.
Una buona grammatica riduce il bisogno di spiegazioni esterne.

### Nomi

- Usare nomi specifici: `costruisci_piano_target` e meglio di `elabora_dati`.
- Evitare nomi generici come `manager`, `handler`, `utils`, `helper` se non sono davvero delimitati.
- Un nome deve dire cosa rappresenta, non come e capitato li.
- Le funzioni usano verbi: `carica_pool`, `valida_distribuzione`, `genera_sql`.
- Le classi e i tipi usano sostantivi: `ContestoGenerazione`, `RisultatoValidazione`, `PianoTarget`.
- I booleani devono leggersi come condizioni: `e_valido`, `ha_allegati`, `deve_ritentare`.
- Le costanti devono rappresentare decisioni nominate, non numeri magici travestiti.

### Funzioni

- Una funzione deve fare una cosa principale.
- Se una funzione richiede commenti per separare blocchi interni, valutare l'estrazione di helper.
- Input e output devono essere piccoli e prevedibili.
- Evitare parametri booleani che cambiano radicalmente comportamento: preferire funzioni distinte o
  opzioni esplicite.
- Non usare valori sentinella ambigui (`None`, stringa vuota, `0`) senza contratto chiaro.
- Non modificare input mutabili senza dichiararlo nel nome, nella docstring o nel tipo.
- Type Hinting obbligatorio sui confini: tutte le nuove funzioni, metodi e classi devono avere le annotazioni dei tipi (`type hints`) per i parametri e il valore di ritorno, specialmente per i confini dei moduli, per intercettare gli errori in fase di analisi statica.

### Moduli

- Un modulo deve avere coesione: funzioni che cambiano per lo stesso motivo stanno insieme.
- Un modulo enorme e un segnale, non una colpa: prima test, poi estrazioni progressive.
- Evitare dipendenze circolari. Se compaiono, manca un contratto intermedio.
- I file `utilita` sono ammessi solo se piccoli, stabili e tematici: per esempio `utilita_date`,
  `utilita_testo_html`, `utilita_percorsi`.

### Testi e messaggi

- I messaggi utente devono essere chiari, corti e orientati all'azione.
- I messaggi di errore devono dire cosa e successo e cosa fare dopo, quando possibile.
- Log e messaggi tecnici devono includere contesto utile: id, path, record, stato, operazione.
- Evitare ironia, gergo interno e messaggi vaghi come "errore generico".

## Gestione della complessita

La complessita non si elimina con un nome elegante. Si riduce con confini, test e decisioni esplicite.

Segnali di complessita da trattare:

- funzioni lunghe con molti `if`
- cicli annidati con regole di dominio
- parametri che viaggiano insieme senza un tipo dedicato
- dizionari con chiavi implicite
- eccezioni catturate e ignorate
- duplicazione quasi uguale in piu punti
- codice UI che calcola regole di business
- generatori che validano, trasformano e renderizzano nello stesso blocco
- test difficili da scrivere perche il codice dipende da stato globale

Strategia standard:

1. Scrivere o trovare un test di caratterizzazione.
2. Dare un nome al comportamento da isolare.
3. Estrarre una funzione pura o un piccolo servizio.
4. Mantenere invariato il contratto esterno.
5. Eseguire test e quality gate.
6. Solo dopo, semplificare internamente.

Soglia mentale: se non si riesce a spiegare una funzione in tre frasi concrete, va scomposta o
documentata con un contratto migliore.

## Refactor

Un refactor valido cambia la struttura senza cambiare il comportamento osservabile.

Regole:

- Mai mischiare refactor, nuove feature e pulizia cosmetica nello stesso cambio se si puo evitare.
- Prima mettere in sicurezza con test, snapshot o output campione.
- Procedere per passi piccoli, ognuno verificabile.
- Se il comportamento cambia, non chiamarlo refactor: e una modifica funzionale.
- Conservare i nomi pubblici quando sono parte del contratto.
- Aggiornare documentazione e test quando cambia un confine architetturale.
- Non inseguire la perfezione: fermarsi quando il rischio residuo e piu basso del rischio di
  continuare.

## Test

I test non servono a dimostrare che abbiamo ragione. Servono a scoprire quando abbiamo torto.

### Piramide pratica

| Tipo | Quando usarlo | Cosa verifica |
|---|---|---|
| Unit test | Regole pure, parser, validazioni, trasformazioni | Casi piccoli e deterministici |
| Characterization test | Codice storico o poco chiaro | Comportamento attuale prima del refactor |
| Integration test | Confini tra moduli, filesystem, database locale, API simulate | Contratti tra parti |
| E2E test | Flussi critici utente o pipeline completa | Che il sistema lavori da ingresso a uscita |
| Test manuale | UI, esperienza, installazione, casi visuali | Aspetti non coperti bene dall'automazione |

### Regole per scrivere test

- Il nome del test deve dire il comportamento atteso.
- Un test deve fallire per un motivo chiaro.
- Preferire fixture piccole e leggibili.
- Evitare test byte-per-byte su output lunghi se bastano proprieta strutturali.
- Testare edge case reali: input vuoti, duplicati, encoding, path strani, limiti numerici, errori
  esterni.
- Ogni bug corretto deve lasciare almeno un test che falliva prima.
- I test non devono dipendere dall'ordine globale, dall'orario reale o da rete esterna senza controllo.
- Isolamento del tempo e del caso: le funzioni del nucleo che dipendono dall'orario corrente, da identificativi casuali o da fattori esterni non deterministici devono ricevere tali valori come parametri di input o tramite iniezione di dipendenze (es. passando un orologio o generatore_id mockabile), garantendo che i test unitari siano deterministici al 100%.
- I test lenti o di integrazione devono essere marcati e separabili.

### Quality gate minimo

Ogni progetto deve avere un comando standard che esegue almeno:

1. lint o static check
2. type check se il linguaggio lo consente
3. test automatizzati
4. controllo complessita se disponibile
5. build o smoke test dell'applicazione

Il comando deve essere documentato e ripetibile da una macchina pulita.
- Quality gate locale preventivo: lo sviluppatore deve eseguire localmente il comando standard di verifica (es. pytest, ruff, mypy) prima di effettuare qualsiasi commit o push, garantendo che il codice remoto rimanga sempre in uno stato stabile.

## Errori, logging e diagnosi

- Fallire presto quando l'input viola un contratto.
- Fallire con messaggi utili, non con stack trace incomprensibili per l'utente finale.
- Non catturare `Exception` senza rilanciare, loggare o trasformare l'errore.
- I log devono aiutare a ricostruire il percorso: operazione, input rilevante, output, durata,
  errore.
- Non loggare segreti, token, password, dati sensibili o file privati.
- Separare errori utente, errori dati, errori di sistema ed errori di programmazione.
- Le recovery automatiche devono essere esplicite e testate.

## Sicurezza, dati e configurazione

- **Nessun segreto nel codice:** password, chiavi API, token e certificati non devono mai essere hardcoded nel codice, nei test o nei file committati.
- **Gestione credenziali fortificata:** utilizzare variabili d'ambiente (file `.env` ignorato da Git) o gestori di segreti (secrets manager). Le credenziali locali o di test non devono essere condivise o salvate in chiaro.
- **Cifratura dei dati sensibili:** le password o i dati critici memorizzati devono essere protetti tramite algoritmi di hashing sicuri e moderni (es. bcrypt, Argon2) o cifratura forte, mai salvati in chiaro.
- **Principio del minimo privilegio:** i token, gli account del database e i permessi del filesystem usati dall'applicazione devono avere solo i privilegi minimi necessari per svolgere il proprio compito.
- **Esecuzione sicura dei comandi:** evitare l'uso di funzioni di esecuzione dinamica di codice (come `eval()` o `exec()`) o chiamate di sistema (`subprocess` con `shell=True`) usando input utente non sanificato, per prevenire attacchi di command injection.
- **Serializzazione protetta:** non deserializzare dati da fonti non sicure usando formati vulnerabili (come `pickle` in Python); preferire formati sicuri come JSON o protocolli di serializzazione con schemi rigidi.
- **Audit delle vulnerabilita:** controllare periodicamente le dipendenze esterne per verificare la presenza di vulnerabilita note (es. tramite strumenti come `pip-audit`).
- Configurazioni diverse per sviluppo, test e produzione.
- I default devono essere sicuri e documentati.
- Le migrazioni dati devono essere ripetibili e reversibili quando possibile.
- Prima di cancellare o trasformare dati reali, creare backup o dry-run.
- I file temporanei devono avere una destinazione chiara e una politica di cleanup.
- Le fixture di test devono essere anonime, minime e non derivate da dati sensibili senza bonifica.

## Bibbia del database

Il database, quando esiste, e un contratto applicativo. Non e un dettaglio interno da cambiare a
caso, perche contiene stato, storia e responsabilita operative.

### Quando introdurlo

- Usare un database quando servono persistenza, query, concorrenza, integrita o audit reali.
- Non usare un database per evitare di progettare file, cache o strutture dati.
- Per prototipi e tool locali, valutare prima file strutturati o SQLite.
- Per dati condivisi, concorrenti o critici, scegliere un motore adatto e documentare il motivo.

### Schema

- Ogni tabella deve rappresentare un concetto chiaro del dominio o una relazione tecnica necessaria.
- Ogni colonna deve avere tipo, nullabilita, default e significato chiari.
- Le chiavi primarie devono essere stabili e prive di significato ambiguo.
- Le chiavi esterne devono esprimere relazioni reali e proteggere l'integrita.
- I vincoli (`NOT NULL`, `UNIQUE`, `CHECK`, FK) devono stare nel database quando rappresentano regole
  invarianti.
- Gli indici devono nascere da query reali o requisiti evidenti, non da abitudine.
- I nomi di tabelle, colonne, indici, viste, procedure e migrazioni devono essere in italiano, salvo
  limiti tecnici o integrazioni esterne.
- I campi di audit (`creato_il`, `aggiornato_il`, `creato_da`, `aggiornato_da`) vanno previsti quando
  servono tracciabilita e diagnosi.

### Migrazioni

- Ogni modifica schema deve passare da una migrazione versionata.
- Le migrazioni devono essere ripetibili, ordinate e applicabili da ambiente pulito.
- Le migrazioni distruttive richiedono backup, piano di rollback o procedura esplicita.
- Separare modifiche schema, backfill dati e cleanup quando il rischio cresce.
- Una migrazione deve spiegare cosa cambia e perche, almeno nel nome o nel commento.
- Mai modificare retroattivamente una migrazione gia applicata in ambienti condivisi: crearne una
  nuova.

### Accesso ai dati

- Le query devono stare in repository, DAO, servizio di persistenza o layer equivalente.
- La UI non deve eseguire query dirette.
- Il dominio non deve dipendere da dettagli SQL se non attraverso contratti espliciti.
- Usare query parametrizzate, mai concatenazione di stringhe con input esterno.
- Le transazioni devono avere confini chiari: cosa entra, cosa viene confermato, cosa viene annullato.
- Le connessioni devono avere timeout e gestione esplicita del ciclo di vita.
- Errori DB devono essere tradotti in errori applicativi comprensibili.

### Dati reali

- Prima di toccare dati reali, sapere quale ambiente si sta usando.
- Ogni script su dati reali deve avere dry-run o output di anteprima quando possibile.
- Ogni bonifica deve lasciare log o report di cosa e stato cambiato.
- I dump reali non devono entrare nel repository.
- I dati usati nei test devono essere sintetici o anonimizzati.
- Backup e restore devono essere provati, non solo dichiarati.

### Test del database

- Testare mapping, query critiche, vincoli e migrazioni.
- Usare database temporanei o transazioni rollback per test ripetibili.
- Non far dipendere i test da un DB condiviso popolato manualmente.
- Verificare sia i casi validi sia le violazioni di vincolo.
- Per query complesse, testare il risultato atteso e almeno un caso limite.

### Prestazioni e manutenzione

- Ogni query lenta va misurata con dati realistici.
- Prima di aggiungere indici, leggere il piano di esecuzione quando possibile.
- Evitare query N+1 nei flussi ripetuti.
- Prevedere archiviazione o pulizia per tabelle che crescono senza limite.
- Monitorare dimensioni, tempi, errori, lock e saturazione connessioni negli ambienti importanti.

## Dipendenze

- Aggiungere una dipendenza solo se riduce complessita reale o rischio.
- Preferire librerie mature, mantenute e compatibili con il target del progetto.
- Bloccare o documentare versioni quando la stabilita conta.
- Isolare le librerie esterne dietro wrapper quando il cambio futuro sarebbe costoso.
- Rimuovere dipendenze non usate.
- Non introdurre framework per risolvere un problema che il progetto non ha.

## Prestazioni

Prima regola: misurare.

- Ottimizzare solo colli di bottiglia osservati o prevedibili con dati realistici.
- Preferire algoritmi chiari e strutture dati adeguate prima di micro-ottimizzazioni.
- Evitare I/O ripetuto in cicli stretti.
- Gestire dataset grandi con streaming, batch o paginazione quando serve.
- Le cache devono avere invalidazione, limiti e test.
- Ogni ottimizzazione non ovvia deve spiegare il motivo.

## UI e interazione

- La UI deve orchestrare, non contenere il dominio.
- Ogni azione importante deve avere stato chiaro: pronto, in corso, completato, errore.
- Non bloccare l'interfaccia con operazioni lunghe.
- Validare prima possibile e vicino al punto in cui l'utente puo correggere.
- Messaggi, label e pulsanti devono usare la lingua dell'utente del prodotto.
- Evitare schermate che richiedono memoria: mostrare contesto, riepiloghi e scelte attive.
- Ogni workflow critico deve avere almeno uno smoke test manuale documentato se non automatizzato.

## Documentazione

La documentazione buona riduce rischio operativo.

Deve esistere documentazione per:

- architettura e confini principali
- setup e comandi di sviluppo
- test e quality gate
- regole di dominio non ovvie
- procedure operative per build, release, deploy o migrazioni
- debito tecnico noto e priorita
- decisioni importanti che sarebbe costoso riscoprire

Regole:

- Aggiornare i documenti nello stesso cambio che modifica il comportamento documentato.
- Preferire esempi piccoli e reali a descrizioni astratte.
- Segnare lo stato: attuale, desiderato, deprecato, temporaneo.
- Non duplicare documentazione in dieci posti; creare un indice o rimandare al documento autorevole.
- Ponte codice-Obsidian: se il progetto e aperto come vault Obsidian (verificare la presenza
  della cartella `.obsidian/` nella root), nei file di codice piu complessi (portanti: retriever,
  generatori, pipeline, router di dominio, migrazioni non banali) inserire nella docstring o nel
  commento di intestazione un riferimento `[[wikilink]]` alla nota tecnica corrispondente in `docs/`.
  Esempio: `Vedi documentazione di dettaglio in: [[docs/RICERCA_VETTORIALE]]`. Crea un ponte
  bidirezionale codice-note (backlink in Obsidian). Solo nei file portanti (non nei file piccoli o
  ovvi, per evitare rumore); il link punta alla nota canonica del tema, con il nome-nota reale e
  senza estensione; se la nota non esiste ancora, il link va bene lo stesso e segnala una nota da
  scrivere.

## Git e gestione delle modifiche

- Un commit deve raccontare una modifica coerente.
- Non committare artefatti generati, cache, DB temporanei o segreti.
- Prima di modificare file toccati da altri, leggere il diff e rispettare il lavoro esistente.
- Non formattare interi file senza motivo dentro una modifica funzionale piccola.
- Le migrazioni rischiose devono stare in commit separati.
- I messaggi di commit devono dire cosa cambia e perche, non solo "fix".
- Prima di merge o release, eseguire il quality gate standard.

## Checklist prima di chiudere una modifica

- Il comportamento richiesto e implementato.
- I confini architetturali sono rispettati.
- I nomi nuovi sono chiari e coerenti.
- La complessita non e aumentata senza motivo.
- I casi errore principali sono gestiti.
- I test coprono il comportamento nuovo o modificato.
- Il quality gate passa, oppure il motivo del mancato passaggio e documentato.
- La documentazione rilevante e aggiornata.
- Non sono stati introdotti segreti, artefatti temporanei o dipendenze inutili.

## Checklist per iniziare un nuovo progetto

1. Scrivere un `README.md` con scopo, setup, comandi e struttura.
2. Creare `docs/` con architettura, testing e debito tecnico.
3. Definire cartelle per dominio, interfaccia, I/O, test e strumenti.
4. Configurare lint, test e build prima che il progetto cresca.
5. Stabilire come gestire configurazioni e segreti.
6. Scrivere il primo test su una regola reale.
7. Automatizzare il comando "controlla tutto".
8. Aggiungere `.gitignore` prima di generare artefatti.
9. Documentare le prime decisioni irreversibili.
10. Rileggere questo documento e adattare solo cio che il progetto giustifica davvero.

## Frasi guida

- Se non e testabile, non e ancora ben progettato.
- Se non sai dove metterlo, probabilmente manca un confine.
- Se devi spiegarlo a voce ogni volta, serve un nome migliore o un documento.
- Se un bug torna, mancava un test.
- Se una funzione fa troppe cose, il primo passo e darle parti nominabili.
- Se un cambiamento sembra enorme, spezzarlo finche diventa verificabile.
- Se una scorciatoia resta nel codice, diventa architettura.
- Se il codice e chiaro solo oggi, domani e gia debito.


