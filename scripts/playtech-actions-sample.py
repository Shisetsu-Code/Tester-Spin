"""Run an explicit official demo sample through the normal isolated CLI."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from tester_spin.models import Game
from tester_spin.providers.catalogs.adapter import validate_rows
from tester_spin.run_result_publisher import _public_value
from tester_spin.storage import Storage


def write_report(path, value):
    safe = _public_value(value)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return safe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", nargs="+", required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--spins", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--wall-timeout", type=int, default=240)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if min(args.spins, args.timeout, args.wall_timeout) < 1:
        parser.error("Los límites deben ser positivos")
    os.environ["TESTER_SPIN_PUBLISH_RESULTS"] = "0"
    args.data_root = args.data_root.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.data_root.mkdir(parents=True, exist_ok=True)
    snapshot = Path(__file__).resolve().parents[1] / "tester_spin/providers/catalogs/snapshots/playtech.json"
    rows = validate_rows("playtech", json.loads(snapshot.read_text(encoding="utf-8"))["games"])
    by_code = {row["symbol"]: row for row in rows if row.get("game_kind") == "slot"}
    codes = list(dict.fromkeys(args.games))
    if set(codes) - by_code.keys():
        parser.error("Hay códigos fuera del catálogo oficial de slots incluido")
    storage = Storage(args.data_root / "tester-spin.sqlite3")
    if storage.latest_results("playtech"):
        parser.error("La muestra requiere una carpeta de datos nueva")
    games = [Game("playtech", by_code[code]["slug"], by_code[code]["name"],
                  by_code[code]["url"], symbol=code) for code in codes]
    storage.upsert_games(games)
    report = {"schema": "tester-spin/playtech-actions-sample/v1",
              "source_commit": os.environ.get("GITHUB_SHA", ""),
              "catalog_source": "included-official-slots-snapshot",
              "fresh_data": True, "dry_run": args.dry_run,
              "spins_per_mode": args.spins, "selected": codes, "results": []}
    write_report(args.output_dir / "summary.json", report)
    if args.dry_run:
        print(json.dumps({"selected": [{"symbol": g.symbol, "name": g.name} for g in games],
                          "game_requests_sent": 0}, ensure_ascii=False), flush=True)
        return 0
    failed = False
    for game in games:
        print("Inicio de demo oficial: " + game.name + " (" + game.symbol + ")", flush=True)
        cli_summary = args.output_dir / (game.symbol + "-batch.json")
        with (args.data_root / (game.symbol + ".private.log")).open("w", encoding="utf-8") as log:
            completed = subprocess.run([sys.executable, "-m", "tester_spin.cli", "run", "playtech",
                "--data-root", str(args.data_root), "--game", game.symbol, "--statuses", "ALL",
                "--spins", str(args.spins), "--timeout", str(args.timeout),
                "--wall-timeout", str(args.wall_timeout), "--public-summary", str(cli_summary)],
                stdout=log, stderr=subprocess.STDOUT, check=False)
        payload = next((r for r in storage.latest_results("playtech") if r["slug"] == game.slug), None)
        if payload is None:
            payload = {"game_name": game.name, "symbol": game.symbol, "slug": game.slug,
                       "status": "ERROR", "error": "CLI_RESULT_MISSING", "successful_spins": 0}
        detail = {key: payload.get(key) for key in ("provider", "slug", "game_name", "symbol", "status",
            "requested_spins", "successful_spins", "failed_spins", "elapsed_ms", "error")}
        detail["cli_exit_code"] = completed.returncode
        detail["attempts"] = [{key: attempt.get(key) for key in
            ("number", "mode_id", "ok", "terminal", "wire_steps", "error")}
            for attempt in payload.get("attempts", [])]
        structural = payload.get("structural_map", {})
        detail["execution_issues"] = structural.get("execution_issues", [])
        detail["return_to_base_verified"] = structural.get("return_to_base_verified", False)
        detail["capture_next_steps"] = structural.get("capture_next_steps", [])
        protocol = structural.get("playtech_protocol", {})
        detail["protocol"] = {key: protocol.get(key) for key in
            ("variant", "transport", "fresh_demo", "server_execution", "source_sha256", "execution_plan")}
        detail["feature_domains"] = payload.get("feature_domains", {})
        runs_root = args.data_root / "providers/playtech" / game.slug / "analysis/runs"
        runs = sorted(runs_root.glob("*")) if runs_root.is_dir() else []
        run = Path(payload["run_dir"]) if payload.get("run_dir") else (runs[-1] if runs else None)
        folder = args.output_dir / game.symbol
        folder.mkdir(exist_ok=True)
        if run is not None:
            run = run.resolve()
            run.relative_to(args.data_root)
            detail["artifact_files"] = sorted(p.name for p in run.iterdir() if p.is_file())
            for name in ("client-contracts.json", "ngm-har-contracts.json", "execution-plan.json", "diagnostic.json"):
                path = run / name
                if path.is_file() and path.stat().st_size <= 16 * 1024 * 1024:
                    value = json.loads(path.read_text(encoding="utf-8"))
                    write_report(folder / name, value)
                    if name == "diagnostic.json":
                        detail["diagnostic"] = {key: value.get(key) for key in ("modes", "evidence_gaps", "sample_diagnostics")}
                        detail["coverage_complete"] = value.get("coverage", {}).get("complete")
        safe = write_report(folder / "result.json", detail)
        report["results"].append(detail)
        write_report(args.output_dir / "summary.json", report)
        print("PLAYTECH_RESULT " + json.dumps(safe, ensure_ascii=False), flush=True)
        failed = failed or completed.returncode != 0
        if completed.returncode in (3, 4):
            print("Lote detenido por bloqueo, cancelación o cierre de procesos no verificado.", flush=True)
            break
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as output:
            output.write("## Playtech: muestra de demos oficiales\n\n| Juego | Estado | Rondas verificadas |\n|---|---|---:|\n")
            for row in report["results"]:
                output.write(f"| {row['game_name']} | {row['status']} | {row['successful_spins']} |\n")
            output.write("\nLos diagnósticos y motivos están en el artefacto de esta ejecución.\n")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
