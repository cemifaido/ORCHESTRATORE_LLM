from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import bacheca
import orchestratore_brainstorming as orchestratore


def _completato(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    completato = MagicMock()
    completato.returncode = returncode
    completato.stdout = stdout
    completato.stderr = stderr
    return completato


def _risposta_locale_con_sintesi(sintesi: str) -> MagicMock:
    risposta = MagicMock()
    risposta.choices = [MagicMock()]
    risposta.choices[0].message.content = f'{{"sintesi": "{sintesi}", "conflitto": null}}'
    return risposta


def _misurazione_finta() -> MagicMock:
    misurazione = MagicMock()
    misurazione.token_totali = 123
    misurazione.modello = "qwen2.5-7b-instruct-q3_k_m.gguf"
    return misurazione


class InvocaClaudeHeadlessTest(unittest.TestCase):
    @patch("orchestratore_brainstorming.subprocess.run")
    def test_successo(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _completato(returncode=0, stdout="Proposta di Claude.\n")
        risultato = orchestratore.invoca_claude_headless("prompt di prova")
        self.assertTrue(risultato["ok"])
        self.assertEqual(risultato["testo"], "Proposta di Claude.")

    @patch("orchestratore_brainstorming.subprocess.run")
    def test_binario_non_trovato(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError()
        risultato = orchestratore.invoca_claude_headless("prompt")
        self.assertFalse(risultato["ok"])
        self.assertIn("non trovato", risultato["errore"])

    @patch("orchestratore_brainstorming.subprocess.run")
    def test_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=180)
        risultato = orchestratore.invoca_claude_headless("prompt")
        self.assertFalse(risultato["ok"])
        self.assertIn("180", risultato["errore"])

    @patch("orchestratore_brainstorming.subprocess.run")
    def test_codice_uscita_non_zero(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _completato(returncode=1, stderr="errore di autenticazione")
        risultato = orchestratore.invoca_claude_headless("prompt")
        self.assertFalse(risultato["ok"])
        self.assertIn("errore di autenticazione", risultato["errore"])

    @patch("orchestratore_brainstorming.subprocess.run")
    def test_output_vuoto(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _completato(returncode=0, stdout="   ")
        risultato = orchestratore.invoca_claude_headless("prompt")
        self.assertFalse(risultato["ok"])
        self.assertIn("vuoto", risultato["errore"])


class AvviaBrainstormingTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.percorso_bacheca = Path(self._tmp.name) / "messaggi.jsonl"

    @patch("bacheca.litellm.completamento_locale")
    @patch("orchestratore_brainstorming.subprocess.run")
    def test_flusso_completo_scrive_due_messaggi_collegati(
        self, mock_run: MagicMock, mock_completamento: MagicMock
    ) -> None:
        mock_run.return_value = _completato(returncode=0, stdout="Proposta lunga di Claude.")
        mock_completamento.return_value = (
            _risposta_locale_con_sintesi("Sintesi compatta."),
            _misurazione_finta(),
        )

        esito = orchestratore.avvia_brainstorming("nome modulo cache", self.percorso_bacheca)

        self.assertTrue(esito["ok"])
        self.assertFalse(esito["sintesi_locale_fallita"])

        messaggi = bacheca.leggi_messaggi(self.percorso_bacheca)
        self.assertEqual(len(messaggi), 2)
        self.assertEqual(messaggi[0]["mittente"], "claude")
        self.assertEqual(messaggi[0]["testo"], "Proposta lunga di Claude.")
        self.assertEqual(messaggi[1]["mittente"], "locale")
        self.assertEqual(messaggi[1]["destinatari"], ["gemini", "codex"])
        self.assertEqual(messaggi[1]["testo"], "Sintesi compatta.")
        self.assertEqual(messaggi[1]["thread_id"], messaggi[0]["thread_id"])
        self.assertEqual(messaggi[1]["correla_a"], messaggi[0]["id_messaggio"])

    @patch("orchestratore_brainstorming.subprocess.run")
    def test_claude_fallisce_non_scrive_nulla_in_bacheca(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError()

        esito = orchestratore.avvia_brainstorming("argomento", self.percorso_bacheca)

        self.assertFalse(esito["ok"])
        self.assertEqual(esito["fase"], "claude")
        self.assertFalse(self.percorso_bacheca.exists())

    @patch("bacheca.litellm.completamento_locale")
    @patch("orchestratore_brainstorming.subprocess.run")
    def test_sintesi_locale_irraggiungibile_usa_testo_integrale_come_fallback(
        self, mock_run: MagicMock, mock_completamento: MagicMock
    ) -> None:
        mock_run.return_value = _completato(returncode=0, stdout="Proposta integrale di Claude.")
        mock_completamento.side_effect = ConnectionError("llama-server non raggiungibile")

        esito = orchestratore.avvia_brainstorming("argomento", self.percorso_bacheca)

        self.assertTrue(esito["ok"])
        self.assertTrue(esito["sintesi_locale_fallita"])

        messaggi = bacheca.leggi_messaggi(self.percorso_bacheca)
        messaggio_per_gemini = messaggi[1]
        self.assertEqual(messaggio_per_gemini["testo"], "Proposta integrale di Claude.")
        self.assertTrue(messaggio_per_gemini["metadati"]["sintesi_locale_fallita"])


class MainCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.percorso_bacheca = Path(self._tmp.name) / "messaggi.jsonl"

    @patch("bacheca.litellm.completamento_locale")
    @patch("orchestratore_brainstorming.subprocess.run")
    def test_main_ritorna_zero_su_successo(
        self, mock_run: MagicMock, mock_completamento: MagicMock
    ) -> None:
        mock_run.return_value = _completato(returncode=0, stdout="Proposta.")
        mock_completamento.return_value = (
            _risposta_locale_con_sintesi("Sintesi."), _misurazione_finta(),
        )
        codice = orchestratore.main([
            "--argomento", "prova", "--bacheca", str(self.percorso_bacheca),
        ])
        self.assertEqual(codice, 0)

    @patch("orchestratore_brainstorming.subprocess.run")
    def test_main_ritorna_uno_su_fallimento_claude(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError()
        codice = orchestratore.main([
            "--argomento", "prova", "--bacheca", str(self.percorso_bacheca),
        ])
        self.assertEqual(codice, 1)


if __name__ == "__main__":
    unittest.main()
