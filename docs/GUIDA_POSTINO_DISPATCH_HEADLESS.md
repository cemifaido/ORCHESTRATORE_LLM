# Guida: il postino e il dispatch headless

**Stato**: funzionante e verificato dal vivo. Dispatch headless attivo dal
2026-08-25; **sistema di profili operativi** (standard/brainstorming/super/
smodata, sostituisce i due vecchi interruttori grezzi) dal 2026-08-27 — vedi
sezione dedicata sotto. Questa è la guida operativa di riferimento — cosa fa,
cosa serve per farlo funzionare, come si usa, come si replica su un'altra
macchina. Per la storia delle decisioni e i guardrail concordati con
Gemini/Codex vedi `docs/PIANO_RISVEGLI_AUTOMATICI.md`; per l'idea originale
vedi `docs/PROPOSTA_RIUSO_IDEE_WEFT.md`.

## Il profilo operativo (un solo controllo, non due interruttori)

Fino al 2026-08-26 il Postino si accendeva con due interruttori indipendenti
(`POSTINO_ATTIVO`/`POSTINO_HEADLESS_ATTIVO`, vedi più sotto per la parte
ancora presente sul disco per compatibilità). **Ora ogni progetto ha un solo
profilo operativo**, scelto dalla dashboard (menu a tendina "Profilo
Operativo Postino"), che sostituisce entrambi i vecchi interruttori:

| Profilo | Cosa fa | Stato oggi |
|---|---|---|
| **standard** | Nessuna automazione. Il risveglio resta solo passivo (focus finestra + prompt negli appunti, umano incolla e invia) — identico al vecchio "Postino spento", sempre disponibile, nessun limite. | **Attivo**, default per ogni progetto nuovo |
| **brainstorming** | Dispatch headless reale (l'agente risponde da solo in bacheca), limiti di ritmo larghi. | **Attivo** |
| **super** | Come brainstorming, in più l'agente può scrivere file — mai comandi Git in scrittura. | Selezionabile ma **non ancora attivo**: manca la whitelist di comandi che decide davvero cosa può fare un agente in scrittura (vedi "Limiti noti") |
| **smodata** | Stessa capacità di "super", limiti di ritmo praticamente rimossi (mai davvero infiniti — un tetto assoluto in codice impedisce un loop/costo incontrollato anche qui). | Selezionabile ma **non ancora attivo**, stesso motivo di "super" |

Per **super** e **smodata**, la dashboard mostra onestamente, per ciascun
agente (Claude/Codex/Gemini), se la garanzia sarebbe `enforced` (vincolo
tecnico vero), `prompt_only` (solo un'istruzione nel prompt, nessun blocco
tecnico) o `non_disponibile` (oggi, per tutti — il dispatch non parte
comunque finché non esiste la whitelist). Non promette mai la stessa
protezione per tutti e tre gli agenti sotto un'unica etichetta: Claude ha
oggi il perimetro più restringibile per davvero (`--allowedTools`), Codex e
Gemini restano più spesso legati alla sola disciplina del prompt.

**Git non è mai automatico, in nessun profilo.** Nemmeno "smodata" autorizza
un commit o un push automatico — quello resta sempre un'azione in sessione
interattiva, su ordine esplicito dell'umano, invariato rispetto a sempre.
"Smodata" riguarda solo il ritmo (quante volte/quanto in fretta), non i
permessi.

### Matrice completa: capacità × garanzia reale per agente

Colonne capacità = cosa il profilo *autorizza* in linea di principio.
Colonne agente = cosa quella capacità *garantisce davvero* per ciascuno, non
solo cosa promette a parole — `enforced` (vincolo tecnico imposto dallo
strumento), `prompt_only` (solo istruzione nel prompt, nessun blocco
tecnico), `non_disponibile` (il dispatch non parte, a prescindere).

| Profilo | Dispatch headless | Scrittura file | Git in scrittura | Claude | Codex | Gemini |
|---|---|---|---|---|---|---|
| **standard** | mai | mai | mai | — (nessuna automazione, nulla da garantire) | — | — |
| **brainstorming** | sì (solo risposta in bacheca) | mai | mai | `enforced` | `prompt_only` | `prompt_only` |
| **super** | sì, con scrittura file | sì | mai | `non_disponibile` oggi → `enforced` una volta pronta la whitelist | `non_disponibile` oggi → resterà `prompt_only` anche a regime (`--sandbox` di Codex non espone una whitelist granulare) | `non_disponibile` oggi → resterà `prompt_only` anche a regime (bypass permessi, nessun perimetro scoped) |
| **smodata** | sì, con scrittura file | sì | mai | come "super" | come "super" | come "super" |

Righe "una volta pronta la whitelist"/"a regime" descrivono l'esito atteso
della fase C (bacheca thread `89fbd0ec`/`40f2528b`, in corso con Codex al
momento di scrivere questo): per Codex e Gemini `prompt_only` **resta** anche
a lavoro finito — non è uno stato transitorio, è un limite reale degli
strumenti oggi disponibili, verificato non assunto (vedi "Limiti noti").

Endpoint: `POST /api/bacheca/postino/profilo` (`{progetto_id, profilo}`),
sostituisce i due vecchi `postino/toggle`/`postino/headless/toggle`. Cambia
profilo, pulisce automaticamente gli eventuali vecchi marker
`POSTINO_ATTIVO`/`POSTINO_HEADLESS_ATTIVO` rimasti sul disco (housekeeping,
non serve farlo a mano). Stato letto da `GET /api/bacheca` (campo `profilo`
col DTO completo, `garanzie_per_agente`, `limiti_effettivi`).

**Spegnimento d'emergenza**: seleziona "standard" dal menu — interrompe
tutto (dispatch headless e ritmo automatico), comprese le code già pronte.
I vecchi marker su disco non contano più nulla: anche se rimasti da
un'installazione precedente, il profilo (o la sua assenza, che equivale a
"standard") è l'unica fonte di verità del runtime.

## Cos'è, in una frase

Un meccanismo che toglie l'umano dal ruolo di "postino" tra gli agenti:
quando c'è un messaggio pendente in bacheca, il sistema lo nota da solo e fa
rispondere l'agente destinatario — a finestra (deep-link) o, se abilitato,
in un vero processo in background che legge, decide e scrive la risposta da
solo, senza aprire nulla.

## Come funziona (architettura)

```
messaggi.jsonl cambia
        │
        ▼
watcher (task asyncio dentro il processo FastAPI di interfaccia.py,
poll ogni 2.5s su st_mtime — nessun demone nuovo)
        │
        ▼
per ogni agente con un messaggio pendente non ancora notificato:
        │
        ├─ dispatch_headless = profili_operativi.dispatch_abilitato(profilo)
        │                      (oggi vero solo per "brainstorming")
        │                      AND agente in postino.COMANDI (claude/codex/gemini)
        │
        ├─ SE dispatch_headless ──► postino.dispatch(): lancia claude -p /
        │                           codex exec / agy -p in background, nessuna finestra
        │
        └─ ALTRIMENTI ──────────► _esegui_risveglio_os(): apre/porta in primo
                                   piano l'IDE dell'agente, copia il prompt
                                   negli appunti (richiede un umano che
                                   incolli e invii — resta sempre disponibile
                                   in profilo "standard", senza limiti: è il
                                   risveglio passivo, non automazione)
```

`postino.py` è il motore di policy, usato dal dispatch headless:

- `autorizza(radice, agente, thread_id)` — decide se il turno è permesso
  (profilo, capability, tetti, debounce). Non esegue nulla, solo decide.
- `dispatch(radice, agente, thread_id)` — se autorizzato, lancia davvero il
  processo headless e registra l'esito, incluso il profilo/garanzia/limiti
  applicati.
- `registra_canale(radice, agente, thread_id, canale)` — resta nel codice
  (gating capability/profilo, guardrail di concorrenza) ma **oggi non ha più
  nessun chiamante nel percorso reale**: il risveglio passivo in "standard"
  ci passa deliberatamente accanto, per restare senza limiti come il vecchio
  "Postino spento" (decisione 2026-08-27, vedi sezione profili sopra e
  `docs/PIANO_INDUSTRIALIZZAZIONE.md` §9 per il seguito).

## I tetti (configurabili, mai un file nuovo)

In `config/comandi.json`, blocco `"postino"`:

```json
"postino": {
  "max_turni_thread": 8,
  "max_invii_giorno": 10,
  "debounce_secondi": 300
}
```

- **`max_turni_thread`**: massimo di risvegli automatici consecutivi per un
  thread senza un tocco umano — **condiviso tra tutti gli agenti sullo
  stesso thread**, non contato separatamente per ciascuno: in una
  conversazione a tre, ogni risposta di chiunque consuma lo stesso
  contatore. Un messaggio con `mittente=umano` nel thread azzera il
  conteggio — non è "mai più di N messaggi", è "mai più di N senza che un
  umano intervenga". Vale per **tutti** i canali (headless e deep-link).
  Alzato da 3 a 8 il 2026-08-25 (decisione umana, dopo aver collegato anche
  Gemini) per lasciare margine a conversazioni a tre agenti (~3 scambi a
  testa) restando comunque più vicino allo spirito conservativo iniziale
  che al tetto massimo di 10 che avrebbe coperto 3 scambi pieni a testa.
- **`max_invii_giorno`**: budget giornaliero, ma conta **solo il canale
  headless** — il fallback a finestra apre solo un pannello all'umano, non
  consuma quota dei provider.
- **`debounce_secondi`**: intervallo minimo tra due risvegli automatici per
  la stessa coppia agente+thread.

Un `config/comandi.json` assente, corrotto o con un valore non valido **non
allarga mai** i limiti: ogni chiave torna al default conservativo,
indipendentemente dalle altre. La taratura si fa modificando questi numeri,
mai il codice.

## Cosa serve per farlo funzionare (prerequisiti — la parte costata due giorni)

Il codice era pronto da subito; l'ambiente no. Se replichi questo sistema su
un'altra macchina, questi sono i punti che *davvero* bloccano, in ordine di
probabilità:

1. **Le CLI devono essere installate come eseguibili standalone**, non solo
   come estensione IDE. `claude` e `codex` devono risolversi da riga di
   comando (`Get-Command claude`/`codex` su Windows, `which` altrove).
   L'estensione VS Code/Antigravity **non** basta: è un processo diverso.
2. **La versione di Codex conta**: una build vecchia ("research preview",
   numerazione tipo `0.1.xxxxxxxxxx`) non ha un `exec` headless reale — lancia
   comunque l'interfaccia interattiva e crasha senza un terminale vero.
   Serve `npm install -g @openai/codex@latest` (verificato funzionante da
   `0.149.1` in su).
3. **Il workspace deve fidarsi di Claude**: la prima volta che l'installazione
   standalone di `claude` opera su una cartella, va lanciata **interattiva**
   in quella cartella e va accettato il trust dialog. Senza, `-p` ignora i
   permessi e fallisce. È un gesto umano deliberato, non automatizzabile né
   bypassabile da codice — è un confine di sicurezza voluto.
4. **Windows, se c'è un antivirus/whitelisting di eseguibili** (es.
   ThreatLocker): un eseguibile lanciato da uno script Python, fuori dal
   processo dell'IDE, può essere bloccato silenziosamente con errori che
   sembrano un problema di sandboxing del tool (es. `CreateProcessWithLogonW
   failed: 5`, accesso negato) e non lo sono. Se un dispatch fallisce in modo
   strano su Windows, questo è il primo sospetto da controllare — prima di
   scavare in teorie più complesse.
