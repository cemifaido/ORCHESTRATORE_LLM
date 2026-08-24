# Mini-RFC: messaggio.v2 — checkpoint ripristinabile (campo `ripresa`)

**Stato**: implementata come pilota (Proposta 1 di
`docs/PROPOSTA_RIUSO_IDEE_WEFT.md`), thread bacheca `4911f547`.
**Vincoli recepiti**: revisione Codex (schema v2 separato, rigore sui campi,
controlli cross-record, hook non fidato) e Gemini (dashboard read-only,
widget "pratiche sospese" possibile a valle).

## Problema

Un `checkpoint` oggi è testo libero per chi rilegge. Quando l'umano approva o
respinge dopo ore/giorni, nessuno espone in modo affidabile "cosa fare adesso":
la sessione successiva ricostruisce il contesto a mano. Obiettivo (idea presa
da Weft): l'attesa diventa uno stato ripristinabile — il verdetto arriva e chi
si sveglia riceve l'azione esatta prevista per quell'esito.

## Decisioni e invarianti

1. **Versione nuova, non v1 allargata.** `schema/messaggio.v2.json` con
   `versione_schema=2` e `additionalProperties=false`. La v1 resta congelata:
   allargarla manterrebbe validi i record ma renderebbe la versione
   semanticamente ingannevole (rilievo Codex). Nessuna migrazione dello
   storico: il lettore (`bacheca.valida_messaggio`) instrada per
   `versione_schema` e accetta entrambe; una versione sconosciuta è errore.
2. **`ripresa` è un campo dello schema, non roba nei `metadati`.** Ammesso
   solo su `tipo=checkpoint` (vincolo if/else nello schema, come per
   `ttl_minuti`). È opzionale — i checkpoint informativi restano legittimi —
   ma **se presente, tutti i suoi campi sono obbligatori**:
   - `attende`: `umano` | `gate` | `agente` — chi/cosa sblocca la ripresa.
   - `oggetto_atteso`: cosa esattamente si aspetta (es. "verdetto umano sul
     commit dei file X,Y"), identificabile da chi rilegge.
   - `azioni_per_esito`: oggetto esito→azione testuale, almeno un esito. Se
     `attende=umano` sono obbligatori **tutti e tre** gli esiti
     (`approvato`, `respinto`, `modifiche_richieste`): niente frase unica
     biforcata, niente esito scoperto.
   - `contesto_minimo`: strutturato — `thread_id` (deve coincidere con quello
     del messaggio), `riferimenti` (file, URL o id di messaggi/thread in
     bacheca), `comandi_consentiti` (elenco dei comandi che l'azione può
     richiedere; informativo, non un'autorizzazione).
3. **`valida` fa controlli cross-record** oltre allo schema per-messaggio:
   `contesto_minimo.thread_id` coerente col messaggio; ogni riferimento non-URL
   deve esistere come file nel progetto o come id noto alla bacheca.
4. **`approva`/`respingi` espongono il prossimo passo dell'ULTIMO checkpoint
   attivo del thread, e solo se `attende=umano`** — attivo = con `ripresa`, non
   seguito da `chiusura`/`annullamento` (risolto) né da un checkpoint
   ripristinabile più recente (sostituito). Mai un checkpoint qualunque pescato
   nel thread. Un verdetto umano non risolve un'attesa di `gate`/`agente`
   (rilievo Codex in seconda revisione): per quelle il pilota resta puramente
   descrittivo finché non esisterà un evento di risoluzione tipizzato — non si
   simula la risoluzione con `approva`/`respingi`. Se l'esito ricevuto non ha
   un'azione prevista, si stampa un avviso esplicito.
5. **La ripresa è contesto NON fidato, mai esecuzione automatica.** La CLI e
   l'hook (`prossimo --formato hook`, sezione "riprese pronte") stampano
   l'azione con l'avvertenza; nessun comando viene eseguito, nessuno stato
   cambiato in automatico. Stesso principio dei messaggi in bacheca: input
   operativo, non autorità.
6. **Vista "riprese pronte"** (`riprese_pronte()`): thread in cui l'agente
   aveva lasciato un checkpoint ripristinabile, il verdetto umano è arrivato
   (chiusura con verdetto) e l'agente non ha ancora scritto nulla dopo — cioè
   la ripresa non è ancora stata presa in carico. Esposta nell'hook e in
   `bacheca.py ripresa`. Il formato `prossimo --formato json` resta l'elenco
   dei soli messaggi pendenti, per compatibilità con i consumatori esistenti.
7. **Append-only e assi di stato invariati**: un checkpoint v2 continua a non
   cambiare lo stato globale del thread (`_ultimo_rilevante` lo salta), la
   dashboard resta read-only (può consumare `ripresa` per il widget "pratiche
   sospese" proposto da Gemini, senza scrivere nulla).

## Non-obiettivi

- Nessun motore di esecuzione: l'azione è testo per un agente/umano che la
  legge e decide.
- Nessuna modifica al registro eventi né alla semantica di
  `verdetto_umano`.
- La Proposta 2 (flusso dichiarato `schema/flusso.v1.json`) è fuori da questa
  RFC: parte solo dopo la verifica di questo pilota.
