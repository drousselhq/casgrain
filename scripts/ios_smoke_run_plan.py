#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the first fixture-specific iOS smoke plan against the real simulator harness."
    )
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--artifact-dir", required=True)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def validate_supported_plan(plan: dict) -> None:
    expect(plan.get("target", {}).get("platform") == "ios", "fixture bridge only supports iOS plans")
    steps = plan.get("steps", [])
    expect(len(steps) == 4, "fixture bridge currently supports exactly four tap-counter steps")

    launch, tap, assertion, screenshot = steps
    expect(
        launch.get("action", {}).get("kind") == "launch_app"
        and launch["action"].get("app_id") == "app.under.test",
        "first step must launch the fixture app",
    )
    expect(
        launch.get("postconditions")
        == [{"kind": "app_in_foreground", "app_id": "app.under.test"}],
        "launch step must assert the fixture app is in the foreground",
    )
    expect(
        tap.get("action", {}).get("kind") == "tap"
        and tap["action"].get("target", {}).get("kind") == "accessibility_id"
        and tap["action"]["target"].get("value") == "tap-button",
        "second step must tap accessibility id tap-button",
    )
    expect(not tap.get("postconditions"), "tap step must not introduce extra postconditions")
    expect(
        assertion.get("action", {}).get("kind") == "noop"
        and assertion.get("postconditions")
        == [
            {
                "kind": "text_equals",
                "target": {"kind": "accessibility_id", "value": "count-label"},
                "value": "Count: 1",
            }
        ],
        "third step must assert count-label equals Count: 1",
    )
    expect(
        screenshot.get("action", {}).get("kind") == "take_screenshot"
        and screenshot["action"].get("name") == "tap-counter",
        "final step must capture screenshot tap-counter",
    )


def load_json(path: Path, label: str) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as error:
        raise SystemExit(f"missing {label} at {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise SystemExit(f"invalid JSON in {label} at {path}: {error}") from error
    except OSError as error:
        raise SystemExit(f"failed to read {label} at {path}: {error}") from error


def sha256_for(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    plan_path = Path(args.plan).resolve()
    artifact_dir = Path(args.artifact_dir).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    plan = load_json(plan_path, "compiled plan")
    validate_supported_plan(plan)

    screenshot_path = artifact_dir / "tap-counter-1.png"
    simulator_info_path = artifact_dir / "simulator.json"
    shell_script = repo_root / "scripts" / "ios_smoke.sh"
    expect(shell_script.is_file(), f"missing iOS smoke harness script at {shell_script}")

    started_at = utc_now()
    env = os.environ.copy()
    env["ARTIFACT_DIR"] = str(artifact_dir)
    env["CASGRAIN_SMOKE_SCREENSHOT_PATH"] = str(screenshot_path)

    subprocess.run([str(shell_script)], cwd=repo_root, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    simulator_info = load_json(simulator_info_path, "simulator descriptor")
    finished_at = utc_now()

    steps = [
        {
            "step_id": step["step_id"],
            "status": "passed",
            "attempts": 1,
            "failure": None,
            "artifacts": [],
        }
        for step in plan["steps"]
    ]

    diagnostics = []
    artifacts = [
        {
            "artifact_id": "ios-smoke-xcresult",
            "artifact_type": "xcresult_bundle",
            "path": str(artifact_dir / "CasgrainSmoke.xcresult"),
            "sha256": None,
            "step_id": None,
        },
        {
            "artifact_id": "ios-smoke-log",
            "artifact_type": "xcodebuild_log",
            "path": str(artifact_dir / "xcodebuild.log"),
            "sha256": sha256_for(artifact_dir / "xcodebuild.log"),
            "step_id": None,
        },
        {
            "artifact_id": "ios-smoke-simulator",
            "artifact_type": "simulator_descriptor",
            "path": str(artifact_dir / "simulator.json"),
            "sha256": sha256_for(artifact_dir / "simulator.json"),
            "step_id": None,
        },
    ]

    if screenshot_path.is_file():
        screenshot_artifact = {
            "artifact_id": "tap-counter-1",
            "artifact_type": "screenshot",
            "path": str(screenshot_path),
            "sha256": sha256_for(screenshot_path),
            "step_id": plan["steps"][-1]["step_id"],
        }
        artifacts.insert(0, screenshot_artifact)
        steps[-1]["artifacts"] = [screenshot_artifact]
    else:
        diagnostics.append(
            {
                "severity": "warning",
                "message": "deterministic screenshot export path was empty; inspect the xcresult bundle for the captured attachment",
                "location": str(artifact_dir / "CasgrainSmoke.xcresult"),
            }
        )

    trace = {
        "run_id": f"ios-smoke-{plan['plan_id']}",
        "plan_id": plan["plan_id"],
        "device": {
            "platform": "ios",
            "name": simulator_info.get("device_name", "unknown iOS simulator"),
            "os_version": str(simulator_info.get("runtime_name", "unknown")).removeprefix("iOS "),
        },
        "started_at": started_at,
        "finished_at": finished_at,
        "status": "passed",
        "steps": steps,
        "artifacts": artifacts,
        "diagnostics": diagnostics,
    }
    print(json.dumps(trace))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        message = error.stderr.strip() or error.stdout.strip() or str(error)
        print(message, file=sys.stderr)
        raise SystemExit(error.returncode)
