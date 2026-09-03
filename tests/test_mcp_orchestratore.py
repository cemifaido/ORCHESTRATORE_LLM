from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import bacheca
import mcp_orchestratore as mcp
import piano_comandi
import registro


def _dialogo(radice: Path, agente: str, richieste: list[dict]) -> list[dict]:
    entrata = io.StringIO("\n".join(json.dumps(r) for r in richieste) + "\n")
    uscita = io.StringIO()
    mcp.servi(entrata, uscita, radice, agente)
    return [json.loads(riga) for riga in uscita.getvalue().splitlines()]


class McpOrchestratoreTest(unittest.TestCase):
    def _radice_con_thread(self, tmp: str) -> tuple[Path, dict]:
        radice = Path(tmp)
        (radice / "dati_locali" / "orchestrazione").mkdir(parents=True)
        msg = bacheca.costruisci_messaggio(
            mittente="umano", destinatari=["claude"], tipo="richiesta",
            testo="fai X", thread_id="T1",
        )
        bacheca.aggiungi_messaggio(radice / "dati_locali" / "orchestrazione" / "messaggi.jsonl", msg)
        return radice, msg

    def test_initialize_ed_echo_versione_protocollo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, _ = self._radice_con_thread(tmp)
            [risp] = _dialogo(radice, "claude", [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2025-06-18"}},
            ])
            self.assertEqual(risp["result"]["protocolVersion"], "2025-06-18")
            self.assertIn("tools", risp["result"]["capabilities"])

    def test_notifica_initialized_non_produce_risposta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, _ = self._radice_con_thread(tmp)
            risposte = _dialogo(radice, "claude", [
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
            ])
            self.assertEqual(risposte, [])

    def test_tool_di_lettura_marcati_contenuto_non_fidato(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, _ = self._radice_con_thread(tmp)
            [risp] = _dialogo(radice, "claude", [
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            ])
            desc = {t["name"]: t["description"] for t in risp["result"]["tools"]}
            for lettura in ("bacheca_pendenti", "bacheca_thread", "piano_stato", "note_codice_elenco"):
                self.assertIn("DATO", desc[lettura])  # risultato = dato, non istruzione

    def test_bacheca_pendenti_per_agente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, msg = self._radice_con_thread(tmp)
            [risp] = _dialogo(radice, "claude", [
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "bacheca_pendenti", "arguments": {}}},
            ])
            self.assertFalse(risp["result"]["isError"])
            payload = json.loads(risp["result"]["content"][0]["text"])
            self.assertEqual(payload["pendenti"][0]["id_messaggio"], msg["id_messaggio"])
            # per codex, niente pendenti
            [risp_codex] = _dialogo(radice, "codex", [
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "bacheca_pendenti", "arguments": {}}},
            ])
            self.assertEqual(json.loads(risp_codex["result"]["content"][0]["text"])["pendenti"], [])

    def test_bacheca_thread_e_errore_su_thread_assente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, _ = self._radice_con_thread(tmp)
            ok, ko = _dialogo(radice, "claude", [
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                 "params": {"name": "bacheca_thread", "arguments": {"thread_id": "T1"}}},
                {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                 "params": {"name": "bacheca_thread", "arguments": {"thread_id": "ignoto"}}},
            ])
            self.assertFalse(ok["result"]["isError"])
            self.assertEqual(len(json.loads(ok["result"]["content"][0]["text"])["messaggi"]), 1)
            self.assertTrue(ko["result"]["isError"])
            self.assertIn("non trovato", ko["result"]["content"][0]["text"])

    def test_tool_e_metodo_sconosciuti(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, _ = self._radice_con_thread(tmp)
            a, b, c = _dialogo(radice, "claude", [
                {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                 "params": {"name": "inventato", "arguments": {}}},
                {"jsonrpc": "2.0", "id": 7, "method": "metodo/ignoto"},
                {"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                 "params": {"name": "bacheca_thread", "arguments": {}}},
            ])
            self.assertEqual(a["error"]["code"], -32602)
            self.assertEqual(b["error"]["code"], -32601)
            self.assertTrue(c["result"]["isError"])  # thread_id mancante -> _ErroreTool

    def test_riga_non_json_non_ferma_il_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, _ = self._radice_con_thread(tmp)
            entrata = io.StringIO(
                "non-json\n"
                + json.dumps({"jsonrpc": "2.0", "id": 9, "method": "tools/list"}) + "\n"
            )
            uscita = io.StringIO()
            mcp.servi(entrata, uscita, radice, "claude")
            righe = [json.loads(r) for r in uscita.getvalue().splitlines()]
            self.assertEqual(righe[0]["error"]["code"], -32700)
            self.assertIn("tools", righe[1]["result"])

    def test_params_non_oggetto_e_jsonrpc_errato_non_fermano_il_loop(self) -> None:
        """Revisione Codex: `params` stringa (JSON valido ma non oggetto) sollevava
        AttributeError e fermava il loop."""
        with tempfile.TemporaryDirectory() as tmp:
            radice, _ = self._radice_con_thread(tmp)
            a, b, c = _dialogo(radice, "claude", [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": "boh"},
                {"jsonrpc": "1.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
            ])
            self.assertEqual(a["error"]["code"], -32602)
            self.assertEqual(b["error"]["code"], -32600)
            self.assertIn("tools", c["result"])  # il loop e' andato avanti

    def test_ping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, _ = self._radice_con_thread(tmp)
            [risp] = _dialogo(radice, "claude", [
                {"jsonrpc": "2.0", "id": 1, "method": "ping"},
            ])
            self.assertEqual(risp["result"], {})

    def test_protocol_version_negoziata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, _ = self._radice_con_thread(tmp)
            nota, ignota = _dialogo(radice, "claude", [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2024-11-05"}},
                {"jsonrpc": "2.0", "id": 2, "method": "initialize",
                 "params": {"protocolVersion": "3000-01-01"}},
            ])
            self.assertEqual(nota["result"]["protocolVersion"], "2024-11-05")
            self.assertEqual(ignota["result"]["protocolVersion"], mcp._VERSIONI_PROTOCOLLO[0])

    def test_bacheca_thread_limita_i_messaggi(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, primo = self._radice_con_thread(tmp)
            for i in range(5):
                bacheca.aggiungi_messaggio(
                    radice / "dati_locali" / "orchestrazione" / "messaggi.jsonl",
                    bacheca.costruisci_messaggio(
                        mittente="claude", destinatari=["umano"], tipo="risposta",
                        testo=f"r{i}", thread_id="T1", correla_a=primo["id_messaggio"],
                    ),
                )
            [risp] = _dialogo(radice, "claude", [
                {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                 "params": {"name": "bacheca_thread", "arguments": {"thread_id": "T1", "limite": 2}}},
            ])
            payload = json.loads(risp["result"]["content"][0]["text"])
            self.assertEqual(len(payload["messaggi"]), 2)
            self.assertEqual(payload["messaggi_totali"], 6)
            self.assertTrue(payload["troncato"])

    def test_tools_list_include_le_scritture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, _ = self._radice_con_thread(tmp)
            [risp] = _dialogo(radice, "claude", [
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            ])
            nomi = {t["name"] for t in risp["result"]["tools"]}
            self.assertEqual(nomi, {
                "bacheca_pendenti", "bacheca_thread", "piano_stato", "note_codice_elenco",
                "bacheca_rispondi", "bacheca_prendi", "piano_prendi_passo", "piano_offri_passo",
                "piano_approva_handoff", "registro_aggiungi",
            })

    def test_registro_aggiungi_fissa_agente_e_costo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, _ = self._radice_con_thread(tmp)
            [risp] = _dialogo(radice, "codex", [
                {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                    "name": "registro_aggiungi",
                    "arguments": {
                        "id_compito": "mcp-fase2", "tipo_compito": "servizi", "stato": "passato",
                        "esito_gate": "superato", "note": "gate verificato",
                    },
                }},
            ])
            self.assertFalse(risp["result"]["isError"])
            evento = registro.leggi_eventi(radice / "dati_locali" / "orchestrazione" / "eventi.jsonl")[0]
            self.assertEqual(evento["agente"], "codex")
            self.assertEqual(evento["costo_stimato_usd"], 0.0)
            self.assertEqual(evento["esito_gate"], "superato")

    def test_piano_approva_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, msg = self._radice_con_thread(tmp)
            percorso = radice / "dati_locali" / "orchestrazione" / "messaggi.jsonl"
            piano_comandi.crea_passo(
                percorso, piano_id="P", passo_id="s1", descrizione="passo",
                attore="umano", thread_id=msg["thread_id"],
            )
            self.assertEqual(
                piano_comandi.prendi_passo(percorso, msg["thread_id"], "s1", "codex")["esito"],
                "ok",
            )
            self.assertEqual(
                piano_comandi.offri_passo(percorso, msg["thread_id"], "s1", "codex", "gemini")["esito"],
                "ok",
            )
            [risp] = _dialogo(radice, "codex", [
                {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                    "name": "piano_approva_handoff",
                    "arguments": {"thread_id": msg["thread_id"], "passo_id": "s1"},
                }},
            ])
            self.assertEqual(json.loads(risp["result"]["content"][0]["text"])["esito"], "ok")

    def test_bacheca_rispondi_scrive_e_idempotente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, msg = self._radice_con_thread(tmp)
            call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                "name": "bacheca_rispondi",
                "arguments": {"thread_id": "T1", "testo": "ci penso io",
                              "correla_a": msg["id_messaggio"], "idempotency_key": "k1"},
            }}
            ok, replay = _dialogo(radice, "codex", [call, {**call, "id": 2}])
            self.assertEqual(json.loads(ok["result"]["content"][0]["text"])["esito"], "ok")
            self.assertEqual(json.loads(replay["result"]["content"][0]["text"])["esito"], "gia_applicato")
            righe = (radice / "dati_locali" / "orchestrazione" / "messaggi.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(righe), 2)  # richiesta + una sola risposta
            risposta = json.loads(righe[1])
            self.assertEqual(risposta["mittente"], "codex")  # l'agente di avvio del server
            self.assertEqual(risposta["correla_a"], msg["id_messaggio"])

    def test_bacheca_prendi_e_thread_inesistente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, msg = self._radice_con_thread(tmp)
            presa, ko = _dialogo(radice, "gemini", [
                {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                    "name": "bacheca_prendi",
                    "arguments": {"thread_id": "T1", "correla_a": msg["id_messaggio"]},
                }},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                    "name": "bacheca_rispondi", "arguments": {"thread_id": "ignoto", "testo": "x"},
                }},
            ])
            self.assertEqual(json.loads(presa["result"]["content"][0]["text"])["esito"], "ok")
            self.assertEqual(
                json.loads(ko["result"]["content"][0]["text"])["esito"], "thread_inesistente",
            )

    def test_smoke_subprocess_stdio(self) -> None:
        """Il server avviato come processo reale risponde a initialize + tools/list
        + tools/call su stdio (contratto dichiarato nella RFC)."""
        with tempfile.TemporaryDirectory() as tmp:
            radice, _ = self._radice_con_thread(tmp)
            richieste = "\n".join(json.dumps(r) for r in [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2025-06-18"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "bacheca_pendenti", "arguments": {}}},
            ]) + "\n"
            res = subprocess.run(
                [sys.executable, "mcp_orchestratore.py", "--radice", str(radice), "--agente", "claude"],
                input=richieste, capture_output=True, text=True, timeout=30,
                cwd=str(Path(__file__).resolve().parent.parent),
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            righe = [json.loads(r) for r in res.stdout.splitlines() if r.strip()]
            self.assertEqual(righe[0]["result"]["serverInfo"]["name"], "orchestratore-locale")
            self.assertEqual({t["name"] for t in righe[1]["result"]["tools"]}, {
                "bacheca_pendenti", "bacheca_thread", "piano_stato", "note_codice_elenco",
                "bacheca_rispondi", "bacheca_prendi", "piano_prendi_passo", "piano_offri_passo",
                "piano_approva_handoff", "registro_aggiungi",
            })
            self.assertFalse(righe[2]["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
