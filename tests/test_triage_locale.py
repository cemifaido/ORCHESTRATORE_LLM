from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import registro
import triage_locale
from adattatori.litellm import MisurazioneLiteLLM


def _risposta_con_testo(testo: str) -> MagicMock:
    risposta = MagicMock()
    risposta.choices = [MagicMock()]
    risposta.choices[0].message.content = testo
    return risposta


def _misurazione_finta(token_totali: int = 45) -> MisurazioneLiteLLM:
    return MisurazioneLiteLLM(
        modello="qwen2.5-7b-instruct-q3_k_m.gguf", provider="locale", costo_usd=0.0,
        token_prompt=30, token_completion=token_totali - 30, token_totali=token_totali,
    )


class ClassificaTest(unittest.TestCase):
    @patch("adattatori.litellm.completamento_locale")
    def test_classifica_routine(self, mock_completamento: MagicMock) -> None:
        mock_completamento.return_value = (
            _risposta_con_testo('{"esito": "routine", "motivo": "tutto ok"}'), _misurazione_finta()
        )
        risultato = triage_locale.classifica("test passati")
        self.assertEqual(risultato["esito"], "routine")
        self.assertEqual(risultato["motivo"], "tutto ok")

    @patch("adattatori.litellm.completamento_locale")
    def test_classifica_include_token_totali_reali(self, mock_completamento: MagicMock) -> None:
        mock_completamento.return_value = (
            _risposta_con_testo('{"esito": "routine", "motivo": "ok"}'), _misurazione_finta(token_totali=77)
        )
        risultato = triage_locale.classifica("output")
        self.assertEqual(risultato["token_totali"], 77)

    @patch("adattatori.litellm.completamento_locale")
    def test_classifica_escalation(self, mock_completamento: MagicMock) -> None:
        mock_completamento.return_value = (
            _risposta_con_testo('{"esito": "escalation", "motivo": "bug reale"}'), _misurazione_finta()
        )
        risultato = triage_locale.classifica("AssertionError: 1 != 3")
        self.assertEqual(risultato["esito"], "escalation")
        self.assertEqual(risultato["motivo"], "bug reale")

    @patch("adattatori.litellm.completamento_locale")
    def test_classifica_risposta_non_json_ritorna_escalation(self, mock_completamento: MagicMock) -> None:
        mock_completamento.return_value = (_risposta_con_testo("non sono json"), _misurazione_finta())
        risultato = triage_locale.classifica("qualunque output")
        self.assertEqual(risultato["esito"], "escalation")
        self.assertIn("non interpretabile", risultato["motivo"])

    @patch("adattatori.litellm.completamento_locale")
    def test_classifica_esito_non_valido_ritorna_escalation(self, mock_completamento: MagicMock) -> None:
        mock_completamento.return_value = (
            _risposta_con_testo('{"esito": "forse", "motivo": "boh"}'), _misurazione_finta()
        )
        risultato = triage_locale.classifica("output")
        self.assertEqual(risultato["esito"], "escalation")

    @patch("adattatori.litellm.completamento_locale")
    def test_classifica_modello_non_raggiungibile_ritorna_escalation(self, mock_completamento: MagicMock) -> None:
        mock_completamento.side_effect = ConnectionError("server non risponde")
        risultato = triage_locale.classifica("output")
        self.assertEqual(risultato["esito"], "escalation")
        self.assertIn("non raggiungibile", risultato["motivo"])

    @patch("adattatori.litellm.completamento_locale")
    def test_classifica_risposta_a_forma_inattesa_ritorna_escalation_senza_crash(
        self, mock_completamento: MagicMock
    ) -> None:
        """Se il provider locale (o un futuro cambio di endpoint/libreria) ritorna una
        forma diversa da ModelResponse, testo_da_risposta() torna "" invece di far
        sollevare AttributeError qui: il triage deve degradare a escalation, mai
        crashare — e' proprio quello che deve intercettare un problema inatteso."""
        mock_completamento.return_value = (object(), _misurazione_finta())
        risultato = triage_locale.classifica("output")
        self.assertEqual(risultato["esito"], "escalation")
        self.assertIn("non interpretabile", risultato["motivo"])


class RegistraClassificazioneTest(unittest.TestCase):
    def test_registra_classificazione_scrive_evento_valido(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "eventi.jsonl"
            triage_locale.registra_classificazione(
                {"esito": "routine", "motivo": "tutto ok"},
                latenza_ms=250,
                percorso_registro=percorso,
                id_compito="triage-test",
                contesto="test suite",
                thread_id="thread-test",
            )
            eventi = registro.leggi_eventi(percorso)
            self.assertEqual(eventi[0]["thread_id"], "thread-test")
            self.assertEqual(len(eventi), 1)
            evento = eventi[0]
            self.assertEqual(evento["agente"], "locale")
            self.assertEqual(evento["stato"], "passato")
            self.assertEqual(evento["esito_gate"], "non_eseguito")
            self.assertEqual(evento["costo_stimato_usd"], 0.0)
            self.assertEqual(evento["origine_costo"], "misurato")
            self.assertEqual(evento["latenza_ms"], 250)
            self.assertIn("tutto ok", evento["note"])

    def test_registra_classificazione_salva_token_totali_nei_metadati(self) -> None:
        """Il dato grezzo (token reali) va conservato cosi' com'e', non trasformato in
        una stima di risparmio congelata: quella si ricalcola quando serve, con un
        prezzo di riferimento dichiarato al momento del calcolo."""
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "eventi.jsonl"
            triage_locale.registra_classificazione(
                {"esito": "routine", "motivo": "ok", "token_totali": 123},
                latenza_ms=50,
                percorso_registro=percorso,
                id_compito="triage-test-3",
                contesto="",
            )
            evento = registro.leggi_eventi(percorso)[0]
            self.assertEqual(evento["metadati"]["token_totali"], 123)

    def test_registra_classificazione_escalation_diventa_da_rivedere(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "eventi.jsonl"
            triage_locale.registra_classificazione(
                {"esito": "escalation", "motivo": "bug reale"},
                latenza_ms=100,
                percorso_registro=percorso,
                id_compito="triage-test-2",
                contesto="",
            )
            evento = registro.leggi_eventi(percorso)[0]
            self.assertEqual(evento["stato"], "da_rivedere")


if __name__ == "__main__":
    unittest.main()
