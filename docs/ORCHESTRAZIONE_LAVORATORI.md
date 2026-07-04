# Orchestrazione dei lavoratori — agenti AI, LLM locale e umano

**Stato**: specifica operativa iniziale (2026-07-03). Documento vivo.

Vedi anche: [Indice](INDEX.md) · [Regole generali di programmazione](REGOLE_GENERALI_PROGRAMMAZIONE_DA_RISPETTARE_SEMPRE.MD) · [Integrazione LiteLLM](INTEGRAZIONE_LITELLM.md).

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

Il LLM locale è capoturno, non programmatore.

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
rispettivi strumenti, **non ancora verificato** che antigravity-ide/Codex CLI li carichino
davvero da soli come fa Claude Code con `CLAUDE.md` — la prima volta che apri una
sessione con uno dei due, verifica esplicitamente che li abbia letti). Non è
sincronizzazione in tempo reale — è un changelog condiviso, lo stesso che vede
l'operatore umano nella dashboard.

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

**Limite noto**: il modello locale (llama-server, quantizzazione Q3_K_M) a volte genera
un carattere accentato come sequenza UTF-8 malformata (es. "è" → `�`), probabilmente per
un token spezzato male in fase di generazione. Non altera mai l'esito
`routine`/`escalation`, solo occasionalmente il testo libero del campo `motivo`. Non
ancora investigato a fondo: non è un bug nel codice dell'orchestratore.

## Capoturno

**Come si ottiene davvero del codice scritto, oggi (2026-07-04)** — quattro vie possibili, non alternative fra loro ma con un default esplicito:

| Modalità | Chi scrive davvero il codice | Quando si attiva | Note |
|---|---|---|---|
| **Sessione interattiva (default)** | L'assistente Claude Code, direttamente in conversazione, con accesso reale a file/terminale | Quando il compito viene chiesto direttamente in chat | Nessuna chiamata API esterna da capoturno, nessun rischio di crediti/chiave esauriti |
| Gemini (via LiteLLM) | Modello chiamato da `capoturno.py` | Solo se si lancia dal pannello dashboard "Live Agent Handoff" con Tipo Compito → interfaccia | Richiede `OPENAI_API_KEY`: l'etichetta è "gemini" ma il modello reale chiamato è `openai/gpt-4o-mini`, non un vero modello Google (limite noto, da correggere) |
| Claude (via LiteLLM) | Modello Claude chiamato da `capoturno.py` | Idem, Tipo Compito → servizi/database/documentazione | Richiede chiave Anthropic, soggetto a crediti/quota come qualunque chiamata API |
| Codex | — | Suggerito dal routing per revisione/sicurezza | **Non cablato in `capoturno.py`**: se scelto, il motore chiamerebbe comunque il modello Claude ma registrerebbe l'evento come `agente=codex` — bug noto, non usare questo instradamento finché non è corretto |

Finché la delega via LiteLLM resta legata a crediti/chiavi che possono mancare o esaurirsi, la sessione interattiva resta la via primaria per il lavoro reale; il pannello "Live Agent Handoff" resta disponibile per quando si vuole tornare alla delega automatica via API.

