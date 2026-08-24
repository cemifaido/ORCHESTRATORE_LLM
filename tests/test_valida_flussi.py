from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import valida_flussi


class ValidaFlussiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = valida_flussi.carica_json(valida_flussi.PERCORSO_SCHEMA_PREDEFINITO)
        self.flusso = valida_flussi.carica_json(valida_flussi.PERCORSO_FLUSSO_PREDEFINITO)

    def _passo(self, identita: str) -> dict:
        return next(passo for passo in self.flusso["passi"] if passo["id"] == identita)

    def test_flusso_standard_valido(self) -> None:
        self.assertEqual(valida_flussi.valida_flusso(self.flusso, self.schema), [])

    def test_schema_rifiuta_proprieta_non_dichiarata(self) -> None:
        dati = copy.deepcopy(self.flusso)
        dati["passi"][0]["motore_esecuzione"] = "vietato"
        self.assertTrue(valida_flussi.valida_flusso(dati, self.schema))

    def test_rileva_id_duplicato(self) -> None:
        dati = copy.deepcopy(self.flusso)
        dati["passi"][1]["id"] = "compito"
        errori = valida_flussi.valida_flusso(dati, self.schema)
        self.assertTrue(any("duplicato" in errore for errore in errori))

    def test_rileva_richiesta_senza_produttore(self) -> None:
        dati = copy.deepcopy(self.flusso)
        self._sostituisci(dati, "gate", "richiede", ["artefatto_assente"])
        errori = valida_flussi.valida_flusso(dati, self.schema)
        self.assertTrue(any("senza produttore" in errore for errore in errori))

    def test_rileva_produzione_non_consumata(self) -> None:
        dati = copy.deepcopy(self.flusso)
        self._sostituisci(dati, "chiusura", "produce", ["output_morto"])
        errori = valida_flussi.valida_flusso(dati, self.schema)
        self.assertTrue(any("mai consumato" in errore for errore in errori))

    def test_produzione_di_passo_opzionale_puo_non_essere_consumata(self) -> None:
        dati = copy.deepcopy(self.flusso)
        self._sostituisci(dati, "registrazione", "richiede_opzionali", [])
        self._sostituisci(dati, "chiusura", "richiede_opzionali", [])
        self.assertEqual(valida_flussi.valida_flusso(dati, self.schema), [])

    def test_rileva_artefatto_obbligatorio_prodotto_da_passo_opzionale(self) -> None:
        dati = copy.deepcopy(self.flusso)
        self._sostituisci(dati, "registrazione", "richiede", ["esito_gate", "classificazione_triage"])
        self._sostituisci(dati, "registrazione", "richiede_opzionali", [])
        errori = valida_flussi.valida_flusso(dati, self.schema)
        self.assertTrue(any("prodotto da passo opzionale" in errore for errore in errori))

    def test_rileva_passo_orfano(self) -> None:
        dati = copy.deepcopy(self.flusso)
        dati["passi"].append(
            {
                "id": "isolato",
                "esecutore": "agente_llm",
                "descrizione": "Passo senza collegamenti",
                "richiede": [],
                "produce": [],
                "irreversibile": False,
                "iniziale": False,
            }
        )
        errori = valida_flussi.valida_flusso(dati, self.schema)
        self.assertTrue(any("orfano" in errore for errore in errori))

    def test_rileva_irreversibile_senza_approvazione_a_monte(self) -> None:
        dati = copy.deepcopy(self.flusso)
        self._sostituisci(dati, "azione_irreversibile", "richiede", ["esito_gate"])
        errori = valida_flussi.valida_flusso(dati, self.schema)
        self.assertTrue(any("senza approvazione umana" in errore for errore in errori))

    def test_schema_rifiuta_approvazione_senza_verdetto_esplicito(self) -> None:
        dati = copy.deepcopy(self.flusso)
        self._sostituisci(dati, "approvazione_umana", "produce", ["nota_umano"])
        self.assertTrue(valida_flussi.valida_flusso(dati, self.schema))

    def test_cli_restituisce_zero_e_un_per_file_valido_e_non_valido(self) -> None:
        with tempfile.TemporaryDirectory() as cartella:
            percorso = Path(cartella) / "flusso.json"
            percorso.write_text(json.dumps(self.flusso), encoding="utf-8")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(valida_flussi.main([str(percorso)]), 0)
            dati_non_validi = copy.deepcopy(self.flusso)
            self._sostituisci(dati_non_validi, "gate", "richiede", ["assente"])
            percorso.write_text(json.dumps(dati_non_validi), encoding="utf-8")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(valida_flussi.main([str(percorso)]), 1)

    @staticmethod
    def _sostituisci(dati: dict, identita: str, chiave: str, valore: object) -> None:
        next(passo for passo in dati["passi"] if passo["id"] == identita)[chiave] = valore


if __name__ == "__main__":
    unittest.main()
