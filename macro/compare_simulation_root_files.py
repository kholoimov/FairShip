#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP Collaboration

import argparse
import json
import sys
from pathlib import Path

import ROOT


BRANCHES_TO_COMPARE = (
    "MCTrack",
    "vetoPoint",
    "UpstreamTaggerPoint",
    "strawtubesPoint",
    "TimeDetPoint",
    "splitcalPoint",
)


def _open_root_file(path):
    root_file = ROOT.TFile.Open(str(path), "READ")
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"Cannot open ROOT file: {path}")
    return root_file


def _tree_branch_names(tree):
    return sorted(branch.GetName() for branch in tree.GetListOfBranches())


def _event_collection_size(collection):
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


def _event_summary(tree, event_index):
    tree.GetEntry(event_index)
    summary = {}
    for branch_name in BRANCHES_TO_COMPARE:
        if tree.GetBranch(branch_name):
            summary[branch_name] = _event_collection_size(getattr(tree, branch_name, None))
    return summary


def compare_root_files(reference_file, candidate_file):
    reference_root = _open_root_file(reference_file)
    candidate_root = _open_root_file(candidate_file)
    try:
        reference_tree = reference_root.Get("cbmsim")
        candidate_tree = candidate_root.Get("cbmsim")
        if not reference_tree:
            raise RuntimeError(f"ROOT file does not contain cbmsim tree: {reference_file}")
        if not candidate_tree:
            raise RuntimeError(f"ROOT file does not contain cbmsim tree: {candidate_file}")

        reference_branches = _tree_branch_names(reference_tree)
        candidate_branches = _tree_branch_names(candidate_tree)
        if reference_branches != candidate_branches:
            raise AssertionError(
                "Branch list mismatch\n"
                f"Reference: {reference_branches}\n"
                f"Candidate: {candidate_branches}"
            )

        reference_events = int(reference_tree.GetEntries())
        candidate_events = int(candidate_tree.GetEntries())
        if reference_events != candidate_events:
            raise AssertionError(
                f"Event count mismatch: reference has {reference_events}, candidate has {candidate_events}"
            )

        mismatches = []
        for event_index in range(reference_events):
            reference_event = _event_summary(reference_tree, event_index)
            candidate_event = _event_summary(candidate_tree, event_index)
            if reference_event != candidate_event:
                mismatches.append(
                    {
                        "event": event_index,
                        "reference": reference_event,
                        "candidate": candidate_event,
                    }
                )
                if len(mismatches) >= 20:
                    break

        if mismatches:
            raise AssertionError(
                "Event-by-event MC collection mismatch detected\n"
                + json.dumps(mismatches, indent=2, sort_keys=True)
            )
    finally:
        reference_root.Close()
        candidate_root.Close()


def main():
    parser = argparse.ArgumentParser(
        description="Compare two FairShip simulation ROOT files event by event using MC collection sizes."
    )
    parser.add_argument("-r", "--reference-file", required=True, help="Reference simulation ROOT file")
    parser.add_argument("-c", "--candidate-file", required=True, help="Candidate simulation ROOT file")
    args = parser.parse_args()

    compare_root_files(Path(args.reference_file), Path(args.candidate_file))
    print("ROOT file comparison passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
