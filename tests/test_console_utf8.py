#!/usr/bin/env python3
"""Test per console_utf8.forza_console_utf8."""
from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

import console_utf8


class _FlussoFinto:
    def __init__(self, *, con_reconfigure: bool, errore: Exception | None = None) -> None:
        self.chiamate: list[dict] = []
        self._errore = errore
        if con_reconfigure:
            self.reconfigure = self._reconfigure  # type: ignore[method-assign]

    def _reconfigure(self, **kw: object) -> None:
        self.chiamate.append(kw)
        if self._errore is not None:
            raise self._errore


class ForzaConsoleUtf8Test(unittest.TestCase):
    def test_riconfigura_stdout_e_stderr_non_stdin_per_default(self) -> None:
        out = _FlussoFinto(con_reconfigure=True)
        err = _FlussoFinto(con_reconfigure=True)
        inp = _FlussoFinto(con_reconfigure=True)
        with patch.object(sys, "stdout", out), patch.object(sys, "stderr", err), \
             patch.object(sys, "stdin", inp):
            console_utf8.forza_console_utf8()
        self.assertEqual(out.chiamate, [{"encoding": "utf-8", "errors": "replace"}])
        self.assertEqual(err.chiamate, [{"encoding": "utf-8", "errors": "replace"}])
        self.assertEqual(inp.chiamate, [])

    def test_anche_stdin(self) -> None:
        inp = _FlussoFinto(con_reconfigure=True)
        with patch.object(sys, "stdout", _FlussoFinto(con_reconfigure=True)), \
             patch.object(sys, "stderr", _FlussoFinto(con_reconfigure=True)), \
             patch.object(sys, "stdin", inp):
            console_utf8.forza_console_utf8(anche_stdin=True)
        self.assertEqual(inp.chiamate, [{"encoding": "utf-8", "errors": "replace"}])

    def test_flusso_senza_reconfigure_non_solleva(self) -> None:
        with patch.object(sys, "stdout", _FlussoFinto(con_reconfigure=False)), \
             patch.object(sys, "stderr", _FlussoFinto(con_reconfigure=False)):
            console_utf8.forza_console_utf8()  # nessuna eccezione

    def test_errore_di_reconfigure_viene_ingoiato(self) -> None:
        out = _FlussoFinto(con_reconfigure=True, errore=ValueError("stream staccato"))
        with patch.object(sys, "stdout", out), \
             patch.object(sys, "stderr", _FlussoFinto(con_reconfigure=False)):
            console_utf8.forza_console_utf8()  # ValueError ingoiato


if __name__ == "__main__":
    unittest.main()
