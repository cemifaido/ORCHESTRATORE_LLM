from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import bacheca
import postino
import registro


def _radice_attiva(tmp: str) -> Path:
    radice = Path(tmp)
    flag = radice / "dati_locali" / "orchestrazione" / "POSTINO_ATTIVO"
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text("POSTINO_ATTIVO=1\n", encoding="utf-8")
    return radice


def _scrivi_invii(radice: Path, invii: list[dict]) -> None:
    percorso = radice / "dati_locali" / "orchestrazione" / "postino_stato.json"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(
        json.dumps({"versione_schema": 1, "invii": invii}), encoding="utf-8"
    )


def _invio(minuti_fa: int, *, agente: str = "codex", thread_id: str = "t-postino", canale: str = "headless") -> dict:
    quando = (datetime.now(UTC) - timedelta(minutes=minuti_fa)).isoformat()
    return {"quando": quando, "agente": agente, "thread_id": thread_id, "canale": canale, "codice": 0}


class PostinoPolicyTest(unittest.TestCase):
    """Guardrail del controllore (docs/PIANO_RISVEGLI_AUTOMATICI.md): opt-in
    fail-closed, budget solo headless, tetto per thread su tutti i canali con
    azzeramento al tocco umano, debounce per coppia agente+thread."""

    def test_kill_switch_default_spento(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            esito = postino.autorizza(Path(tmp), "claude", "t-postino")
            self.assertEqual(esito, {"esito": "bloccato", "motivo": "kill_switch"})

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
            # 10 deep-link odierni su thread diversi: il budget headless resta libero
            _scrivi_invii(radice, [
                _invio(i + 1, thread_id=f"t-{i}", canale="deep_link") for i in range(10)
            ])
            self.assertEqual(postino.autorizza(radice, "claude", "t-postino"), {"esito": "autorizzato"})
            # 10 headless odierni: budget esaurito
            _scrivi_invii(radice, [
                _invio(i + 1, thread_id=f"t-{i}", canale="headless") for i in range(10)
            ])
            self.assertEqual(
                postino.autorizza(radice, "claude", "t-postino"),
                {"esito": "bloccato", "motivo": "budget_giornaliero"},
            )

    def test_record_storico_senza_canale_conta_come_headless(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _radice_attiva(tmp)
            invii = [_invio(i + 1, thread_id=f"t-{i}") for i in range(10)]
            for invio in invii:
                del invio["canale"]
            _scrivi_invii(radice, invii)
            self.assertEqual(
                postino.autorizza(radice, "claude", "t-postino"),
                {"esito": "bloccato", "motivo": "budget_giornaliero"},
            )

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
            stato, "claude", "t-postino", datetime.now(UTC), postino.LIMITI_PREDEFINITI
        )
        self.assertEqual(motivo, "debounce")
        # stesso thread, agente diverso: niente debounce (e sotto il tetto giri)
        motivo = postino._motivo_blocco(
            stato, "codex", "t-postino", datetime.now(UTC), postino.LIMITI_PREDEFINITI
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

    def test_dispatch_rifiuta_capability_non_autorizzata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            esegui = MagicMock()
            esito = postino.dispatch(_radice_attiva(tmp), "gemini", "t-postino", esegui=esegui)
            self.assertEqual(esito, {"esito": "bloccato", "motivo": "capability_non_autorizzata"})
            esegui.assert_not_called()

    def test_dispatch_bloccato_da_kill_switch_non_esegue_nulla(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            esegui = MagicMock()
            esito = postino.dispatch(Path(tmp), "claude", "t-postino", esegui=esegui)
            self.assertEqual(esito, {"esito": "bloccato", "motivo": "kill_switch"})
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


if __name__ == "__main__":
    unittest.main()
