from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import bacheca
import verifica_aggiornamenti_cli as vac


class EstraiVersioneTest(unittest.TestCase):
    def test_estrae_da_output_eterogenei(self) -> None:
        self.assertEqual(vac._estrai_versione("codex-cli 0.149.1"), "0.149.1")
        self.assertEqual(vac._estrai_versione("2.1.204 (Claude Code)"), "2.1.204")
        self.assertEqual(vac._estrai_versione("1.1.0"), "1.1.0")

    def test_nessuna_versione_trovata(self) -> None:
        self.assertIsNone(vac._estrai_versione("errore, nessuna versione qui"))


class ConfrontaVersioniTest(unittest.TestCase):
    def test_confronto_numerico_non_lessicografico(self) -> None:
        # '0.9.0' < '0.10.0' numericamente, ma '0.10.0' < '0.9.0' come stringhe:
        # qui si verifica che il confronto sia quello giusto (numerico).
        self.assertEqual(vac.confronta_versioni("0.9.0", "0.10.0"), -1)
        self.assertEqual(vac.confronta_versioni("0.10.0", "0.9.0"), 1)

    def test_uguali(self) -> None:
        self.assertEqual(vac.confronta_versioni("1.2.3", "1.2.3"), 0)

    def test_maggiore_minore(self) -> None:
        self.assertEqual(vac.confronta_versioni("2.1.204", "2.1.245"), -1)
        self.assertEqual(vac.confronta_versioni("2.1.245", "2.1.204"), 1)


class VersioneInstallataTest(unittest.TestCase):
    def test_agente_sconosciuto_ritorna_none(self) -> None:
        self.assertIsNone(vac.versione_installata("locale"))

    def test_estrae_versione_da_stdout(self) -> None:
        esegui = MagicMock(return_value=MagicMock(stdout="codex-cli 0.149.1\n", stderr=""))
        with patch.object(vac, "_risolvi_eseguibile", return_value=r"C:\fake\codex.CMD"):
            versione = vac.versione_installata("codex", esegui=esegui)
        self.assertEqual(versione, "0.149.1")
        esegui.assert_called_once_with([r"C:\fake\codex.CMD", "--version"], capture_output=True, text=True, timeout=15, check=False)

    def test_eseguibile_non_risolvibile_ritorna_none_senza_chiamare_esegui(self) -> None:
        esegui = MagicMock()
        with patch.object(vac, "_risolvi_eseguibile", return_value=None):
            self.assertIsNone(vac.versione_installata("claude", esegui=esegui))
        esegui.assert_not_called()

    def test_comando_non_trovato_non_esplode(self) -> None:
        esegui = MagicMock(side_effect=FileNotFoundError())
        with patch.object(vac, "_risolvi_eseguibile", return_value=r"C:\fake\claude.EXE"):
            self.assertIsNone(vac.versione_installata("claude", esegui=esegui))


class VersioneDisponibileTest(unittest.TestCase):
    def test_npm_per_claude_e_codex(self) -> None:
        richiedi = MagicMock(return_value=MagicMock(returncode=0, stdout="2.1.245\n"))
        with patch.object(vac, "_risolvi_eseguibile", return_value=r"C:\fake\npm.CMD"):
            versione = vac.versione_disponibile("claude", esegui_npm=richiedi)
        self.assertEqual(versione, "2.1.245")
        richiedi.assert_called_once_with(
            [r"C:\fake\npm.CMD", "view", "@anthropic-ai/claude-code", "version"],
            capture_output=True, text=True, timeout=20, check=False,
        )

    def test_npm_non_risolvibile_ritorna_none(self) -> None:
        richiedi = MagicMock()
        with patch.object(vac, "_risolvi_eseguibile", return_value=None):
            self.assertIsNone(vac.versione_disponibile("claude", esegui_npm=richiedi))
        richiedi.assert_not_called()

    def test_npm_fallito_ritorna_none(self) -> None:
        richiedi = MagicMock(return_value=MagicMock(returncode=1, stdout=""))
        with patch.object(vac, "_risolvi_eseguibile", return_value=r"C:\fake\npm.CMD"):
            self.assertIsNone(vac.versione_disponibile("codex", esegui_npm=richiedi))

    def test_manifest_per_gemini(self) -> None:
        risposta = MagicMock()
        risposta.__enter__.return_value.read.return_value = json.dumps({"version": "1.1.20"}).encode()
        apri_url = MagicMock(return_value=risposta)
        self.assertEqual(vac.versione_disponibile("gemini", apri_url=apri_url), "1.1.20")
        apri_url.assert_called_once_with(vac.MANIFEST_AGY_URL, timeout=15)

    def test_manifest_irraggiungibile_ritorna_none(self) -> None:
        import urllib.error
        apri_url = MagicMock(side_effect=urllib.error.URLError("no network"))
        self.assertIsNone(vac.versione_disponibile("gemini", apri_url=apri_url))

    def test_agente_sconosciuto_ritorna_none(self) -> None:
        self.assertIsNone(vac.versione_disponibile("locale"))


