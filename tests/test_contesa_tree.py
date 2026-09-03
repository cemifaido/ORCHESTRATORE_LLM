#!/usr/bin/env python3
"""Test per contesa_tree (80% leggero di Slice C)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import contesa_tree


def _git(stdout: str, returncode: int = 0) -> MagicMock:
    return MagicMock(return_value=MagicMock(stdout=stdout, returncode=returncode))


class FileNonCommittatiTest(unittest.TestCase):
    def test_parsa_porcelain_z(self) -> None:
        # --porcelain=v1 -z: record separati da NUL; il rename porta due path
        out = " M src/a.py\x00?? nuovo.py\x00A  tests/b.py\x00R  src/c.py\x00vecchio.py\x00"
        got = contesa_tree.file_non_committati(Path("."), esegui=_git(out))
        self.assertEqual(got, ["nuovo.py", "src/a.py", "src/c.py", "tests/b.py", "vecchio.py"])

    def test_path_con_spazi_e_freccia_letterale(self) -> None:
        # con -z i path sono letterali: ' -> ' dentro un nome non e' un rename
        out = " M src/a -> b.py\x00"
        got = contesa_tree.file_non_committati(Path("."), esegui=_git(out))
        self.assertEqual(got, ["src/a -> b.py"])

    def test_none_se_git_fallisce(self) -> None:
        self.assertIsNone(contesa_tree.file_non_committati(Path("."), esegui=_git("", 128)))

    def test_none_se_git_non_invocabile(self) -> None:
        boom = MagicMock(side_effect=FileNotFoundError("git"))
        self.assertIsNone(contesa_tree.file_non_committati(Path("."), esegui=boom))


class ValutaContesaTest(unittest.TestCase):
    def test_write_set_vuoto_e_libero(self) -> None:
        v = contesa_tree.valuta_contesa(Path("."), [], esegui=_git(" M x.py\n"))
        self.assertEqual(v["esito"], contesa_tree.LIBERO)

    def test_git_non_verificabile_non_blocca(self) -> None:
        v = contesa_tree.valuta_contesa(Path("."), ["src/a.py"], esegui=_git("", 128))
        self.assertEqual(v["esito"], contesa_tree.NON_VERIFICABILE)

    def test_tree_pulito_e_libero(self) -> None:
        v = contesa_tree.valuta_contesa(Path("."), ["src/a.py"], esegui=_git(""))
        self.assertEqual(v["esito"], contesa_tree.LIBERO)

    def test_sporco_ma_disgiunto_e_libero(self) -> None:
        v = contesa_tree.valuta_contesa(
            Path("."), ["src/a.py"], esegui=_git(" M docs/altro.md\n?? note.txt\n"))
        self.assertEqual(v["esito"], contesa_tree.LIBERO)

    def test_sovrapposizione_e_conteso(self) -> None:
        v = contesa_tree.valuta_contesa(
            Path("."), ["src/a.py", "tests/**"],
            esegui=_git(" M src/a.py\x00 M docs/x.md\x00?? tests/test_a.py\x00"))
        self.assertEqual(v["esito"], contesa_tree.CONTESO)
        self.assertEqual(set(v["file"]), {"src/a.py", "tests/test_a.py"})
        self.assertEqual(v["totale"], 2)

    def test_lista_file_limitata(self) -> None:
        sporchi = "".join(f" M src/f{i}.py\x00" for i in range(30))
        v = contesa_tree.valuta_contesa(Path("."), ["src/**"], esegui=_git(sporchi))
        self.assertEqual(v["esito"], contesa_tree.CONTESO)
        self.assertEqual(v["totale"], 30)
        self.assertEqual(len(v["file"]), contesa_tree._MAX_FILE_ELENCATI)


class RegistraContesaTest(unittest.TestCase):
    def test_append_su_contese_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            (radice / "dati_locali" / "orchestrazione").mkdir(parents=True)
            contesa_tree.registra_contesa(
                radice, agente="codex", thread_id="t1",
                write_set=["src/a.py"], file_contesi=["src/a.py"],
            )
            righe = (radice / "dati_locali" / "orchestrazione" / "contese.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(righe), 1)
            rec = json.loads(righe[0])
            self.assertEqual(rec["agente"], "codex")
            self.assertEqual(rec["file_contesi"], ["src/a.py"])

    def test_totale_reale_nel_jsonl_anche_con_lista_troncata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            radice = Path(tmp)
            (radice / "dati_locali" / "orchestrazione").mkdir(parents=True)
            troncata = [f"src/f{i}.py" for i in range(contesa_tree._MAX_FILE_ELENCATI)]
            contesa_tree.registra_contesa(
                radice, agente="codex", thread_id="t1",
                write_set=["src/**"], file_contesi=troncata, totale=42,
            )
            rec = json.loads(
                (radice / "dati_locali" / "orchestrazione" / "contese.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()[0]
            )
            self.assertEqual(len(rec["file_contesi"]), contesa_tree._MAX_FILE_ELENCATI)
            self.assertEqual(rec["file_contesi_totale"], 42)


if __name__ == "__main__":
    unittest.main()
