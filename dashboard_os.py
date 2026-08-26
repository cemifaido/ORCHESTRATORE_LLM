#!/usr/bin/env python3
"""Adapter di sistema operativo per la Dashboard (Lotto E).

Centralizza le interazioni a basso livello con Windows e il runtime:
- Verifica PID vivi via Windows API (Kernel32) o segnali POSIX
- Discovery delle sessioni Claude attive in ~/.claude/sessions
- Manipolazione appunti (PowerShell su Windows)
- Protocol handler antigravity-ide:// e avvio processi staccati
- Invocazione subprocess per sentinella.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def pid_vivo(pid: Any) -> bool:
    """True se esiste un processo vivo con questo pid.

    Su Windows NON si puo' usare os.kill(pid, 0): viene tradotto in TerminateProcess.
    Si usa OpenProcess + GetExitCodeProcess.
    """
    if not isinstance(pid, int) or pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            codice = ctypes.c_ulong(0)
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(codice))
            return bool(ok) and codice.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def trova_ultima_sessione_claude(percorso_progetto: Path) -> str | None:
    """Cerca tra le sessioni di Claude memorizzate in ~/.claude/sessions
    quella associata a questo progetto il cui processo e' ancora vivo."""
    dir_sessioni = Path.home() / ".claude" / "sessions"
    if not dir_sessioni.exists():
        return None
    sessioni = []
    for f in dir_sessioni.glob("*.json"):
        try:
            dati = json.loads(f.read_text(encoding="utf-8"))
            cwd_sessione = Path(dati.get("cwd", ""))
            if cwd_sessione.resolve() != percorso_progetto.resolve():
                continue
            if not pid_vivo(dati.get("pid")):
                continue
            sessioni.append((dati.get("startedAt", 0), dati.get("sessionId")))
        except Exception:
            pass
    if not sessioni:
        return None
    sessioni.sort(reverse=True)
    return sessioni[0][1]


def copia_negli_appunti(testo: str) -> None:
    """Copia il testo negli appunti di sistema (PowerShell su Windows)."""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"],
        input=testo,
        text=True,
        check=True,
    )


def lancia_ide_uri(uri: str) -> None:
    """Invoca Antigravity IDE per aprire un URI o portare a fuoco l'editor."""
    antigravity_cmd = os.path.expandvars(
        r"%LOCALAPPDATA%\Programs\Antigravity IDE\bin\antigravity-ide.cmd"
    )
    subprocess.Popen([antigravity_cmd, "--open-url", uri])


def avvia_processo_sostituto(script_interfaccia: Path, radice: Path) -> None:
    """Avvia una nuova istanza staccata dell'interfaccia prima di terminare quella corrente."""
    kwargs: dict[str, Any] = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([sys.executable, str(script_interfaccia)], cwd=str(radice), env=os.environ.copy(), **kwargs)


def interpreta_output_sentinella(output_std: str, output_err: str = "") -> dict:
    """Decodifica l'output JSON completo stampato da sentinella.py."""
    try:
        return json.loads(output_std.strip())
    except Exception:
        return {"output": output_std, "stderr": output_err}


def esegui_sentinella_subprocess(
    script_sentinella: Path,
    comando: str,
    percorso_comandi: Path,
    percorso_registro: Path,
    cwd_path: Path,
    timeout_secondi: int = 180,
) -> tuple[int, dict]:
    """Esegue sentinella.py in un processo figlio e ne restituisce il codice di uscita e i dati decodificati."""
    completato = subprocess.run(
        [
            sys.executable,
            str(script_sentinella),
            comando,
            "--config", str(percorso_comandi),
            "--registro", str(percorso_registro),
            "--triage-locale",
        ],
        cwd=cwd_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_secondi,
        shell=False,
    )
    dati = interpreta_output_sentinella(completato.stdout or "", completato.stderr or "")
    return completato.returncode, dati
