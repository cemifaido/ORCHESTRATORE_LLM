from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import capability_policy
import hook_gemini


def _catalogo(*voci: dict) -> dict:
    return {"capability": list(voci)}


def _voce(**extra: str) -> dict[str, str]:
    base = {
        "id": "claude_cli_headless",
        "stato": "verified",
        "modalita_operativa": "automatica",
        "expires_at": "2026-09-01T00:00:00Z",
    }
    base.update(extra)
    return base


class CapabilityPolicyTest(unittest.TestCase):
    def test_verified_automatica_non_scaduta_e_autorizzata(self) -> None:
        esito = capability_policy.valuta_catalogo(
            _catalogo(_voce()), "claude", "headless",
            ora=datetime(2026, 8, 26, tzinfo=timezone.utc),
        )
        self.assertEqual(esito, {"esito": "autorizzato", "capability": "claude_cli_headless"})

    def test_assente_non_verificata_non_automatica_e_scaduta_sono_bloccate(self) -> None:
        ora = datetime(2026, 8, 26, tzinfo=timezone.utc)
        casi = [
            (_catalogo(), "capability_assente"),
            (_catalogo(_voce(stato="unknown")), "capability_non_verificata"),
            (_catalogo(_voce(modalita_operativa="manual_only")), "capability_non_automatica"),
            (_catalogo(_voce(expires_at="2026-08-25T00:00:00Z")), "capability_scaduta"),
        ]
        for catalogo, motivo in casi:
            with self.subTest(motivo=motivo):
                self.assertEqual(
                    capability_policy.valuta_catalogo(catalogo, "claude", "headless", ora=ora)["motivo"], motivo
                )

    def test_catalogo_mancante_blocca_fail_closed(self) -> None:
        esito = capability_policy.autorizza_automazione(
            "claude", "headless", catalogo_path=Path("catalogo-inesistente.json")
        )
        self.assertEqual(esito["motivo"], "catalogo_non_leggibile")

    def test_blocco_e_registrato_in_jsonl_locale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            decisione = {"esito": "bloccato", "motivo": "capability_scaduta", "capability": "claude_cli_headless"}
            self.assertTrue(capability_policy.registra_blocco(Path(tmp), "claude", "headless", decisione))
            percorso = Path(tmp) / "dati_locali" / "orchestrazione" / "capability_blocchi.jsonl"
            record = json.loads(percorso.read_text(encoding="utf-8"))
            self.assertEqual(record["motivo"], "capability_scaduta")

    def test_hook_gemini_bloccato_non_legge_bacheca_e_scrive_diagnostica(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(hook_gemini, "RADICE", Path(tmp)), \
             patch("hook_gemini.capability_policy.autorizza_automazione", return_value={
                 "esito": "bloccato", "motivo": "capability_non_verificata", "capability": "gemini_hook_pull",
             }), patch("hook_gemini.bacheca.leggi_messaggi") as leggi_messaggi, \
             patch("sys.stdout", new_callable=io.StringIO) as stdout, \
             patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(hook_gemini.main(), 0)
            leggi_messaggi.assert_not_called()
            self.assertEqual(stdout.getvalue().strip(), "{}")
            self.assertIn("capability_non_verificata", stderr.getvalue())
            log = Path(tmp) / "dati_locali" / "orchestrazione" / "log_hook_antigravity.jsonl"
            self.assertIn("capability_non_verificata", log.read_text(encoding="utf-8"))
