# RFC — Piano dichiarato e passi posseduti

**Stato:** APPROVATA (umano, 2026-09-02) e implementata. Slice (a) — campo `piano`, proiezione, `piano_overlap`,
`piano_comandi`/`bacheca.py piano` — e slice (b) — enforcement del dispatch in
`dashboard_risvegli` via `piano_overlap.valuta_dispatch_piano` — sono chiuse
(2026-08-31 → 2026-09-02, vedi `docs/PIANO_INDUSTRIALIZZAZIONE.md` §14.3). Resta
la slice (c): widget "corsie" in dashboard. Questo documento è la spec di
riferimento, aggiornato dove l'implementazione ha precisato una scelta.  
**Ambito:** progetto S14.3.

## Obiettivo e confini

Il piano rende esplicita la divisione del lavoro di un thread e fornisce un
vincolo verificabile prima del dispatch. Non è un motore di esecuzione e non
trasforma il prompt o la dashboard in una fonte di autorità. L'autorità è la
proiezione validata dei record append-only e l'enforcement server-side, che dal
2026-09-02 è agganciato nel watcher: `dashboard_risvegli.calcola_ed_esegui_risvegli`
consulta `piano_overlap.valuta_dispatch_piano` prima di `postino.dispatch` e su
collisione sospende il risveglio automatico, postando una `segnalazione_conflitto`
senza retry.

Il primo slice resta compatibile con `messaggio.v1`: aggiunge soltanto il campo
opzionale `piano` ai record pertinenti. I messaggi v1 esistenti senza il campo
continuano a essere validi e non si introduce `messaggio.v2` né una migrazione.
La presente è la proposta del campo, non una modifica a
`schema/messaggio.v1.json`.

## Modello proposto

`piano` è un oggetto-evento, non una copia mutabile dello stato corrente. Una
proiezione, ricostruita nell'ordine append-only del log, applica gli eventi al
piano del `thread_id`. Ogni evento porta `piano_id` e `passo_id`; il valore di
`thread_id` del passo deve essere identico a quello della busta del messaggio.

```json
{
  "piano": {
    "azione": "crea|aggiorna_passo|proponi_handoff|approva_handoff",
    "piano_id": "piano-s14-3",
    "passo": {
      "id": "s14-3-modello",
      "thread_id": "<thread UUID>",
      "repo": "orchestratore-llm",
      "branch": "main",
      "descrizione": "Modello, proiezione e test del piano",
      "proprietario": null,
      "stato": "non_iniziato",
      "versione": 0,
      "attore_aggiornamento": "umano",
      "idempotency_key": "<UUID o chiave opaca>",
      "write_set": ["bacheca.py", "tests/test_bacheca.py"],
      "read_set": ["schema/messaggio.v1.json"]
    },
    "precondizione": { "versione": 0, "stato": "non_iniziato" }
  }
}
```

Valori ammessi per `stato`: `non_iniziato`, `in_corso`, `fatto`, `bloccato`.
`id` è immutabile entro `piano_id`; `repo`, `branch`, descrizione e set possono
essere corretti soltanto tramite un nuovo evento con precondizione. Il
`proprietario` è chi possiede il lavoro, mentre `attore_aggiornamento` identifica
chi ha emesso l'evento: non sono intercambiabili. `idempotency_key` identifica
una *richiesta di transizione*, non il passo: riusare la stessa chiave con un
payload diverso è un errore.

Un piano deve dichiarare i passi in modo completo prima del dispatch automatico.
Un piano parziale può essere mostrato in UI, ma non abilita automaticamente i
passi che non rispettano i requisiti seguenti.

## Contratto dei set di file

Ogni elemento di `write_set` e `read_set` è una stringa di path o glob, relativa
alla root del `repo` dichiarato. Il set di scrittura è obbligatorio per un
dispatch automatico; il set di lettura è opzionale e, se omesso, vale `[]`.

La normalizzazione proposta è:

1. rifiutare path assoluti, drive/UNC, `.` e `..` come componenti, stringhe
   vuote e separatori finali ambigui;
2. convertire `\\` in `/`, comprimere separatori ripetuti e usare componenti
   relativi alla root;
3. nel profilo Windows v1, confrontare in case-folded (minuscolo Unicode
   semplice); il valore normalizzato, non quello inserito, è quello auditato;
4. ammettere solo glob portabili `*`, `?` e `**` per componente. Brace expansion,
   extglob, negazioni, variabili, output di shell o pattern generati a runtime
   sono `dinamici_o_ambigui`.

