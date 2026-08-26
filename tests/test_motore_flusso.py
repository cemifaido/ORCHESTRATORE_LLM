from __future__ import annotations

import json
import unittest
from pathlib import Path

import motore_flusso


FLUSSO = json.loads((Path(__file__).parent.parent / "config" / "flussi" / "compito_standard.json").read_text(encoding="utf-8"))
THREAD = "thread-d3"


def evento(**extra: object) -> dict:
    base: dict[str, object] = {
        "thread_id": THREAD, "agente": "codex", "file_modificati": [],
        "esito_gate": "non_eseguito", "regole_incluse": [], "artefatti_flusso": [],
        "metadati": {}, "verdetto_umano": "non_revisionato",
    }
    base.update(extra)
    return base


class MotoreFlussoTest(unittest.TestCase):
    def test_nuovo_thread_parte_da_compito(self) -> None:
        stato = motore_flusso.deriva_stato(FLUSSO, [], [], THREAD)
        self.assertEqual((stato["stato"], stato["fase"]), ("attivo", "compito"))

    def test_deriva_gate_da_file_modificati_correlati(self) -> None:
        stato = motore_flusso.deriva_stato(FLUSSO, [evento(file_modificati=["a.py"])], [], THREAD)
        self.assertEqual(stato["fase"], "gate")

    def test_evento_non_correlato_non_avanza(self) -> None:
        stato = motore_flusso.deriva_stato(FLUSSO, [evento(thread_id="altro", file_modificati=["a.py"])], [], THREAD)
        self.assertEqual(stato["fase"], "compito")

    def test_approvazione_richiede_prova_doppia(self) -> None:
        eventi = [evento(file_modificati=["a.py"], esito_gate="superato"), evento(agente="umano", verdetto_umano="approvato")]
        messaggi = [{"thread_id": THREAD, "verdetto_umano": "approvato", "tipo": "risposta"}]
        stato = motore_flusso.deriva_stato(FLUSSO, eventi, messaggi, THREAD)
        self.assertIn("verdetto_umano", stato["prove"])

    def test_thread_chiuso_senza_prove_e_incoerente(self) -> None:
        stato = motore_flusso.deriva_stato(FLUSSO, [], [{"thread_id": THREAD, "tipo": "chiusura", "verdetto_umano": "non_revisionato"}], THREAD)
        self.assertEqual(stato["stato"], "incoerente")

    def test_prova_fuori_sequenza_non_salva_un_thread_chiuso(self) -> None:
        stato = motore_flusso.deriva_stato(
            FLUSSO,
            [evento(esito_gate="superato")],
            [{"thread_id": THREAD, "tipo": "chiusura", "verdetto_umano": "non_revisionato"}],
            THREAD,
        )
        self.assertEqual(stato["stato"], "incoerente")

    def test_compilatore_rifiuta_ciclo(self) -> None:
        flusso = {"passi": [{"id": "a", "richiede": ["y"], "produce": ["x"]}, {"id": "b", "richiede": ["x"], "produce": ["y"]}]}
        with self.assertRaises(ValueError):
            motore_flusso.compila_flusso(flusso)

    def test_dto_ha_sempre_tutte_le_chiavi_del_contratto(self) -> None:
        stato = motore_flusso.deriva_stato({"passi": "corrotti"}, [], [], THREAD)
        self.assertEqual(stato["stato"], "invalido")
        self.assertEqual(
            set(stato),
            {"stato", "fase", "passi_completati", "passi_abilitati", "prove", "artefatti_mancanti", "diagnostica"},
        )

    def test_commit_richiede_artefatto_e_hash_strutturato(self) -> None:
        eventi = [
            evento(file_modificati=["a.py"], esito_gate="superato"),
            evento(agente="umano", verdetto_umano="approvato"),
            evento(artefatti_flusso=["commit"], metadati={"flusso": {"commit_hash": "abc123"}}),
        ]
        messaggi = [{"thread_id": THREAD, "verdetto_umano": "approvato", "tipo": "risposta"}]
        stato = motore_flusso.deriva_stato(FLUSSO, eventi, messaggi, THREAD)
        self.assertIn("commit", stato["prove"])

    def test_configurazione_invalida_non_avanza(self) -> None:
        flusso = {"passi": [{"id": "a", "richiede": [], "produce": ["x"]}, {"id": "b", "richiede": ["x"], "produce": ["x"]}]}
        stato = motore_flusso.deriva_stato(flusso, [], [], THREAD)
        self.assertEqual(stato["stato"], "invalido")


if __name__ == "__main__":
    unittest.main()
