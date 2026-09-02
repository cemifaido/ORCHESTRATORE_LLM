from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

import bacheca
import mcp_orchestratore as mcp


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

    def test_tools_list_elenca_i_quattro_tool_mvp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice, _ = self._radice_con_thread(tmp)
            [risp] = _dialogo(radice, "claude", [
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            ])
            nomi = {t["name"] for t in risp["result"]["tools"]}
            self.assertEqual(
                nomi, {"bacheca_pendenti", "bacheca_thread", "piano_stato", "note_codice_elenco"},
            )
            for t in risp["result"]["tools"]:
                self.assertIn("DATO", t["description"])  # marcato non fidato

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


if __name__ == "__main__":
    unittest.main()