class VerificaTuttiTest(unittest.TestCase):
    def test_segnala_aggiornamento_disponibile(self) -> None:
        with patch.object(vac, "versione_installata", side_effect=lambda a, **_: {"claude": "2.1.204"}.get(a)), \
             patch.object(vac, "versione_disponibile", side_effect=lambda a, **_: {"claude": "2.1.245"}.get(a)):
            esito = vac.verifica_tutti(agenti=("claude",))
        self.assertTrue(esito["claude"]["aggiornamento_disponibile"])
        self.assertEqual(esito["claude"]["installata"], "2.1.204")
        self.assertEqual(esito["claude"]["disponibile"], "2.1.245")

    def test_nessun_aggiornamento_se_gia_ultima(self) -> None:
        with patch.object(vac, "versione_installata", return_value="1.1.20"), \
             patch.object(vac, "versione_disponibile", return_value="1.1.20"):
            esito = vac.verifica_tutti(agenti=("gemini",))
        self.assertFalse(esito["gemini"]["aggiornamento_disponibile"])

    def test_versione_mancante_non_segnala_aggiornamento(self) -> None:
        """Se non riusciamo a leggere una delle due versioni, mai dedurre un
        aggiornamento per difetto - fail-closed, coerente col resto del progetto."""
        with patch.object(vac, "versione_installata", return_value=None), \
             patch.object(vac, "versione_disponibile", return_value="1.1.20"):
            esito = vac.verifica_tutti(agenti=("gemini",))
        self.assertFalse(esito["gemini"]["aggiornamento_disponibile"])


class LlamaAttivoTest(unittest.TestCase):
    def test_health_ok_ritorna_true(self) -> None:
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock()
        with patch("verifica_aggiornamenti_cli.urllib.request.urlopen", return_value=cm):
            self.assertTrue(vac.llama_attivo())

    def test_connessione_rifiutata_ritorna_false(self) -> None:
        import urllib.error
        with patch("verifica_aggiornamenti_cli.urllib.request.urlopen", side_effect=urllib.error.URLError("rifiutata")):
            self.assertFalse(vac.llama_attivo())


class AssicuraLlamaAttivoTest(unittest.TestCase):
    def test_non_avvia_nulla_se_gia_attivo(self) -> None:
        with patch.object(vac, "llama_attivo", return_value=True), \
             patch.object(vac, "avvia_llama_leggero") as avvia_mock:
            self.assertTrue(vac.assicura_llama_attivo())
        avvia_mock.assert_not_called()

    def test_avvia_col_modello_leggero_se_spento(self) -> None:
        with patch.object(vac, "llama_attivo", return_value=False), \
             patch.object(vac, "avvia_llama_leggero", return_value=True) as avvia_mock:
            self.assertTrue(vac.assicura_llama_attivo())
        avvia_mock.assert_called_once()


