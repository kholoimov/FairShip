#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP Collaboration

from argparse import ArgumentParser
from glob import glob
from math import sqrt
from pathlib import Path

import ROOT

SPILL_DURATION_SECONDS = 1.0
HZ_TO_KHZ = 1.0e-3
DEFAULT_REFERENCE_EVENTS = 4.12e8


def make_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Compare UBT MC points and digi hits in one or more reco files")
    parser.add_argument(
        "-f",
        "--inputFile",
        dest="input_files",
        nargs="+",
        required=True,
        help="Reconstruction ROOT file(s), glob(s), or directory path(s) containing ship_reco_sim",
    )
    parser.add_argument(
        "-n",
        "--nEvents",
        dest="n_events",
        type=int,
        default=-1,
        help="Number of events to inspect (-1 means all)",
    )
    parser.add_argument(
        "--max-print",
        dest="max_print",
        type=int,
        default=20,
        help="Maximum number of detailed hit comparisons to print",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        default="ubt_hit_comparison",
        help="Directory for histogram outputs",
    )
    parser.add_argument(
        "--pattern",
        default="sim_*_rec.root",
        help="ROOT filename pattern to use when an input path is a directory",
    )
    parser.add_argument(
        "--reference-events",
        dest="reference_events",
        type=float,
        default=DEFAULT_REFERENCE_EVENTS,
        help="Reference sample size used for rate normalization (default: 4.12e8)",
    )
    return parser


def make_histograms(prefix: str = "", weighted: bool = False):
    def name(base: str) -> str:
        return f"{prefix}{base}" if prefix else base

    y_label = "Rate [kHz]" if weighted else "Hits"
    z_label = "Rate [kHz]" if weighted else "Hits"

    return {
        "dx": ROOT.TH1D(name("h_dx"), f"UBT digi minus MC in x;#Deltax [cm];{y_label}", 120, -6.0, 6.0),
        "dy": ROOT.TH1D(name("h_dy"), f"UBT digi minus MC in y;#Deltay [cm];{y_label}", 120, -6.0, 6.0),
        "dz": ROOT.TH1D(name("h_dz"), f"UBT digi minus MC in z;#Deltaz [cm];{y_label}", 120, -1.0, 1.0),
        "dt": ROOT.TH1D(name("h_dt"), f"UBT digi minus MC in time;#Deltat [ns];{y_label}", 120, -2.0, 2.0),
        "dr": ROOT.TH1D(name("h_dr"), f"UBT spatial offset magnitude;|#Deltar| [cm];{y_label}", 120, 0.0, 8.0),
        "dxdy": ROOT.TH2D(
            name("h_dxdy"),
            f"UBT digi minus MC in x/y;#Deltax [cm];#Deltay [cm];{z_label}",
            120,
            -6.0,
            6.0,
            120,
            -6.0,
            6.0,
        ),
        "mc_xy": ROOT.TH2D(
            name("h_mc_xy"),
            f"UBT MC hit map;x [cm];y [cm];{z_label}",
            160,
            -400.0,
            400.0,
            120,
            -300.0,
            300.0,
        ),
        "digi_xy": ROOT.TH2D(
            name("h_digi_xy"),
            f"UBT digitized hit map;x [cm];y [cm];{z_label}",
            160,
            -400.0,
            400.0,
            120,
            -300.0,
            300.0,
        ),
    }


def get_event_rate(tree) -> float:
    if not tree.GetBranch("MCTrack"):
        return 1.0
    for track in tree.MCTrack:
        if abs(track.GetPdgCode()) == 13:
            return track.GetWeight()
    return 1.0


def convert_weight_to_rate_khz(weight: float) -> float:
    return weight / SPILL_DURATION_SECONDS * HZ_TO_KHZ


def get_sample_scale(reference_events: float, processed_events: int) -> float:
    if processed_events <= 0:
        return 0.0
    return reference_events / processed_events


def scale_histograms(histograms, factor: float) -> None:
    for hist in histograms.values():
        hist.Scale(factor)


