# RFC (bozza) — Stati di consegna del risveglio

**Stato:** bozza, revisione Codex recepita (2026-09-02, thread bacheca
`4ddae141`). Solo spec: transizioni e invarianti. Nessun codice in questo
incremento. In attesa di revisione Gemini e verdetto umano.
**Origine:** PIANO_INDUSTRIALIZZAZIONE.md §15 Slice A (thread bacheca `fb8338d2`).
Codex, 2026-09-02: «distinguere `attenzione_richiamata` / `acquisito_da_hook` /
`preso_in_carico`, ma prima definire transizioni e invarianti; nessun cambio al
profilo Postino standard».

**Modifiche dalla revisione Codex:** (1) gli eventi di consegna vivono in un
JSONL append-only dedicato, `risvegli_notificati.json` resta una cache/proiezione
— la bozza precedente li teneva in una lista dentro un JSON riscritto, non
append-only (incoerente con I1); (2) l'hook non scrive lo stato consegna: emette
una riga in un log append-only separato (`hook_contesto.jsonl`) che la proiezione
incrocia — resta non-mutante; (3) `preso_in_carico` non usa più un confronto di
timestamp fra sorgenti diverse: prova forte = messaggio dell'agente con
`correla_a = id_messaggio`; i fallback usano l'ordine del log append-only.

## Problema

Oggi `dati_locali/orchestrazione/risvegli_notificati.json` tiene un solo bit per
coppia `(agente, id_messaggio)`:

```json
{ "versione_schema": 1, "notificati": { "claude": ["m-1", "m-2"], "codex": [] } }
```

`notificato` significa soltanto «il watcher ha smesso di occuparsene»: copre
insieme casi molto diversi —