class AvviaLlamaLeggeroTest(unittest.TestCase):
    def test_lancia_il_processo_col_modello_leggero_e_attende_health(self) -> None:
        avvia_processo = MagicMock()
        chiamate_health = iter([False, False, True])
        with patch.object(vac.Path, "exists", return_value=True), \
             patch.object(vac, "llama_attivo", side_effect=lambda **_: next(chiamate_health)), \
             patch("verifica_aggiornamenti_cli.time.sleep"):
            esito = vac.avvia_llama_leggero(avvia_processo=avvia_processo)
        self.assertTrue(esito)
        avvia_processo.assert_called_once()
        comando = avvia_processo.call_args.args[0]
        self.assertIn(str(vac.MODELLO_LEGGERO_GGUF), comando)
        self.assertIn("-LlamaParallel", comando)

    def test_script_mancante_solleva_errore_chiaro(self) -> None:
        with patch.object(vac.Path, "exists", return_value=False):
            with self.assertRaises(FileNotFoundError):
                vac.avvia_llama_leggero(avvia_processo=MagicMock())

    def test_timeout_avvio_ritorna_false_senza_attendere_a_lungo(self) -> None:
        with patch.object(vac.Path, "exists", return_value=True), \
             patch.object(vac, "llama_attivo", return_value=False), \
             patch("verifica_aggiornamenti_cli.time.sleep"):
            esito = vac.avvia_llama_leggero(avvia_processo=MagicMock(), timeout_avvio_secondi=0.01)
        self.assertFalse(esito)


class NoteRilascioTest(unittest.TestCase):
    def test_codex_legge_body_dalla_release_github(self) -> None:
        risposta = MagicMock()
        risposta.__enter__.return_value.read.return_value = json.dumps(
            {"tag_name": "rust-v0.149.1", "body": "## Changelog\nFix vari."}
        ).encode()
        apri_url = MagicMock(return_value=risposta)
        self.assertEqual(vac._note_rilascio_codex(apri_url=apri_url), "## Changelog\nFix vari.")

    def test_codex_corpo_vuoto_ritorna_none(self) -> None:
        risposta = MagicMock()
        risposta.__enter__.return_value.read.return_value = json.dumps({"body": "  "}).encode()
        apri_url = MagicMock(return_value=risposta)
        self.assertIsNone(vac._note_rilascio_codex(apri_url=apri_url))

    def test_codex_irraggiungibile_ritorna_none(self) -> None:
        import urllib.error
        apri_url = MagicMock(side_effect=urllib.error.URLError("no network"))
        self.assertIsNone(vac._note_rilascio_codex(apri_url=apri_url))

    def test_gemini_usa_agy_changelog(self) -> None:
        esegui = MagicMock(return_value=MagicMock(returncode=0, stdout="Note di rilascio 1.1.20\n"))
        with patch.object(vac, "_risolvi_eseguibile", return_value=r"C:\fake\agy.EXE"):
            testo = vac._note_rilascio_gemini(esegui=esegui)
        self.assertEqual(testo, "Note di rilascio 1.1.20")
        esegui.assert_called_once_with([r"C:\fake\agy.EXE", "changelog"], capture_output=True, text=True, timeout=20, check=False)

    def test_gemini_eseguibile_non_risolvibile_ritorna_none(self) -> None:
        with patch.object(vac, "_risolvi_eseguibile", return_value=None):
            self.assertIsNone(vac._note_rilascio_gemini(esegui=MagicMock()))

    def test_claude_non_ha_fonte_nota_ritorna_none_senza_chiamate(self) -> None:
        """Nessuna fonte affidabile nota per claude: e' un limite dichiarato,
        non un errore - note_rilascio torna None senza tentare nulla."""
        self.assertIsNone(vac.note_rilascio("claude"))

    def test_agente_sconosciuto_ritorna_none(self) -> None:
        self.assertIsNone(vac.note_rilascio("locale"))


