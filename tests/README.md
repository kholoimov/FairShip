# FairShip Validation Tests

This directory contains the integration-style validation tests for a local FairShip build.

The suite checks four different things:

- the project still builds cleanly
- representative simulation modes still run
- output files still have the expected structure and content
- tracking reconstruction still produces sane benchmark metrics

This README explains:

- what each test runs
- how each test validates the result
- how to run the tests
- how to regenerate the reference files

## Before You Start

These tests assume:

- you are in the FairShip checkout
- the actual runtime working directory is the parent of the checkout
  Example:
  if the repository is `/ship_build/FairShip`, runtime commands are launched from `/ship_build`
- CVMFS is available at `/cvmfs/ship.cern.ch/26.03/setUp.sh`
- the local aliBuild package for your branch can be loaded with:
  `eval "$(alienv load FairShip/latest-<current-branch>-release)"`

All runtime phases are started in a fresh shell:

```bash
/bin/bash -lc '<command>'
```

So simulation, validation, reconstruction, and reference-generation steps do not reuse shell state from earlier phases.

## How The Commands Are Built

Most runtime tests use the same shell prefix:

```bash
source /cvmfs/ship.cern.ch/26.03/setUp.sh
eval "$(alienv load FairShip/latest-<branch>-release)"
```

After that, the test runs one of the local FairShip scripts from:

- `<repo_root>/macro/run_simScript.py`
- `<repo_root>/macro/ShipReco.py`
- `<repo_root>/macro/validate_simulation_output.py`
- `<repo_root>/macro/compare_simulation_root_files.py`

In the examples below:

- `<repo_root>` means the FairShip checkout
- `<repo_parent>` means the parent directory of the checkout
- `<tmp_output_dir>` is the temporary directory created by `pytest`

## Test By Test

### `tests/test_build_clean.py`

Purpose:
- checks that the build command succeeds
- scans the build log for warnings and errors

Default command:

```bash
echo "Loading SHiP environment..." && \
source /cvmfs/ship.cern.ch/26.03/setUp.sh && \
echo "Building FairShip..." && \
aliBuild build FairShip \
  --force-rebuild FairShip \
  --always-prefer-system \
  --config-dir "$SHIPDIST" \
  --defaults release \
  -j 100
```

Validation:

- the command must return exit code `0`
- the combined build log must not contain warning lines or error lines
- the build output must mention the expected aliBuild package name for the current branch

Useful overrides:

- `FAIRSHIP_BUILD_TEST_COMMAND`
- `FAIRSHIP_BUILD_TEST_WORKDIR`
- `FAIRSHIP_BUILD_TEST_JOBS`
- `FAIRSHIP_BUILD_WARNING_ALLOWLIST`

### `tests/test_simulation_validation.py`

Purpose:
- runs the muon-background simulation path
- validates the result using numeric summary statistics

Simulation command shape:

```bash
source /cvmfs/ship.cern.ch/26.03/setUp.sh && \
eval "$(alienv load FairShip/latest-<branch>-release)" && \
python3 <repo_root>/macro/run_simScript.py \
  -n 5000 \
  -i 100 \
  --MuonBack --FollowMuon --FastMuon \
  -f /tmp/pythia8_Geant4_10.0_withCharmandBeauty0_mu.root \
  -o <tmp_output_dir> \
  --tag pytest_validation \
  --sameSeed 42 \
  --seed 42
```

Validation command shape:

```bash
source /cvmfs/ship.cern.ch/26.03/setUp.sh && \
eval "$(alienv load FairShip/latest-<branch>-release)" && \
python3 <repo_root>/macro/validate_simulation_output.py \
  -f <tmp_output_dir>/sim_pytest_validation.root \
  -o <tmp_output_dir>/sim_pytest_validation.validation.json
```

Validation method:

- checks that these files exist:
  - `sim_pytest_validation.root`
  - `geo_pytest_validation.root`
  - `params_pytest_validation.root`
