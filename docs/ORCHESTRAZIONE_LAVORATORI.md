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

Ogni riga è validata da `schema/evento.v1.json`.

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

Il framework si autoinstalla all'interno del progetto di destinazione quando questo viene registrato tramite l'interfaccia. L'integrazione esegue:
1. Creazione delle cartelle di runtime `dati_locali/orchestrazione/` nel percorso di destinazione.
2. Copia degli schemi di validazione degli eventi `schema/evento.v1.json` e `schema/compito.v1.json`.
3. Copia dei file di configurazione di esempio `config/comandi.esempio.json` e `config/agenti.esempio.json` se non già presenti.
4. Installazione locale dei tre script del framework (`registro.py`, `sentinella.py`, `genera_cruscotto.py`) in modo che il progetto possa eseguire la sentinella o registrare eventi in locale in modo indipendente.
5. Aggiornamento automatico del file `.gitignore` del progetto target per escludere tutti i file copiati/gestiti dall'orchestratore, prevenendo commit indesiderati nei repository dei singoli progetti.

## Interfaccia Web (Dashboard)

Il server `interfaccia.py` (FastAPI/Uvicorn, porta `8095`) offre un'interfaccia di monitoraggio visiva ad alto impatto grafico (dark theme, glassmorphic layout) basata su:
- **Grafici Chart.js**: Visualizzazione ripartita dei costi stimati ed istogrammi di esecuzioni/rework per ogni lavoratore.
- **Selettore Progetti**: Form per inserire il percorso assoluto e nome di una nuova cartella per effettuarne l'integrazione ed il monitoraggio automatico.
- **Pannello Sentinella**: Console web interattiva per lanciare comandi deterministici whitelistati (es. pytest, git status) su un determinato progetto in un subprocesso isolato, visualizzandone il log di ritorno.

