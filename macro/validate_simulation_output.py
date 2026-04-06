#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP Collaboration

import argparse
import json
import sys
from pathlib import Path

import ROOT


BRANCHES_TO_SUMMARIZE = {
    "MCTrack": "mc_tracks",
    "vetoPoint": "sbt_hits",
    "UpstreamTaggerPoint": "ubt_hits",
    "strawtubesPoint": "straw_hits",
    "TimeDetPoint": "timedet_hits",
    "splitcalPoint": "splitcal_hits",
}


def _branch_exists(tree, name):
    return bool(tree.GetBranch(name))


def _event_collection_size(tree, branch_name):
    collection = getattr(tree, branch_name, None)
    if collection is None:
        return 0
    if hasattr(collection, "GetEntriesFast"):
        return int(collection.GetEntriesFast())
    if hasattr(collection, "size"):
        return int(collection.size())
    try:
        return len(collection)
    except TypeError:
        return 0


def _build_branch_summary(tree, branch_name):
    total = 0
    nonempty_events = 0
    maximum = 0

    for event_index in range(tree.GetEntries()):
        tree.GetEntry(event_index)
        count = _event_collection_size(tree, branch_name)
        total += count
        if count > 0:
            nonempty_events += 1
        if count > maximum:
            maximum = count

    return {
        "total": total,
        "nonempty_events": nonempty_events,
        "max_per_event": maximum,
        "mean_per_event": total / tree.GetEntries() if tree.GetEntries() else 0.0,
    }


def summarize_simulation_file(input_file):
    root_file = ROOT.TFile.Open(str(input_file), "READ")
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"Cannot open ROOT file: {input_file}")

    tree = root_file.Get("cbmsim")
    if not tree:
        raise RuntimeError(f"ROOT file does not contain cbmsim tree: {input_file}")

    summary = {
        "input_file": str(input_file),
        "n_events": int(tree.GetEntries()),
        "branches_present": sorted(branch.GetName() for branch in tree.GetListOfBranches()),
        "metrics": {},
    }

    for branch_name, metric_name in BRANCHES_TO_SUMMARIZE.items():
        if _branch_exists(tree, branch_name):
            summary["metrics"][metric_name] = _build_branch_summary(tree, branch_name)

    root_file.Close()
    return summary


def print_summary(summary):
    print(f"Validation summary for {summary['input_file']}")
    print(f"Events: {summary['n_events']}")
    print()

    for metric_name, metric in summary["metrics"].items():
        print(f"{metric_name}:")
        print(f"  total: {metric['total']}")
        print(f"  nonempty_events: {metric['nonempty_events']}")
        print(f"  max_per_event: {metric['max_per_event']}")
        print(f"  mean_per_event: {metric['mean_per_event']:.3f}")


def main():
    parser = argparse.ArgumentParser(description="Summarize a FairShip simulation ROOT file for validation.")
    parser.add_argument("-f", "--input-file", required=True, help="Simulation ROOT file, usually sim_*.root")
    parser.add_argument(
        "-o",
        "--output-json",
        help="Optional path to write the summary as JSON for later reference comparisons.",
    )
    args = parser.parse_args()

    summary = summarize_simulation_file(Path(args.input_file))
    print_summary(summary)

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print()
        print(f"Wrote JSON summary to {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
