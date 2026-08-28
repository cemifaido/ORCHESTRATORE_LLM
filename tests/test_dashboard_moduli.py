#!/usr/bin/env python3
"""Test unitari per i moduli estratti della dashboard (Lotti D & E):
- dashboard_config.py
- dashboard_progetti.py
- dashboard_flussi.py
- dashboard_servizi.py
- dashboard_os.py
- dashboard_risvegli.py
- interfaccia_api.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import dashboard_config
import dashboard_freschezza
import dashboard_flussi
import dashboard_os
import dashboard_progetti
import dashboard_risvegli
import dashboard_servizi
import interfaccia
import profili_operativi


class DashboardConfigTest(unittest.TestCase):
    def test_bind_e_loopback(self) -> None:
        self.assertTrue(dashboard_config.bind_e_loopback("127.0.0.1"))
        self.assertTrue(dashboard_config.bind_e_loopback("localhost"))
        self.assertTrue(dashboard_config.bind_e_loopback("::1"))
        self.assertFalse(dashboard_config.bind_e_loopback("0.0.0.0"))
        self.assertFalse(dashboard_config.bind_e_loopback("192.168.1.100"))

    def test_carica_env_custom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f_env = Path(tmp) / ".env"
            f_env.write_text(
                "# Commento\n"
                "TEST_CHIAVE_DASHBOARD_1=\"valore_con_spazi\"\n"
                "TEST_CHIAVE_DASHBOARD_2='valore_apici'\n"
                "RIGA_SENZA_UGUALE\n"
                "TEST_CHIAVE_DASHBOARD_3=valore_liscio\n",
                encoding="utf-8",
            )
            lette = dashboard_config.carica_env(f_env)
            self.assertIn("TEST_CHIAVE_DASHBOARD_1", lette)
            self.assertEqual(os.environ.get("TEST_CHIAVE_DASHBOARD_1"), "valore_con_spazi")
            self.assertEqual(os.environ.get("TEST_CHIAVE_DASHBOARD_2"), "valore_apici")
            self.assertEqual(os.environ.get("TEST_CHIAVE_DASHBOARD_3"), "valore_liscio")

    def test_verifica_bind_sicuro_fail_closed(self) -> None:
        dashboard_config.verifica_bind_sicuro("127.0.0.1", "")
        dashboard_config.verifica_bind_sicuro("localhost", "chiave123")
        dashboard_config.verifica_bind_sicuro("0.0.0.0", "chiave_segreta")

        with self.assertRaises(SystemExit):
            dashboard_config.verifica_bind_sicuro("0.0.0.0", "")


class MisuraPollingTest(unittest.TestCase):
    def test_timestamp_valido_restituisce_attesa_non_negativa(self) -> None:
        attesa = dashboard_risvegli.attesa_poll_ms("2026-01-01T00:00:00Z")
        assert attesa is not None
        self.assertIsInstance(attesa, float)
        self.assertGreaterEqual(attesa, 0)

    def test_timestamp_non_valido_non_inventa_una_misura(self) -> None:
        self.assertIsNone(dashboard_risvegli.attesa_poll_ms("non e' un timestamp"))
        self.assertIsNone(dashboard_risvegli.attesa_poll_ms(None))


class DashboardFreschezzaTest(unittest.TestCase):
    def test_impronta_rileva_modifica_aggiunta_e_rimozione(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            modulo = radice / "modulo.py"
            modulo.write_text("VERSIONE = 1\n", encoding="utf-8")
            avvio = dashboard_freschezza._impronta(radice)
            self.assertEqual(
                dashboard_freschezza.stato_codice_dashboard(radice=radice, impronta_avvio=avvio)["stato"],
                "allineato",
            )
            modulo.write_text("VERSIONE = 2\n", encoding="utf-8")
            (radice / "nuovo.py").write_text("x = 1\n", encoding="utf-8")
            stato = dashboard_freschezza.stato_codice_dashboard(radice=radice, impronta_avvio=avvio)
            self.assertEqual(stato["stato"], "modificato")
            self.assertEqual(stato["file_modificati"], ["modulo.py", "nuovo.py"])
            modulo.unlink()
            stato = dashboard_freschezza.stato_codice_dashboard(radice=radice, impronta_avvio=avvio)
            self.assertEqual(stato["file_modificati"], ["modulo.py", "nuovo.py"])

    def test_errore_lettura_e_non_verificabile(self) -> None:
        with patch.object(dashboard_freschezza, "_impronta", side_effect=OSError("negato")):
            stato = dashboard_freschezza.stato_codice_dashboard(impronta_avvio={})
        self.assertEqual(stato["stato"], "non_verificabile")
        self.assertEqual(stato["file_modificati"], [])


class DashboardProgettiTest(unittest.TestCase):
    def test_leggi_e_salva_progetti(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f_cfg = Path(tmp) / "progetti.json"
            progetti_init = dashboard_progetti.leggi_progetti(f_cfg)
            self.assertEqual(len(progetti_init), 1)
            self.assertEqual(progetti_init[0]["id"], "orchestratore")

            nuovi = [{"id": "p1", "nome": "Proj 1", "percorso": str(Path(tmp))}]
            dashboard_progetti.salva_progetti(nuovi, f_cfg)

            letti = dashboard_progetti.leggi_progetti(f_cfg)
            self.assertEqual(len(letti), 1)
            self.assertEqual(letti[0]["id"], "p1")

    def test_leggi_progetti_corrotto_ritorna_vuoto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f_cfg = Path(tmp) / "progetti.json"
            f_cfg.write_text("{bad json line", encoding="utf-8")
            self.assertEqual(dashboard_progetti.leggi_progetti(f_cfg), [])

    def test_integra_progetto_e_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_dest = Path(tmp)
            dashboard_progetti.integra_progetto(p_dest)

            self.assertTrue((p_dest / "dati_locali" / "orchestrazione").exists())
            self.assertTrue((p_dest / "CLAUDE.md").exists())
            self.assertTrue((p_dest / "GEMINI.md").exists())
            self.assertTrue((p_dest / "AGENTS.md").exists())
            self.assertTrue((p_dest / ".gitignore").exists())

            gi = (p_dest / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("CLAUDE.md", gi)
            self.assertIn("dati_locali/orchestrazione/", gi)

    def test_comandi_disponibili_e_arricchisci_progetto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_dest = Path(tmp)
            cfg_dir = p_dest / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "comandi.json").write_text(json.dumps({
                "versione_schema": 1,
                "comandi": {
                    "test_cmd": {"descrizione": "Esegui test"}
                }
            }), encoding="utf-8")

            proj = {"id": "p_test", "nome": "Test", "percorso": str(p_dest)}
            arricchito = dashboard_progetti.arricchisci_progetto(proj)
            self.assertEqual(len(arricchito["comandi"]), 1)
            self.assertEqual(arricchito["comandi"][0]["nome"], "test_cmd")
            self.assertEqual(arricchito["comandi"][0]["descrizione"], "Esegui test")


class DashboardFlussiTest(unittest.TestCase):
    def test_leggi_flussi_dichiarati_da_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_flussi = Path(tmp)
            (p_flussi / "flusso1.json").write_text(json.dumps({
                "id_flusso": "f1",
                "nome": "Flusso 1",
            }), encoding="utf-8")

            flussi = dashboard_flussi.leggi_flussi_dichiarati(p_flussi)
            self.assertIn("f1", flussi)
            self.assertEqual(flussi["f1"]["nome"], "Flusso 1")

    def test_calcola_fase_flusso_adapter(self) -> None:
        mock_flusso = {"id_flusso": "compito_standard", "fasi": [{"id_fase": "avvio"}]}
        with patch("motore_flusso.deriva_stato", return_value={"stato": "attivo", "fase": "avvio"}):
            fase = dashboard_flussi.calcola_fase_flusso([], "t1", flusso=mock_flusso)
            self.assertEqual(fase, "avvio")

        with patch("motore_flusso.deriva_stato", return_value={"stato": "completato", "fase": "chiusura"}):
            fase = dashboard_flussi.calcola_fase_flusso([], "t1", flusso=mock_flusso)
            self.assertEqual(fase, "chiusura")

        with patch("motore_flusso.deriva_stato", return_value={"stato": "non_definito", "fase": None}):
            fase = dashboard_flussi.calcola_fase_flusso([], "t1", flusso=mock_flusso)
            self.assertIsNone(fase)


class DashboardServiziTest(unittest.TestCase):
    def test_toggle_postino_e_headless(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_dir = Path(tmp)
            self.assertFalse(dashboard_servizi.postino_attivo(p_dir))
            self.assertFalse(dashboard_servizi.postino_headless_attivo(p_dir))

            res_on = dashboard_servizi.imposta_postino(p_dir, True)
            self.assertTrue(res_on)
            self.assertTrue(dashboard_servizi.postino_attivo(p_dir))

            res_off = dashboard_servizi.imposta_postino(p_dir, False)
            self.assertFalse(res_off)
            self.assertFalse(dashboard_servizi.postino_attivo(p_dir))

            res_h_on = dashboard_servizi.imposta_postino_headless(p_dir, True)
            self.assertTrue(res_h_on)
            self.assertTrue(dashboard_servizi.postino_headless_attivo(p_dir))

            res_h_off = dashboard_servizi.imposta_postino_headless(p_dir, False)
            self.assertFalse(res_h_off)
            self.assertFalse(dashboard_servizi.postino_headless_attivo(p_dir))

    def test_ottieni_stato_aggregato(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_dir = Path(tmp)
            progetti = [{"id": "p_serv", "nome": "Serv Proj", "percorso": str(p_dir)}]
            stato = dashboard_servizi.ottieni_stato(pagina=1, per_pagina=10, progetti=progetti)
            self.assertIn("progetti", stato)
            self.assertIn("globali", stato)
            self.assertEqual(stato["globali"]["progetti_totali"], 1)


class DashboardOsTest(unittest.TestCase):
    def test_pid_vivo_su_pid_non_valido_e_valido(self) -> None:
        self.assertFalse(dashboard_os.pid_vivo(None))
        self.assertFalse(dashboard_os.pid_vivo(0))
        self.assertFalse(dashboard_os.pid_vivo(-10))
        self.assertTrue(dashboard_os.pid_vivo(os.getpid()))

    def test_interpreta_output_sentinella_json_e_fallback(self) -> None:
        out_json = '{\n  "esito": "superato",\n  "codice": 0\n}\n'
        res = dashboard_os.interpreta_output_sentinella(out_json)
        self.assertEqual(res.get("esito"), "superato")

        out_txt = "Errore di parsing"
        res_txt = dashboard_os.interpreta_output_sentinella(out_txt, output_err="dettaglio")
        self.assertEqual(res_txt.get("output"), out_txt)
        self.assertEqual(res_txt.get("stderr"), "dettaglio")

    def test_protocollo_riavvio_persistente_e_log_del_figlio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            richiesto = dashboard_os.richiedi_riavvio(radice)
            stato_richiesto = dashboard_os.leggi_stato_riavvio(radice)
            assert stato_richiesto is not None
            self.assertEqual(stato_richiesto["stato"], "richiesto")
            with patch("dashboard_os.subprocess.Popen", return_value=type("P", (), {"pid": 4321})()) as popen:
                pid = dashboard_os.avvia_processo_sostituto(radice / "interfaccia.py", radice)
            self.assertEqual(pid, 4321)
            self.assertEqual(popen.call_args.args[0], [sys.executable, str(radice / "interfaccia.py")])
            stato_avviato = dashboard_os.leggi_stato_riavvio(radice)
            assert stato_avviato is not None
            self.assertEqual(stato_avviato["stato"], "processo_avviato")
            self.assertIn("pid=4321", (radice / "dati_locali" / "orchestrazione" / "dashboard_riavvio.log").read_text(encoding="utf-8"))
            dashboard_os.registra_dashboard_pronto(radice)
            pronto = dashboard_os.leggi_stato_riavvio(radice)
            assert pronto is not None
            self.assertEqual(pronto["id"], richiesto["id"])
            self.assertEqual(pronto["stato"], "pronto")


class DashboardRisvegliTest(unittest.TestCase):
    def test_stato_risvegli_read_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_stato = Path(tmp) / "risvegli_notificati.json"
            stato_vuoto, init_vuoto = dashboard_risvegli.leggi_stato_risvegli(p_stato)
            self.assertFalse(init_vuoto)
            self.assertEqual(stato_vuoto.get("notificati"), {})

            stato_salvato = {"versione_schema": 1, "notificati": {"claude": ["msg1"]}}
            dashboard_risvegli.scrivi_stato_risvegli(p_stato, stato_salvato)

            stato_letto, init_letto = dashboard_risvegli.leggi_stato_risvegli(p_stato)
            self.assertTrue(init_letto)
            self.assertEqual(stato_letto["notificati"]["claude"], ["msg1"])

    def test_genera_prompt_risveglio_fallback_e_troncamento(self) -> None:
        fallback = dashboard_risvegli.genera_prompt_risveglio_con_llm("gemini", [])
        self.assertIn("gemini", fallback)
        self.assertIn("prossimo", fallback)

    def test_piattaforma_supporta_risveglio_os(self) -> None:
        """Il deep-link/clipboard di dashboard_os.py e' Windows-only (vedi
        os_supportati=['windows'] delle capability *_uri_wake): il gate deve
        rispecchiare esattamente os.name, senza fallback impliciti."""
        with patch.object(dashboard_risvegli.os, "name", "nt"):
            self.assertTrue(dashboard_risvegli.piattaforma_supporta_risveglio_os())
        with patch.object(dashboard_risvegli.os, "name", "posix"):
            self.assertFalse(dashboard_risvegli.piattaforma_supporta_risveglio_os())

    @staticmethod
    def _pendente(agente: str = "claude") -> dict[str, list[dict]]:
        return {
            "claude": ([{"id_messaggio": "m-nuovo", "thread_id": "t-1", "cronologia": []}] if agente == "claude" else []),
            "codex": [],
            "gemini": [],
        }

    def test_brainstorming_esegue_dispatch_headless(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            dashboard_risvegli.scrivi_stato_risvegli(
                dashboard_risvegli.percorso_stato_risvegli(radice), {"versione_schema": 1, "notificati": {}},
            )
            with patch("dashboard_risvegli.thread_pendenti_per_agente", return_value=self._pendente()), \
                 patch("profili_operativi.carica", return_value={"profilo": "brainstorming"}), \
                 patch("profili_operativi.dispatch_abilitato", return_value=True), \
                 patch("postino.dispatch", return_value={"esito": "inviato", "codice": 0}) as dispatch, \
                 patch("interfaccia._trova_ultima_sessione_claude", return_value=None), \
                 patch("interfaccia._esegui_risveglio_os") as risveglio:
                _, esiti = dashboard_risvegli.calcola_ed_esegui_risvegli(radice, [])

            dispatch.assert_called_once_with(
                radice, "claude", "t-1", id_messaggio_attivatore="m-nuovo",
            )
            risveglio.assert_not_called()
            self.assertEqual(esiti[0]["status"], "headless")

    def test_standard_esegue_risveglio_passivo_senza_gating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            dashboard_risvegli.scrivi_stato_risvegli(
                dashboard_risvegli.percorso_stato_risvegli(radice), {"versione_schema": 1, "notificati": {}},
            )
            with patch("dashboard_risvegli.thread_pendenti_per_agente", return_value=self._pendente()), \
                 patch("profili_operativi.carica", return_value=profili_operativi.profilo_standard()), \
                 patch("profili_operativi.dispatch_abilitato", return_value=False), \
                 patch("postino.dispatch") as dispatch, \
                 patch("postino.registra_canale") as registra_canale, \
                 patch("interfaccia._trova_ultima_sessione_claude", return_value=None), \
                 patch("interfaccia._esegui_risveglio_os", return_value={"status": "eseguito", "modalita": "focus_ide"}) as risveglio:
                _, esiti = dashboard_risvegli.calcola_ed_esegui_risvegli(radice, [])

            dispatch.assert_not_called()
            registra_canale.assert_not_called()
            risveglio.assert_called_once_with("claude", [], None)
            self.assertEqual(esiti[0]["status"], "eseguito")


class DashboardProfiliOperativiTest(unittest.TestCase):
    def test_post_profilo_e_get_bacheca(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice_progetto = Path(tmp)
            f_cfg = radice_progetto / "progetti.json"
            progetti = [{"id": "test_proj", "nome": "Test Proj", "percorso": str(radice_progetto)}]
            dashboard_progetti.salva_progetti(progetti, f_cfg)

            # Crea marker legacy da ripulire
            p_leg = radice_progetto / "dati_locali" / "orchestrazione"
            p_leg.mkdir(parents=True, exist_ok=True)
            (p_leg / "POSTINO_ATTIVO").write_text("1", encoding="utf-8")
            (p_leg / "POSTINO_HEADLESS_ATTIVO").write_text("1", encoding="utf-8")

            with patch("dashboard_progetti.leggi_progetti", return_value=progetti), \
                 patch("interfaccia.leggi_progetti", return_value=progetti):
                client = TestClient(interfaccia.app)

                # 1. POST profilo valido
                res_post = client.post(
                    "/api/bacheca/postino/profilo",
                    json={"progetto_id": "test_proj", "profilo": "brainstorming"},
                )
                self.assertEqual(res_post.status_code, 200)
                dati_post = res_post.json()
                self.assertEqual(dati_post["status"], "ok")
                self.assertEqual(dati_post["profilo"]["profilo"], "brainstorming")
                self.assertEqual(dati_post["garanzie_per_agente"]["claude"], "enforced")
                self.assertEqual(dati_post["garanzie_per_agente"]["codex"], "prompt_only")

                # Verifica housekeeping su marker legacy
                self.assertFalse((p_leg / "POSTINO_ATTIVO").exists())
                self.assertFalse((p_leg / "POSTINO_HEADLESS_ATTIVO").exists())

                # 2. GET bacheca include profilo DTO e garanzie
                res_get = client.get("/api/bacheca?progetto_id=test_proj")
                self.assertEqual(res_get.status_code, 200)
                dati_get = res_get.json()
                self.assertIn("profilo", dati_get)
                self.assertEqual(dati_get["profilo"]["profilo"], "brainstorming")
                self.assertIn("garanzie_per_agente", dati_get)
                self.assertIn("descrizione_profilo", dati_get)

                # 3. Il flag che la UI usa e' la policy backend: super/smodata
                # sono attivi, standard resta fail-closed.
                for profilo, attivo in (("super", True), ("smodata", True), ("standard", False)):
                    with self.subTest(profilo=profilo):
                        res = client.post(
                            "/api/bacheca/postino/profilo",
                            json={"progetto_id": "test_proj", "profilo": profilo},
                        )
                        self.assertEqual(res.status_code, 200)
                        dati = client.get("/api/bacheca?progetto_id=test_proj").json()
                        self.assertEqual(dati["profilo"]["profilo"], profilo)
                        self.assertEqual(dati["postino_headless_attivo"], attivo)

                # 4. POST profilo non valido => HTTP 400
                res_bad_prof = client.post(
                    "/api/bacheca/postino/profilo",
                    json={"progetto_id": "test_proj", "profilo": "profilo_inventato"},
                )
                self.assertEqual(res_bad_prof.status_code, 400)

                # 5. POST progetto inesistente => HTTP 404
                res_bad_proj = client.post(
                    "/api/bacheca/postino/profilo",
                    json={"progetto_id": "non_esiste", "profilo": "standard"},
                )
                self.assertEqual(res_bad_proj.status_code, 404)


class InterfacciaSmokeTest(unittest.TestCase):
    def test_smoke_app_e_route_principali(self) -> None:
        client = TestClient(interfaccia.app)
        res_index = client.get("/")
        self.assertEqual(res_index.status_code, 200)

        res_stato = client.get("/api/stato")
        self.assertEqual(res_stato.status_code, 200)
        self.assertIn("progetti", res_stato.json())

        res_flussi = client.get("/api/flussi")
        self.assertEqual(res_flussi.status_code, 200)
        self.assertIn("flussi", res_flussi.json())


if __name__ == "__main__":
    unittest.main()
