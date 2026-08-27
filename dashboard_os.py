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
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


NOME_STATO_RIAVVIO = "dashboard_riavvio.json"
NOME_LOG_RIAVVIO = "dashboard_riavvio.log"


def _percorso_stato_riavvio(radice: Path) -> Path:
    return radice / "dati_locali" / "orchestrazione" / NOME_STATO_RIAVVIO


def _adesso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scrivi_stato_riavvio(radice: Path, stato: dict[str, Any]) -> None:
    """Stato atomico, leggibile anche dopo l'uscita del processo precedente."""
    percorso = _percorso_stato_riavvio(radice)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=percorso.parent, delete=False) as file:
        json.dump(stato, file, ensure_ascii=False, sort_keys=True)
        file.write("\n")
        temporaneo = Path(file.name)
    os.replace(temporaneo, percorso)


def leggi_stato_riavvio(radice: Path) -> dict[str, Any] | None:
    try:
        stato = json.loads(_percorso_stato_riavvio(radice).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return stato if isinstance(stato, dict) else None


def richiedi_riavvio(radice: Path) -> dict[str, Any]:
    stato = {"id": str(uuid.uuid4()), "stato": "richiesto", "aggiornato_utc": _adesso_utc()}
    _scrivi_stato_riavvio(radice, stato)
    return stato


def registra_dashboard_pronto(radice: Path) -> None:
    """Il nuovo processo scrive readiness solo dopo l'avvio di FastAPI."""
    precedente = leggi_stato_riavvio(radice) or {}
    _scrivi_stato_riavvio(radice, {
        "id": precedente.get("id"), "stato": "pronto", "pid": os.getpid(), "aggiornato_utc": _adesso_utc(),
    })


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


def avvia_processo_sostituto(script_interfaccia: Path, radice: Path) -> int:
    """Avvia l'istanza sostituta e conserva l'output locale per diagnosticarla."""
    percorso_log = radice / "dati_locali" / "orchestrazione" / NOME_LOG_RIAVVIO
    percorso_log.parent.mkdir(parents=True, exist_ok=True)
    stato_precedente = leggi_stato_riavvio(radice) or {}
    # Va scritto PRIMA della Popen: il figlio puo' raggiungere lo startup prima
    # che questa funzione torni. Scrivere dopo sovrascriverebbe il suo "pronto".
    _scrivi_stato_riavvio(radice, {**stato_precedente, "stato": "processo_avviato", "aggiornato_utc": _adesso_utc()})
    kwargs: dict[str, Any] = {"stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    with percorso_log.open("a", encoding="utf-8") as log:
        log.write(f"{_adesso_utc()} avvio processo sostituto\n")
        kwargs["stdout"] = log
        kwargs["stderr"] = subprocess.STDOUT
        try:
            processo = subprocess.Popen(
                [sys.executable, str(script_interfaccia)], cwd=str(radice), env=os.environ.copy(), **kwargs
            )
        except OSError:
            _scrivi_stato_riavvio(radice, {**stato_precedente, "stato": "errore_avvio", "aggiornato_utc": _adesso_utc()})
            raise
        log.write(f"{_adesso_utc()} processo sostituto pid={processo.pid}\n")
    return processo.pid


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
