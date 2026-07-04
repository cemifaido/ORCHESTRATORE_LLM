from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import esempi.chiamata_agente_litellm
import registro


class EsempioLiteLLMTest(unittest.TestCase):
    def test_main_esegue_correttamente_e_scrive_evento_misurato(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # Creiamo la cartella dei dati locali per il log eventi mockato
            registro_dir = tmp_path / "dati_locali" / "orchestrazione"
            registro_dir.mkdir(parents=True, exist_ok=True)
            registro_file = registro_dir / "eventi.jsonl"

            # Mockiamo RADICE nello script di esempio affinché scriva nel nostro tmp
            with patch("esempi.chiamata_agente_litellm.RADICE", tmp_path):
                # Eseguiamo il main dell'esempio
                codice_uscita = esempi.chiamata_agente_litellm.main([])

            self.assertEqual(codice_uscita, 0)
            self.assertTrue(registro_file.exists())

            # Leggiamo gli eventi salvati per validare il costo misurato
            eventi = registro.leggi_eventi(registro_file)
            self.assertEqual(len(eventi), 1)

            evento = eventi[0]
            self.assertEqual(evento["id_compito"], "refactoring-esempio")
            self.assertEqual(evento["origine_costo"], "misurato")
            self.assertEqual(evento["costo_stimato_usd"], 0.00033)
            self.assertIn("litellm", evento["metadati"])
            self.assertEqual(evento["metadati"]["litellm"]["token_totali"], 165)


if __name__ == "__main__":
    unittest.main()