5. **`PATH` aggiornato di recente non basta da solo**: un processo già in
   esecuzione (compreso il server della dashboard) non vede un PATH
   modificato finché non riparte per davvero. Il pulsante "↻ Riavvia
   Sistema" della dashboard **non** risolve questo: copia l'ambiente dal
   processo vecchio invece di rileggerlo da Windows (bug noto, non ancora
   corretto — vedi sezione limiti sotto). Dopo aver installato/aggiornato
   una CLI o cambiato il PATH, riavvia il processo del server a mano
   (terminarlo e farne partire uno nuovo da una shell aperta di recente),
   o meglio ancora riavvia l'intera macchina/IDE.
6. **Gemini/`agy` non ha un modo scoped di dare i permessi**: le regole
   granulari (`permissions.allow`/`permissionGrants`) si caricano
   correttamente (verificabile nei log CLI) ma il comando resta comunque
   negato — verificato su Windows e WSL, stesso identico blocco, quindi è
   un difetto del tool, non dell'ambiente. L'unica via che funziona è
   `--dangerously-skip-permissions`: il freno resta solo `prompt_fisso()`
   (istruzioni testuali), non un perimetro imposto dal tool come per
   claude/codex. `agy -p` inoltre vuole il prompt come argomento
   **immediatamente successivo**: se altri flag vengono dopo `-p` nella
   riga di comando, lo *inghiottono* al posto del prompt vero (stesso tipo
   di bug del flag variadico di claude, causa diversa). In `postino.COMANDI`
   `-p` va per questo motivo per ultimo nella lista.