class RiassumiNoteRilascioTest(unittest.TestCase):
    def test_passa_il_testo_al_modello_locale_e_ritorna_il_riassunto(self) -> None:
        misurazione = MagicMock()
        chiama_locale = MagicMock(return_value=(MagicMock(), misurazione))
        with patch.object(vac.litellm, "testo_da_risposta", return_value="Riassunto breve."):
            riassunto = vac.riassumi_note_rilascio("testo lungo di note di rilascio", chiama_locale=chiama_locale)
        self.assertEqual(riassunto, "Riassunto breve.")
        chiama_locale.assert_called_once()
        self.assertEqual(chiama_locale.call_args.kwargs["messaggi"][0]["role"], "system")

    def test_tronca_il_testo_troppo_lungo(self) -> None:
        chiama_locale = MagicMock(return_value=(MagicMock(), MagicMock()))
        with patch.object(vac.litellm, "testo_da_risposta", return_value="ok"):
            vac.riassumi_note_rilascio("x" * 20000, chiama_locale=chiama_locale)
        testo_inviato = chiama_locale.call_args.kwargs["messaggi"][1]["content"]
        self.assertLessEqual(len(testo_inviato), 6000)

    def test_modello_locale_non_raggiungibile_ritorna_none(self) -> None:
        chiama_locale = MagicMock(side_effect=ConnectionError("giu'"))
        self.assertIsNone(vac.riassumi_note_rilascio("testo", chiama_locale=chiama_locale))


class NotificaBachecaAggiornamentoTest(unittest.TestCase):
    def test_scrive_un_messaggio_leggibile_da_bacheca(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            messaggio = vac.notifica_bacheca_aggiornamento(radice, "codex", "0.149.0", "0.149.1", "riassunto qui")
            self.assertEqual(messaggio["mittente"], "sistema")
            self.assertEqual(messaggio["destinatari"], ["claude"])
            self.assertIn("codex", messaggio["testo"])
            self.assertIn("0.149.0", messaggio["testo"])
            self.assertIn("riassunto qui", messaggio["testo"])

            messaggi = bacheca.leggi_messaggi(radice / "dati_locali" / "orchestrazione" / "messaggi.jsonl")
            self.assertEqual(len(messaggi), 1)
            self.assertEqual(messaggi[0]["id_messaggio"], messaggio["id_messaggio"])

    def test_senza_riassunto_lo_dichiara_esplicitamente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            messaggio = vac.notifica_bacheca_aggiornamento(Path(tmp), "claude", "2.1.200", "2.1.245", None)
            self.assertIn("Nessun riassunto disponibile", messaggio["testo"])


class EseguiControlloENotificaTest(unittest.TestCase):
    def test_notifica_solo_gli_agenti_con_aggiornamento(self) -> None:
        finto_esito = {
            "claude": {"installata": "2.1.200", "disponibile": "2.1.245", "aggiornamento_disponibile": True},
            "codex": {"installata": "0.149.1", "disponibile": "0.149.1", "aggiornamento_disponibile": False},
            "gemini": {"installata": "1.1.20", "disponibile": "1.1.20", "aggiornamento_disponibile": False},
        }
        with patch.object(vac, "assicura_llama_attivo", return_value=True), \
             patch.object(vac, "verifica_tutti", return_value=finto_esito), \
             patch.object(vac, "note_rilascio", return_value=None), \
             patch.object(vac, "notifica_bacheca_aggiornamento", return_value={"id_messaggio": "abc123"}) as notifica_mock:
            esito = vac.esegui_controllo_e_notifica(radice=Path("."))
        notifica_mock.assert_called_once_with(Path("."), "claude", "2.1.200", "2.1.245", None)
        self.assertEqual(esito["notificati"], ["abc123"])

    def test_nessun_aggiornamento_non_notifica_nulla(self) -> None:
        finto_esito = {
            "claude": {"installata": "2.1.245", "disponibile": "2.1.245", "aggiornamento_disponibile": False},
        }
        with patch.object(vac, "assicura_llama_attivo", return_value=True), \
             patch.object(vac, "verifica_tutti", return_value=finto_esito), \
             patch.object(vac, "notifica_bacheca_aggiornamento") as notifica_mock:
            esito = vac.esegui_controllo_e_notifica(radice=Path("."))
        notifica_mock.assert_not_called()
        self.assertEqual(esito["notificati"], [])


if __name__ == "__main__":
    unittest.main()
