from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import registro
import sentinella


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


if __name__ == "__main__":
    unittest.main()