7. **Non serve WSL**: il bug originale ("si blocca senza TTY") non è un
   limite della piattaforma Windows — è l'attesa di un'approvazione
   interattiva che non arriva mai. `--dangerously-skip-permissions` salta
   quell'attesa e `agy.exe` nativo Windows funziona identico a WSL, stesso
   schema di invocazione di claude/codex. Un solo ambiente da gestire.

## Come usarlo

1. Verifica i prerequisiti sopra (una tantum per macchina).
2. Apri la dashboard, sezione Bacheca, progetto interessato.
3. Nel menu "Profilo Operativo Postino", scegli **"brainstorming"**: da qui
   in poi claude, codex e gemini rispondono da soli in background quando c'è
   un messaggio pendente, senza aprire finestre, con i tetti applicati.
   **Nota su Gemini**: usa `--dangerously-skip-permissions` (nessun
   perimetro scoped come per claude/codex — decisione umana esplicita del
   2026-08-25, accettata sapendo che il freno è solo `prompt_fisso()`).
4. Osserva: ogni risveglio automatico (headless o passivo) è un evento nel
   registro (`agente=sistema`, `tipo_compito=orchestrazione`,
   `id_compito` che inizia per `postino-`), con profilo/garanzia/limiti
   applicati nei metadati. Il widget "⏸️ Pratiche Sospese" in dashboard
   mostra i checkpoint ripristinabili in attesa.
