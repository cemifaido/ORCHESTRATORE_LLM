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

    def test_valida_rifiuta_union_type_non_corrispondente(self) -> None:
        evento = self.evento_valido()
        evento["voto_qualita"] = "alto"  # schema: ["integer", "null"]
        errori = registro.valida_evento(evento)
        self.assertTrue(any("voto_qualita" in errore for errore in errori))

    def test_valida_accetta_null_in_union_type(self) -> None:
        evento = self.evento_valido()
        evento["voto_qualita"] = None
        self.assertEqual(registro.valida_evento(evento), [])

    def test_valida_rifiuta_timestamp_non_conforme_a_date_time(self) -> None:
        evento = self.evento_valido()
        evento["timestamp"] = "non-e-una-data"
        errori = registro.valida_evento(evento)
        self.assertTrue(any("timestamp" in errore for errore in errori))

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

    def test_metriche_per_livello_smista_per_tipo_compito(self) -> None:
        evento_frontend = self.evento_valido()
        evento_frontend["id_evento"] = "evt-frontend"
        evento_frontend["tipo_compito"] = "interfaccia"
        evento_db = self.evento_valido()
        evento_db["id_evento"] = "evt-db"
        evento_db["tipo_compito"] = "database"
        evento_backend = self.evento_valido()
        evento_backend["id_evento"] = "evt-backend"
        evento_backend["tipo_compito"] = "servizi"

        dati = registro.metriche_per_livello([evento_frontend, evento_db, evento_backend])

        self.assertEqual(dati["codex"]["frontend"], 1)
        self.assertEqual(dati["codex"]["database"], 1)
        self.assertEqual(dati["codex"]["backend"], 1)

    def test_metriche_per_livello_categorie_trasversali_confluiscono_in_backend(self) -> None:
        tipi_trasversali = ["revisione", "sicurezza", "monitoraggio", "orchestrazione", "documentazione", "sconosciuto"]
        eventi = []
        for i, tipo in enumerate(tipi_trasversali):
            evento = self.evento_valido()
            evento["id_evento"] = f"evt-{i}"
            evento["tipo_compito"] = tipo
            eventi.append(evento)

        dati = registro.metriche_per_livello(eventi)

        self.assertEqual(dati["codex"]["backend"], len(tipi_trasversali))
        self.assertEqual(dati["codex"]["database"], 0)
        self.assertEqual(dati["codex"]["frontend"], 0)

    def test_metriche_per_livello_agente_senza_eventi_non_compare(self) -> None:
        dati = registro.metriche_per_livello([self.evento_valido()])
        self.assertNotIn("umano", dati)

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
            self.assertNotIn("errore", progetto_stats["vuoto"])

    def test_carica_eventi_multi_progetto_segnala_registro_corrotto_invece_di_nasconderlo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp) / "progetto_rotto"
            percorso_eventi = p_path / "dati_locali" / "orchestrazione" / "eventi.jsonl"
            percorso_eventi.parent.mkdir(parents=True, exist_ok=True)
            percorso_eventi.write_text("questa non e' una riga json valida\n", encoding="utf-8")

            progetti = [{"id": "progetto_rotto", "nome": "Progetto Rotto", "percorso": str(p_path)}]
            tutti_eventi, progetto_stats = registro.carica_eventi_multi_progetto(progetti)

            self.assertEqual(tutti_eventi, [])
            self.assertIn("errore", progetto_stats["progetto_rotto"])
            self.assertIn("corrotto", progetto_stats["progetto_rotto"]["errore"])


if __name__ == "__main__":
    unittest.main()
