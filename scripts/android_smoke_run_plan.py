#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and dispatch the first Android smoke fixture plan."
    )
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--artifact-dir", required=True)
    return parser.parse_args()


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def load_json(path: Path, label: str) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as error:
        raise SystemExit(f"missing {label} at {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise SystemExit(f"invalid JSON in {label} at {path}: {error}") from error
    except OSError as error:
        raise SystemExit(f"failed to read {label} at {path}: {error}") from error


def validate_supported_plan(plan: dict) -> None:
    expect(
        plan.get("target", {}).get("platform") == "android",
        "fixture bridge only supports Android plans",
    )
    expect(
        plan.get("target", {}).get("device_class") == "emulator",
        "fixture bridge currently supports emulator-targeted plans only",
    )
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
        and screenshot["action"].get("name") == "android-tap-counter",
        "final step must capture screenshot android-tap-counter",
    )


def main() -> int:
    args = parse_args()
    plan = load_json(Path(args.plan), "compiled plan")
    validate_supported_plan(plan)
    Path(args.artifact_dir).mkdir(parents=True, exist_ok=True)
    raise SystemExit(
        "Android smoke execution is not wired to a real emulator harness yet. "
        "This script currently validates the generated plan contract only; "
        "set CASGRAIN_ANDROID_SMOKE_RUNNER in tests or a future emulator-backed slice to execute it."
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:  # pragma: no cover - defensive CLI wrapper
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
