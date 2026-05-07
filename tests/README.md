# Pytest simulation workflow

The simulation reference workflow is driven by [`tests/pytest_reference_cases.toml`](/Users/vkholoimov/Documents/SHIP/FairShip/tests/pytest_reference_cases.toml).
Each case has:

- a `bash` command
- a link to the `.ref` file that stores the expected stdout snapshot

Before the simulation command runs, the helper scripts source the FairShip environment via:

```bash
source /cvmfs/ship.cern.ch/${SHIP_RELEASE:-26.04}/setUp.sh
```

If a local aliBuild environment exists under `../sw/*/FairShip/latest`, the helper scripts source that local `init.sh` directly. Otherwise they fall back to `alienv load`.

You can override the fallback package name with `FAIRSHIP_ALIENV_PACKAGE`.

The `.ref` files are intentionally simple. Pytest checks:

- the command from [`tests/pytest_reference_cases.toml`](/Users/vkholoimov/Documents/SHIP/FairShip/tests/pytest_reference_cases.toml)
- the return code from the TOML case
- the full normalized `stdout` against the `.ref` file
- whether any optional `expected_outputs` listed in the TOML case were created

The `.ref` files can be created from a real command run, for example:

```bash
bash tests/scripts/run_particle_gun.sh | tee tests/reference/particle_gun_io.ref
```

Run the workflow with:

```bash
pytest tests/test_simulation_references.py
```

To run cases in parallel with `pytest-xdist`:

```bash
pytest -n auto tests/test_simulation_references.py
```

Or only the reference suite:

```bash
pytest -n auto -m reference
```

Regenerate references with:

```bash
bash tests/regenerate_references.sh
```

You can also regenerate in parallel if your environment supports it:

```bash
bash tests/regenerate_references.sh -n auto
```

Each case writes into its own temporary output directory, so parallel workers do not share generated ROOT files.

The current commands mirror the earlier runtime cases from `dev_vkholoim_pytest_implementation`:

- [`tests/scripts/run_build_clean.sh`](/Users/vkholoimov/Documents/SHIP/FairShip/tests/scripts/run_build_clean.sh)
- [`tests/scripts/run_particle_gun.sh`](/Users/vkholoimov/Documents/SHIP/FairShip/tests/scripts/run_particle_gun.sh)
- [`tests/scripts/run_muonback_io.sh`](/Users/vkholoimov/Documents/SHIP/FairShip/tests/scripts/run_muonback_io.sh)
- [`tests/scripts/run_muonback_summary.sh`](/Users/vkholoimov/Documents/SHIP/FairShip/tests/scripts/run_muonback_summary.sh)
- [`tests/scripts/run_pythia8_summary.sh`](/Users/vkholoimov/Documents/SHIP/FairShip/tests/scripts/run_pythia8_summary.sh)
- [`tests/scripts/run_evtgen_summary.sh`](/Users/vkholoimov/Documents/SHIP/FairShip/tests/scripts/run_evtgen_summary.sh)
- [`tests/scripts/run_tracking_benchmark.sh`](/Users/vkholoimov/Documents/SHIP/FairShip/tests/scripts/run_tracking_benchmark.sh)

The muonback case needs an input file. Point it to one with:

- `SHIP_TEST_INPUT`
- `FAIRSHIP_SIM_IO_TEST_INPUT`
- `FAIRSHIP_SIM_TEST_INPUT`