`capoturno.py` è il motore che esegue davvero il ciclo "Watch-and-Solve" per le tre vie via LiteLLM: riceve un compito, lo fa lavorare a un agente reale, applica la patch sul progetto target, la valida con la sentinella e ripete in caso di errore. Non è un nuovo lavoratore: automatizza meccanicamente il ruolo di capoturno (instradamento, delega, validazione, rework) che la tabella dei [Lavoratori](#lavoratori) assegna al LLM locale — chi scrive codice resta sempre Gemini/Claude/Codex, mai il locale.

Ciclo eseguito da `Capoturno.esegui_compito(...)`:

1. **Routing**: `instrada.instrada(tipo_compito, rischio, registro)` suggerisce l'agente (stessa tabella di [Routing](#routing)). Se il rischio è alto o l'agente suggerito è `umano`, viene notificato "serve umano prima" — nella v1 il motore procede comunque (non c'è ancora un blocco sincrono in attesa di approvazione, vedi Limiti noti).
2. **Chiamata all'agente**: prompt minimale (codice attuale del file, compito, errore dell'ultimo tentativo se è un rework) inviato via `adattatori/litellm.py`. Il modello risponde con un blocco di codice Python racchiuso in ` ```python `.
3. **Scrittura patch**: il codice estratto viene scritto su `file_target` dentro il progetto reale (`progetto_percorso`), non nell'orchestratore.
4. **Validazione (gate)**: viene lanciata la sentinella **centrale** (mai una copia), comando `controllo_lint`, con `cwd` sul progetto target e `--config` puntato al `config/comandi.json` centrale — così `ruff check .` valida davvero il file appena scritto nel progetto giusto, non il codice dell'orchestratore.
5. **Rework**: se il gate fallisce, l'errore viene incluso nel prompt del tentativo successivo (fino a 3 rework). Se il gate passa, l'evento viene registrato `stato=passato`/`esito_gate=superato` nel registro **del progetto target**.
6. **Failover infrastrutturale**: se la chiamata all'agente fallisce per errore di rete/quota/credenziali (non per codice scritto male), il motore ritenta automaticamente con l'agente di riserva (`claude` ↔ `gemini`). Se anche il fallback fallisce, l'evento viene registrato `stato=errore_ambiente`/`esito_gate=non_eseguito` (non `fallito`): non inquina il conteggio rework, e segnala che serve intervento umano (crediti, chiave API, rete), non una correzione di codice.

### Avvio dalla dashboard

Pannello **"🤝 Live Agent Handoff & Cooperazione"**: seleziona progetto target, tipo compito, file target, rischio e descrivi il compito, poi "▶ Lancia Compito Reale". Il form chiama `POST /api/compiti/avvia` (esecuzione in background), la dashboard fa polling su `GET /api/compiti/stato` e anima il diagramma SVG passo per passo; a fine corsa chiama `POST /api/compiti/reset`.

### Replay di un commit reale (demo)

Nello stesso pannello, "Rivivi un commit reale" mostra un selettore di commit (`GET /api/commit/lista`, da `git log`, con hash/data/autore/messaggio) e un pulsante "🎬 Riproduci". Alla scelta, una card mostra i metadati del commit (hash breve, data, autore, messaggio) e `GET /api/commit/eventi?progetto_id=...&hash=...` (modulo `commit_replay.py`) calcola la finestra temporale del commit (tra il suo timestamp e quello del commit precedente, confrontati come date timezone-aware in UTC — non come stringhe, perché git usa il fuso locale e il registro usa sempre `Z`) e ritorna gli eventi del registro caduti in quella finestra. La dashboard li anima in sequenza sullo stesso diagramma SVG — inferendo la direzione linea-per-linea dall'ordine cronologico degli eventi (verde se passato, rossa se fallito/da rivedere) e chiudendo il ciclo verso il nodo "umano" a fine sequenza — poi mostra una statistica reale, non uno scenario finto:

- **percentuale di controlli di verifica gestiti gratis dal modello locale** sul totale (locale + eventuali revisioni/sicurezza fatte da un agente a pagamento nella stessa finestra) — varia per commit, non è mai fissa al 100%;
- **stima in $ del risparmio**, calcolata solo sui `token_totali` realmente misurati (metadati degli eventi `agente=locale`) moltiplicati per il prezzo pubblico di un modello di riferimento dichiarato (GPT-4o-mini, tariffa input, scelta conservativa) — mai un numero inventato.

Un commit senza eventi di verifica (es. solo lavoro conversazionale, costo sempre stimato/0) mostra correttamente "nessun controllo da cui stimare un risparmio": non si forza una percentuale quando non c'è nulla di comparabile.

### Limiti noti (v1)

- Un solo compito reale alla volta: lo stato (`STATO_COMPITO_CORRENTE`) è globale in memoria nel processo `interfaccia.py`, non per-progetto. Un secondo tentativo di avvio viene rifiutato finché il primo non è `finito`.
- "Serve umano prima" (rischio alto): l'umano che lancia il compito dalla dashboard è già il gate umano (ha compilato il form e cliccato "Lancia"), quindi il backend non blocca nulla — ma se `rischio=alto` il frontend chiede una conferma esplicita in più (`confirm()` col riepilogo del compito) prima di inviare la richiesta. Non è ancora una sospensione lato server: un secondo canale (es. API diretta) potrebbe bypassarla.
- Il modello viene scelto solo in base a `gemini` vs "tutto il resto → claude": se il routing suggerisce `locale` o `codex` (tipi come `monitoraggio`/`revisione`), il motore chiamerebbe comunque un LLM reale con modello Claude invece di restare deterministico — situazione non ancora incontrata nell'uso reale, da chiudere se emerge.
- Quando l'agente scelto è `gemini`, il modello effettivamente chiamato via LiteLLM è `openai/gpt-4o-mini`, non un vero modello Google Gemini: l'etichetta "gemini" nel routing non corrisponde al provider reale usato. Per questo compito serve una chiave `OPENAI_API_KEY`, non una chiave Google — da correggere se si vuole davvero chiamare Gemini.
- Il file da modificare va scelto a mano nel form: il motore non esplora il progetto né decide da solo dove scrivere, gestisce un solo file per compito. Un'evoluzione naturale (proposta e non ancora implementata) è una chiamata preliminare "di scoping" allo stesso agente suggerito dal routing, per fargli individuare il file più pertinente prima di scrivere la patch — lasciando comunque il campo compilabile a mano come opzione/override.

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

Il server `interfaccia.py` (FastAPI/Uvicorn, porta `8095`) offre un'interfaccia di monitoraggio visiva ad alto impatto grafico (dark theme, glassmorphic layout) basata su:
- **Grafici Chart.js**: Visualizzazione ripartita dei costi stimati ed istogrammi di esecuzioni/rework per ogni lavoratore.
- **Selettore Progetti**: Form per inserire il percorso assoluto e nome di una nuova cartella per effettuarne l'integrazione ed il monitoraggio automatico.
- **Pannello Sentinella**: Console web interattiva per lanciare comandi deterministici whitelistati (es. pytest, git status) su un determinato progetto in un subprocesso isolato, visualizzandone il log di ritorno.
- **Live Agent Handoff & Cooperazione**: pannello per lanciare un compito reale tramite `capoturno.py` (vedi [Capoturno](#capoturno)), con diagramma SVG animato e console che mostrano in tempo reale quale agente sta lavorando e con quale esito.
- **Riavvio Sistema**: `POST /api/sistema/riavvia` avvia un nuovo processo `interfaccia.py` (che ricarica il codice corrente da disco) e termina quello in esecuzione non appena il nuovo ha preso la porta (`__main__` ritenta il bind per ~10s in caso di sovrapposizione). Necessario perché uvicorn non ricarica mai i moduli modificati: senza riavvio, la dashboard resta silenziosamente disallineata dal codice sorgente.
- **Costi in EUR**: i costi (`costo_stimato_usd`) sono mostrati in dashboard convertiti in euro. Il tasso di cambio viene scaricato da un servizio esterno (`open.er-api.com`) al massimo una volta al giorno e tenuto in `localStorage` del browser: un riavvio del server o un semplice reload della pagina nello stesso giorno riusano il tasso già scaricato invece di rifare la chiamata.

