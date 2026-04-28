import json
import math
from pathlib import Path


FLOAT_REL_TOL = 1e-9
FLOAT_ABS_TOL = 1e-9


def load_reference_json(path):
    return json.loads(Path(path).read_text())


def compare_simulation_summary(summary, reference):
    assert summary["n_events"] == reference["n_events"], (
        f"Event count mismatch: expected {reference['n_events']}, got {summary['n_events']}"
    )

    assert summary["branches_present"] == reference["branches_present"], (
        "Branch list mismatch\n"
        f"Expected: {reference['branches_present']}\n"
        f"Got: {summary['branches_present']}"
    )

    assert summary["metrics"].keys() == reference["metrics"].keys(), (
        "Metric set mismatch\n"
        f"Expected: {sorted(reference['metrics'])}\n"
        f"Got: {sorted(summary['metrics'])}"
    )

    for metric_name, reference_metric in reference["metrics"].items():
        summary_metric = summary["metrics"][metric_name]
        assert summary_metric.keys() == reference_metric.keys(), (
            f"Metric field mismatch for {metric_name}\n"
            f"Expected: {sorted(reference_metric)}\n"
            f"Got: {sorted(summary_metric)}"
        )
        for key, reference_value in reference_metric.items():
            summary_value = summary_metric[key]
            if isinstance(reference_value, float):
                assert math.isclose(
                    summary_value,
                    reference_value,
                    rel_tol=FLOAT_REL_TOL,
                    abs_tol=FLOAT_ABS_TOL,
                ), (
                    f"Float metric mismatch for {metric_name}.{key}\n"
                    f"Expected: {reference_value}\n"
                    f"Got: {summary_value}"
                )
            else:
                assert summary_value == reference_value, (
                    f"Metric mismatch for {metric_name}.{key}\n"
                    f"Expected: {reference_value}\n"
                    f"Got: {summary_value}"
                )