Un elenco mancante/vuoto per `write_set`, un elemento invalido, oppure un pattern
dinamico o ambiguo produce `non_dispatchabile`: il sistema non invia il lavoro
automaticamente e registra una segnalazione che chiede set esplicito o decisione
umana. Questo è fail-closed; può produrre un falso positivo, mai un via libera
basato su un'interpretazione incerta.

## Regola di overlap

Per il passo candidato `C` e ogni altro passo `A` in stato `in_corso` (incluso
un passo posseduto da un altro operatore dello stesso ruolo), valutare:

| Coppia | Esito |
| --- | --- |
| `C.write_set × A.write_set` | blocco se overlap o indeterminato |
| `C.write_set × A.read_set` | blocco se overlap o indeterminato |
| `C.read_set × A.write_set` | blocco se overlap o indeterminato |
| `C.read_set × A.read_set` | mai un conflitto |

Il controllo confronta singolarmente i pattern. Può concludere `disgiunto` solo
quando i prefissi letterali normalizzati divergono prima del primo componente
wildcard (per esempio `docs/**` e `tests/**`). In tutti gli altri casi in cui
non possa provare la disgiunzione — wildcard sovrapponibili, `**`, pattern
incompleti o semantica non supportata — restituisce `overlap_o_indeterminato`.
Questa semantica conservativa evita che due glob apparentemente diversi ottengano
un falso via libera.

Pseudocodice di riferimento:

```text
valuta_dispatch(candidato, passi):
    C = normalizza_e_valida(candidato)
    se C.write_set è non_dispatchabile: nega("write_set non deterministico")

    per A grezzo in passi con stato == "in_corso":
        A = normalizza_e_valida(A grezzo)
        se A.write_set è non_dispatchabile: nega("passo attivo non deterministico", A)
        se interseca(C.write_set, A.write_set) != DISGIUNTO: nega("write×write", A)
        se interseca(C.write_set, A.read_set)  != DISGIUNTO: nega("write×read", A)
        se interseca(C.read_set,  A.write_set) != DISGIUNTO: nega("read×write", A)

    consenti_con_avviso_passivo()

interseca(set1, set2):
    per p in set1, q in set2:
        se prefissi_letterali_provano_disgiunzione(p, q): continua
        altrimenti: ritorna OVERLAP_O_INDETERMINATO
    ritorna DISGIUNTO
```

Il diniego deve indicare passo attivo, proprietario, set normalizzati e coppia
che collide; viene registrato come evento e non attiva un retry automatico.

## `prendi-passo`, `offri-passo` e compare-and-set

La proiezione non basta, da sola, a rendere atomica un'acquisizione. Il futuro
sottocomando deve serializzare **lettura della proiezione, verifica della
precondizione e append del nuovo record** mediante il lock locale del registro
(o una primitiva equivalente del suo singolo writer). Non deve fare una lettura,
rilasciare il lock e poi appendere.

`prendi-passo` su un passo `non_iniziato` e senza proprietario presenta
`precondizione.versione = v`; nella sezione atomica, se stato e versione
corrispondono, appende `aggiorna_passo` con proprietario richiedente,
`stato=in_corso`, `versione=v+1`, attore e idempotency key. Se un secondo agente
ha già vinto, la sua precondizione su `v` fallisce e riceve un conflitto, senza
scrivere un secondo possesso.

```text
CAS_prendi(passo_id, attore, atteso_v, chiave):
    con lock_del_registro:
        se esiste evento con chiave e stesso payload: ritorna esito_precedente
        se esiste evento con chiave ma payload diverso: errore_idempotenza
        corrente = proietta(passo_id)
        se corrente.versione != atteso_v o corrente.stato != non_iniziato
           o corrente.proprietario != null: conflitto_senza_append
        append(evento proprietario=attore, stato=in_corso, versione=atteso_v+1)
        ritorna acquisito
```

`offri-passo` non trasferisce un passo `in_corso`: appende una proposta di
handoff con precondizione sulla versione corrente e lascia invariati proprietario
e stato. Solo l'approvazione esplicita del proprietario attuale o dell'umano,
anch'essa CAS sulla medesima versione, può appendere il trasferimento. Un timeout
non costituisce mai approvazione. Per un passo `non_iniziato` senza proprietario,
`offri-passo` può delegare a `CAS_prendi` e poi emettere l'avviso passivo.

## Sequenza prevista dopo l'approvazione

1. Validazione del campo opzionale, proiezione append-only, normalizzazione /
   overlap e test di concorrenza-idempotenza.
2. Enforcement nei sottocomandi bacheca e in postino/dashboard risvegli.
3. Solo allora UI checklist e azioni human-in-the-loop, sempre derivate dalla
   proiezione validata.