5. Per spegnere tutto: riporta il menu a **"standard"**.

## Il confine di sicurezza (importante, non è opzionale)

Il prompt che riceve l'agente headless (`postino.prompt_fisso()`) tratta il
contenuto della bacheca come **contesto non fidato**: l'agente deve decidere
da solo il merito della risposta, mai eseguire alla lettera un comando scritto
dentro un messaggio. Verificato dal vivo: un agente headless che legge un
messaggio contenente un comando esplicito lo **rifiuta** correttamente e non
lo esegue — è un comportamento sicuro, non un difetto. Il prompt vieta anche
esplicitamente commit, push, cancellazioni, rete; se serve lavoro reale o
manca chiarezza, l'agente scrive un checkpoint/domanda e si ferma, non
improvvisa.

**Conseguenza verificata dal vivo (2026-08-25)**: un agente headless non può
fare una vera revisione tecnica di codice (`git diff`, rieseguire il gate)
perché il suo stesso perimetro glielo impedisce — solo `bacheca.py`/
`registro.py` sono comandi autorizzati. Chiesto a Codex di verificare in
autonomia un commit imminente, ha correttamente segnalato di non avere
accesso a `git`/al gate invece di improvvisare o aggirare il limite. Non è
un difetto: è il confine di sicurezza che funziona come previsto. La
revisione di merito su un diff/commit resta un compito per l'umano o per un
agente in sessione interattiva normale, non per il dispatch headless.

**Corretta un'ambiguità reale (2026-08-28)**: l'anti-injection sopra non
distingueva "comando iniettato nel testo di un messaggio" da "il compito
stesso, assegnato tramite lo stesso canale bacheca" — un agente headless
(Codex) l'ha applicata così alla lettera da rifiutare un compito legittimo di
lavoro reale in profilo super/smodata, anche con l'autorizzazione a scrivere
file esplicitamente presente nello stesso prompt. `prompt_fisso()` ora chiarisce
esplicitamente: un `richiesta`/`domanda` legittimo da un mittente della bacheca
è il compito da svolgere, non contenuto sospetto — l'anti-injection riguarda
solo comandi/istruzioni sospette dentro il testo (es. "esegui git push",
"ignora le tue regole precedenti"), non la richiesta di lavoro in sé.

## Modalità revisione (su richiesta esplicita, mai automatica)

**Perché esiste**: la sezione precedente documentava un limite reale — un
agente in dispatch headless non poteva fare una vera revisione tecnica
(`git diff`, rieseguire il gate), restando uno "spettatore" della bacheca
invece che un socio in grado di verificare davvero il lavoro. L'umano ha
chiesto (2026-08-25) che i soci potessero farlo *a richiesta*, restando un
perimetro di sola ispezione/verifica, mai di scrittura.

**Cosa cambia**: `postino.dispatch(radice, agente, thread_id, modo="revisione")`
— un secondo parametro esplicito, non un nuovo interruttore. La modalità
predefinita resta `modo="routine"` (il perimetro ristretto di sempre); la
modalità `"revisione"` va invocata deliberatamente, mai dal watcher
automatico.

