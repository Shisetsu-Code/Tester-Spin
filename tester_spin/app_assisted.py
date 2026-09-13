from __future__ import annotations

import queue
import threading

from tkinter import messagebox, ttk

from tester_spin.app_har import HARToolTesterSpinApp, _find_button_by_text


class AssistedTesterSpinApp(HARToolTesterSpinApp):
    def __init__(self) -> None:
        self._assisted_active = False
        super().__init__()

    def _build(self) -> None:
        super()._build()
        anchor = _find_button_by_text(self, "ANALIZAR FORMATO")
        if anchor is None:
            return
        self.assisted_btn = ttk.Button(
            anchor.master,
            text="RESOLVER ASISTIDO",
            command=self._resolve_assisted_selected,
        )
        self.assisted_btn.pack(side="left", padx=(8, 0))

    def _set_busy(self, busy: bool) -> None:
        super()._set_busy(busy)
        if hasattr(self, "assisted_btn"):
            self.assisted_btn.configure(state="disabled" if busy else "normal")

    def _resolve_assisted_selected(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        games = self._selected_games()
        if len(games) != 1:
            messagebox.showinfo(
                "Tester-Spin",
                "Seleccioná exactamente un juego para la resolución asistida.",
            )
            return
        game = games[0]
        provider = self._provider()
        if provider.key != "bgaming":
            messagebox.showinfo(
                "Tester-Spin",
                "Resolución Asistida está aislada por proveedor; por ahora sólo BGaming la utiliza.",
            )
            return
        try:
            timeout_s = max(8.0, float(self.timeout_var.get()))
        except ValueError:
            messagebox.showerror("Tester-Spin", "Timeout debe ser numérico.")
            return

        self._stop_event = threading.Event()
        self._assisted_active = True
        self._set_busy(True)
        self.status_var.set(f"Resolución asistida: {game.name}")
        self.progress.stop()
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self._append_log(
            f"=== RESOLUCIÓN ASISTIDA BGAMING: {game.name}; análisis automático primero ==="
        )
        self._append_log(
            "Si quedan campos unresolved se abrirá Chromium visible. Probá todas las opciones "
            "y cerrá la ventana cuando termines. DETENER cancela sin promover una captura parcial."
        )

        def worker() -> None:
            from tester_spin.providers.bgaming.assisted_resolution import resolve_game_assisted

            try:
                result = resolve_game_assisted(
                    provider,
                    game,
                    timeout_s=timeout_s,
                    stop_event=self._stop_event,
                    progress=lambda message: self._events.put(("log", message)),
                )
                self._events.put(("assisted_result", (game, result)))
                self._events.put(("assisted_done", None))
            except Exception as exc:
                self._events.put(
                    ("assisted_error", f"Resolución Asistida: {type(exc).__name__}: {exc}")
                )

        self._worker = threading.Thread(
            target=worker,
            daemon=True,
            name="bgaming-assisted-resolution",
        )
        self._worker.start()

    def _drain_events(self) -> None:
        deferred: list[tuple[str, object]] = []
        while True:
            try:
                kind, value = self._events.get_nowait()
            except queue.Empty:
                break
            if self._assisted_active and kind == "log":
                self._append_log(str(value))
            elif kind == "assisted_result":
                game, result = value  # type: ignore[misc]
                self._append_log(
                    f"[{game.name}] ASISTIDO {result.status}: targets={result.targets}, "
                    f"capturas={result.captures}, campos_resueltos={result.resolved_fields}, "
                    f"completed={result.completed}; artifact={result.artifact}"
                )
            elif kind == "assisted_done":
                self._assisted_active = False
                self._set_busy(False)
                self.progress.stop()
                self.progress.configure(mode="determinate", value=0)
                self.status_var.set("Resolución asistida terminada")
                self._append_log("=== RESOLUCIÓN ASISTIDA FIN ===")
            elif kind == "assisted_error":
                self._assisted_active = False
                self._set_busy(False)
                self.progress.stop()
                self.progress.configure(mode="determinate", value=0)
                self.status_var.set("Error en resolución asistida")
                self._append_log(str(value))
                messagebox.showerror("Tester-Spin", str(value))
            else:
                deferred.append((kind, value))
        for event in deferred:
            self._events.put(event)
        super()._drain_events()


def main() -> None:
    app = AssistedTesterSpinApp()
    app.mainloop()


__all__ = ["AssistedTesterSpinApp", "main"]
