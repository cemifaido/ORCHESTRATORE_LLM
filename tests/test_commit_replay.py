from __future__ import annotations

import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import commit_replay
import registro


class ConversioneUtcTest(unittest.TestCase):
    def test_timestamp_con_z_e_con_offset_esplicito_diventano_uguali_in_utc(self) -> None:
        """Un timestamp di git in fuso +02:00 e uno del registro in Z che indicano lo
        stesso istante devono confrontare uguali: prima del fix sarebbero stati
        confrontati come stringhe, sfasando la finestra di 2 ore."""
        dt_git = commit_replay._a_utc("2026-07-04T16:00:00+02:00")
        dt_registro = commit_replay._a_utc("2026-07-04T14:00:00Z")
        self.assertEqual(dt_git, dt_registro)

    def test_a_utc_ritorna_sempre_timezone_aware(self) -> None:
        dt = commit_replay._a_utc("2026-07-04T14:00:00Z")
        self.assertEqual(dt.tzinfo, timezone.utc)


class RepoGitRealeTest(unittest.TestCase):
    """Verifica contro il repository reale dell'orchestratore: non mocka git, prova
    che la correlazione commit -> finestra temporale funzioni per davvero."""

    def test_lista_commit_sul_repo_reale(self) -> None:
        commit = commit_replay.lista_commit(commit_replay.RADICE, limite=3)
        self.assertGreaterEqual(len(commit), 1)
        for c in commit:
            self.assertIn("hash", c)
            self.assertIn("data", c)
            self.assertIn("autore", c)
            self.assertIn("messaggio", c)
            self.assertIn("interazioni", c)
            self.assertIsInstance(c["interazioni"], int)
            self.assertGreaterEqual(c["interazioni"], 0)

    def test_lista_commit_con_registro_custom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso_reg = Path(tmp) / "eventi.jsonl"
            # Lista commit senza eventi nel registro temporaneo -> interazioni 0
            commit = commit_replay.lista_commit(commit_replay.RADICE, limite=2, percorso_registro=percorso_reg)
            self.assertGreaterEqual(len(commit), 1)
            for c in commit:
                self.assertEqual(c["interazioni"], 0)

    def test_finestra_temporale_head_e_coerente_col_commit_precedente(self) -> None:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=commit_replay.RADICE,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        inizio, fine = commit_replay.finestra_temporale_commit(commit_replay.RADICE, head)
        self.assertLess(inizio, fine)
        self.assertEqual(fine.tzinfo, timezone.utc)


class EventiNellaFinestraTest(unittest.TestCase):
    def evento(self, timestamp: str, agente: str = "locale", tipo_compito: str = "monitoraggio",
               token_totali: int | None = None) -> dict:
        return {
            "versione_schema": 1, "id_evento": f"evt-{timestamp}", "timestamp": timestamp,
            "id_compito": "t", "agente": agente, "tipo_compito": tipo_compito,
            "stato": "passato", "esito_gate": "non_eseguito", "verdetto_umano": "non_revisionato",
            "costo_stimato_usd": 0.0, "origine_costo": "stimato", "latenza_ms": 0,
            "regole_incluse": [], "file_modificati": [], "note": "",
            "metadati": {"token_totali": token_totali} if token_totali is not None else {},
        }

    def test_filtra_solo_eventi_dentro_la_finestra(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "eventi.jsonl"
            registro.aggiungi_evento(percorso, self.evento("2026-07-04T10:00:00Z"))
            registro.aggiungi_evento(percorso, self.evento("2026-07-04T12:00:00Z"))
            registro.aggiungi_evento(percorso, self.evento("2026-07-04T14:00:00Z"))

            inizio = datetime(2026, 7, 4, 11, 0, tzinfo=timezone.utc)
            fine = datetime(2026, 7, 4, 13, 0, tzinfo=timezone.utc)
            eventi = commit_replay.eventi_nella_finestra(percorso, inizio, fine)

            self.assertEqual(len(eventi), 1)
            self.assertEqual(eventi[0]["timestamp"], "2026-07-04T12:00:00Z")

    def test_registro_inesistente_ritorna_lista_vuota(self) -> None:
        eventi = commit_replay.eventi_nella_finestra(
            Path("non/esiste/eventi.jsonl"),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        self.assertEqual(eventi, [])


class StimaRisparmioTest(unittest.TestCase):
    def evento(self, agente: str, tipo_compito: str, token_totali: int | None = None) -> dict:
        return {"agente": agente, "tipo_compito": tipo_compito,
                "metadati": {"token_totali": token_totali} if token_totali is not None else {}}

    def test_solo_locale_da_percentuale_100(self) -> None:
        eventi = [
            self.evento("locale", "monitoraggio", 50),
            self.evento("locale", "monitoraggio", 30),
        ]
        stima = commit_replay.stima_risparmio(eventi)
        self.assertEqual(stima["percentuale_gratis"], 100.0)
        self.assertEqual(stima["controlli_locale"], 2)
        self.assertEqual(stima["controlli_a_pagamento"], 0)
        self.assertEqual(stima["token_totali_locale"], 80)

    def test_locale_piu_revisione_a_pagamento_da_percentuale_parziale(self) -> None:
        eventi = [
            self.evento("locale", "monitoraggio", 50),
            self.evento("locale", "monitoraggio", 50),
            self.evento("codex", "revisione"),
        ]
        stima = commit_replay.stima_risparmio(eventi)
        # 2 su 3 controlli gestiti gratis
        self.assertAlmostEqual(stima["percentuale_gratis"], 66.7, places=1)

    def test_nessun_evento_di_verifica_ritorna_percentuale_none(self) -> None:
        eventi = [{"agente": "claude", "tipo_compito": "servizi", "metadati": {}}]
        stima = commit_replay.stima_risparmio(eventi)
        self.assertIsNone(stima["percentuale_gratis"])

    def test_risparmio_usd_calcolato_dai_token_reali_col_prezzo_di_riferimento(self) -> None:
        eventi = [self.evento("locale", "monitoraggio", 1_000_000)]
        stima = commit_replay.stima_risparmio(eventi)
        self.assertAlmostEqual(stima["risparmio_stimato_usd"], 0.15, places=4)
        self.assertIn("GPT-4o-mini", stima["modello_riferimento"])

    def test_evento_locale_senza_token_totali_non_rompe_il_calcolo(self) -> None:
        eventi = [self.evento("locale", "monitoraggio", token_totali=None)]
        stima = commit_replay.stima_risparmio(eventi)
        self.assertEqual(stima["token_totali_locale"], 0)
        self.assertEqual(stima["risparmio_stimato_usd"], 0.0)


if __name__ == "__main__":
    unittest.main()