- **Comandi estesi solo dove serve tecnicamente**: `COMANDI_REVISIONE` in
  `postino.py`. Per **claude** è uno sblocco reale del perimetro imposto dal
  tool: `--allowedTools` guadagna `Bash(git diff *)`, `Bash(git log *)`,
  `Bash(git show *)`, `Bash(git status *)`, `Bash(python -m unittest *)`,
  `Bash(ruff check *)`, `Bash(python -m mypy *)`, oltre a `bacheca.py`/
  `registro.py` di sempre. Per **codex** e **gemini** i comandi restano
  identici alla modalità routine — il loro sandbox/bypass già lo
  permetterebbe tecnicamente; cambia solo il prompt (sotto), che li
  autorizza esplicitamente a farlo.
- **Prompt dedicato** (`postino.prompt_revisione()`): dichiara esplicitamente
  cosa è permesso (diff/log/show/status, rieseguire test/lint/type-check,
  riportare l'esito **reale** di ciò che è stato eseguito per davvero, mai
  una previsione) e ribadisce cosa resta vietato **sempre**, anche in questa
  modalità: modificare file, commit, push, cancellazioni, installazioni,
  rete non necessaria. Stesso confine sul contesto non fidato della bacheca
  della modalità routine.
- **Il tetto_thread si azzera ad ogni turno di revisione**, esattamente come
  un tocco umano (decisione umana esplicita, 2026-08-25: *"nessun tetto
  fisso: si azzera anche su ogni risposta scritta da un agente in modalità
  revisione"*) — non un numero più alto, un reset. `postino._ultimo_reset_thread()`
  prende il più recente fra l'ultimo messaggio `mittente=umano` sul thread e
  l'ultimo invio con `modo="revisione"` sul thread: ogni turno di revisione
  sposta di nuovo in avanti il punto da cui si riparte a contare, non solo il
  primo. Il budget giornaliero (`max_invii_giorno`) e il debounce restano
  invariati — la modalità revisione consuma comunque quota e resta soggetta
  al debounce per coppia agente+thread, evita solo il blocco per "troppi
  turni senza un umano".
- **Ha un pulsante dedicato in dashboard** (dal 2026-08-25): nel dettaglio di
  un thread del pannello Bacheca, "🔎 Revisione da {agente}" per ciascuno dei
  tre agenti — chiama `POST /api/bacheca/postino/revisione`
  (`{progetto_id, agente, thread_id}`), che invoca sempre e solo
  `postino.dispatch(..., modo="revisione")`, mai il default `"routine"`. Il
  watcher automatico continua a chiamare sempre e solo `modo="routine"` di
  default: nessun rischio che la modalità revisione parta da sola. Resta
  comunque invocabile anche direttamente da codice/script per chi preferisce
  quella via.

## Controllo automatico degli aggiornamenti delle CLI

Un compito separato ma imparentato: le tre CLI che il postino usa
(`claude`, `codex`, `agy`) si aggiornano nel tempo, e vale la pena sapere
quando c'è qualcosa di nuovo — senza però aggiornarle mai da sole senza
un verdetto umano, stesso principio del resto del sistema.

**Come funziona** (`verifica_aggiornamenti_cli.py`):

1. `assicura_llama_attivo()` — se il modello locale (llama-server) è già
   acceso, lo usa così com'è; se è spento, lo accende col modello leggero
   Qwen 2.5 3B (solo testo, adatto a riassumere senza il peso del modello
   con visione usato per altri scopi nel progetto).
2. `verifica_tutti()` — confronta la versione installata di ciascun tool
   con l'ultima disponibile: `npm view` per claude/codex (la CLI standalone
   non è distribuita via npm, ma il pacchetto npm segue lo stesso treno di
   release ed è un modo sicuro per controllare senza installare nulla),
   l'endpoint ufficiale del manifest di aggiornamento per `agy`
   (`.../manifests/windows_amd64.json`). Il confronto è numerico per
   componente, non lessicografico (`0.9.0 < 0.10.0`).
3. Se c'è un aggiornamento, `note_rilascio()` recupera il testo delle note
   di rilascio dove esiste una fonte affidabile nota: API GitHub releases
   per Codex, `agy changelog` per Gemini. **Per Claude non c'è una fonte
   nota** — non è un errore, è un limite dichiarato: la notifica arriva
   comunque coi soli numeri di versione, l'approfondimento si fa a mano.
4. Il testo recuperato va al modello locale (`riassumi_note_rilascio()`)
   per un riassunto in italiano semplice — il modello locale non naviga
   mai internet da solo, riceve solo testo già recuperato.
