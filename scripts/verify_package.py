"""Verify a relocated source package using a local server and local-rule run."""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def check(condition, name, checks):
    if not condition:
        raise AssertionError(name)
    checks.append(name)


def verify_release_manifest(root, checks):
    """Check a frozen release explicitly; working repositories legitimately change."""
    manifest_file = root / "RELEASE_MANIFEST.json"
    check(manifest_file.is_file(), "Release manifest is present", checks)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    for row in manifest["files"]:
        file = root / row["path"]
        check(file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest() == row["sha256"],
              "manifest: " + row["path"], checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=ROOT / "evidence" / "generated" / "package-verification.json")
    parser.add_argument("--verify-manifest", action="store_true",
                        help="Also verify the frozen release hashes (use on an unmodified release ZIP).")
    args = parser.parse_args()
    checks = []
    env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    # This check always uses Local_Rule; inherited credentials are unnecessary.
    for key in list(env):
        if key.endswith("API_KEY"):
            env.pop(key)
    if args.verify_manifest:
        verify_release_manifest(ROOT, checks)

    with tempfile.TemporaryDirectory(prefix="evacuation-package-check-") as tmp:
        temp = Path(tmp)
        cli = subprocess.run([
            sys.executable, str(ROOT / "02_可视化沙盒" / "run_cli.py"),
            "--config", str(ROOT / "examples" / "local-smoke.json"), "--output", str(temp / "runs"),
        ], cwd=temp, env=env, text=True, encoding="utf-8", capture_output=True, check=True)
        result = json.loads(cli.stdout.strip().splitlines()[-1])
        check(result["status"] == "completed", "CLI completes from an unrelated working directory", checks)
        replay_path = Path(result["replay"])
        replay = json.loads(replay_path.read_text(encoding="utf-8"))
        check(replay["source"] == "live_local" and replay["fallback_count"] == 0,
              "Smoke run is a genuine local-policy run without LLM fallback", checks)
        check(len(replay["snapshots"][0]["agents"]) == 4, "Configured four agents are present", checks)
        expected = {"C01": "N01", "C02": "N03", "P03": "N04", "F04": "N17"}
        actual = {a["id"]: a["node"] for a in replay["snapshots"][0]["agents"]}
        check(expected == actual, "Exact initial positions survive packaging", checks)
        check((replay_path.parent / "events.jsonl").is_file()
              and list((replay_path.parent / "research").rglob("agent_step.csv")),
              "Event log, replay and research CSV files are generated", checks)
        check(not any(e["type"] == "api.started" for e in replay["events"]),
              "No paid-model request is made", checks)
        check("api_key" not in json.dumps(replay), "Credentials are absent from the replay", checks)

        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        with (temp / "server.log").open("w", encoding="utf-8") as log:
            server = subprocess.Popen([
                sys.executable, str(ROOT / "start.py"), "--port", str(port),
            ], cwd=temp, env=env, stdout=log, stderr=log)
            try:
                base = f"http://127.0.0.1:{port}"
                deadline = time.monotonic() + 20
                while True:
                    try:
                        with urlopen(base + "/api/ping", timeout=1) as response:
                            ping = json.load(response)
                        break
                    except OSError:
                        if server.poll() is not None or time.monotonic() > deadline:
                            raise RuntimeError("Packaged server failed: " + (temp / "server.log").read_text(encoding="utf-8"))
                        time.sleep(.2)
                check(ping["ok"] and ping["repo_exists"], "Packaged server resolves its simulation engine", checks)
                with urlopen(base + "/api/meta", timeout=5) as response:
                    meta = json.load(response)
                check(meta["implementation"] == "studio-1.4-context-ui", "Service identifies the current implementation", checks)
                for asset in ("/", "/studio.js", "/pixel-world.js", "/scene-effects.js", "/agent-narrative.js", "/studio_data.js", "/replay_data.js"):
                    with urlopen(base + asset, timeout=5) as response:
                        check(response.status == 200 and bool(response.read()), "HTTP asset: " + asset, checks)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)

    offline = ROOT / "02_可视化沙盒" / "疏散沙盒-单文件版.html"
    check(offline.is_file() and "window.STUDIO_RUNS" in offline.read_text(encoding="utf-8"),
          "Offline single-file page contains the recorded demos", checks)
    report = {"python": sys.version.split()[0], "implementation": "studio-1.4-context-ui",
              "manifest_verification": "passed" if args.verify_manifest else "not_requested",
              "paid_api_calls": 0, "passed": len(checks), "checks": checks,
              "final_smoke_counts": replay["snapshots"][-1]["counts"]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": len(checks), "paid_api_calls": 0, "final_smoke_counts": report["final_smoke_counts"]}))


if __name__ == "__main__":
    main()
