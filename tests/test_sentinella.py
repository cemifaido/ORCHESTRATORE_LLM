from __future__ import annotations

import contextlib
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import registro
import sentinella


def porta_libera() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as tmp_socket:
        tmp_socket.bind(("127.0.0.1", 0))
        return tmp_socket.getsockname()[1]


class SentinellaTest(unittest.TestCase):
    def test_rifiuta_comando_non_whitelistato(self) -> None:
        with self.assertRaises(ValueError):
            sentinella.esegui("mancante", {})

    def test_esegue_comando_whitelistato_e_salva_log_fuori_evento(self) -> None:
        comando = {
            "prova": {
                "cartella": ".",
                "argomenti": ["python", "-c", "print('ok')"],
                "timeout_secondi": 10,
                "limite_output_caratteri": 1000,
            }
        }
        esito, codice, _latenza, output = sentinella.esegui("prova", comando)
        self.assertEqual(esito, "superato")
        self.assertEqual(codice, 0)
        self.assertIn("ok", output)

        with tempfile.TemporaryDirectory() as tmp:
            metadati = sentinella.salva_log_output("evt", output, Path(tmp))
            self.assertIn("sha256_output", metadati)
            self.assertIn("estratto_output", metadati)
            self.assertNotIn("output", metadati)
            self.assertTrue(Path(metadati["log_output"]).exists())

    def test_rifiuta_cartella_fuori_dalla_radice_del_progetto(self) -> None:
        """Guardrail di sicurezza (revisione esterna, 2026-08-25): comandi.json
        non e' firmato, quindi 'cartella' va sempre verificata contro la radice
        del progetto quando la si conosce - senza questo un comandi.json
        malevolo potrebbe far girare comandi arbitrari fuori dal progetto."""
        with tempfile.TemporaryDirectory() as radice, tempfile.TemporaryDirectory() as fuori:
            comando = {
                "prova": {
                    "cartella": fuori,
                    "argomenti": ["python", "-c", "print('ok')"],
                    "timeout_secondi": 10,
                    "limite_output_caratteri": 1000,
                }
            }
            with self.assertRaises(ValueError):
                sentinella.esegui("prova", comando, radice_progetto=Path(radice))

    def test_accetta_cartella_dentro_la_radice_del_progetto(self) -> None:
        with tempfile.TemporaryDirectory() as radice:
            comando = {
                "prova": {
                    "cartella": radice,
                    "argomenti": ["python", "-c", "print('ok')"],
                    "timeout_secondi": 10,
                    "limite_output_caratteri": 1000,
                }
            }
            esito, codice, _latenza, _output = sentinella.esegui(
                "prova", comando, radice_progetto=Path(radice)
            )
            self.assertEqual(esito, "superato")
            self.assertEqual(codice, 0)

    def test_senza_radice_progetto_nessun_controllo_di_contenimento(self) -> None:
        """Compatibilita' con i chiamanti che non conoscono ancora la radice:
        radice_progetto=None (default) non applica il controllo."""
        with tempfile.TemporaryDirectory() as fuori:
            comando = {
                "prova": {
                    "cartella": fuori,
                    "argomenti": ["python", "-c", "print('ok')"],
                    "timeout_secondi": 10,
                    "limite_output_caratteri": 1000,
                }
            }
            esito, codice, _latenza, _output = sentinella.esegui("prova", comando)
            self.assertEqual(esito, "superato")
            self.assertEqual(codice, 0)

    def test_verifica_connessione_risorsa_raggiungibile(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(5)
        porta = server.getsockname()[1]
        try:
            self.assertTrue(sentinella.verifica_connessione(f"127.0.0.1:{porta}"))
            self.assertTrue(sentinella.verifica_connessione(f"http://127.0.0.1:{porta}"))
        finally:
            server.close()

    def test_verifica_connessione_risorsa_non_raggiungibile(self) -> None:
        porta = porta_libera()
        self.assertFalse(sentinella.verifica_connessione(f"127.0.0.1:{porta}"))

    def test_esegui_con_risorsa_offline_ritorna_errore_ambiente_senza_avviare_comando(self) -> None:
        porta = porta_libera()
        comando = {
            "prova": {
                "cartella": ".",
                "argomenti": ["python", "-c", "raise SystemExit(1)"],
                "timeout_secondi": 10,
                "limite_output_caratteri": 1000,
                "verifiche_connessione": [f"127.0.0.1:{porta}"],
            }
        }
        esito, codice, latenza_ms, output = sentinella.esegui("prova", comando)
        self.assertEqual(esito, "errore_ambiente")
        self.assertEqual(codice, 111)
        self.assertEqual(latenza_ms, 0)
        self.assertIn("non è raggiungibile", output)

    def test_determina_stato(self) -> None:
        self.assertEqual(sentinella.determina_stato("superato"), "passato")
        self.assertEqual(sentinella.determina_stato("errore_ambiente"), "errore_ambiente")
        self.assertEqual(sentinella.determina_stato("fallito"), "fallito")
        self.assertEqual(sentinella.determina_stato("timeout"), "fallito")

    @patch("sentinella.triage_locale.classifica")
    def test_triage_successo_ripetitivo_non_chiama_modello_locale(self, mock_classifica: MagicMock) -> None:
        output = "Ran 68 tests in 12.991s\n\nOK\n"
        risultato, metodo, _latenza = sentinella.classifica_con_guardia_locale(
            "superato", 0, output, contesto="test unittest"
        )
        self.assertEqual(risultato["esito"], "routine")
        self.assertEqual(metodo, "triage_deterministico")
        mock_classifica.assert_not_called()

    @patch("sentinella.triage_locale.classifica")
    def test_triage_output_ambiguo_chiama_modello_locale(self, mock_classifica: MagicMock) -> None:
        mock_classifica.return_value = {"esito": "routine", "motivo": "warning noto", "token_totali": 55}
        risultato, metodo, _latenza = sentinella.classifica_con_guardia_locale(
            "superato", 0, "WARNING: provider remoto non raggiungibile, fallback mock", contesto="test"
        )
        self.assertEqual(risultato["esito"], "routine")
        self.assertEqual(risultato["token_totali"], 55)
        self.assertEqual(metodo, "triage_locale")
        mock_classifica.assert_called_once()

    @patch("sentinella.triage_locale.classifica")
    def test_triage_fallimento_standard_non_chiama_modello_locale(self, mock_classifica: MagicMock) -> None:
        risultato, metodo, _latenza = sentinella.classifica_con_guardia_locale(
            "fallito", 1, "FAILED test_modulo.py::test_caso", contesto="test fallito"
        )
        self.assertEqual(risultato["esito"], "escalation")
        self.assertEqual(metodo, "triage_deterministico")
        mock_classifica.assert_not_called()

    @patch("sentinella.triage_locale.classifica")
    def test_triage_modello_locale_non_raggiungibile_diventa_escalation(self, mock_classifica: MagicMock) -> None:
        mock_classifica.return_value = {
            "esito": "escalation",
            "motivo": "modello locale non raggiungibile",
            "token_totali": None,
        }
        risultato, metodo, _latenza = sentinella.classifica_con_guardia_locale(
            "fallito", 2, "process exited with status 2", contesto="errore non strutturato"
        )
        self.assertEqual(risultato["esito"], "escalation")
        self.assertEqual(metodo, "triage_locale")

    def test_registra_triage_usa_stesso_id_compito_del_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "eventi.jsonl"
            evento = sentinella.registra_triage(
                risultato={"esito": "routine", "motivo": "ok deterministico", "token_totali": None},
                metodo="triage_deterministico",
                percorso_registro=percorso,
                id_compito="task-test",
                comando="test_servizi",
                esito_gate="superato",
                codice=0,
                latenza_ms=1,
            )
            eventi = registro.leggi_eventi(percorso)
            self.assertEqual(evento["id_compito"], "task-test")
            self.assertEqual(eventi[0]["id_compito"], "task-test")
            self.assertEqual(eventi[0]["regole_incluse"], ["triage_deterministico"])
            self.assertEqual(eventi[0]["metadati"]["comando"], "test_servizi")
            self.assertEqual(eventi[0]["metadati"]["esito_gate_collegato"], "superato")


if __name__ == "__main__":
    unittest.main()
