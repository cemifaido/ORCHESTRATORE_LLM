from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import capoturno
import registro
from adattatori import litellm


class CapoturnoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.progetto_path = Path(self.tmp_dir.name)
        self.registro_dir = self.progetto_path / "dati_locali" / "orchestrazione"
        self.registro_dir.mkdir(parents=True, exist_ok=True)
        self.registro_file = self.registro_dir / "eventi.jsonl"

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    @patch("adattatori.litellm.completamento")
    @patch("subprocess.run")
    def test_esegui_compito_successo_lineare(self, mock_run: MagicMock, mock_completamento: MagicMock) -> None:
        # Mock completamento LiteLLM
        mock_completamento.return_value = (
            "Ecco il codice:\n```python\ndef saluta():\n    print('ciao')\n```",
            litellm.MisurazioneLiteLLM(modello="openai/gpt-4o-mini", provider="openai", costo_usd=0.0001, token_prompt=10, token_completion=15, token_totali=25)
        )
        # Mock esito sentinella (0 = successo)
        mock_run.return_value = MagicMock(returncode=0, stdout="All checks passed", stderr="")

        c = capoturno.Capoturno(
            progetto_id="test_proj",
            progetto_percorso=str(self.progetto_path),
            registro_percorso=str(self.registro_file)
        )

        esito = c.esegui_compito(
            id_compito="t1",
            tipo_compito="servizi",
            compito_prompt="crea saluta",
            file_target="funzione.py"
        )

        self.assertTrue(esito)
        # Verifica scrittura file
        file_creato = self.progetto_path / "funzione.py"
        self.assertTrue(file_creato.exists())
        self.assertEqual(file_creato.read_text(encoding="utf-8"), "def saluta():\n    print('ciao')")

        # Verifica registrazione evento
        eventi = registro.leggi_eventi(self.registro_file)
        self.assertEqual(len(eventi), 1)
        self.assertEqual(eventi[0]["stato"], "passato")
        self.assertEqual(eventi[0]["esito_gate"], "superato")

    @patch("adattatori.litellm.completamento")
    @patch("subprocess.run")
    def test_esegui_compito_con_risposta_litellm_reale_non_stringa(
        self, mock_run: MagicMock, mock_completamento: MagicMock
    ) -> None:
        """litellm.completion() reale ritorna un oggetto ModelResponse con
        .choices[0].message.content, non una stringa: i mock degli altri test la
        semplificano a stringa e mascherano un TypeError che si presenta solo con
        una risposta a forma reale (vedi Capoturno._testo_da_risposta)."""
        risposta_reale = MagicMock()
        risposta_reale.choices = [MagicMock()]
        risposta_reale.choices[0].message.content = "```python\ndef reale(): pass\n```"
        mock_completamento.return_value = (
            risposta_reale,
            litellm.MisurazioneLiteLLM(
                modello="claude-3-haiku", provider="anthropic", costo_usd=0.0001,
                token_prompt=10, token_completion=5, token_totali=15
            )
        )
        mock_run.return_value = MagicMock(returncode=0, stdout="All checks passed", stderr="")

        c = capoturno.Capoturno(
            progetto_id="test_proj",
            progetto_percorso=str(self.progetto_path),
            registro_percorso=str(self.registro_file)
        )

        esito = c.esegui_compito(
            id_compito="t-reale",
            tipo_compito="servizi",
            compito_prompt="crea reale",
            file_target="reale.py"
        )

        self.assertTrue(esito)
        file_creato = self.progetto_path / "reale.py"
        self.assertEqual(file_creato.read_text(encoding="utf-8"), "def reale(): pass")

    @patch("adattatori.litellm.completamento")
    @patch("subprocess.run")
    def test_esegui_compito_con_failover_agenti(self, mock_run: MagicMock, mock_completamento: MagicMock) -> None:
        # Primo tentativo fallisce per APIError (simula crediti esauriti)
        # Secondo tentativo (failover) ha successo
        mock_completamento.side_effect = [
            Exception("Crediti esauriti su Claude"),
            (
                "```python\ndef fallback(): pass\n```",
                litellm.MisurazioneLiteLLM(
                    modello="openai/gpt-4o-mini", provider="openai", costo_usd=0.0002,
                    token_prompt=10, token_completion=10, token_totali=20
                )
            )
        ]
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        c = capoturno.Capoturno(
            progetto_id="test_proj",
            progetto_percorso=str(self.progetto_path),
            registro_percorso=str(self.registro_file)
        )

        esito = c.esegui_compito(
            id_compito="t2",
            tipo_compito="servizi",  # Instradamento consiglia claude -> fallisce -> failover gemini
            compito_prompt="crea fallback",
            file_target="fallback.py"
        )

        self.assertTrue(esito)
        self.assertTrue((self.progetto_path / "fallback.py").exists())

        eventi = registro.leggi_eventi(self.registro_file)
        self.assertEqual(len(eventi), 1)
        self.assertEqual(eventi[0]["agente"], "gemini")  # Salvato l'agente che ha risolto
        self.assertEqual(eventi[0]["stato"], "passato")

    @patch("adattatori.litellm.completamento")
    @patch("subprocess.run")
    def test_esegui_compito_rework_loop(self, mock_run: MagicMock, mock_completamento: MagicMock) -> None:
        # LLM risponde sempre con codice
        mock_completamento.return_value = (
            "```python\ndef fix(): pass\n```",
            litellm.MisurazioneLiteLLM(modello="openai/gpt-4o-mini", provider="openai", costo_usd=0.0001, token_prompt=10, token_completion=5, token_totali=15)
        )
        # Sentinella fallisce al primo tentativo (returncode=1) e passa al secondo (returncode=0)
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="SyntaxError: unexpected EOF", stderr=""),
            MagicMock(returncode=0, stdout="All clean", stderr="")
        ]

        c = capoturno.Capoturno(
            progetto_id="test_proj",
            progetto_percorso=str(self.progetto_path),
            registro_percorso=str(self.registro_file)
        )

        esito = c.esegui_compito(
            id_compito="t3",
            tipo_compito="servizi",
            compito_prompt="crea fix",
            file_target="fix.py"
        )

        self.assertTrue(esito)
        # Verifichiamo che subprocess.run sia stato invocato 2 volte
        self.assertEqual(mock_run.call_count, 2)
        # E litellm completamento sia stato chiamato 2 volte (1 per creazione, 1 per rework)
        self.assertEqual(mock_completamento.call_count, 2)

        eventi = registro.leggi_eventi(self.registro_file)
        self.assertEqual(len(eventi), 1)
        self.assertEqual(eventi[0]["stato"], "passato")

    @patch("adattatori.litellm.completamento")
    def test_esegui_compito_errore_ambiente_totale(self, mock_completamento: MagicMock) -> None:
        # Entrambi gli agenti (claude e gemini) falliscono a causa di eccezioni API
        mock_completamento.side_effect = Exception("API key non valida")

        c = capoturno.Capoturno(
            progetto_id="test_proj",
            progetto_percorso=str(self.progetto_path),
            registro_percorso=str(self.registro_file)
        )

        esito = c.esegui_compito(
            id_compito="t4",
            tipo_compito="servizi",
            compito_prompt="crea crash",
            file_target="crash.py"
        )

        self.assertFalse(esito)

        eventi = registro.leggi_eventi(self.registro_file)
        self.assertEqual(len(eventi), 1)
        self.assertEqual(eventi[0]["stato"], "errore_ambiente")
        self.assertEqual(eventi[0]["esito_gate"], "non_eseguito")


if __name__ == "__main__":
    unittest.main()