def build_rate_per_tile_histogram(source_hist, name: str, title: str):
    max_rate = source_hist.GetMaximum()
    upper_edge = max(10.0, 1.05 * max_rate) if max_rate > 0.0 else 10.0
    rate_hist = ROOT.TH1D(name, title, 200, 0.0, upper_edge)
    for ix in range(1, source_hist.GetNbinsX() + 1):
        for iy in range(1, source_hist.GetNbinsY() + 1):
            value = source_hist.GetBinContent(ix, iy)
            if value > 0.0:
                rate_hist.Fill(value)
    return rate_hist


def resolve_input_files(input_paths: list[str], pattern: str) -> list[Path]:
    resolved: list[Path] = []
    seen: set[Path] = set()

    for raw_path in input_paths:
        path = Path(raw_path)
        matches: list[Path] = []

        if any(token in raw_path for token in "*?[]"):
            matches = [Path(candidate) for candidate in glob(raw_path)]
        elif path.is_dir():
            matches = sorted(path.rglob(pattern))
        else:
            matches = [path]

        for match in matches:
            resolved_path = match.resolve()
            if resolved_path not in seen:
                seen.add(resolved_path)
                resolved.append(resolved_path)

    return resolved


def save_histograms(histograms, output_dir: Path, prefix: str = "") -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_root = output_dir / "ubt_hit_comparison.root"
    file_mode = "RECREATE" if not output_root.exists() or not prefix else "UPDATE"
    with ROOT.TFile.Open(str(output_root), file_mode) as root_out:
        for hist in histograms.values():
            hist.Write()

    ROOT.gROOT.SetBatch(True)
    ROOT.gStyle.SetOptStat(0)
    ROOT.gStyle.SetPalette(ROOT.kBird)
    ROOT.gStyle.SetNumberContours(100)
    ROOT.gStyle.SetTitleSize(0.04, "XYZ")
    ROOT.gStyle.SetLabelSize(0.035, "XYZ")
    ROOT.gStyle.SetTitleOffset(1.15, "X")
    ROOT.gStyle.SetTitleOffset(1.2, "Y")
    ROOT.gStyle.SetTitleOffset(1.1, "Z")
    canvas = ROOT.TCanvas("c_ubt_compare", "UBT comparison", 1100, 700)
    canvas.SetLeftMargin(0.12)
    canvas.SetRightMargin(0.18)
    canvas.SetBottomMargin(0.12)
    for name, hist in histograms.items():
        canvas.Clear()
        if hist.InheritsFrom("TH2"):
            hist.SetContour(100)
            hist.GetZaxis().SetTitleOffset(1.25)
            hist.GetZaxis().SetLabelSize(0.03)
        draw_option = "COLZ" if hist.InheritsFrom("TH2") else ""
        hist.Draw(draw_option)
        canvas.SaveAs(str(output_dir / f"{prefix}{name}.png"))