- reads the JSON summary produced by `validate_simulation_output.py`
- compares it to:
  [tests/reference/muonback_fast_100.json](/Users/vkholoimov/Documents/SHIP/FairShip/tests/reference/muonback_fast_100.json)

The JSON summary contains:

- `n_events`
- `branches_present`
- per-collection metrics for:
  - `MCTrack`
  - `vetoPoint`
  - `UpstreamTaggerPoint`
  - `strawtubesPoint`
  - `TimeDetPoint`
  - `splitcalPoint`

Each metric block contains:

- `total`
- `nonempty_events`
- `min_per_event`
- `max_per_event`
- `mean_per_event`
- `rms_per_event`
- `sigma_per_event`

### `tests/test_simulation_io.py`

Purpose:
- performs a strict muon-background I/O comparison

Simulation command shape:

```bash
source /cvmfs/ship.cern.ch/26.03/setUp.sh && \
eval "$(alienv load FairShip/latest-<branch>-release)" && \
python3 <repo_root>/macro/run_simScript.py \
  -n 100 \
  -i 100 \
  --MuonBack --FollowMuon --FastMuon \
  -f /tmp/pythia8_Geant4_10.0_withCharmandBeauty0_mu.root \
  -o <tmp_output_dir> \
  --tag pytest_io \
  --sameSeed 42 \
  --seed 42
```

Comparison command shape:

```bash
source /cvmfs/ship.cern.ch/26.03/setUp.sh && \
eval "$(alienv load FairShip/latest-<branch>-release)" && \
python3 <repo_root>/macro/compare_simulation_root_files.py \
  -r <repo_root>/tests/reference/muonback_fast_100.root \
  -c <tmp_output_dir>/sim_pytest_io.root
```

Validation method:

- checks that the candidate ROOT file exists
- compares the candidate ROOT file against:
  [tests/reference/muonback_fast_100.root](/Users/vkholoimov/Documents/SHIP/FairShip/tests/reference/muonback_fast_100.root)
- comparison is event by event
- for each event, it compares collection sizes for:
  - `MCTrack`
  - `vetoPoint`
  - `UpstreamTaggerPoint`
  - `strawtubesPoint`
  - `TimeDetPoint`
  - `splitcalPoint`
- before the event loop starts, it also checks:
  - branch-list equality
  - total event-count equality

Important:

- this test is intentionally capped at `100` events
- if `FAIRSHIP_SIM_IO_TEST_EVENTS` is set above `100`, the test fails immediately

### `tests/test_particle_gun_io.py`

Purpose:
- performs a strict particle-gun I/O comparison

Simulation command shape:

```bash
source /cvmfs/ship.cern.ch/26.03/setUp.sh && \
eval "$(alienv load FairShip/latest-<branch>-release)" && \
python3 <repo_root>/macro/run_simScript.py \
  -n 100 \
  -s 42 \
  --debug 0 \
  --vacuums \
  --tag pytest_pg \
  -o <tmp_output_dir> \
  PG \
  --pID 13 \
  --Estart 1.0 \
  --Eend 10.0 \
  --Vz 8300.0 \
  --multiplePG \
  --Dx 50.0 \
  --Dy 50.0
```

Comparison command shape:

```bash
source /cvmfs/ship.cern.ch/26.03/setUp.sh && \
eval "$(alienv load FairShip/latest-<branch>-release)" && \
python3 <repo_root>/macro/compare_simulation_root_files.py \
  -r <repo_root>/tests/reference/sim_reference_run.root \
  -c <tmp_output_dir>/sim_pytest_pg.root
```

Validation method:

- checks that the candidate ROOT file exists
- compares it event by event against:
  [tests/reference/sim_reference_run.root](/Users/vkholoimov/Documents/SHIP/FairShip/tests/reference/sim_reference_run.root)
- uses the same branch-list and per-event collection-size comparison as the muon-background I/O test

Important:

- this test is intentionally capped at `100` events
- if `FAIRSHIP_PARTICLE_GUN_TEST_EVENTS` is set above `100`, the test fails immediately

### `tests/test_pythia8_validation.py`

Purpose:
- runs the Pythia8 simulation path
- validates the output using numeric summary statistics

Simulation command shape:

```bash
source /cvmfs/ship.cern.ch/26.03/setUp.sh && \
eval "$(alienv load FairShip/latest-<branch>-release)" && \
python3 <repo_root>/macro/run_simScript.py \
  --Pythia8 \
  -t \
  -n 1000 \
  --debug 0 \
  -o <tmp_output_dir> \
  --tag pytest_pythia8 \
  --seed 42
```

Validation command shape:

```bash
source /cvmfs/ship.cern.ch/26.03/setUp.sh && \
eval "$(alienv load FairShip/latest-<branch>-release)" && \
python3 <repo_root>/macro/validate_simulation_output.py \
  -f <tmp_output_dir>/sim_pytest_pythia8.root \
  -o <tmp_output_dir>/sim_pytest_pythia8.validation.json
```

Validation method:

- checks that simulation, geometry, and parameter ROOT files exist
- compares the produced summary JSON against:
  [tests/reference/pythia8_reference_run.json](/Users/vkholoimov/Documents/SHIP/FairShip/tests/reference/pythia8_reference_run.json)

### `tests/test_evtgen_validation.py`

Purpose:
- runs the EvtGen decayer path
- validates the output using numeric summary statistics

Simulation command shape:

```bash
source /cvmfs/ship.cern.ch/26.03/setUp.sh && \
eval "$(alienv load FairShip/latest-<branch>-release)" && \
python3 <repo_root>/macro/run_simScript.py \
  --EvtGenDecayer \
  -t \
  -n 1000 \
  --debug 0 \
  -o <tmp_output_dir> \
  --tag pytest_evtgen \
  --seed 42
```

Validation command shape:

```bash
source /cvmfs/ship.cern.ch/26.03/setUp.sh && \
eval "$(alienv load FairShip/latest-<branch>-release)" && \
python3 <repo_root>/macro/validate_simulation_output.py \
  -f <tmp_output_dir>/sim_pytest_evtgen.root \
  -o <tmp_output_dir>/sim_pytest_evtgen.validation.json
```

Validation method:

- checks that simulation, geometry, and parameter ROOT files exist
- compares the produced summary JSON against:
  [tests/reference/evtgen_reference_run.json](/Users/vkholoimov/Documents/SHIP/FairShip/tests/reference/evtgen_reference_run.json)

### `tests/test_tracking_benchmark.py`

Purpose:
- runs a full tracking benchmark flow
- performs simulation
- performs reconstruction
- computes tracking metrics

Simulation command shape:

```bash
source /cvmfs/ship.cern.ch/26.03/setUp.sh && \
eval "$(alienv load FairShip/latest-<branch>-release)" && \
python3 <repo_root>/macro/run_simScript.py \
  -n 1000 \
  -s 42 \
  --debug 0 \
  --vacuums \
  --SND \
  --SND_design 2 \
  --shieldName TRY_2025 \
  --tag ci-benchmark \
  -o <tmp_output_dir> \
  PG \
  --pID 13 \
  --Estart 1.0 \
  --Eend 100.0 \
  --Vz 8300.0 \
  --multiplePG \
  --Dx 200.0 \
  --Dy 300.0
```

Reconstruction command shape:

```bash
source /cvmfs/ship.cern.ch/26.03/setUp.sh && \
eval "$(alienv load FairShip/latest-<branch>-release)" && \
cd <tmp_output_dir> && \
python3 <repo_root>/macro/ShipReco.py \
  -f <tmp_output_dir>/sim_ci-benchmark.root \
  -g <tmp_output_dir>/geo_ci-benchmark.root \
  -n 1000 \
  --realPR AR
```

