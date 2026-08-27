"""Golden path integrato: bacheca -> postino -> registro -> dashboard."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import bacheca
import dashboard_servizi
import postino
import profili_operativi
import registro


class GoldenPathBachecaPostinoDashboardTest(unittest.TestCase):
    def test_messaggio_dispatch_registro_e_proiezione_dashboard(self) -> None:
        """Un turno autorizzato resta osservabile, con tempo riproducibile,
        dalla richiesta umana fino alle due proiezioni della dashboard."""
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            thread_id = "thread-golden"
            (radice / "dati_locali" / "orchestrazione").mkdir(parents=True)
            profili_operativi.imposta(radice, "brainstorming", revisione="test-golden")
            bacheca.aggiungi_messaggio(
                radice / "dati_locali" / "orchestrazione" / "messaggi.jsonl",
                bacheca.costruisci_messaggio(
                    mittente="umano", destinatari=["codex"], tipo="richiesta",
                    testo="Verifica il golden path.", thread_id=thread_id,
                ),
            )
            ora_fissa = datetime(2026, 8, 27, 7, 0, tzinfo=timezone.utc)

            # Il catalogo capability e' configurazione dell'installazione, non
            # una precondizione di questo test del flusso applicativo: il
            # confine policy e' coperto separatamente da test_capability_policy.
            with patch.object(
                postino.capability_policy,
                "autorizza_automazione",
                return_value={"esito": "autorizzato", "capability": "test_cli_headless"},
            ), patch.object(postino, "_risolvi_eseguibile", return_value="agente-finto"):
                esito = postino.dispatch(
                    radice, "codex", thread_id,
                    esegui=lambda *args, **kwargs: SimpleNamespace(returncode=0),
                    adesso=lambda: ora_fissa,
                )

            self.assertEqual(esito["esito"], "inviato")
            self.assertEqual(esito["quando"], ora_fissa.isoformat())
            eventi = registro.leggi_eventi(radice / "dati_locali" / "orchestrazione" / "eventi.jsonl")
            self.assertEqual(len(eventi), 1)
            self.assertEqual(eventi[0]["metadati"]["postino"]["thread_id"], thread_id)

            progetti = [{"id": "golden", "nome": "Golden", "percorso": str(radice)}]
            bacheca_dashboard = dashboard_servizi.ottieni_bacheca_progetto("golden", progetti=progetti)
            self.assertEqual(bacheca_dashboard["errore"] if "errore" in bacheca_dashboard else None, None)
            self.assertEqual(bacheca_dashboard["thread"][0]["thread_id"], thread_id)
            self.assertEqual(bacheca_dashboard["thread"][0]["fase_flusso"], "compito")
            self.assertEqual(bacheca_dashboard["thread"][0]["stato_flusso"]["stato"], "attivo")

            stato_dashboard = dashboard_servizi.ottieni_stato(progetti=progetti)
            self.assertEqual(stato_dashboard["globali"]["eventi_totali"], 1)
            self.assertEqual(stato_dashboard["eventi"][0]["id_evento"], eventi[0]["id_evento"])