def process_file(input_file: Path, options, histograms, weighted_histograms):
    root_file = ROOT.TFile.Open(str(input_file), "READ")
    if not root_file or root_file.IsZombie():
        raise OSError(f"Failed to open input file: {input_file}")

    tree = root_file.Get("ship_reco_sim")
    if not tree:
        raise KeyError(f"TTree 'ship_reco_sim' not found in input file: {input_file}")
    if not tree.GetBranch("UpstreamTaggerPoint"):
        raise KeyError(f"Branch 'UpstreamTaggerPoint' not found in ship_reco_sim for {input_file}")
    if not tree.GetBranch("Digi_UpstreamTaggerHits"):
        raise KeyError(f"Branch 'Digi_UpstreamTaggerHits' not found in ship_reco_sim for {input_file}")

    n_entries = tree.GetEntries()
    n_events = n_entries if options.n_events < 0 else min(options.n_events, n_entries)

    total_pairs = 0
    detector_id_mismatches = 0
    print_budget = options.max_print

    sum_dx = sum_dy = sum_dz = sum_dt = 0.0
    sum_dr = 0.0
    weighted_pairs = 0.0
    weighted_detector_id_mismatches = 0.0
    weighted_sum_dx = weighted_sum_dy = weighted_sum_dz = weighted_sum_dt = 0.0
    weighted_sum_dr = 0.0
    max_abs_dx = max_abs_dy = max_abs_dz = max_abs_dt = 0.0
    max_dr = 0.0

    for event_index in range(n_events):
        tree.GetEntry(event_index)
        mc_points = tree.UpstreamTaggerPoint
        digi_hits = tree.Digi_UpstreamTaggerHits
        event_t0 = tree.ShipEventHeader.GetEventTime() if tree.GetBranch("ShipEventHeader") else 0.0
        event_rate = get_event_rate(tree)

        if len(mc_points) != len(digi_hits):
            print(
                f"Event {event_index}: branch size mismatch "
                f"(MC={len(mc_points)}, digi={len(digi_hits)})"
            )

        for hit_index, (mc_point, digi_hit) in enumerate(zip(mc_points, digi_hits)):
            dx = digi_hit.GetX() - mc_point.GetX()
            dy = digi_hit.GetY() - mc_point.GetY()
            dz = digi_hit.GetZ() - mc_point.GetZ()
            dt = digi_hit.GetTime() - (mc_point.GetTime() + event_t0)
            dr = sqrt(dx * dx + dy * dy + dz * dz)
            histograms["dx"].Fill(dx)
            histograms["dy"].Fill(dy)
            histograms["dz"].Fill(dz)
            histograms["dt"].Fill(dt)
            histograms["dr"].Fill(dr)
            histograms["dxdy"].Fill(dx, dy)
            histograms["mc_xy"].Fill(mc_point.GetX(), mc_point.GetY())
            histograms["digi_xy"].Fill(digi_hit.GetX(), digi_hit.GetY())
            weighted_histograms["dx"].Fill(dx, event_rate)
            weighted_histograms["dy"].Fill(dy, event_rate)
            weighted_histograms["dz"].Fill(dz, event_rate)
            weighted_histograms["dt"].Fill(dt, event_rate)
            weighted_histograms["dr"].Fill(dr, event_rate)
            weighted_histograms["dxdy"].Fill(dx, dy, event_rate)
            weighted_histograms["mc_xy"].Fill(mc_point.GetX(), mc_point.GetY(), event_rate)
            weighted_histograms["digi_xy"].Fill(digi_hit.GetX(), digi_hit.GetY(), event_rate)

            total_pairs += 1
            sum_dx += dx
            sum_dy += dy
            sum_dz += dz
            sum_dt += dt
            sum_dr += dr
            weighted_pairs += event_rate
            weighted_sum_dx += dx * event_rate
            weighted_sum_dy += dy * event_rate
            weighted_sum_dz += dz * event_rate
            weighted_sum_dt += dt * event_rate
            weighted_sum_dr += dr * event_rate
            max_abs_dx = max(max_abs_dx, abs(dx))
            max_abs_dy = max(max_abs_dy, abs(dy))
            max_abs_dz = max(max_abs_dz, abs(dz))
            max_abs_dt = max(max_abs_dt, abs(dt))
            max_dr = max(max_dr, dr)

            if digi_hit.GetDetectorID() != mc_point.GetDetectorID():
                detector_id_mismatches += 1
                weighted_detector_id_mismatches += event_rate

            if print_budget > 0:
                print(
                    f"file={input_file} event={event_index} hit={hit_index} detID(mc/digi)="
                    f"{mc_point.GetDetectorID()}/{digi_hit.GetDetectorID()} "
                    f"mc=({mc_point.GetX():.2f},{mc_point.GetY():.2f},{mc_point.GetZ():.2f}) "
                    f"digi=({digi_hit.GetX():.2f},{digi_hit.GetY():.2f},{digi_hit.GetZ():.2f}) "
                    f"dxyz=({dx:.2f},{dy:.2f},{dz:.2f}) dt={dt:.3f} ns"
                )
                print_budget -= 1

    root_file.Close()

    return {
        "file": str(input_file),
        "events": n_events,
        "pairs": total_pairs,
        "detector_id_mismatches": detector_id_mismatches,
        "weighted_pairs": weighted_pairs,
        "weighted_detector_id_mismatches": weighted_detector_id_mismatches,
        "sum_dx": sum_dx,
        "sum_dy": sum_dy,
        "sum_dz": sum_dz,
        "sum_dt": sum_dt,
        "sum_dr": sum_dr,
        "weighted_sum_dx": weighted_sum_dx,
        "weighted_sum_dy": weighted_sum_dy,
        "weighted_sum_dz": weighted_sum_dz,
        "weighted_sum_dt": weighted_sum_dt,
        "weighted_sum_dr": weighted_sum_dr,
        "max_abs_dx": max_abs_dx,
        "max_abs_dy": max_abs_dy,
        "max_abs_dz": max_abs_dz,
        "max_abs_dt": max_abs_dt,
        "max_dr": max_dr,
    }