The `cd <tmp_output_dir>` step is intentional. `ShipReco.py` writes `sim_<tag>_rec.root` into the current working directory, so the test changes directory before reconstruction to keep the reco file next to the simulation file.

Metrics command shape:

```bash
source /cvmfs/ship.cern.ch/26.03/setUp.sh && \
eval "$(alienv load FairShip/latest-<branch>-release)" && \
python3 - <<'PY'
import tracking_benchmark
bench = tracking_benchmark.TrackingBenchmark(
    r'<tmp_output_dir>/sim_ci-benchmark.root',
    r'<tmp_output_dir>/sim_ci-benchmark_rec.root',
    r'<tmp_output_dir>/geo_ci-benchmark.root',
)
metrics = bench.compute_metrics()
bench.save_json(r'<tmp_output_dir>/tracking_metrics.json')
bench.save_histograms(r'<tmp_output_dir>/tracking_benchmark_histos.root')
bench.print_summary()
PY
```

Validation method:

- checks that these files exist:
  - `sim_ci-benchmark.root`
  - `geo_ci-benchmark.root`
  - `params_ci-benchmark.root`
  - `sim_ci-benchmark_rec.root`
  - `tracking_metrics.json`
  - `tracking_benchmark_histos.root`
- checks that the histogram ROOT file is non-empty
- validates important tracking counters:
  - `n_events`
  - `n_reconstructible`
  - `n_total_reco`
  - `efficiency`
  - `clone_rate`
  - `ghost_rate`
  - `dp_over_p_sigma`
  - `dx_rms`
  - `dy_rms`
  - `dtx_rms`
  - `dty_rms`
- optionally compares the produced JSON to a reference if `FAIRSHIP_TRACKING_REFERENCE_JSON` is set

## Helper Scripts

### `tests/run_validation_sequence.py`

This script runs the full validation sequence in order:

1. build validation
2. muon-background summary validation
3. muon-background strict I/O validation
4. particle-gun strict I/O validation
5. Pythia8 validation
6. EvtGen validation
7. tracking benchmark validation

It also writes JUnit reports to:

- `test_reports/build.xml`
- `test_reports/simulation.xml`
- `test_reports/simulation_io.xml`
- `test_reports/particle_gun_io.xml`
- `test_reports/pythia8.xml`
- `test_reports/evtgen.xml`
- `test_reports/tracking.xml`

### `tests/regenerate_simulation_references.py`

This script regenerates the reference files used by the tests.

Current behavior by target:

- `muonback`
  - regenerates the numeric summary JSON with `5000` events by default
  - regenerates the strict ROOT I/O reference with `100` events by default
- `particle_gun`
  - regenerates the numeric summary JSON with `5000` events by default
  - regenerates the strict ROOT I/O reference with `100` events by default
- `pythia8`
  - regenerates the numeric summary JSON with `1000` events by default
- `evtgen`
  - regenerates the numeric summary JSON with `1000` events by default

The script uses fresh `/bin/bash -lc` shells for each phase, just like the tests.

If you pass `--verbose`, it prints every command and streams all subprocess output live.

## How To Run The Tests

Run the full suite:

```bash
cd /ship_build/FairShip
python3 tests/run_validation_sequence.py
```

Run a single test:

```bash
pytest -v tests/test_build_clean.py
pytest -v tests/test_simulation_validation.py
pytest -v tests/test_simulation_io.py
pytest -v tests/test_particle_gun_io.py
pytest -v tests/test_pythia8_validation.py
pytest -v tests/test_evtgen_validation.py
pytest -v tests/test_tracking_benchmark.py
```

Run a single test with live subprocess output:

```bash
export FAIRSHIP_SIM_TEST_DEBUG=1
pytest -s -v tests/test_simulation_validation.py
```

Equivalent debug flags exist for the other runtime tests:

