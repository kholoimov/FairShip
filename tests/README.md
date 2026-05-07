# Pytest simulation workflow

The simulation reference workflow is driven by [`tests/pytest_reference_cases.toml`](/Users/vkholoimov/Documents/SHIP/FairShip/tests/pytest_reference_cases.toml).
Each case has:

- a `bash` command
- a link to the `.ref` file that stores the expected command/result/output contract

The `.ref` files are intentionally simple. They check:

- the command
- the return code
- required `stdout`/`stderr` fragments
- whether the expected output files were created

They do not inspect ROOT contents.

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

The current dummy commands are:

- [`tests/scripts/run_particle_gun.sh`](/Users/vkholoimov/Documents/SHIP/FairShip/tests/scripts/run_particle_gun.sh)
- [`tests/scripts/run_fast_muon_dummy.sh`](/Users/vkholoimov/Documents/SHIP/FairShip/tests/scripts/run_fast_muon_dummy.sh)
