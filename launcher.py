from __future__ import annotations

import os
import subprocess
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path

from tester_spin.updater import Updater


def _launcher_name() -> str:
    return str(os.environ.get("TESTER_SPIN_LAUNCHER_NAME") or "Tester-Spin").strip() or "Tester-Spin"


def _entrypoint_name() -> str:
    raw = str(os.environ.get("TESTER_SPIN_LAUNCH_ENTRYPOINT") or "run.py").strip()
    if not raw or Path(raw).name != raw or not raw.lower().endswith(".py"):
        return "run.py"
    return raw


def _home_override() -> Path | None:
    raw = str(os.environ.get("TESTER_SPIN_LAUNCH_HOME") or "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def _data_override() -> Path | None:
    raw = str(os.environ.get("TESTER_SPIN_LAUNCH_DATA_DIR") or "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def _message_box(title: str, message: str, *, error: bool = False) -> None:
    if os.name == "nt":
        try:
            import ctypes

            flags = 0x10 if error else 0x40
            ctypes.windll.user32.MessageBoxW(None, message, title, flags)
            return
        except Exception:
            pass
    stream = sys.stderr if error else sys.stdout
    print(f"{title}: {message}", file=stream)


class Splash:
    def __init__(self) -> None:
        self.root = None
        self.label = None
        name = _launcher_name()
        try:
            import tkinter as tk
            from tkinter import ttk

            root = tk.Tk()
            root.title(name)
            root.geometry("470x130")
            root.resizable(False, False)
            root.attributes("-topmost", True)
            frame = ttk.Frame(root, padding=18)
            frame.pack(fill="both", expand=True)
            ttk.Label(frame, text=name, font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
            label = ttk.Label(frame, text="Iniciando...", wraplength=430)
            label.pack(anchor="w", pady=(12, 0))
            root.update_idletasks()
            root.update()
            self.root = root
            self.label = label
        except Exception:
            self.root = None
            self.label = None

    def set(self, message: str) -> None:
        if self.root is None or self.label is None:
            return
        try:
            self.label.configure(text=message)
            self.root.update_idletasks()
            self.root.update()
        except Exception:
            self.root = None
            self.label = None

    def close(self) -> None:
        if self.root is not None:
            try:
                self.root.destroy()
            except Exception:
                pass
        self.root = None
        self.label = None


def _tail(path, max_chars: int = 5000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[-max_chars:].strip()
    except Exception:
        return ""


def main() -> int:
    name = _launcher_name()
    splash = Splash()
    try:
        updater = Updater(home=_home_override())
        data_override = _data_override()
        if data_override is not None:
            updater.config.data_dir = str(data_override)
            updater._write_json_atomic(updater.config_path, asdict(updater.config))

        app_dir = updater.prepare_runtime(splash.set)
        python_exe, env = updater.ensure_environment(app_dir, splash.set)
        entrypoint = app_dir / _entrypoint_name()
        if not entrypoint.exists():
            raise RuntimeError(f"no existe {entrypoint}")

        if '--providers' in sys.argv:
            from tester_spin.runtime_entry import cli_command
            command, console_env = cli_command(python_exe, app_dir, env, [])
            # Start the menu from the active runtime, with a visible terminal.
            command = command[:1] + ['-m', 'tester_spin.provider_menu']
            subprocess.Popen(command, cwd=str(app_dir), env=console_env,
                creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
            splash.close()
            return 0

        splash.set(f"Abriendo {name}...")
        startup_log = updater.home / "app-startup.log"
        startup_log.parent.mkdir(parents=True, exist_ok=True)
        with startup_log.open("w", encoding="utf-8", errors="replace") as log:
            process = subprocess.Popen(
                [str(python_exe), str(entrypoint)],
                cwd=str(updater.data_dir.parent),
                env=env,
                stdout=log,
                stderr=log,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                code = process.poll()
                if code is not None:
                    log.flush()
                    runtime_error = updater.home / "app-startup-error.log"
                    detail = _tail(runtime_error) or _tail(startup_log)
                    if not detail:
                        detail = f"El proceso terminó inmediatamente con código {code}."
                    raise RuntimeError(
                        f"{name} se cerró durante el inicio (código {code}).\n\n"
                        f"{detail}\n\n"
                        f"Diagnóstico: {startup_log}"
                    )
                time.sleep(0.1)

        splash.close()
        return 0
    except Exception as exc:
        splash.close()
        detail = f"{type(exc).__name__}: {exc}"
        log_path = None
        try:
            updater = locals().get("updater")
            if updater is not None:
                log_path = updater.home / "launcher-error.log"
                log_path.write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        if log_path:
            detail += f"\n\nDiagnóstico: {log_path}"
        _message_box(f"{name} - Error de inicio", detail, error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