- dispatch headless riuscito (l'agente ha *sicuramente* risposto);
- risveglio OS eseguito (focus finestra + clipboard) — l'umano **potrebbe** non
  aver incollato niente;
- `molla` dopo N fallimenti transitori o per un limite deliberato — nessuno ha
  visto il messaggio;
- inizializzazione a freddo (`gia_inizializzato == False`) — marcato senza alcun
  tentativo, per non rispondere a tutto lo storico al primo giro.

Di conseguenza la dashboard non può dire «questo messaggio è stato consegnato ma
non ancora raccolto», e un eventuale meccanismo di sollecito non sa distinguere
«mai arrivato» da «arrivato, in lavorazione».

## Stati proposti

Per coppia `(agente, id_messaggio)`, un solo stato corrente fra:

| Stato | Significato | Evidenza che lo determina |
|---|---|---|
| `in_attesa` | il watcher lo considera pendente, nessuna azione ancora | (assenza di record) |
| `attenzione_richiamata` | il watcher ha agito (dispatch OS, clipboard+deep-link, oppure dispatch headless partito) ma non c'è prova che l'agente lo abbia letto | record scritto dal watcher con `canale` e `azione` |
| `acquisito_da_hook` | l'hook `bacheca.py prossimo --formato hook` dell'agente ha restituito **quel** messaggio nel contesto di un turno | riga in `hook_contesto.jsonl` scritta dall'hook (append-only), incrociata in proiezione per `(agente, id_messaggio)` sul **primo** evento |
| `preso_in_carico` | l'agente ha prodotto un record sul thread che si riferisce **esplicitamente** a quella notifica (`correla_a = id_messaggio`) | proiezione della bacheca: messaggio dell'agente con `correla_a` uguale all'`id_messaggio` della notifica |
| `chiuso_senza_consegna` | il watcher ha rinunciato (limite deliberato, o N fallimenti transitori) senza che nessuno degli stati sopra sia stato raggiunto | evento `molla` del watcher nel log consegne |

`dispatch headless riuscito` non è uno stato a sé. Ci sono **due prove
indipendenti** per `preso_in_carico`, nessuna delle quali confronta timestamp fra
sorgenti diverse:

- **(a) prova di bacheca** — un messaggio dell'agente con `correla_a =
  id_messaggio`. Vale per qualsiasi canale. *Gap odierno*: `bacheca.py rispondi`
  e `presa_in_carico` non impostano `correla_a`; va esteso il comando (e, per
  `presa_in_carico`, verificato che lo schema lo consenta) perché questa diventi
  una prova e non un semplice indizio.
- **(b) prova di provenienza del watcher** — un record in `postino_stato.json`
  (`invii`) con `id_messaggio_attivatore = id_messaggio` ed `esito = inviato`: il
  watcher sa di aver dispatchato *quel* messaggio e che la CLI è uscita con
  successo. Solo canale headless.

Se `postino.dispatch` è `bloccato`/`collisione_piano`, la coppia va in
`chiuso_senza_consegna` con `motivo`.

## Persistenza

Due file, ruoli distinti:

1. **`dati_locali/orchestrazione/consegne_risveglio.jsonl`** — log append-only,
   una riga per **transizione**: `{agente, id_messaggio, stato, motivo?, quando,
   canale?, origine}`. È la fonte di verità. Stesso singolo-writer + lock di
   `scrittura_jsonl` già usato per registro e bacheca.
2. **`dati_locali/orchestrazione/risvegli_notificati.json`** — resta, ma cambia
   ruolo: da fonte di verità a **cache/proiezione** rigenerabile dal log. Il
   watcher continua a leggerlo per la domanda calda «questa coppia è già stata
   gestita?» senza riproiettare il JSONL a ogni giro; viene riscritto (non
   append) come qualunque cache. Se sparisse, si ricostruisce dal log.
3. **`dati_locali/orchestrazione/hook_contesto.jsonl`** — log append-only scritto
   dall'hook: `{agente, id_messaggio, thread_id, quando}` per ogni coppia inclusa
   nel contesto emesso. L'hook resta di sola aggiunta, mai di modifica: non tocca
   né la bacheca né lo stato operativo dei risvegli. La proiezione degli stati
   incrocia questo log (primo evento per coppia) per portare a `acquisito_da_hook`.

## Transizioni ammesse

```
in_attesa ──► attenzione_richiamata ──► acquisito_da_hook ──► preso_in_carico
    │                  │                        │
    │                  └────────────────────────┴──► preso_in_carico   (salto in avanti: prova diretta)
    │
    └──► chiuso_senza_consegna
                  │
attenzione_richiamata ──► chiuso_senza_consegna   (rinuncia dopo tentativi)
```

Regole:

1. **Monotòna in avanti.** L'ordine è
   `in_attesa < attenzione_richiamata < acquisito_da_hook < preso_in_carico`.
   Una transizione non può tornare indietro. `chiuso_senza_consegna` è raggiungibile
   solo da `in_attesa` o `attenzione_richiamata` ed è terminale **per il watcher**
   (smette di agire); una prova esterna successiva (regola 3) può comunque portare
   la coppia a `preso_in_carico`.
2. **Salti in avanti sì, salti indietro no.** Se arriva la prova di
   `preso_in_carico` mentre lo stato è `attenzione_richiamata` (l'agente ha
   risposto senza che l'hook lo abbia registrato), si passa direttamente a
   `preso_in_carico`.
3. **`chiuso_senza_consegna` non blocca una consegna successiva.** Se dopo la
   rinuncia l'agente risponde comunque (l'umano l'ha svegliato a mano), la
   proiezione della bacheca porta la coppia a `preso_in_carico`: la prova diretta
   vince sul record di rinuncia del watcher. Lo stato terminale è terminale per
   il *watcher*, non per la verità del thread.
4. **Reset solo esplicito e umano.** L'unico modo di riportare una coppia a
   `in_attesa` è un'azione umana registrata (serve un comando dedicato, fuori da
   questo incremento). Nessun automatismo lo fa.

## Invarianti

- **I1** — `consegne_risveglio.jsonl` è append-only: non si riscrive né si
  cancella una riga. Lo stato corrente di una coppia `(agente, id_messaggio)` è
  la proiezione delle sue righe in ordine di append (l'ultima transizione valida
  secondo le regole sotto). `risvegli_notificati.json` è cache derivata e non
  vincola nulla: può essere riscritto o rigenerato.
- **I2** — `preso_in_carico` implica almeno una fra: (a) un messaggio di bacheca
  dell'agente con `correla_a = id_messaggio`; (b) un record `invii` in
  `postino_stato.json` con `id_messaggio_attivatore = id_messaggio` ed
  `esito = inviato`. Mai un confronto di timestamp fra bacheca e giro watcher.
- **I3** — `acquisito_da_hook` implica una riga in `hook_contesto.jsonl` per
  quella coppia. Il watcher non può portarci una coppia da solo; l'hook non può
  scrivere in `consegne_risveglio.jsonl` né in `risvegli_notificati.json`.
- **I4** — `chiuso_senza_consegna` non è mai preceduto da `acquisito_da_hook` o
  `preso_in_carico` (quelli sono già consegne riuscite).
- **I5** — Il watcher smette di agire su una coppia appena raggiunge
  `attenzione_richiamata` o oltre: nessun secondo dispatch/risveglio per lo
  stesso `id_messaggio`. (Oggi già così, via `notificati`.)
- **I6** — Il profilo `standard` non introduce nuovi stati: il risveglio passivo
  scrive comunque `attenzione_richiamata` (ha richiamato l'attenzione tramite
  deep-link/clipboard), mai oltre.

## Mappatura sul comportamento del watcher

| Esito dispatch odierno | Stato risultante |
|---|---|
| `inviato` | `preso_in_carico` per prova di provenienza (b): il record `invii` con `id_messaggio_attivatore` ed `esito = inviato` |
| risveglio OS `eseguito`/`test` | `attenzione_richiamata` |
| `os_wake` per canale chiuso | `attenzione_richiamata` |
| `molla` (limite deliberato) | `chiuso_senza_consegna` |
| `molla` (N fallimenti transitori) | `chiuso_senza_consegna` |
| `collisione_piano` (§14.3 slice b) | `chiuso_senza_consegna` (con `motivo`) |
| `ritenta` | nessun record nuovo, resta `in_attesa` |

`chiuso_senza_consegna` porta con sé il `motivo` (già oggi nei record `risvegli`)
così la dashboard può distinguere «rinuncia per tetto» da «collisione di piano»
da «agy in timeout 3 volte».

## Migrazione dal formato attuale

- Nessuna riscrittura dello storico e nessun nuovo campo dentro
  `risvegli_notificati.json`: il nuovo stato vive tutto in
  `consegne_risveglio.jsonl`, che parte vuoto.
- Alla prima lettura, ogni `(agente, id_messaggio)` presente in
  `notificati: {agente: [id...]}` **ma assente** dal log JSONL vale
  `attenzione_richiamata` (assunzione conservativa — «il watcher se n'era
  occupato», senza pretendere di sapere se era andata a buon fine). Non si
  scrive una riga di migrazione: l'assenza dal log + presenza in `notificati`
  *è* già la proiezione di `attenzione_richiamata`.
- Da quel momento le nuove transizioni vanno solo nel log JSONL; `notificati`
  continua a essere aggiornato come cache calda in parallelo, così un lettore
  che conosce solo il vecchio formato non regredisce.
- `gia_inizializzato == False` (prima esecuzione su un progetto) resta com'è: il
  watcher popola `notificati` con tutto lo storico senza scrivere nel log —
  proiettato come `attenzione_richiamata`, «roba vecchia di cui non ci si occupa».

## Fuori perimetro di questo incremento

- Il comando di reset umano di una coppia.
- Qualunque meccanismo di **sollecito** automatico (ri-notifica di una coppia
  ferma in `attenzione_richiamata` da troppo tempo): prima serve osservare gli
  stati reali, poi decidere se e come sollecitare — stesso metodo del Livello 3
  del Postino.
- Modifiche a `postino.py`: il watcher scrive gli stati, il Postino resta com'è.

## Domande chiuse in revisione (Codex, 2026-09-02)

1. **Dove scrive l'hook?** → log `hook_contesto.jsonl` append-only separato, non
   `risvegli_notificati.json`. L'hook resta non-mutante; il suo fallimento non
   blocca l'injection del contesto. Recepito nella sezione "Persistenza".
2. **Finestra temporale per `preso_in_carico`?** → nessuna. I timestamp fra
   bacheca e giro watcher non sono confrontabili (e il dispatch headless sincrono
   può rispondere *prima* che il record sia persistito). Prova = `correla_a` o
   provenienza del watcher; fallback = ordine del log append-only. Recepito in I2.
3. **`chiuso_senza_consegna` per-motivo o stato unico + campo?** → stato unico +
   `motivo`, corretto per UI/metriche. Non moltiplicare stati. Confermata la
   proposta.

## Domande ancora aperte

- **`correla_a` come prova.** Perché `preso_in_carico` (a) sia una *prova* e non
  un indizio serve che `bacheca.py rispondi` e `bacheca.py prendi`
  (`presa_in_carico`) impostino `correla_a = id_messaggio` quando rispondono a un
  risveglio. Va deciso: (i) estendere quei comandi con un `--correla-a` che
  l'hook suggerisce nel contesto emesso; (ii) verificare che lo schema
  `messaggio.v1` ammetta `correla_a` su un record `presa_in_carico`
  (`additionalProperties: false` sul ramo tipizzato?). Se non si fa, `preso_in_carico`
  si regge solo sulla prova (b), quindi solo per il canale headless.
- **Ricostruzione della cache.** Se `risvegli_notificati.json` e il log JSONL
  divergono (crash a metà scrittura), quale vince? Proposta: il log è la verità,
  la cache si rigenera; ma serve un punto in cui la rigenerazione avviene senza
  bloccare il watcher.
