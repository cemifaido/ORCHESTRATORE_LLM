from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import bacheca
import postino
import profili_operativi
import registro


def _radice_attiva(tmp: str) -> Path:
    radice = Path(tmp)
    flag = radice / "dati_locali" / "orchestrazione" / "POSTINO_ATTIVO"
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text("POSTINO_ATTIVO=1\n", encoding="utf-8")
    # I marker legacy non attivano piu' il Postino: le fixture scelgono il
    # profilo brainstorming in modo esplicito.
    profili_operativi.imposta(radice, "brainstorming")
    return radice


def _scrivi_invii(radice: Path, invii: list[dict]) -> None:
    percorso = radice / "dati_locali" / "orchestrazione" / "postino_stato.json"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(
        json.dumps({"versione_schema": 1, "invii": invii}), encoding="utf-8"
    )


def _invio(
    minuti_fa: int, *, agente: str = "codex", thread_id: str = "t-postino",
    canale: str = "headless", modo: str | None = None,
) -> dict:
    quando = (datetime.now(timezone.utc) - timedelta(minutes=minuti_fa)).isoformat()
    return {"quando": quando, "agente": agente, "thread_id": thread_id, "canale": canale, "modo": modo, "codice": 0}


class PostinoPolicyTest(unittest.TestCase):
    """Guardrail del controllore (docs/PIANO_RISVEGLI_AUTOMATICI.md): opt-in
    fail-closed, budget solo headless, tetto per thread su tutti i canali con
    azzeramento al tocco umano, debounce per coppia agente+thread."""

    def test_kill_switch_default_spento(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            esito = postino.autorizza(Path(tmp), "claude", "t-postino")
            self.assertEqual(esito, {"esito": "bloccato", "motivo": "profilo_standard"})

    def test_autorizzato_con_opt_in_esplicito(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            esito = postino.autorizza(_radice_attiva(tmp), "claude", "t-postino")
            self.assertEqual(esito, {"esito": "autorizzato"})

    def test_fail_closed_su_stato_corrotto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            percorso = radice / "dati_locali" / "orchestrazione" / "postino_stato.json"
            percorso.write_text("json rotto {", encoding="utf-8")
            esito = postino.autorizza(radice, "claude", "t-postino")
            self.assertEqual(esito, {"esito": "bloccato", "motivo": "stato_non_leggibile"})

    def test_budget_giornaliero_conta_solo_headless(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            tetto = postino.LIMITI_PREDEFINITI["max_invii_giorno"]
            # N deep-link odierni su thread diversi: il budget headless resta libero
            _scrivi_invii(radice, [
                _invio(i + 1, thread_id=f"t-{i}", canale="deep_link") for i in range(tetto)
            ])
            self.assertEqual(postino.autorizza(radice, "claude", "t-postino"), {"esito": "autorizzato"})
            # N headless odierni (N = tetto del profilo attivo): budget esaurito
            _scrivi_invii(radice, [
                _invio(i + 1, thread_id=f"t-{i}", canale="headless") for i in range(tetto)
            ])
            self.assertEqual(
                postino.autorizza(radice, "claude", "t-postino"),
                {"esito": "bloccato", "motivo": "budget_giornaliero"},
            )

    def test_record_storico_senza_canale_conta_come_headless(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            tetto = postino.LIMITI_PREDEFINITI["max_invii_giorno"]
            invii = [_invio(i + 1, thread_id=f"t-{i}") for i in range(tetto)]
            for invio in invii:
                del invio["canale"]
            _scrivi_invii(radice, invii)
            self.assertEqual(
                postino.autorizza(radice, "claude", "t-postino"),
                {"esito": "bloccato", "motivo": "budget_giornaliero"},
            )

    def test_e_di_oggi_confronto_semantico_non_prefisso_di_stringa(self) -> None:
        """Guardrail L4 (revisione sicurezza, 2026-08-25): un confronto sulla
        data vera, non su un prefisso di stringa ISO."""
        oggi = datetime(2026, 8, 25, tzinfo=timezone.utc).date()
        self.assertTrue(postino._e_di_oggi("2026-08-25T09:00:00+00:00", oggi))
        self.assertTrue(postino._e_di_oggi("2026-08-25T09:00:00.123456+00:00", oggi))
        self.assertFalse(postino._e_di_oggi("2026-08-24T23:59:59+00:00", oggi))

    def test_e_di_oggi_timestamp_illeggibile_conta_come_oggi(self) -> None:
        """Fail-closed: un timestamp non parsabile non deve mai far sotto-contare
        il budget, quindi si conta come 'di oggi'."""
        oggi = datetime(2026, 8, 25, tzinfo=timezone.utc).date()
        self.assertTrue(postino._e_di_oggi("non-un-timestamp", oggi))
        self.assertTrue(postino._e_di_oggi("", oggi))

    def test_tetto_thread_vale_per_tutti_i_canali(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            _scrivi_invii(radice, [
                _invio(30, canale="deep_link"), _invio(20, canale="deep_link"), _invio(10, canale="deep_link"),
            ])
            self.assertEqual(
                postino.autorizza(radice, "claude", "t-postino"),
                {"esito": "bloccato", "motivo": "tetto_thread"},
            )

    def test_tocco_umano_azzera_il_tetto_del_thread(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            # 3 invii vecchi di un'ora sul thread, poi un messaggio umano ADESSO
            _scrivi_invii(radice, [_invio(60 + i) for i in range(3)])
            messaggio = bacheca.costruisci_messaggio(
                mittente="umano", destinatari=["claude"], tipo="richiesta",
                testo="verdetto: procedete", thread_id="t-postino",
            )
            bacheca.aggiungi_messaggio(
                radice / "dati_locali" / "orchestrazione" / "messaggi.jsonl", messaggio
            )
            self.assertEqual(postino.autorizza(radice, "claude", "t-postino"), {"esito": "autorizzato"})

    def test_debounce_per_coppia_agente_thread(self) -> None:
        stato = {"versione_schema": 1, "invii": [_invio(1, agente="claude")]}
        motivo = postino._motivo_blocco(
            stato, "claude", "t-postino", datetime.now(timezone.utc), postino.LIMITI_PREDEFINITI
        )
        self.assertEqual(motivo, "debounce")
        # stesso thread, agente diverso: niente debounce (e sotto il tetto giri)
        motivo = postino._motivo_blocco(
            stato, "codex", "t-postino", datetime.now(timezone.utc), postino.LIMITI_PREDEFINITI
        )
        self.assertIsNone(motivo)


class CaricaLimitiTest(unittest.TestCase):
    """I limiti sono configurabili dal blocco 'postino' di config/comandi.json;
    un config assente/corrotto/invalido non deve mai ALLARGARE i limiti."""

    def _scrivi_config(self, radice: Path, contenuto: str) -> None:
        percorso = radice / "config" / "comandi.json"
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(contenuto, encoding="utf-8")

    def test_config_assente_usa_i_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(postino.carica_limiti(Path(tmp)), postino.LIMITI_PREDEFINITI)

    def test_config_valido_sovrascrive_i_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            self._scrivi_config(radice, json.dumps({
                "versione_schema": 1,
                "postino": {"max_turni_thread": 5, "max_invii_giorno": 30, "debounce_secondi": 60},
            }))
            self.assertEqual(
                postino.carica_limiti(radice),
                {"max_turni_thread": 5, "max_invii_giorno": 30, "debounce_secondi": 60},
            )

    def test_valori_non_validi_tornano_al_default_chiave_per_chiave(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            self._scrivi_config(radice, json.dumps({
                "postino": {"max_turni_thread": 0, "max_invii_giorno": "tanti", "debounce_secondi": 120},
            }))
            limiti = postino.carica_limiti(radice)
            self.assertEqual(limiti["max_turni_thread"], postino.LIMITI_PREDEFINITI["max_turni_thread"])
            self.assertEqual(limiti["max_invii_giorno"], postino.LIMITI_PREDEFINITI["max_invii_giorno"])
            self.assertEqual(limiti["debounce_secondi"], 120)

    def test_config_corrotto_usa_i_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            self._scrivi_config(radice, "json rotto {")
            self.assertEqual(postino.carica_limiti(radice), postino.LIMITI_PREDEFINITI)

    def test_override_enorme_e_clampato_al_tetto_rigido(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            self._scrivi_config(radice, json.dumps({
                "postino": {"max_turni_thread": 999999, "max_invii_giorno": 999999, "debounce_secondi": 999999},
            }))
            self.assertEqual(postino.carica_limiti(radice), postino.LIMITI_MASSIMI)

    def test_autorizza_usa_i_limiti_del_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            # tetto per thread abbassato a 1: il secondo risveglio va bloccato
            self._scrivi_config(radice, json.dumps({"postino": {"max_turni_thread": 1}}))
            _scrivi_invii(radice, [_invio(10)])
            self.assertEqual(
                postino.autorizza(radice, "claude", "t-postino"),
                {"esito": "bloccato", "motivo": "tetto_thread"},
            )


class PostinoDispatchTest(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch(
            "postino.capability_policy.autorizza_automazione",
            return_value={"esito": "autorizzato", "capability": "test_cli_headless"},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_dispatch_simulato_registra_stato_e_registro(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            esegui = MagicMock(return_value=MagicMock(returncode=0))
            # shutil.which mockato: su Windows un nome nudo ("claude") non risolve
            # mai un wrapper .cmd/.ps1 via CreateProcess (bug reale trovato in
            # verifica live) - dispatch deve sempre passare dal percorso risolto.
            with patch("postino.shutil.which", return_value=r"C:\fake\claude.cmd"):
                esito = postino.dispatch(radice, "claude", "t-postino", esegui=esegui)

            self.assertEqual(esito["esito"], "inviato")
            self.assertEqual(esito["canale"], "headless")
            self.assertIn("prompt_sha256", esito)
            comando = esegui.call_args.args[0]
            self.assertEqual(comando[0], r"C:\fake\claude.cmd")
            self.assertEqual(comando[1], "-p")
            self.assertFalse(esegui.call_args.kwargs["shell"])

            stato = json.loads(
                (radice / "dati_locali" / "orchestrazione" / "postino_stato.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(stato["invii"]), 1)
            eventi = registro.leggi_eventi(radice / "dati_locali" / "orchestrazione" / "eventi.jsonl")
            self.assertEqual(len(eventi), 1)
            self.assertEqual(eventi[0]["agente"], "sistema")
            self.assertNotIn("Sei claude", json.dumps(eventi[0]), "mai il testo del prompt nel registro")
            record = eventi[0]["metadati"]["postino"]
            self.assertEqual(record["profilo"], "brainstorming")
            self.assertIsNotNone(record["revisione_profilo"])
            self.assertEqual(record["garanzia"], "enforced")

    def test_super_e_smodata_usano_whitelist_claude_di_scrittura_file(self) -> None:
        """La garanzia enforced di Claude deve derivare dalla CLI, non dal prompt."""
        for nome_profilo in ("super", "smodata"):
            with self.subTest(profilo=nome_profilo), tempfile.TemporaryDirectory() as tmp:
                radice = Path(tmp)
                profili_operativi.imposta(radice, nome_profilo)
                esegui = MagicMock(return_value=MagicMock(returncode=0))
                with patch("postino.shutil.which", return_value=r"C:\\fake\\claude.cmd"):
                    esito = postino.dispatch(radice, "claude", "t-postino", esegui=esegui)

                self.assertEqual(esito["esito"], "inviato")
                self.assertEqual(esito["garanzia"], "enforced")
                comando = esegui.call_args.args[0]
                allowlist = next(arg for arg in comando if arg.startswith("--allowedTools="))
                voci = allowlist.removeprefix("--allowedTools=").split(",")
                self.assertIn("Edit", voci)
                self.assertIn("Write", voci)
                self.assertIn("Bash(git status *)", voci)
                self.assertIn("Bash(git diff *)", voci)
                self.assertIn("Bash(git log *)", voci)
                self.assertNotIn("Bash", voci)
                self.assertNotIn("git commit", allowlist)
                self.assertNotIn("git push", allowlist)

    def test_super_e_smodata_registrano_prompt_only_per_codex_e_gemini(self) -> None:
        for nome_profilo in ("super", "smodata"):
            for agente in ("codex", "gemini"):
                with self.subTest(profilo=nome_profilo, agente=agente), tempfile.TemporaryDirectory() as tmp:
                    radice = Path(tmp)
                    profili_operativi.imposta(radice, nome_profilo)
                    esegui = MagicMock(return_value=MagicMock(returncode=0))
                    with patch("postino.shutil.which", return_value=r"C:\\fake\\agente.cmd"):
                        esito = postino.dispatch(radice, agente, "t-postino", esegui=esegui)

                    self.assertEqual(esito["esito"], "inviato")
                    self.assertEqual(esito["garanzia"], "prompt_only")

    def test_marker_legacy_non_riattiva_il_dispatch_standard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            flag = radice / "dati_locali" / "orchestrazione" / "POSTINO_ATTIVO"
            flag.parent.mkdir(parents=True)
            flag.write_text("POSTINO_ATTIVO=1\n", encoding="utf-8")
            esegui = MagicMock()
            esito = postino.dispatch(radice, "claude", "t-postino", esegui=esegui)
            self.assertEqual(esito, {"esito": "bloccato", "motivo": "profilo_standard"})
            esegui.assert_not_called()

    def test_profilo_standard_blocca_prima_del_gate_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("postino.capability_policy.autorizza_automazione") as capability:
                esito = postino.dispatch(Path(tmp), "claude", "t-postino")
            self.assertEqual(esito, {"esito": "bloccato", "motivo": "profilo_standard"})
            capability.assert_not_called()

    def test_dispatch_eseguibile_non_trovato_non_esplode_e_si_registra(self) -> None:
        """Se il comando non e' installato/risolvibile (successo qui su questa
        stessa macchina prima di installare claude), dispatch non deve mai
        propagare un'eccezione: il watcher la logga e basta, e senza
        registrazione riproverebbe ogni 2.5s all'infinito senza che i tetti
        (che contano solo gli invii registrati) possano mai frenarlo."""
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            esegui = MagicMock()
            with patch("postino.shutil.which", return_value=None):
                esito = postino.dispatch(radice, "claude", "t-postino", esegui=esegui)

            self.assertEqual(esito["esito"], "errore")
            self.assertEqual(esito["motivo"], "eseguibile_non_trovato")
            esegui.assert_not_called()

            stato = json.loads(
                (radice / "dati_locali" / "orchestrazione" / "postino_stato.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(stato["invii"]), 1, "il tentativo fallito va comunque registrato")

    def test_dispatch_eseguibile_non_trovato_conta_per_debounce(self) -> None:
        """Un tentativo fallito consuma comunque il conteggio dei tetti: e' la
        difesa contro il retry ogni 2.5s senza mai essere frenato."""
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            with patch("postino.shutil.which", return_value=None):
                postino.dispatch(radice, "claude", "t-postino", esegui=MagicMock())
                secondo = postino.autorizza(radice, "claude", "t-postino")

            self.assertEqual(secondo, {"esito": "bloccato", "motivo": "debounce"})

    def test_dispatch_nonzero_salva_diagnostica_redatta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            esegui = MagicMock(return_value=MagicMock(
                returncode=1,
                stdout="Errore agy: Authorization: Bearer my_secret_token_123456789 state=oauth_state_123456789",
            ))
            with patch("postino.shutil.which", return_value=r"C:\\fake\\agy.cmd"):
                esito = postino.dispatch(radice, "gemini", "t-postino", esegui=esegui)

            self.assertEqual(esito["esito"], "inviato")
            self.assertEqual(esito["codice"], 1)
            self.assertEqual(esito["diagnostica"]["tipo"], "codice_uscita_non_zero")
            log = Path(esito["diagnostica"]["log_output"]).read_text(encoding="utf-8")
            self.assertIn("Errore agy", log)
            self.assertNotIn("my_secret_token_123456789", log)
            self.assertNotIn("oauth_state_123456789", log)
            self.assertIn("[REDACTED_SECRET]", log)

    def test_dispatch_timeout_non_propagato_e_diagnosticato(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            with patch("postino.shutil.which", return_value=r"C:\\fake\\agy.cmd"):
                esito = postino.dispatch(
                    radice, "gemini", "t-postino",
                    esegui=MagicMock(side_effect=subprocess.TimeoutExpired("agy", 300)),
                )

            self.assertEqual(esito["esito"], "errore")
            self.assertEqual(esito["motivo"], "timeout")
            self.assertEqual(esito["diagnostica"]["tipo"], "timeout")
            log = Path(esito["diagnostica"]["log_output"]).read_text(encoding="utf-8")
            self.assertIn("timeout di 300", log)

    def test_dispatch_rifiuta_capability_non_autorizzata(self) -> None:
        # 'locale' e' un agente valido nel sistema bacheca ma non e' mai stato
        # pensato come bersaglio del postino (non e' in COMANDI): rappresenta
        # qui "capability non provata", lo stesso ruolo che 'gemini' aveva
        # prima di essere verificata e aggiunta (2026-08-25).
        with tempfile.TemporaryDirectory() as tmp:
            esegui = MagicMock()
            esito = postino.dispatch(_radice_attiva(tmp), "locale", "t-postino", esegui=esegui)
            self.assertEqual(esito, {"esito": "bloccato", "motivo": "capability_non_autorizzata"})
            esegui.assert_not_called()

    def test_dispatch_bloccato_da_catalogo_registra_diagnostica_e_non_esegue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            esegui = MagicMock()
            with patch("postino.capability_policy.autorizza_automazione", return_value={
                "esito": "bloccato", "motivo": "capability_scaduta", "capability": "claude_cli_headless",
            }):
                esito = postino.dispatch(radice, "claude", "t-postino", esegui=esegui)
            self.assertEqual(esito["motivo"], "capability_scaduta")
            esegui.assert_not_called()
            percorso = radice / "dati_locali" / "orchestrazione" / "capability_blocchi.jsonl"
            self.assertIn("capability_scaduta", percorso.read_text(encoding="utf-8"))

    def test_dispatch_bloccato_da_kill_switch_non_esegue_nulla(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            esegui = MagicMock()
            esito = postino.dispatch(Path(tmp), "claude", "t-postino", esegui=esegui)
            self.assertEqual(esito, {"esito": "bloccato", "motivo": "profilo_standard"})
            esegui.assert_not_called()

    def test_registra_canale_consuma_contatori_ma_non_budget_headless(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            esito = postino.registra_canale(radice, "gemini", "t-postino", "deep_link")
            self.assertEqual(esito["esito"], "registrato")
            stato = json.loads(
                (radice / "dati_locali" / "orchestrazione" / "postino_stato.json").read_text(encoding="utf-8")
            )
            self.assertEqual(stato["invii"][0]["canale"], "deep_link")

    def test_registra_canale_ri_verifica_policy_sotto_lock(self) -> None:
        """Guardrail (trovato da Codex in revisione, 2026-08-26, sullo stesso
        schema di dispatch()): il chiamante (interfaccia.py) autorizza con
        autorizza() e poi esegue l'azione OS PRIMA di chiamare
        registra_canale() - fra i due passaggi il budget puo' essersi gia'
        esaurito per un'altra chiamata concorrente. registra_canale() deve
        rifiutarsi invece di superare il tetto in silenzio."""
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            percorso_config = radice / "config" / "comandi.json"
            percorso_config.parent.mkdir(parents=True, exist_ok=True)
            percorso_config.write_text(
                json.dumps({"versione_schema": 1, "postino": {"max_turni_thread": 1}}), encoding="utf-8",
            )
            # stesso thread: il tetto per thread vale per TUTTI i canali (deep_link
            # incluso), non solo per l'headless.
            primo = postino.registra_canale(radice, "gemini", "t-postino", "deep_link")
            secondo = postino.registra_canale(radice, "codex", "t-postino", "deep_link")

            self.assertEqual(primo["esito"], "registrato")
            self.assertEqual(secondo, {"esito": "bloccato", "motivo": "tetto_thread"})
            stato = postino._leggi_stato(radice)
            assert stato is not None
            self.assertEqual(len(stato["invii"]), 1)


class PostinoModoRevisioneTest(unittest.TestCase):
    """Modalita' revisione (decisione umana, 2026-08-25): su richiesta esplicita
    i soci possono ispezionare/verificare davvero, non solo commentare in
    bacheca; i suoi turni azzerano il tetto_thread come un tocco umano, ad
    ogni risposta scritta in questa modalita' (nessun tetto fisso alzato)."""

    def setUp(self) -> None:
        patcher = patch(
            "postino.capability_policy.autorizza_automazione",
            return_value={"esito": "autorizzato", "capability": "test_cli_headless"},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_dispatch_modo_revisione_usa_comandi_estesi_e_registra_modo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            esegui = MagicMock(return_value=MagicMock(returncode=0))
            with patch("postino.shutil.which", return_value=r"C:\fake\claude.cmd"):
                esito = postino.dispatch(radice, "claude", "t-postino", modo="revisione", esegui=esegui)

            self.assertEqual(esito["esito"], "inviato")
            self.assertEqual(esito["modo"], "revisione")
            comando = esegui.call_args.args[0]
            self.assertIn("Bash(git diff *)", comando[2])
            self.assertIn("Bash(ruff check *)", comando[2])
            self.assertIn("Bash(python -m mypy *)", comando[2])

            stato = json.loads(
                (radice / "dati_locali" / "orchestrazione" / "postino_stato.json").read_text(encoding="utf-8")
            )
            self.assertEqual(stato["invii"][0]["modo"], "revisione")

    def test_dispatch_modo_routine_predefinito_usa_comandi_ristretti(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            esegui = MagicMock(return_value=MagicMock(returncode=0))
            with patch("postino.shutil.which", return_value=r"C:\fake\claude.cmd"):
                postino.dispatch(radice, "claude", "t-postino", esegui=esegui)

            comando = esegui.call_args.args[0]
            self.assertNotIn("git diff", comando[2])
            stato = json.loads(
                (radice / "dati_locali" / "orchestrazione" / "postino_stato.json").read_text(encoding="utf-8")
            )
            self.assertEqual(stato["invii"][0]["modo"], "routine")

    def test_invio_revisione_azzera_il_tetto_del_thread(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            # 3 invii routine (default max_turni_thread=3) esauriscono il tetto
            _scrivi_invii(radice, [_invio(60 + i) for i in range(3)])
            self.assertEqual(
                postino.autorizza(radice, "claude", "t-postino"),
                {"esito": "bloccato", "motivo": "tetto_thread"},
            )
            # un invio in modalita' revisione ADESSO azzera il tetto, come un tocco umano
            invii = json.loads(
                (radice / "dati_locali" / "orchestrazione" / "postino_stato.json").read_text(encoding="utf-8")
            )["invii"]
            invii.append(_invio(0, modo="revisione"))
            _scrivi_invii(radice, invii)
            self.assertEqual(postino.autorizza(radice, "claude", "t-postino"), {"esito": "autorizzato"})

    def test_ogni_invio_revisione_azzera_di_nuovo_il_tetto(self) -> None:
        """'si azzera anche su ogni risposta scritta da un agente in modalita'
        revisione' (decisione umana, 2026-08-25): non solo il primo turno di
        revisione, ma OGNI turno sposta in avanti il punto di reset."""
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            invii = [_invio(50, modo="revisione")]
            invii += [_invio(40 - i) for i in range(3)]  # 3 routine dopo il primo reset: esauriscono il tetto
            _scrivi_invii(radice, invii)
            self.assertEqual(
                postino.autorizza(radice, "claude", "t-postino"),
                {"esito": "bloccato", "motivo": "tetto_thread"},
            )
            invii.append(_invio(1, modo="revisione"))  # nuovo turno di revisione: azzera di nuovo
            _scrivi_invii(radice, invii)
            self.assertEqual(postino.autorizza(radice, "claude", "t-postino"), {"esito": "autorizzato"})

    def test_invio_revisione_su_altro_thread_non_azzera(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            invii = [_invio(60 + i) for i in range(3)]
            invii.append(_invio(0, thread_id="altro-thread", modo="revisione"))
            _scrivi_invii(radice, invii)
            self.assertEqual(
                postino.autorizza(radice, "claude", "t-postino"),
                {"esito": "bloccato", "motivo": "tetto_thread"},
            )


class ConcorrenzaStatoTest(unittest.TestCase):
    """Guardrail H5 (revisione di sicurezza v3, 2026-08-25): il watcher
    automatico e il pulsante 'Revisione' della dashboard possono chiamare
    dispatch() nello stesso momento - senza un lock, due read-modify-write
    concorrenti su postino_stato.json si sovrascrivono a vicenda."""

    def test_prenota_invio_impedisce_doppia_autorizzazione_sullo_stesso_budget(self) -> None:
        """Guardrail approfondito (trovato da Codex in modalita' revisione,
        2026-08-26, sul primo fix H5): un lock solo sulla scrittura finale
        non basta - due dispatch concorrenti potevano leggere lo stesso
        budget "ancora libero" ed essere autorizzati entrambi, superando il
        tetto. _prenota_invio deve ri-verificare la policy DENTRO lo stesso
        lock in cui prenota il turno, cosi' la seconda chiamata vede gia'
        la prenotazione della prima e viene bloccata."""
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            percorso_config = radice / "config" / "comandi.json"
            percorso_config.parent.mkdir(parents=True, exist_ok=True)
            percorso_config.write_text(
                json.dumps({"versione_schema": 1, "postino": {"max_invii_giorno": 1}}), encoding="utf-8",
            )
            ora = datetime.now(timezone.utc)
            record_a = {
                "id": "a", "quando": ora.isoformat(), "agente": "claude", "thread_id": "t-a",
                "canale": "headless", "modo": "routine", "prompt_sha256": "x", "codice": None,
            }
            record_b = {
                "id": "b", "quando": ora.isoformat(), "agente": "codex", "thread_id": "t-b",
                "canale": "headless", "modo": "routine", "prompt_sha256": "y", "codice": None,
            }

            motivo_a = postino._prenota_invio(radice, "claude", "t-a", ora, record_a)
            motivo_b = postino._prenota_invio(radice, "codex", "t-b", ora, record_b)

            self.assertIsNone(motivo_a)
            self.assertEqual(motivo_b, "budget_giornaliero")
            stato = postino._leggi_stato(radice)
            assert stato is not None
            self.assertEqual(len(stato["invii"]), 1)
            self.assertEqual(stato["invii"][0]["id"], "a")

    def test_finalizza_invio_aggiorna_solo_il_record_giusto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            stato = {
                "versione_schema": 1,
                "invii": [
                    {**_invio(0, agente="claude", thread_id="t-a"), "id": "a", "codice": None},
                    {**_invio(0, agente="codex", thread_id="t-b"), "id": "b", "codice": None},
                ],
            }
            postino._scrivi_stato(radice, stato)

            postino._finalizza_invio(radice, "b", 0)

            stato_finale = postino._leggi_stato(radice)
            assert stato_finale is not None
            per_id = {i["id"]: i["codice"] for i in stato_finale["invii"]}
            self.assertEqual(per_id, {"a": None, "b": 0})

    def test_scrivi_stato_produce_sempre_json_valido_anche_se_interrotta(self) -> None:
        """Scrittura atomica: il file temporaneo viene creato accanto al
        percorso reale e rinominato solo a scrittura completata - il
        percorso reale non e' mai visibile a meta' scrittura."""
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            postino._scrivi_stato(radice, {"versione_schema": 1, "invii": [_invio(0)]})
            percorso = radice / "dati_locali" / "orchestrazione" / "postino_stato.json"
            # nessun file temporaneo residuo dopo una scrittura riuscita
            residui = list(percorso.parent.glob(".postino_stato_*.tmp"))
            self.assertEqual(residui, [])
            self.assertEqual(json.loads(percorso.read_text(encoding="utf-8"))["invii"][0]["thread_id"], "t-postino")

    def test_blocco_stato_rimuove_lock_abbandonato(self) -> None:
        """Un lock piu' vecchio del timeout si considera abbandonato (processo
        terminato senza pulire, es. kill -9) e viene rimosso invece di
        bloccare per sempre - stesso principio fail-safe del resto del modulo."""
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            percorso_lock = postino._percorso_lock_stato(radice)
            percorso_lock.parent.mkdir(parents=True, exist_ok=True)
            percorso_lock.write_text("", encoding="utf-8")
            vecchio = time.time() - 400
            os.utime(percorso_lock, (vecchio, vecchio))

            with postino._blocco_stato(radice, timeout_secondi=310.0):
                pass  # se il lock abbandonato non viene ripulito, questo si blocca/solleva

            self.assertFalse(percorso_lock.exists())

    def test_blocco_stato_con_timeout_breve_su_lock_attivo_solleva_timeout(self) -> None:
        """Guardrail (bug trovato scrivendo scrittura_jsonl.py, 2026-08-26,
        revisione Codex): un lock fresco (attivamente detenuto, non
        abbandonato) con un timeout_secondi breve deve far scadere
        TimeoutError, non essere trattato come abbandonato solo perche' il
        chiamante ha un timeout corto - la soglia di abbandono e' fissa
        (SOGLIA_LOCK_ABBANDONATO_SECONDI), indipendente da timeout_secondi."""
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            percorso_lock = postino._percorso_lock_stato(radice)
            percorso_lock.parent.mkdir(parents=True, exist_ok=True)
            percorso_lock.touch()  # lock fresco: mtime = adesso

            with self.assertRaises(TimeoutError):
                with postino._blocco_stato(radice, timeout_secondi=0.2):
                    pass

    def test_blocco_stato_e_rientrante_in_sequenza(self) -> None:
        """Due acquisizioni in sequenza (non annidate) funzionano normalmente:
        il lock viene rilasciato alla fine di ciascun 'with'."""
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            with postino._blocco_stato(radice, timeout_secondi=5.0):
                pass
            with postino._blocco_stato(radice, timeout_secondi=5.0):
                pass
            self.assertFalse(postino._percorso_lock_stato(radice).exists())


if __name__ == "__main__":
    unittest.main()
