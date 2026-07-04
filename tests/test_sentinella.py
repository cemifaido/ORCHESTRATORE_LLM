from __future__ import annotations

import contextlib
import socket
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