- `FAIRSHIP_SIM_IO_TEST_DEBUG`
- `FAIRSHIP_PARTICLE_GUN_TEST_DEBUG`
- `FAIRSHIP_PYTHIA8_TEST_DEBUG`
- `FAIRSHIP_EVTGEN_TEST_DEBUG`
- `FAIRSHIP_TRACKING_TEST_DEBUG`

When a runtime test fails, it also writes the exact command and captured logs into its own `tmp_path`, for example:

- `*.command`
- `*.stdout`
- `*.stderr`

That is usually the fastest way to see the fully expanded command that `pytest` actually ran.

## How To Regenerate Reference Files

Regenerate everything:

```bash
cd /ship_build/FairShip
python3 tests/regenerate_simulation_references.py
```

Regenerate everything with live subprocess output:

```bash
python3 -u tests/regenerate_simulation_references.py --verbose
```

Regenerate one target only:

```bash
python3 tests/regenerate_simulation_references.py --target muonback
python3 tests/regenerate_simulation_references.py --target particle_gun
python3 tests/regenerate_simulation_references.py --target pythia8
python3 tests/regenerate_simulation_references.py --target evtgen
```

Override event counts explicitly:

```bash
python3 tests/regenerate_simulation_references.py \
  --muonback-events 5000 \
  --muonback-io-events 100 \
  --particle-gun-events 5000 \
  --particle-gun-io-events 100 \
  --pythia8-events 1000 \
  --evtgen-events 1000
```

## Common Environment Overrides

These are the most useful overrides when you need to adjust behavior:

- `FAIRSHIP_ALIENV_PACKAGE`
  Force a specific aliBuild package name for most tests.
- `FAIRSHIP_GIT_BRANCH`
  Override the branch name used to build the default aliBuild package name.
- `SHIP_TEST_INPUT`
  Override the default muon-background input ROOT file.
- `FAIRSHIP_SIM_TEST_REFERENCE_JSON`
  Override the muon-background summary reference JSON.
- `FAIRSHIP_SIM_IO_REFERENCE_ROOT`
  Override the muon-background strict I/O ROOT reference.
- `FAIRSHIP_PARTICLE_GUN_REFERENCE_ROOT`
  Override the particle-gun strict I/O ROOT reference.
- `FAIRSHIP_PYTHIA8_REFERENCE_JSON`
  Override the Pythia8 summary reference JSON.
- `FAIRSHIP_EVTGEN_REFERENCE_JSON`
  Override the EvtGen summary reference JSON.
- `FAIRSHIP_TRACKING_REFERENCE_JSON`
  Override the tracking benchmark reference JSON.

Generator-specific event-count overrides:

- `FAIRSHIP_SIM_TEST_EVENTS`
- `FAIRSHIP_SIM_IO_TEST_EVENTS`
- `FAIRSHIP_PARTICLE_GUN_TEST_EVENTS`
- `FAIRSHIP_PYTHIA8_TEST_EVENTS`
- `FAIRSHIP_EVTGEN_TEST_EVENTS`
- `FAIRSHIP_TRACKING_TEST_EVENTS`

Important:

- `FAIRSHIP_SIM_IO_TEST_EVENTS` must be `<= 100`
- `FAIRSHIP_PARTICLE_GUN_TEST_EVENTS` must be `<= 100`

## Validation Strategy

This suite intentionally uses two different validation styles.

### 1. Numeric summary validation

Used for:

- muon-background summary validation
- Pythia8 validation
- EvtGen validation

Why:

- much faster than comparing full ROOT files event by event
- still catches structural and statistical regressions
- stores compact references as JSON instead of large ROOT files

### 2. Strict event-by-event ROOT I/O validation

Used for:

- muon-background I/O validation
- particle-gun I/O validation

Why:

- useful for catching low-level I/O or branch-layout regressions
- intentionally limited to small event counts to keep runtime practical

That split is deliberate:

- heavier generator/regression tests use compact numeric references
- strict ROOT-file comparisons are kept where they add the most value
