# Integrazione opzionale LiteLLM

**Stato**: adapter in uso reale. Usato da `triage_locale.py` e script di supporto per chiamate al modello locale e provider esterni. LiteLLM resta comunque una dipendenza opzionale, non core.

Vedi anche: [Indice](INDEX.md) · [Orchestrazione dei lavoratori](ORCHESTRAZIONE_LAVORATORI.md).

## Decisione

LiteLLM entra come gateway opzionale per chiamate LLM, non come nuovo centro dell'orchestratore.

Il registro resta la fonte operativa degli eventi: chi ha lavorato, su quale compito, con quale gate, con quale verdetto e con quale costo. LiteLLM misura la singola chiamata LLM e fornisce costo/token quando disponibili.

## Perché ha senso

- normalizza provider diversi dietro un'interfaccia compatibile;
- gestisce modelli locali e commerciali con lo stesso punto di passaggio;
- può produrre costi misurati e token per chiamata;
- consente di spostare routing e limiti di spesa fuori dal codice applicativo.

## Confine

LiteLLM può:

- eseguire chiamate chat/completion;
- calcolare o riportare costo e token;
- centralizzare provider, chiavi, budget e proxy;
- alimentare `costo_stimato_usd`, `origine_costo` e `metadati.litellm`.

LiteLLM non può:

- sostituire il registro append-only;
- decidere rework, gate o verdetto umano;
- diventare dipendenza obbligatoria del framework;
- ricevere segreti hardcoded nei file committati.

## Convenzione evento

Quando una risposta LiteLLM è associata a un evento del registro:

- `costo_stimato_usd` contiene il costo in USD se disponibile;
- `origine_costo` vale `misurato` se il costo arriva da LiteLLM;
- `metadati.litellm` contiene i dettagli tecnici.

Esempio:

```json
{
  "costo_stimato_usd": 0.0021,
  "origine_costo": "misurato",
  "metadati": {
    "litellm": {
      "fonte": "litellm",
      "modello": "openai/gpt-4.1-mini",
      "provider": "openai",
      "costo_usd": 0.0021,
      "token_prompt": 1200,
      "token_completion": 180,
      "token_totali": 1380
    }
  }
}
```

Il nome `costo_stimato_usd` resta invariato per compatibilità dello schema v1. Il valore è stimato o misurato in base a `origine_costo`.

## Adapter Python

Modulo:

`adattatori/litellm.py`

Funzioni principali:

- `completamento(...)`: importa LiteLLM solo al momento della chiamata;
- `completamento_locale(...)`: stessa chiamata, puntata di default all'endpoint del modello locale (llama-server) e con `costo_usd` sempre forzato a `0.0` misurato — usata da `triage_locale.py` per il triage a costo zero (vedi [LLM locale](ORCHESTRAZIONE_LAVORATORI.md#llm-locale));
- `estrai_misurazione(...)`: legge costo e token da una risposta LiteLLM;
- `testo_da_risposta(...)`: estrae il testo generato da una risposta (oggetto `ModelResponse`, dict o stringa), tornando `""` invece di sollevare eccezione se la forma è inattesa (usata da `triage_locale.py` per il parsing della classificazione JSON);
- `arricchisci_evento(...)`: copia un evento e aggiunge costo/metadati LiteLLM.

Per un esempio completo, documentato ed eseguibile che gestisce anche il fallback mock per lo sviluppo locale, fai riferimento a [esempi/chiamata_agente_litellm.py](file:///D:/Share/py/_ORCHESTRATORE_LLM/esempi/chiamata_agente_litellm.py).

Esempio:

```python
from adattatori.litellm import arricchisci_evento, completamento
import registro

risposta, misurazione = completamento(
    modello="openai/gpt-4.1-mini",
    messaggi=[{"role": "user", "content": "Riassumi questo diff"}],
)

evento = registro.costruisci_evento(args)
evento = arricchisci_evento(evento, misurazione)
registro.aggiungi_evento(percorso_registro, evento)
```

## Installazione opzionale

Nel progetto che vuole usare il gateway:

```powershell
python -m pip install litellm
```

Le chiavi API restano in variabili d'ambiente o nel secret store scelto dal progetto. Non vanno nel repository.

## Uso con proxy LiteLLM

Per ambienti multi-agente conviene preferire il proxy LiteLLM:

- una configurazione centralizzata per provider e modelli;
- virtual key per agente/progetto;
- tracciamento spesa per chiave, utente o team;
- limiti di budget applicati fuori dal codice del framework.

Il framework deve registrare solo l'esito operativo e i dati misurati restituiti dal gateway.

## Prossimi passi

1. Aggiungere un esempio di configurazione proxy quando avremo il primo progetto reale.
2. Mantenere nei dati/API la distinzione fra costo stimato e misurato; reintrodurla in dashboard solo se torna utile come vista operativa.
3. Valutare un adapter `routing.py` solo dopo aver raccolto eventi reali.
