from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

import registro


class RegistroTest(unittest.TestCase):
    def evento_valido(self) -> dict:
        return {
            "versione_schema": 1,
            "id_evento": "evt-1",
            "timestamp": "2026-07-03T20:00:00Z",
            "id_compito": "task-1",
            "agente": "codex",
            "tipo_compito": "revisione",
            "stato": "accettato",
            "esito_gate": "superato",
            "verdetto_umano": "approvato",
            "costo_stimato_usd": 0.01,
            "origine_costo": "stimato",
            "latenza_ms": 10,
            "regole_incluse": ["core"],
            "file_modificati": [],
            "note": "ok",
            "metadati": {},
        }

    def test_valida_contro_schema_e_rifiuta_campi_extra(self) -> None:
        evento = self.evento_valido()
        evento["campo_non_previsto"] = True
        errori = registro.valida_evento(evento)
        self.assertTrue(any("campi non previsti" in errore for errore in errori))

    def test_rework_non_e_input_dello_schema(self) -> None:
        evento = self.evento_valido()
        evento["rework"] = "si"
        errori = registro.valida_evento(evento)
        self.assertTrue(any("campi non previsti" in errore for errore in errori))

    def test_costruisci_evento_non_emette_rework(self) -> None:
        args = argparse.Namespace(
            id_evento="",
            timestamp="2026-07-03T20:00:00Z",
            id_compito="task",
            agente="codex",
            tipo_compito="revisione",
            stato="accettato",
            esito_gate="fallito",
            verdetto_umano="non_revisionato",
            costo_stimato_usd=0.0,
            origine_costo="stimato",
            latenza_ms=0,
            regole_incluse="core",
            file_modificati="",
            note="",
        )
        self.assertNotIn("rework", registro.costruisci_evento(args))

    def test_metriche_derivano_rework_da_gate_e_verdetto(self) -> None:
        evento_gate = self.evento_valido()
        evento_gate["esito_gate"] = "fallito"
        evento_gate["id_evento"] = "evt-gate"
        evento_umano = self.evento_valido()
        evento_umano["id_evento"] = "evt-umano"
        evento_umano["verdetto_umano"] = "respinto"
        dati = registro.metriche([evento_gate, evento_umano])
        self.assertEqual(dati["codex"]["rework"], 2)

    def test_aggiungi_e_leggi_evento(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "eventi.jsonl"
            registro.aggiungi_evento(percorso, self.evento_valido())
            eventi = registro.leggi_eventi(percorso)
            self.assertEqual(len(eventi), 1)
            self.assertEqual(eventi[0]["id_evento"], "evt-1")

    def test_carica_eventi_multi_progetto_etichetta_e_aggrega_per_progetto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp) / "progetto_a"
            percorso_eventi = p_path / "dati_locali" / "orchestrazione" / "eventi.jsonl"
            registro.aggiungi_evento(percorso_eventi, self.evento_valido())
            evento_fallito = self.evento_valido()
            evento_fallito["id_evento"] = "evt-2"
            evento_fallito["esito_gate"] = "fallito"
            registro.aggiungi_evento(percorso_eventi, evento_fallito)

            progetti = [{"id": "progetto_a", "nome": "Progetto A", "percorso": str(p_path)}]
            tutti_eventi, progetto_stats = registro.carica_eventi_multi_progetto(progetti)

            self.assertEqual(len(tutti_eventi), 2)
            self.assertTrue(all(ev["_progetto_id"] == "progetto_a" for ev in tutti_eventi))
            self.assertEqual(progetto_stats["progetto_a"]["esecuzioni"], 2)
            self.assertEqual(progetto_stats["progetto_a"]["rework"], 1)

    def test_carica_eventi_multi_progetto_ignora_progetto_senza_registro(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progetti = [{"id": "vuoto", "nome": "Vuoto", "percorso": tmp}]
            tutti_eventi, progetto_stats = registro.carica_eventi_multi_progetto(progetti)
            self.assertEqual(tutti_eventi, [])
            self.assertEqual(progetto_stats["vuoto"]["esecuzioni"], 0)


if __name__ == "__main__":
    unittest.main()
