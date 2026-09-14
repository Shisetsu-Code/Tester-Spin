from __future__ import annotations

from tkinter import messagebox, ttk

from tester_spin.app_assisted import AssistedTesterSpinApp
from tester_spin.app_har import _find_button_by_text
from tester_spin.providers.bgaming.complexity import (
    AUTO_COMPLETE,
    INDETERMINATE,
    MANUAL_RESOLVED,
    REVIEW_REQUIRED,
    load_complexity,
)


class ReviewTesterSpinApp(AssistedTesterSpinApp):
    def _build(self) -> None:
        super()._build()
        anchor = _find_button_by_text(self, "RESOLVER ASISTIDO")
        if anchor is None:
            return
        self.review_btn = ttk.Button(
            anchor.master,
            text="SIGUIENTE REVISIÓN (0)",
            command=self._select_next_review,
        )
        self.review_btn.pack(side="left", padx=(8, 0))
        try:
            self.tree.column("status", width=155, minwidth=125, anchor="center")
        except Exception:
            pass

    def _set_busy(self, busy: bool) -> None:
        super()._set_busy(busy)
        if hasattr(self, "review_btn"):
            self.review_btn.configure(state="disabled" if busy else "normal")

    def _complexity(self, game):
        try:
            provider = self.registry.get(game.provider)
            if provider.key != "bgaming":
                return {}
            return load_complexity(provider.game_dir(game))
        except Exception:
            return {}

    def _review_iids(self) -> list[str]:
        return [
            iid
            for iid, game in self._games.items()
            if bool(self._complexity(game).get("requires_review"))
        ]

    def _decorate_complexity(self) -> None:
        review_count = 0
        for iid, game in self._games.items():
            if not self.tree.exists(iid):
                continue
            payload = self._complexity(game)
            classification = str(payload.get("classification") or "")
            suffix = ""
            if classification == AUTO_COMPLETE:
                suffix = "AUTO"
            elif classification == REVIEW_REQUIRED:
                suffix = "REVISIÓN"
                review_count += 1
            elif classification == MANUAL_RESOLVED:
                suffix = "MANUAL"
            elif classification == INDETERMINATE:
                suffix = "?"
            values = list(self.tree.item(iid, "values"))
            if len(values) >= 3:
                base = str(game.last_status or "PENDIENTE")
                values[2] = f"{base} · {suffix}" if suffix else base
                self.tree.item(iid, values=values)
        if hasattr(self, "review_btn"):
            self.review_btn.configure(text=f"SIGUIENTE REVISIÓN ({review_count})")

    def _refresh_games(self) -> None:
        super()._refresh_games()
        self._decorate_complexity()

    def _show_selected_game(self) -> None:
        super()._show_selected_game()
        selection = self.tree.selection()
        if not selection:
            return
        game = self._games.get(selection[0])
        if game is None or game.provider != "bgaming":
            return
        payload = self._complexity(game)
        if not payload:
            return
        reasons = payload.get("reasons") or []
        reason_text = "\n".join(
            f"- {row.get('kind')}: {row.get('value')}"
            for row in reasons[:12]
            if isinstance(row, dict)
        ) or "- sin ramas complejas detectadas"
        extra = (
            "\n\nClasificación BGaming:\n"
            f"{payload.get('classification') or '—'}\n"
            f"Requiere revisión: {'sí' if payload.get('requires_review') else 'no'}\n"
            f"Motivos:\n{reason_text}"
        )
        try:
            self.detail_text.configure(state="normal")
            self.detail_text.insert("end", extra)
            self.detail_text.configure(state="disabled")
        except Exception:
            pass

    def _select_next_review(self) -> None:
        if self._provider().key != "bgaming":
            messagebox.showinfo("Tester-Spin", "La cola de revisión actual es específica de BGaming.")
            return
        rows = self._review_iids()
        if not rows:
            messagebox.showinfo("Tester-Spin", "No hay juegos BGaming pendientes de revisión manual.")
            return
        current = list(self.tree.selection())
        index = 0
        if current and current[0] in rows:
            index = (rows.index(current[0]) + 1) % len(rows)
        iid = rows[index]
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        self.tree.see(iid)
        self._show_selected_game()


def main() -> None:
    ReviewTesterSpinApp().mainloop()


__all__ = ["ReviewTesterSpinApp", "main"]
