from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import interfaccia


class IntegraProgettoTest(unittest.TestCase):
    def test_integra_progetto_funziona_indipendentemente_dalla_cwd(self) -> None:
        """integra_progetto deve leggere schema/config dell'orchestratore dalla propria
        posizione reale (RADICE), non dalla cartella da cui e' stato lanciato il processo:
        altrimenti, lanciato con una cwd diversa, fallisce silenziosamente (skip copia)."""
        cwd_originale = os.getcwd()
        with tempfile.TemporaryDirectory() as cwd_estranea, tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            os.chdir(cwd_estranea)
            try:
                interfaccia.integra_progetto(dest_path)
            finally:
                os.chdir(cwd_originale)

            self.assertTrue((dest_path / "schema" / "evento.v1.json").exists())
            self.assertTrue((dest_path / "config" / "comandi.esempio.json").exists())

    def test_integra_progetto_non_copia_piu_script_orchestratore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            interfaccia.integra_progetto(dest_path)

            for script in ["registro.py", "sentinella.py", "genera_cruscotto.py"]:
                self.assertFalse((dest_path / script).exists())
            self.assertFalse((dest_path / "requirements-orchestratore.txt").exists())

    def test_integra_progetto_aggiorna_gitignore_del_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            interfaccia.integra_progetto(dest_path)

            gitignore_path = dest_path / ".gitignore"
            self.assertTrue(gitignore_path.exists())
            contenuto = gitignore_path.read_text(encoding="utf-8")
            for regola in ["dati_locali/orchestrazione/", "config/comandi.json", "schema/evento.v1.json"]:
                self.assertIn(regola, contenuto)
            for regola_rimossa in ["registro.py", "sentinella.py", "genera_cruscotto.py"]:
                self.assertNotIn(regola_rimossa, contenuto)

    def test_integra_progetto_non_duplica_regole_gitignore_se_rieseguito(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            interfaccia.integra_progetto(dest_path)
            interfaccia.integra_progetto(dest_path)

            contenuto = (dest_path / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(contenuto.count("config/comandi.json"), 1)

    def test_integra_progetto_preserva_regole_gitignore_preesistenti(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest_path = Path(tmp)
            (dest_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

            interfaccia.integra_progetto(dest_path)

            contenuto = (dest_path / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("node_modules/", contenuto)
            self.assertIn("config/comandi.json", contenuto)


class InterpretaOutputSentinellaTest(unittest.TestCase):
    def test_decodifica_json_indentato_multi_riga(self) -> None:
        blob = (
            '{\n'
            '  "esito": "superato",\n'
            '  "codice": 0,\n'
            '  "latenza_ms": 12,\n'
            '  "output": "ok",\n'
            '  "evento": {"esito_gate": "superato"}\n'
            '}\n'
        )
        dati = interfaccia.interpreta_output_sentinella(blob)
        self.assertEqual(dati["esito"], "superato")
        self.assertEqual(dati["evento"]["esito_gate"], "superato")

    def test_fallback_su_output_non_json_include_stderr(self) -> None:
        dati = interfaccia.interpreta_output_sentinella("traceback boom", "errore reale")
        self.assertEqual(dati["output"], "traceback boom")
        self.assertEqual(dati["stderr"], "errore reale")


class EseguiSentinellaTest(unittest.TestCase):
    def test_esegue_comando_nel_progetto_target_senza_copie_di_script(self) -> None:
        """Il progetto target ha solo config/comandi.json, nessuna copia di sentinella.py
        o registro.py: la dashboard deve comunque riuscire a lanciare il comando usando
        lo script centrale, con cwd e --registro puntati al progetto target."""
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            comandi_path = p_path / "config" / "comandi.json"
            comandi_path.parent.mkdir(parents=True, exist_ok=True)
            comandi_path.write_text(json.dumps({
                "versione_schema": 1,
                "comandi": {
                    "prova": {
                        "cartella": ".",
                        "argomenti": ["python", "-c", "print('ok-target')"],
                        "timeout_secondi": 10,
                        "limite_output_caratteri": 1000,
                    }
                }
            }), encoding="utf-8")

            progetti = [{"id": "target", "nome": "Target", "percorso": str(p_path)}]
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                risultato = interfaccia.esegui_sentinella(
                    interfaccia.SentinellaInput(progetto_id="target", comando="prova")
                )

            self.assertEqual(risultato["status"], "success")
            self.assertEqual(risultato["dati"]["esito"], "superato")
            self.assertIn("ok-target", risultato["dati"]["output"])

            self.assertFalse((p_path / "sentinella.py").exists())
            self.assertFalse((p_path / "registro.py").exists())

            eventi_path = p_path / "dati_locali" / "orchestrazione" / "eventi.jsonl"
            self.assertTrue(eventi_path.exists())


class StatoApiTest(unittest.TestCase):
    def test_get_stato_riporta_errore_se_registro_e_corrotto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p_path = Path(tmp)
            # Scrive un file di log corrotto (non JSON)
            registro_dir = p_path / "dati_locali" / "orchestrazione"
            registro_dir.mkdir(parents=True, exist_ok=True)
            (registro_dir / "eventi.jsonl").write_text("corrupted line {bad json}", encoding="utf-8")

            progetti = [{"id": "corrupted_proj", "nome": "Corrotto", "percorso": str(p_path)}]
            with patch.object(interfaccia, "leggi_progetti", return_value=progetti):
                stato = interfaccia.get_stato()

            self.assertIn("corrupted_proj", stato["progetto_stats"])
            stat_proj = stato["progetto_stats"]["corrupted_proj"]
            self.assertIn("errore", stat_proj)
            self.assertIn("registro corrotto", stat_proj["errore"])


if __name__ == "__main__":
    unittest.main()
