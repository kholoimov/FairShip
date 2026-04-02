#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP Collaboration

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run a command, snapshot its outputs, and compare future runs against that reference."
    )
    parser.add_argument("mode", choices=["snapshot", "compare"], help="Create or validate a reference snapshot.")
    parser.add_argument("--reference", required=True, help="Path to the JSON reference file.")
    parser.add_argument(
        "--set",
        dest="variables",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Template variable to inject into the command, for example --set input=/path/to/file.root",
    )
    parser.add_argument(
        "--workdir",
        default=".",
        help="Working directory for the command. The default is the current directory.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for command outputs. Defaults to a temporary directory when omitted.",
    )
    parser.add_argument(
        "--keep-output",
        action="store_true",
        help="Keep the output directory after the command finishes.",
    )
    parser.add_argument(
        "--command",
        nargs=argparse.REMAINDER,
        help="Command to run. This is required for snapshot mode and optional for compare mode.",
    )
    return parser


def parse_key_value(entries):
    values = {}
    for entry in entries:
        if "=" not in entry:
            raise SystemExit(f"Invalid --set value: {entry!r}. Expected NAME=VALUE.")
        key, value = entry.split("=", 1)
        values[key] = value
    return values


def sha256sum(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize_root_file(path):
    import ROOT

    summary = {"keys": [], "trees": {}}
    root_file = ROOT.TFile.Open(str(path), "READ")
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"Failed to open ROOT file: {path}")

    for key in root_file.GetListOfKeys():
        name = key.GetName()
        summary["keys"].append(name)
        obj = key.ReadObj()
        if obj.InheritsFrom("TTree"):
            summary["trees"][name] = {
                "entries": int(obj.GetEntries()),
                "branches": sorted(branch.GetName() for branch in obj.GetListOfBranches()),
            }

    root_file.Close()
    summary["keys"].sort()
    return summary


def summarize_output(path):
    path = Path(path)
    summary = {
        "path": path.name,
        "exists": path.exists(),
    }
    if not path.exists():
        return summary

    summary["size"] = path.stat().st_size
    summary["suffix"] = path.suffix

    if path.suffix == ".root":
        summary["root"] = summarize_root_file(path)
    else:
        summary["sha256"] = sha256sum(path)
    return summary


def substitute_templates(command, variables):
    return [part.format(**variables) for part in command]


def run_command(command, workdir):
    result = subprocess.run(
        command,
        cwd=workdir,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def collect_snapshot(reference, output_dir, execution):
    outputs = []
    for output_name in reference["expected_outputs"]:
        outputs.append(summarize_output(Path(output_dir) / output_name))

    return {
        "command": reference["command"],
        "expected_outputs": reference["expected_outputs"],
        "returncode": execution["returncode"],
        "stdout_contains": reference.get("stdout_contains", []),
        "stderr_contains": reference.get("stderr_contains", []),
        "outputs": outputs,
    }


def ensure_contains(text, required_parts, stream_name):
    for part in required_parts:
        if part not in text:
            raise AssertionError(f"Missing expected text in {stream_name}: {part!r}")


def compare_snapshots(expected, actual):
    if expected["returncode"] != actual["returncode"]:
        raise AssertionError(f"Return code mismatch: expected {expected['returncode']}, got {actual['returncode']}")

    expected_outputs = {entry["path"]: entry for entry in expected["outputs"]}
    actual_outputs = {entry["path"]: entry for entry in actual["outputs"]}

    if expected_outputs.keys() != actual_outputs.keys():
        raise AssertionError(
            f"Output set mismatch: expected {sorted(expected_outputs)}, got {sorted(actual_outputs)}"
        )

    for path, expected_output in expected_outputs.items():
        actual_output = actual_outputs[path]
        if expected_output["exists"] != actual_output["exists"]:
            raise AssertionError(f"Existence mismatch for {path}: expected {expected_output['exists']}, got {actual_output['exists']}")
        if not expected_output["exists"]:
            continue
        if expected_output["suffix"] != actual_output["suffix"]:
            raise AssertionError(f"File type mismatch for {path}: expected {expected_output['suffix']}, got {actual_output['suffix']}")
        if expected_output["suffix"] == ".root":
            if expected_output["root"] != actual_output["root"]:
                raise AssertionError(f"ROOT content mismatch for {path}")
        else:
            if expected_output["sha256"] != actual_output["sha256"]:
                raise AssertionError(f"Checksum mismatch for {path}")


def load_reference(reference_path):
    with open(reference_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_reference(reference_path, payload):
    path = Path(reference_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main():
    args = build_parser().parse_args()
    variables = parse_key_value(args.variables)
    fairship = os.environ.get("FAIRSHIP")
    if fairship:
        variables.setdefault("fairship", fairship)

    managed_output_dir = args.output_dir is None
    output_dir_context = tempfile.TemporaryDirectory(prefix="fairship-reference-") if managed_output_dir else None
    output_dir = Path(args.output_dir or output_dir_context.name).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    variables.setdefault("output_dir", str(output_dir))

    try:
        if args.mode == "snapshot":
            if not args.command:
                raise SystemExit("snapshot mode requires --command ...")
            raw_command = args.command[1:] if args.command and args.command[0] == "--" else args.command
            command = substitute_templates(raw_command, variables)
            execution = run_command(command, args.workdir)
            reference = {
                "command": raw_command,
                "expected_outputs": sorted(path.name for path in output_dir.iterdir() if path.is_file()),
                "stdout_contains": [],
                "stderr_contains": [],
            }
            snapshot = collect_snapshot(reference, output_dir, execution)
            save_reference(args.reference, snapshot)
            print(f"Saved reference snapshot to {args.reference}")
            print(f"Captured outputs from {output_dir}")
        else:
            reference = load_reference(args.reference)
            raw_command = args.command
            if raw_command:
                raw_command = raw_command[1:] if raw_command[0] == "--" else raw_command
            else:
                raw_command = reference["command"]
            command = substitute_templates(raw_command, variables)
            execution = run_command(command, args.workdir)
            ensure_contains(execution["stdout"], reference.get("stdout_contains", []), "stdout")
            ensure_contains(execution["stderr"], reference.get("stderr_contains", []), "stderr")
            actual = collect_snapshot(reference, output_dir, execution)
            compare_snapshots(reference, actual)
            print(f"Reference check passed for {args.reference}")
    finally:
        if output_dir_context is not None and not args.keep_output:
            output_dir_context.cleanup()


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"Reference check failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"Command failed: {shlex.join(exc.cmd)}", file=sys.stderr)
        sys.exit(exc.returncode)
