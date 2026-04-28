# FairShip Validation Tests

The runtime validation suite is now driven by:

- one shared runner: [tests/fairship_validation_runner.py](/Users/vkholoimov/Documents/SHIP/FairShip/tests/fairship_validation_runner.py)
- one YAML test matrix: [tests/fairship_validation_cases.yaml](/Users/vkholoimov/Documents/SHIP/FairShip/tests/fairship_validation_cases.yaml)
- one parametrized pytest entrypoint: [tests/test_fairship_validation_matrix.py](/Users/vkholoimov/Documents/SHIP/FairShip/tests/test_fairship_validation_matrix.py)

This replaces the old pattern of having one dedicated pytest file per simulation mode.

## What The Matrix Supports

Each YAML test case can define:

- one or more runtime steps
- FairShip simulation commands
- follow-up validation commands
- required output files
- text-based validation against reference YAML snapshots
- strict ROOT comparison checks

That lets one case run FairShip once or twice, depending on what needs to be validated.

## Current Runtime Cases

The YAML matrix currently covers:

- muon-background summary validation
- muon-background strict ROOT I/O validation
- particle-gun strict ROOT I/O validation
- Pythia8 summary validation
- EvtGen summary validation

Summary-style tests compare a normalized YAML snapshot against reference files in:

- [tests/reference/muonback_fast_100.yaml](/Users/vkholoimov/Documents/SHIP/FairShip/tests/reference/muonback_fast_100.yaml)
- [tests/reference/pythia8_reference_run.yaml](/Users/vkholoimov/Documents/SHIP/FairShip/tests/reference/pythia8_reference_run.yaml)
- [tests/reference/evtgen_reference_run.yaml](/Users/vkholoimov/Documents/SHIP/FairShip/tests/reference/evtgen_reference_run.yaml)

Strict ROOT I/O tests still use the existing ROOT references.

## Other Tests

The following tests remain separate because they are not part of the runtime simulation matrix:

- [tests/test_build_clean.py](/Users/vkholoimov/Documents/SHIP/FairShip/tests/test_build_clean.py)
- [tests/test_tracking_benchmark.py](/Users/vkholoimov/Documents/SHIP/FairShip/tests/test_tracking_benchmark.py)
- C++ I/O tests from [tests/CMakeLists.txt](/Users/vkholoimov/Documents/SHIP/FairShip/tests/CMakeLists.txt)

## Running The Tests

Run the runtime matrix:

```bash
python3 -m pytest -v tests/test_fairship_validation_matrix.py
```

Run one case only:

```bash
python3 -m pytest -v tests/test_fairship_validation_matrix.py -k muonback_summary
```

Run the full Python validation sequence:

```bash
python3 tests/run_validation_sequence.py
```

## Environment Assumptions

Runtime tests assume:

- the checkout is `FairShip`
- commands are launched from the parent directory of the checkout
- CVMFS is available at `/cvmfs/ship.cern.ch/26.03/setUp.sh`
- the local FairShip package can be loaded via `alienv`

Each runtime step is executed in a fresh shell:

```bash
/bin/bash -lc '<command>'
```

## Environment Overrides

The matrix keeps the existing environment-variable overrides for compatibility.

Examples:

- `FAIRSHIP_SIM_TEST_EVENTS`
- `FAIRSHIP_SIM_IO_TEST_EVENTS`
- `FAIRSHIP_PARTICLE_GUN_TEST_EVENTS`
- `FAIRSHIP_PYTHIA8_TEST_EVENTS`
- `FAIRSHIP_EVTGEN_TEST_EVENTS`
- `SHIP_TEST_INPUT`
- `FAIRSHIP_ALIENV_PACKAGE`

Case-specific workdir, tag, debug, and reference overrides are defined directly in:

- [tests/fairship_validation_cases.yaml](/Users/vkholoimov/Documents/SHIP/FairShip/tests/fairship_validation_cases.yaml)

## Regenerating References

Use:

```bash
python3 tests/regenerate_simulation_references.py
```

This now regenerates:

- normalized YAML summary references
- strict ROOT references for the I/O comparison cases
