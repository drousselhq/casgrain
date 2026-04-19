#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

IOS_SMOKE_WORKFLOW_PATH = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ios-simulator-smoke.yml"


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


def command_output(*args: str) -> str:
    completed = subprocess.run(
        list(args),
        check=True,
        capture_output=True,
        text=True,
    )
    return (completed.stdout + completed.stderr).strip()


def github_run_metadata() -> dict[str, str]:
    return {
        "repository": os.environ.get("GITHUB_REPOSITORY", "local"),
        "workflow": os.environ.get("GITHUB_WORKFLOW", "ios-simulator-smoke"),
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "run_url": os.environ.get(
            "GITHUB_SERVER_URL", "https://github.com"
        )
        + "/"
        + os.environ.get("GITHUB_REPOSITORY", "local")
        + "/actions/runs/"
        + os.environ.get("GITHUB_RUN_ID", "local"),
    }


def read_workflow_job_block(path: Path, job_name: str) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise SystemExit(f"failed to read workflow file at {path}: {error}") from error

    job_header = f"  {job_name}:"
    start_index = None
    for index, line in enumerate(lines):
        if line == job_header:
            start_index = index + 1
            break
    if start_index is None:
        raise SystemExit(f"workflow file {path} is missing jobs.{job_name}")

    collected: list[str] = []
    for line in lines[start_index:]:
        if re.match(r"^  [A-Za-z0-9_-]+:\s*$", line):
            break
        collected.append(line)
    return "\n".join(collected)


def extract_workflow_scalar(block: str, key: str, *, error_context: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}:\s*['\"]?([^'\"\n]+)['\"]?\s*$", block, flags=re.MULTILINE)
    if match:
        return match.group(1).strip()
    raise SystemExit(f"workflow config is missing {error_context}")


def load_ios_workflow_config(path: Path = IOS_SMOKE_WORKFLOW_PATH) -> dict[str, str]:
    smoke_job = read_workflow_job_block(path, "smoke")
    return {
        "runner_label": extract_workflow_scalar(smoke_job, "runs-on", error_context="jobs.smoke.runs-on")
    }


def normalize_runner_image_name(image_name: str, architecture: str) -> str:
    normalized = image_name.strip().lower()
    if not normalized or normalized == "unknown":
        return image_name or "unknown"
    macos_match = re.fullmatch(r"macos(\d+)", normalized)
    if macos_match:
        version = macos_match.group(1)
        architecture = architecture.strip()
        return f"macos-{version}-{architecture}" if architecture else f"macos-{version}"
    return image_name


def build_ios_host_environment(simulator_info: dict[str, str]) -> dict[str, object]:
    workflow_config = load_ios_workflow_config()
    developer_dir = Path(command_output("xcode-select", "-p").splitlines()[0].strip())
    xcode_app = developer_dir.parents[1] if developer_dir.name == "Developer" else developer_dir
    xcode_version_output = command_output("xcodebuild", "-version").splitlines()
    xcode_version = xcode_version_output[0].split()[-1] if xcode_version_output else "unknown"
    simulator_sdk_version = command_output("xcrun", "--sdk", "iphonesimulator", "--show-sdk-version").splitlines()[0].strip()
    os_version = command_output("sw_vers", "-productVersion").splitlines()[0].strip()
    os_build = command_output("sw_vers", "-buildVersion").splitlines()[0].strip()
    architecture = command_output("uname", "-m").splitlines()[0].strip()
    raw_image_name = os.environ.get("ImageOS", "unknown")
    return {
        "generated_at": utc_now(),
        "workflow_run": github_run_metadata(),
        "runner": {
            "label": workflow_config["runner_label"],
            "image_name": normalize_runner_image_name(raw_image_name, architecture),
            "image_version": os.environ.get("ImageVersion", "unknown"),
            "os_name": "macOS",
            "os_version": os_version,
            "os_build": os_build,
        },
        "xcode": {
            "app_path": str(xcode_app),
            "version": xcode_version,
            "simulator_sdk_version": simulator_sdk_version,
        },
        "simulator": {
            "runtime_identifier": str(simulator_info.get("runtime", "unknown")),
            "runtime_name": str(simulator_info.get("runtime_name", "unknown")),
            "device_name": str(simulator_info.get("device_name", "unknown")),
        },
    }


def validate_ios_host_environment(host_environment: dict[str, object]) -> None:
    generated_at = host_environment.get("generated_at")
    expect(isinstance(generated_at, str) and generated_at.strip(), "host-environment.json must include non-empty generated_at")
    workflow_run = host_environment.get("workflow_run")
    expect(isinstance(workflow_run, dict), "host-environment.json must include object 'workflow_run'")
    for field_name in ("repository", "workflow", "run_id", "run_attempt", "run_url"):
        value = workflow_run.get(field_name)
        expect(
            isinstance(value, (str, int, float)) and str(value).strip(),
            f"host-environment.json must include non-empty workflow_run.{field_name}",
        )
    for group_name, required_fields in {
        "runner": ("label", "image_name", "image_version", "os_name", "os_version", "os_build"),
        "xcode": ("app_path", "version", "simulator_sdk_version"),
        "simulator": ("runtime_identifier", "runtime_name", "device_name"),
    }.items():
        group = host_environment.get(group_name)
        expect(isinstance(group, dict), f"host-environment.json must include object {group_name!r}")
        for field_name in required_fields:
            value = group.get(field_name)
            expect(
                isinstance(value, (str, int, float)) and str(value).strip(),
                f"host-environment.json must include non-empty {group_name}.{field_name}",
            )


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
    host_environment_path = artifact_dir / "host-environment.json"
    shell_script = repo_root / "tests" / "test-support" / "scripts" / "ios_smoke.sh"
    expect(shell_script.is_file(), f"missing iOS smoke harness script at {shell_script}")

    started_at = utc_now()
    env = os.environ.copy()
    env["ARTIFACT_DIR"] = str(artifact_dir)
    env["CASGRAIN_SMOKE_SCREENSHOT_PATH"] = str(screenshot_path)

    subprocess.run([str(shell_script)], cwd=repo_root, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    simulator_info = load_json(simulator_info_path, "simulator descriptor")
    host_environment = build_ios_host_environment(simulator_info)
    validate_ios_host_environment(host_environment)
    host_environment_path.write_text(json.dumps(host_environment, indent=2) + "\n")
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
            "artifact_id": "ios-host-environment",
            "artifact_type": "host_environment",
            "path": str(host_environment_path),
            "sha256": sha256_for(host_environment_path),
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
