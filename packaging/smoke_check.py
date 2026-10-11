"""Launch the packaged app headless, load a statement, and report size and startup time.

Used by the release workflow and usable locally:

    python packaging/smoke_check.py --exe dist/StatementPortfolioTracker/StatementPortfolioTracker \
        --sample samples/revolut_sample.csv --bundle-dir dist/StatementPortfolioTracker --label linux-x64

Exits non-zero if the app does not start or cannot load the statement.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RUNS = 3
TIMEOUT_SECONDS = 180


def _megabytes(size: int) -> str:
    return f"{size / 1_000_000:.1f} MB"


def _folder_size(folder: Path) -> int:
    return sum(item.stat().st_size for item in folder.rglob("*") if item.is_file() and not item.is_symlink())


def _run_once(exe: Path, sample: Path, quote: str | None) -> tuple[float, dict[str, object]]:
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp) / "smoke.json"
        command = [str(exe), "--smoke-test", str(sample), "--smoke-out", str(out)]
        if quote:
            command += ["--smoke-quote", quote]
        environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
        started = time.perf_counter()
        completed = subprocess.run(command, env=environment, timeout=TIMEOUT_SECONDS, check=False)
        elapsed = time.perf_counter() - started
        if not out.exists():
            raise SystemExit(f"The app exited with code {completed.returncode} without writing a report.")
        report = json.loads(out.read_text(encoding="utf-8"))
        report["exit_code"] = completed.returncode
        return elapsed, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--exe", type=Path, required=True, help="the packaged executable to launch")
    parser.add_argument("--sample", type=Path, required=True, help="statement file to load")
    parser.add_argument("--label", required=True, help="build name used in the report, e.g. windows-x64")
    parser.add_argument("--bundle-dir", type=Path, help="unpacked app folder, to report its size")
    parser.add_argument("--artifact", type=Path, action="append", default=[], help="download file(s) to report")
    parser.add_argument("--quote", help="also try one price fetch with this Yahoo symbol (network, never fatal)")
    parser.add_argument("--report", type=Path, help="write the markdown report here as well")
    args = parser.parse_args()

    sample = args.sample.resolve()
    timings: list[float] = []
    report: dict[str, object] = {}
    quote: object = None
    for index in range(RUNS):
        # Only the first run tries the network, so the later timings stay comparable.
        elapsed, report = _run_once(args.exe, sample, args.quote if index == 0 else None)
        timings.append(elapsed)
        if index == 0:
            quote = report.get("quote")
        if not report.get("ok") or report["exit_code"] != 0:
            print(json.dumps(report, indent=2))
            print(f"SMOKE TEST FAILED on run {index + 1}", file=sys.stderr)
            return 1

    imports = report.get("imports", {})
    lines = [
        f"### Packaging report: {args.label}",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| App version | {report.get('version')} |",
        f"| Python / platform | {report.get('python')} / {report.get('platform')} |",
        f"| Sample rows loaded | {report.get('sample_rows')} |",
    ]
    for artifact in args.artifact:
        lines.append(f"| Download: `{artifact.name}` | {_megabytes(artifact.stat().st_size)} |")
    if args.bundle_dir:
        lines.append(f"| Installed size | {_megabytes(_folder_size(args.bundle_dir))} |")
    lines += [
        f"| First launch to exit (cold) | {timings[0]:.2f} s |",
        f"| Later launches to exit (warm, best of {RUNS - 1}) | {min(timings[1:]):.2f} s |",
        f"| Window shown after Python start | {report.get('window_shown_s')} s |",
    ]
    for name, details in imports.items():  # type: ignore[union-attr]
        lines.append(f"| Import {name} {details['version']} | {details['seconds']} s |")
    if isinstance(quote, dict):
        outcome = f"worked ({quote.get('currency')})" if quote.get("ok") else f"failed: {quote.get('error')}"
        lines.append(f"| Price fetch from the packaged app | {outcome} |")
    lines.append("")
    lines.append(
        "Launch-to-exit times include importing yfinance and openpyxl, which the real app "
        "does in the background after the window is already visible."
    )
    markdown = "\n".join(lines) + "\n"

    print(markdown)
    if args.report:
        args.report.write_text(markdown, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(markdown + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
