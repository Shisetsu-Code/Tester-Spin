from __future__ import annotations

from tkinter import ttk

from tester_spin.app_har import HARToolTesterSpinApp, _find_button_by_text


class AssistedTesterSpinApp(HARToolTesterSpinApp):
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


__all__ = ["AssistedTesterSpinApp"]
