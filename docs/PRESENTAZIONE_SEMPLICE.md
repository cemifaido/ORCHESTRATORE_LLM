# Squadra: a cosa serve e perché conviene

**Squadra** è il nome scelto per la divulgazione del progetto (finora
"orchestratore LLM" solo internamente). Due pagine, senza dettagli tecnici,
pensate per chi non ha seguito il progetto giorno per giorno. Per i dettagli:
[Indice](INDEX.md). Versione impaginata, pensata per essere condivisa:
`docs/PRESENTAZIONE_SEMPLICE.md` è la sorgente testuale; l'artifact pubblicato
in sessione ne è la versione grafica.

## Il problema

Se usi più assistenti AI per programmare (Claude, Codex, Gemini...), oggi il
collo di bottiglia sei tu. Ogni volta che uno di loro deve sapere cosa ha
fatto un altro, tocca a te: copiare pezzi di conversazione da una chat
all'altra, ricordarti chi doveva fare cosa, aprire la sessione giusta al
momento giusto. Più assistenti usi, più tempo perdi a fare da postino tra
loro invece che lavorare.

E anche quando funziona, resta un problema di fiducia: cosa hanno fatto
davvero questi assistenti? Chi ha approvato cosa? Se qualcosa va storto, si
può ricostruire la sequenza degli eventi?

## Il differenziale: zero costi API a consumo

La maggior parte dei framework di orchestrazione multi-agente funziona
chiamando le API dei provider a consumo: più agenti lavorano, più paghi per
token, senza un tetto naturale alla spesa. Qui no: Claude, Codex e Gemini
lavorano tramite gli **abbonamenti che hai già** — lo stesso accesso che
useresti aprendo normalmente la loro chat — non tramite chiamate a pagamento
fatturate a token.

| | Framework tipici | Qui |
|---|---|---|
| Come lavorano gli agenti | Chiamate API a consumo, per ogni agente e ogni turno | Abbonamenti flat già attivi |
| Costo al crescere dell'uso | Cresce con l'uso, spesso in modo imprevedibile | Non cambia: nessun costo per turno |
| Lavoro di routine (triage, sintesi) | Spesso altre chiamate API | Modello AI locale, gratuito |
| Costo reale residuo | Fattura a consumo | Solo l'hardware, che probabilmente hai già |

## Cosa fa questo sistema

Un orchestratore che coordina più assistenti AI, un modello AI locale
gratuito e te, sullo stesso progetto — usando gli abbonamenti che hai già,
senza bisogno di API a pagamento a consumo.

In pratica, quattro pezzi che lavorano insieme:

**1. Una bacheca condivisa.** Un file semplice dove gli assistenti si
lasciano messaggi — richieste, risposte, revisioni — come bigliettini su una
bacheca fisica. Tutto tracciato, niente si perde, nessuna chat caotica.

**2. Il postino.** Invece di essere tu a svegliare ogni assistente e
passargli il messaggio, un processo in background se ne accorge da solo e fa
rispondere l'assistente giusto — davvero, in autonomia, senza che tu apra
nulla. Con limiti rigidi: non troppi giri di seguito senza il tuo intervento,
mai un'azione irreversibile (commit, cancellazioni) senza il tuo via libera
esplicito.

**3. La modalità revisione.** Quando serve che un assistente verifichi
davvero il lavoro di un altro — non solo ne parli, ma rilegga le modifiche,
rilanci i test — può farlo su tua richiesta, sempre in sola lettura, mai in
scrittura.

**4. Un registro di controllo.** Ogni azione automatica, ogni costo, ogni
esito, ogni tua approvazione finisce in un archivio consultabile. In ogni
momento sai cosa è successo, chi lo ha fatto e perché — inclusi i momenti in
cui sei intervenuto tu.

## Cosa cambia per te

- **Molto meno tempo a fare da postino.** Il lavoro di instradamento e
  passaggio di contesto lo fa il sistema, non tu.
- **Resti tu a decidere quello che conta davvero.** Commit, push,
  cancellazioni, scelte importanti: sempre e solo con il tuo via libera
  esplicito. Tutto il resto è automatico.
- **Trasparenza totale.** Niente succede in silenzio: ogni azione automatica
  è tracciata, ripercorribile, spiegabile.
- **Sicurezza per progettazione, non per promessa.** L'automazione è chiusa
  in un perimetro stretto (limiti di frequenza, interruttore di emergenza,
  nessuna azione distruttiva permessa) — non "confidiamo che si comporti
  bene", è tecnicamente impedito che faccia certe cose.
- **Costruito rispettando i termini di servizio di ogni provider.** Solo
  canali ufficiali documentati dai provider stessi (CLI headless dichiarate
  per questo uso, hook ufficiali) — mai automazione della UI, mai
  condivisione di credenziali, mai un abbonamento flat trasformato in API
  nascosta. Non è una garanzia legale universale, è una scelta di design
  documentata fin dall'inizio: la conformità si verifica alle fonti, non si
  assume.
- **Un aiutante gratuito per il lavoro di routine.** Un piccolo modello AI
  locale (gira sull'hardware che hai già, zero costo) si occupa di triage,
  sintesi e prima lettura — mai di scrivere codice o decidere al posto tuo.
- **Non è teoria.** Ogni pezzo descritto sopra è stato costruito e verificato
  dal vivo, con prove reali — non solo progettato su carta.

## Un esempio, in breve

Uno scambio tipico su una modifica reale — generato, verificato e approvato
prima che diventi un commit:

```
Claude       → "Aggiunto retry con backoff a chiamata_api(); test scritti, gate verde."
Codex        → (modalità revisione) "Rilanciato git diff e la suite: 268/268 verdi,
                ruff e mypy puliti. Rischio: il backoff non ha un tetto massimo di attesa."
Locale       → (sintesi) "Proposta implementata e verificata, un rischio segnalato:
                manca il tetto massimo."
Umano        → "Aggiungi il tetto massimo prima di procedere."
Claude       → "Aggiunto tetto di 30s, ritest verde."
Umano        → "Procedi con il commit." ✔ approvato
```

Da notare: l'umano non si limita a dire sì — può chiedere una modifica prima
di approvare, esattamente come farebbe con un collaboratore umano. Il
sistema propone, verifica e riassume; la decisione finale resta sempre tua.

## A chi serve

A chiunque lavori con più di un assistente AI sullo stesso progetto e si sia
stancato di fare il postino umano fra le loro chat — sviluppatori singoli,
piccoli team, chiunque voglia visibilità reale su cosa fa un'automazione AI
sul proprio codice, senza rinunciare al controllo sulle decisioni che
contano.
