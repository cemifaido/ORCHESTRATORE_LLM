# Proposta: riuso di due idee di Weft nell'orchestratore

**Stato**: proposta aperta alla revisione degli altri agenti, non decisa.
**Autore**: Claude, su richiesta dell'utente (2026-08-24).
**Origine**: analisi di [Weft](https://github.com/WeaveMindAI/weft)
(WeaveMindAI), linguaggio per orchestrazioni AI. Il giudizio complessivo sul
progetto è "interessante ma embrionale, non adottabile" (POC, ~41 commit,
branch main inattivo): questa proposta NON è "usiamo Weft", è "rubiamo due
idee di design e le realizziamo con i mezzi che abbiamo già".

## Le due idee

1. **L'attesa dell'umano come primitiva di prima classe.** In Weft "aspetta 3
   giorni un'approvazione umana" è lo stesso codice di "aspetta 3 secondi una
   API": il programma si sospende con tutto lo stato persistito e riprende
   esattamente da dove era, su qualunque esecuzione successiva.
2. **Il grafo del workflow è dichiarato e verificabile prima dell'esecuzione.**
   In Weft il compilatore controlla l'architettura del flusso (chi produce
   cosa, chi lo consuma) prima che giri; l'LLM che genera il programma viene
   corretto dal compilatore, non dal debugging a valle.

## Cosa abbiamo già (per non reinventarlo)

- Bacheca append-only con `checkpoint`/`ripresa`/`emergenza` (RFC §3.4bis):
  l'interruzione/ripresa esiste già come **annotazione per umani e agenti che
  rileggono**.
- `verdetto_umano` su registro e bacheca (`approva`/`respingi`): l'approvazione
  umana esiste già come **fatto registrato**.
- Schema JSON versionato e validato (`schema/messaggio.v1.json`,
  `bacheca.py valida`): la disciplina "struttura + validatore" è già la nostra.

I buchi rispetto alle due idee: (a) quando l'umano approva dopo giorni,
**nessuno riprende automaticamente il lavoro dal punto esatto** — serve che la
sessione successiva rilegga tutto e ricostruisca il contesto a mano; (b) il
workflow (compito → gate → triage → approvazione → registro) vive **in prosa**
dentro CLAUDE.md/GEMINI.md/AGENTS.md e nelle abitudini: niente lo verifica, e
ogni agente può derivarne una versione leggermente diversa.

## Proposta 1 — Checkpoint ripristinabile ("pratica sospesa")

Obiettivo: un checkpoint che non sia solo leggibile, ma **eseguibile alla
ripresa**. Estensione minima, senza motore nuovo:

- Al `tipo=checkpoint` si aggiunge (schema v2 o campo opzionale in v1) un
  campo strutturato `ripresa` con: `attende` (`umano` | `gate` | `agente`),
  `prossimo_passo` (istruzione operativa in una frase, es. "se approvato:
  eseguire commit dei file X,Y; se respinto: riaprire il thread Z"), e
  `contesto_minimo` (elenco file/thread/comandi sufficienti a ripartire senza
  rileggere tutta la storia).
- `bacheca.py approva`/`respingi` su un thread che contiene un checkpoint con
  `attende=umano` stampa (e l'hook SessionStart/UserPromptSubmit inietta) il
  `prossimo_passo` corrispondente: chi si sveglia dopo — anche una sessione
  nuova, anche un agente diverso — sa esattamente cosa fare, come in Weft la
  resume riparte dal nodo sospeso.
- Nessun demone, nessun runtime: la "durabilità" è il JSONL che già abbiamo.
  Cambia solo il contratto: **un checkpoint senza prossimo passo eseguibile è
  un checkpoint incompleto.**

Costo stimato: modifica a `schema/messaggio.v1.json` + `bacheca.py`
(serializzazione e stampa) + aggiornamento RFC. Nessuna migrazione: i vecchi
checkpoint restano validi, il campo è opzionale.

## Proposta 2 — Flusso dichiarato e validabile (`schema/flusso.v1.json`)

Obiettivo: il workflow standard smette di essere prosa e diventa **dati
validabili**, come già fatto per i messaggi. Primo passo deliberatamente
piccolo:

- Un file `config/flussi/compito_standard.json` che dichiara i passi del
  flusso oggi implicito: `compito → gate (sentinella) → triage (locale, solo se
  ambiguo) → registrazione (registro.py) → [approvazione umana se
  irreversibile] → chiusura`. Per ogni passo: chi lo esegue (`capability`
  richiesta, coerente con `CONFORMITA_TOS_BACHECA.md`), cosa produce, cosa
  richiede dal passo precedente.
- Uno schema `schema/flusso.v1.json` + `bacheca.py valida`-equivalente (o
  sottocomando in `sentinella.py`) che verifica il file: passi orfani,
  produzioni mai consumate, passi irreversibili senza approvazione umana a
  monte. È il "compilatore che controlla l'architettura" di Weft, in versione
  povera ma nostra.
- La dashboard (`interfaccia.py`/`genera_cruscotto.py`) può poi disegnare il
  grafo dal JSON invece che da conoscenza cablata — allineato al punto 3 del
  piano di industrializzazione (governance visibile).

Beneficio collaterale, che è l'argomento più forte di Weft: un flusso
dichiarato in JSON è **generabile e verificabile da un LLM con molti meno
token e molta meno deriva** rispetto a "leggi tre file di istruzioni in prosa
e comportati di conseguenza". Le istruzioni in prosa restano per il perché; il
JSON diventa la fonte per il cosa-dopo-cosa.

## Cosa NON si propone

- Adottare Weft, Restate o un runtime di workflow esterno: lock-in su un POC
  in riscrittura, contro il principio "zero dipendenze a pagamento/fragili"
  del motore attuale.
- Un motore di esecuzione del grafo: il flusso dichiarato all'inizio **descrive
  e valida**, non esegue. L'esecuzione resta agli agenti come oggi.
- Toccare il registro eventi: rimane l'audit trail, invariato.

## Ordine e verifica

1. Prima la Proposta 1 (piccola, valore immediato, un solo file schema da
   toccare), con test su `tests/` per serializzazione e retrocompatibilità.
2. Poi la Proposta 2, partendo dal solo flusso `compito_standard` e dal
   validatore; la dashboard viene dopo, se il validatore si dimostra utile.
3. Ogni passo passa dal gate (`sentinella.py`) e viene registrato nel registro
   come da regole del repo.

Revisione richiesta a Gemini e Codex via bacheca (vedi thread collegato):
in particolare, Codex sul rigore dello schema `ripresa` (v2 vs campo opzionale
v1) e Gemini sull'impatto dashboard/UX della Proposta 2.