def write_summary(rows, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.tsv"
    with summary_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "file\tevents\tpairs\tweighted_pairs\tdetector_id_mismatches\tweighted_detector_id_mismatches\tmean_dx_cm\tmean_dy_cm\tmean_dz_cm\tmean_dt_ns\tmean_dr_cm\tweighted_mean_dx_cm\tweighted_mean_dy_cm\tweighted_mean_dz_cm\tweighted_mean_dt_ns\tweighted_mean_dr_cm\n"
        )
        for row in rows:
            pairs = row["pairs"]
            weighted_pairs = row["weighted_pairs"]
            if pairs > 0:
                mean_dx = row["sum_dx"] / pairs
                mean_dy = row["sum_dy"] / pairs
                mean_dz = row["sum_dz"] / pairs
                mean_dt = row["sum_dt"] / pairs
                mean_dr = row["sum_dr"] / pairs
            else:
                mean_dx = mean_dy = mean_dz = mean_dt = mean_dr = 0.0
            if weighted_pairs > 0:
                weighted_mean_dx = row["weighted_sum_dx"] / weighted_pairs
                weighted_mean_dy = row["weighted_sum_dy"] / weighted_pairs
                weighted_mean_dz = row["weighted_sum_dz"] / weighted_pairs
                weighted_mean_dt = row["weighted_sum_dt"] / weighted_pairs
                weighted_mean_dr = row["weighted_sum_dr"] / weighted_pairs
            else:
                weighted_mean_dx = weighted_mean_dy = weighted_mean_dz = weighted_mean_dt = weighted_mean_dr = 0.0
            handle.write(
                f"{row['file']}\t{row['events']}\t{pairs}\t{weighted_pairs:.6f}\t"
                f"{row['detector_id_mismatches']}\t{row['weighted_detector_id_mismatches']:.6f}\t"
                f"{mean_dx:.6f}\t{mean_dy:.6f}\t{mean_dz:.6f}\t{mean_dt:.6f}\t{mean_dr:.6f}\t"
                f"{weighted_mean_dx:.6f}\t{weighted_mean_dy:.6f}\t{weighted_mean_dz:.6f}\t"
                f"{weighted_mean_dt:.6f}\t{weighted_mean_dr:.6f}\n"
            )


