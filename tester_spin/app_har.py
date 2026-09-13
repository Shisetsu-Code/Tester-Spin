from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from tkinter import messagebox, ttk

from tester_spin.app_current import CurrentTesterSpinApp
from tester_spin.models import Game
from tester_spin.providers import RedTigerProvider, RubyPlayProvider


def _open_directory(path: Path) -> None:
    target = str(Path(path).resolve())
    if os.name == "nt":
        os.startfile(target)  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", target])
        return
    subprocess.Popen(["xdg-open", target])


def _find_button_by_text(root: Any, text: str):
    for child in root.winfo_children():
        try:
            if isinstance(child, ttk.Button) and str(child.cget("text")) == text:
                return child
        except Exception:
            pass
        found = _find_button_by_text(child, text)
        if found is not None:
            return found
    return None


class HARToolTesterSpinApp(CurrentTesterSpinApp):
    """Current GUI plus HAR diagnostics and isolated UI-first discovery."""

    def __init__(self) -> None:
        self._ui_first_total = 0
        self._ui_first_done = 0
        super().__init__()
        # run.py enters through this application layer. New providers are only
        # registered here; their protocol implementations remain isolated under
        # providers/<name>/ and GUI/scheduler/storage stay protocol-neutral.
        for provider in (
            RubyPlayProvider(self.data_root),
            RedTigerProvider(self.data_root),
        ):
            self.registry.register(provider)
            self._display_to_key[provider.display_name] = provider.key
        self.provider_combo.configure(values=list(self._display_to_key))

    def _build(self) -> None:
        super()._build()

        folder_button = _find_button_by_text(self, "Abrir carpeta")
        if folder_button is None:
            return

        self.open_har_folder_btn = ttk.Button(
            folder_button.master,
            text="Abrir carpeta HAR",
            command=self._open_selected_har_folder,
        )
        self.open_har_folder_btn.pack(side="left", padx=(8, 0))

        self.ui_first_btn = ttk.Button(
            folder_button.master,
            text="UI FIRST: DESCUBRIR",
            command=self._ui_first_selected,
        )
        self.ui_first_btn.pack(side="left", padx=(8, 0))

    def _set_busy(self, busy: bool) -> None:
        super()._set_busy(busy)
        if hasattr(self, "ui_first_btn"):
            self.ui_first_btn.configure(state="disabled" if busy else "normal")
        if hasattr(self, "open_har_folder_btn"):
            self.open_har_folder_btn.configure(state="disabled" if busy else "normal")

    def _selected_games(self) -> list[Game]:
        return [self._games[iid] for iid in self.tree.selection() if iid in self._games]

    def _selected_game_for_har(self) -> Game | None:
        selection = list(self.tree.selection())
        if not selection:
            return None
        focused = str(self.tree.focus() or "")
        iid = focused if focused in selection else selection[0]
        return self._games.get(iid)

    def _ui_first_selected(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        games = self._selected_games()
        if not games:
            messagebox.showinfo("Tester-Spin", "Seleccioná al menos un juego para UI First.")
            return
        provider = self._provider()
        if provider.key != "bgaming":
            messagebox.showinfo(
                "Tester-Spin",
                "UI First está aislado por proveedor. En esta iteración sólo BGaming tiene adaptador UI First.",
            )
            return
        try:
            timeout_s = max(8.0, float(self.timeout_var.get()))
        except ValueError:
            messagebox.showerror("Tester-Spin", "Timeout debe ser numérico.")
            return

        self._stop_event = threading.Event()
        self._ui_first_total = len(games)
        self._ui_first_done = 0
        self._set_busy(True)
        self.status_var.set(f"UI First 0/{len(games)}...")
        self.progress.stop()
        self.progress.configure(mode="determinate", maximum=max(1, len(games)), value=0)
        self._append_log(
            f"=== UI FIRST: proveedor=BGaming, juegos={len(games)}, modo separado del farming HTTP ==="
        )

        def worker() -> None:
            from tester_spin.providers.bgaming.ui_first import discover_game_ui_first

            try:
                for game in games:
                    if self._stop_event.is_set():
                        break
                    result = discover_game_ui_first(
                        provider,
                        game,
                        timeout_s=timeout_s,
                        stop_event=self._stop_event,
                        progress=lambda message: self._events.put(("log", message)),
                    )
                    self._events.put(("ui_first_result", (game, result)))
                self._events.put(("ui_first_done", None))
            except Exception as exc:
                self._events.put(("error", f"UI First: {type(exc).__name__}: {exc}"))

        self._worker = threading.Thread(target=worker, daemon=True, name="bgaming-ui-first")
        self._worker.start()

    def _drain_events(self) -> None:
        deferred: list[tuple[str, object]] = []
        while True:
            try:
                kind, value = self._events.get_nowait()
            except queue.Empty:
                break
            if kind == "ui_first_result":
                game, result = value  # type: ignore[misc]
                self._ui_first_done += 1
                self.progress.configure(value=self._ui_first_done)
                self.status_var.set(f"UI First {self._ui_first_done}/{self._ui_first_total}...")
                self._append_log(
                    f"[{game.name}] UI FIRST {result.status}: states={result.states}, "
                    f"actions={result.actions}, unresolved={result.unresolved}, "
                    f"ready_for_farming={result.ready_for_farming}"
                )
            elif kind == "ui_first_done":
                self._set_busy(False)
                self.progress.configure(value=self._ui_first_done)
                self.status_var.set(
                    f"UI First terminado: {self._ui_first_done}/{self._ui_first_total}"
                )
                self._append_log(
                    "=== UI FIRST FIN: el modo HTTP/exhaustive no fue ejecutado ni modificado ==="
                )
            else:
                deferred.append((kind, value))
        for event in deferred:
            self._events.put(event)
        super()._drain_events()

    def _open_selected_har_folder(self) -> None:
        game = self._selected_game_for_har()
        if game is None:
            messagebox.showinfo(
                "Tester-Spin",
                "Seleccioná un juego para abrir su carpeta HAR.",
            )
            return

        try:
            provider = self.registry.get(game.provider)
            folder = provider.har_artifact_dir(game)
        except Exception as exc:
            self._append_log(
                f"[{game.name}] carpeta HAR ERROR: {type(exc).__name__}: {exc}"
            )
            messagebox.showerror(
                "Tester-Spin",
                f"No se pudo localizar la carpeta HAR.\n\n{type(exc).__name__}: {exc}",
            )
            return

        if folder is None or not Path(folder).is_dir():
            messagebox.showinfo(
                "Tester-Spin",
                (
                    "Este juego todavía no tiene un HAR ni un directorio de "
                    "diagnóstico preparado. Ejecutá la prueba una vez para que "
                    "la suite intente capturarlo."
                ),
            )
            return

        try:
            _open_directory(Path(folder))
            self._append_log(f"[{game.name}] abriendo carpeta HAR: {folder}")
        except Exception as exc:
            self._append_log(
                f"[{game.name}] abrir carpeta HAR ERROR: {type(exc).__name__}: {exc}"
            )
            messagebox.showerror(
                "Tester-Spin",
                f"No se pudo abrir la carpeta.\n\n{type(exc).__name__}: {exc}",
            )


def main() -> None:
    app = HARToolTesterSpinApp()
    app.mainloop()


__all__ = ["HARToolTesterSpinApp", "main"]
