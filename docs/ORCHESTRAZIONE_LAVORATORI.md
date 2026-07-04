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
- **Riavvio Sistema**: `POST /api/sistema/riavvia` avvia un nuovo processo `interfaccia.py` (che ricarica il codice corrente da disco) e termina quello in esecuzione non appena il nuovo ha preso la porta (`__main__` ritenta il bind per ~10s in caso di sovrapposizione). Necessario perché uvicorn non ricarica mai i moduli modificati: senza riavvio, la dashboard resta silenziosamente disallineata dal codice sorgente.