5. `notifica_bacheca_aggiornamento()` apre un thread in bacheca
   (`mittente=sistema`, indirizzato a `claude`) con versione installata,
   disponibile, e il riassunto se c'è.

**Chi lo raccoglie**: non serve che un agente sia sveglio nel momento esatto
in cui gira il controllo — la bacheca è pensata apposta per questo. Il
monitor di un `/loop` attivo, o l'hook di avvio di una sessione futura, nota
il messaggio da solo. A quel punto Claude legge, valuta se vale la pena
(nuove funzionalità rilevanti, fix di sicurezza, o solo rumore), e chiede
all'umano se aggiornare e perché. Solo dopo un consenso esplicito parte
l'aggiornamento vero (`codex update` / `agy update` / `claude update`) —
mai automatico.

**Il trigger, settimanale**: non gira dentro il `/loop` di una sessione
interattiva (si fermerebbe alla chiusura del terminale, e tenerne una aperta
una settimana intera non ha senso). Gira invece come **Attività Pianificata
di Windows** (`OrchestratoreLLM_VerificaAggiornamentiCLI`, ogni lunedì alle
15:00, `schtasks`/`Register-ScheduledTask`), completamente indipendente da
qualunque sessione — la sua unica uscita è la bacheca. Per cambiare
frequenza/orario: `Get-ScheduledTask -TaskName
OrchestratoreLLM_VerificaAggiornamentiCLI | Set-ScheduledTask -Trigger
<nuovo trigger>`, o ricreala con `Register-ScheduledTask`.

**Anche a richiesta, in qualunque momento**: `python
verifica_aggiornamenti_cli.py` fa l'intero giro (controllo, note di
rilascio, riassunto, notifica) in un colpo solo — non serve aspettare
lunedì, chiunque (umano o agente) può lanciarlo quando vuole.

## Limiti noti (non ancora risolti)

- **Il self-restart della dashboard non aggiorna l'ambiente**:
  `_avvia_processo_sostituto()` in `interfaccia.py` lancia il nuovo processo
  con `env=os.environ.copy()`, che copia l'ambiente del processo *corrente*
  invece di rileggerlo da Windows — un PATH cambiato non arriva mai al nuovo
  processo attraverso una catena di riavvii automatici, serve un riavvio
  genuino da una shell fresca. Da correggere se diventa un problema
  ricorrente (es. non usare `os.environ.copy()`, o documentare che dopo un
  cambio di PATH serve sempre un riavvio manuale/di macchina).
- **Livello 3 non implementato**: l'integrazione con il flusso dichiarato
  (fermarsi automaticamente ai passi `approvazione_umana`, notificare invece
  di svegliare) resta rimandata, come deciso da tutti fin dall'inizio —
  prima si osserva il funzionamento reale di questo, poi si valuta.
- **Permessi granulari di `agy` irrisolti**: `permissions.allow`/
  `permissionGrants` si caricano (log CLI lo conferma) ma il comando resta
  negato — causa non isolata nonostante l'indagine su due file di
  configurazione corretti, due chiavi annidate corrette, e due piattaforme
  diverse. Se `agy` risolve questo difetto in una versione futura, si può
  restringere il perimetro di Gemini come già fatto per claude/codex; fino
  ad allora resta sul bypass totale, decisione rivedibile.
- **"Super" e "smodata" selezionabili ma inerti**: manca ancora la matrice
  comandi che decide davvero cosa un agente può scrivere in quei profili — un
  progetto messo in "super" oggi si comporta come "standard" (nessun dispatch
  parte, la dashboard lo dichiara onestamente con `non_disponibile`), non
  come un rischio nascosto. Fase C della sequenza concordata con Codex,
  bacheca thread `89fbd0ec`/`40f2528b`, in corso.
- **`postino.registra_canale()` senza chiamanti runtime**: effetto
  collaterale della migrazione al profilo operativo — il risveglio passivo
  in "standard" ci passa deliberatamente accanto (per restare senza limiti,
  identico al vecchio "Postino spento"), quindi tutto il lavoro fatto su
  quella funzione (gating capability, guardrail di concorrenza) resta
  raggiungibile solo dai suoi test in isolamento, non dal codice reale.
  Deciso come voluto per non ampliare il fix del 2026-08-27; decisione
  rimandata su cosa farne (rimuoverla o riservarla a un futuro canale
  esplicito) — vedi `docs/PIANO_INDUSTRIALIZZAZIONE.md` §9.
