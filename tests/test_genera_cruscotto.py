from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import registro
import genera_cruscotto


class RenderizzaTest(unittest.TestCase):
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

    def test_renderizza_include_sintesi_progetto_e_agente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp) / "progetto_a"
            percorso_eventi = p_path / "dati_locali" / "orchestrazione" / "eventi.jsonl"
            registro.aggiungi_evento(percorso_eventi, self.evento_valido())

            progetti = [{"id": "progetto_a", "nome": "Progetto A", "percorso": str(p_path)}]
            markdown = genera_cruscotto.renderizza(progetti)

            self.assertIn("Progetti monitorati: **1**", markdown)
            self.assertIn("Eventi totali registrati: **1**", markdown)
            self.assertIn("| Progetto A |", markdown)
            self.assertIn("| codex |", markdown)

    def test_renderizza_senza_eventi_non_fallisce(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progetti = [{"id": "vuoto", "nome": "Vuoto", "percorso": tmp}]
            markdown = genera_cruscotto.renderizza(progetti)
            self.assertIn("Eventi totali registrati: **0**", markdown)

    def test_renderizza_segnala_registro_corrotto_invece_di_nasconderlo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp) / "progetto_rotto"
            percorso_eventi = p_path / "dati_locali" / "orchestrazione" / "eventi.jsonl"
            percorso_eventi.parent.mkdir(parents=True, exist_ok=True)
            percorso_eventi.write_text("non e' json valido\n", encoding="utf-8")

            progetti = [{"id": "progetto_rotto", "nome": "Progetto Rotto", "percorso": str(p_path)}]
            markdown = genera_cruscotto.renderizza(progetti)

            self.assertIn("Registri non leggibili", markdown)
            self.assertIn("Progetto Rotto", markdown)


if __name__ == "__main__":
    unittest.main()