def main() -> None:
    options = make_parser().parse_args()
    input_files = resolve_input_files(options.input_files, options.pattern)
    if not input_files:
        raise FileNotFoundError("No input ROOT files matched the provided paths/patterns")

    histograms = make_histograms()
    rate_histograms = make_histograms(prefix="rate_", weighted=True)
    rows = []

    for input_file in input_files:
        print(f"Processing {input_file}")
        rows.append(process_file(input_file, options, histograms, rate_histograms))

    total_events = sum(row["events"] for row in rows)
    total_pairs = sum(row["pairs"] for row in rows)
    detector_id_mismatches = sum(row["detector_id_mismatches"] for row in rows)
    weighted_pairs = sum(row["weighted_pairs"] for row in rows)
    weighted_detector_id_mismatches = sum(row["weighted_detector_id_mismatches"] for row in rows)
    sum_dx = sum(row["sum_dx"] for row in rows)
    sum_dy = sum(row["sum_dy"] for row in rows)
    sum_dz = sum(row["sum_dz"] for row in rows)
    sum_dt = sum(row["sum_dt"] for row in rows)
    sum_dr = sum(row["sum_dr"] for row in rows)
    weighted_sum_dx = sum(row["weighted_sum_dx"] for row in rows)
    weighted_sum_dy = sum(row["weighted_sum_dy"] for row in rows)
    weighted_sum_dz = sum(row["weighted_sum_dz"] for row in rows)
    weighted_sum_dt = sum(row["weighted_sum_dt"] for row in rows)
    weighted_sum_dr = sum(row["weighted_sum_dr"] for row in rows)
    max_abs_dx = max((row["max_abs_dx"] for row in rows), default=0.0)
    max_abs_dy = max((row["max_abs_dy"] for row in rows), default=0.0)
    max_abs_dz = max((row["max_abs_dz"] for row in rows), default=0.0)
    max_abs_dt = max((row["max_abs_dt"] for row in rows), default=0.0)
    max_dr = max((row["max_dr"] for row in rows), default=0.0)
    sample_scale = get_sample_scale(options.reference_events, total_events)
    integrated_hit_rate_khz = convert_weight_to_rate_khz(weighted_pairs * sample_scale)
    integrated_mismatch_rate_khz = convert_weight_to_rate_khz(weighted_detector_id_mismatches * sample_scale)

    print("=" * 72)
    print(f"Files processed: {len(rows)}")
    print(f"Events processed: {total_events}")
    print(f"Reference events: {options.reference_events:.6g}")
    print(f"Sample scale factor: {sample_scale:.6g}")
    print(f"Compared hit pairs: {total_pairs}")
    print(f"Integrated hit rate: {integrated_hit_rate_khz:.6f} kHz")
    print(f"Detector ID mismatches: {detector_id_mismatches}")
    print(f"Integrated mismatch rate: {integrated_mismatch_rate_khz:.6f} kHz")
    if total_pairs > 0:
        print(f"Mean dx/dy/dz: {sum_dx / total_pairs:.3f}, {sum_dy / total_pairs:.3f}, {sum_dz / total_pairs:.3f} cm")
        print(f"Mean dt: {sum_dt / total_pairs:.4f} ns")
        print(f"Mean |dr|: {sum_dr / total_pairs:.3f} cm")
        if weighted_pairs > 0:
            print(
                f"Rate-weighted mean dx/dy/dz: "
                f"{weighted_sum_dx / weighted_pairs:.3f}, "
                f"{weighted_sum_dy / weighted_pairs:.3f}, "
                f"{weighted_sum_dz / weighted_pairs:.3f} cm"
            )
            print(f"Rate-weighted mean dt: {weighted_sum_dt / weighted_pairs:.4f} ns")
            print(f"Rate-weighted mean |dr|: {weighted_sum_dr / weighted_pairs:.3f} cm")
        print(f"Max |dx|/|dy|/|dz|: {max_abs_dx:.3f}, {max_abs_dy:.3f}, {max_abs_dz:.3f} cm")
        print(f"Max |dt|: {max_abs_dt:.4f} ns")
        print(f"Max |dr|: {max_dr:.3f} cm")
        output_dir = Path(options.output_dir)
        scale_histograms(rate_histograms, convert_weight_to_rate_khz(sample_scale))
        rate_histograms["digi_tile_rate"] = build_rate_per_tile_histogram(
            rate_histograms["digi_xy"],
            "rate_h_digi_tile_rate",
            "UBT digitized tile rate distribution;Tile rate [kHz];Tiles",
        )
        rate_histograms["mc_tile_rate"] = build_rate_per_tile_histogram(
            rate_histograms["mc_xy"],
            "rate_h_mc_tile_rate",
            "UBT MC tile rate distribution;Tile rate [kHz];Tiles",
        )
        save_histograms(histograms, output_dir)
        save_histograms(rate_histograms, output_dir, prefix="rate_")
        write_summary(rows, output_dir)
        print(f"Saved histograms to: {options.output_dir}")
        print(f"Saved summary to: {output_dir / 'summary.tsv'}")


if __name__ == "__main__":
    main()
