# Pytest integration tests

These tests keep `pytest` very thin and reuse the existing FairShip command-line
scripts.

## Run locally

The recommended entrypoint is the wrapper script in [`tests/run_pytests_after_build.sh`](../run_pytests_after_build.sh).
It:

- sources the SHiP CVMFS release
- runs `aliBuild build FairShip` from the parent directory that contains the
  `FairShip/` checkout
- loads the resulting `alienv` environment
- runs `pytest` from the FairShip repository root

Example with SHiP release `26.05`:

```bash
cd /Users/vkholoimov/Documents/SHIP/FairShip
SHIP_RELEASE=26.05 tests/run_pytests_after_build.sh
```

Extra pytest arguments are forwarded:

```bash
SHIP_RELEASE=26.05 tests/run_pytests_after_build.sh -k overlaps -s
```

If you already built FairShip and loaded the environment manually, you can also
run pytest directly:

```bash
python3 -m pytest tests/integration -m integration
```

If the runtime is not configured, the tests skip instead of failing during
collection.

## Add a new test

Use one of the existing fixtures from `conftest.py`:

- `run_fairship`: runs one repository script in an isolated temporary working
  directory and fails with captured stdout/stderr if the command exits non-zero.
- `sim_chain`: builds one reusable simulation/reconstruction/analysis chain for
  the test session and returns the generated file paths.

Most new tests can stay very small:

```python
def test_something(sim_chain, run_fairship):
    run_fairship(
        "path/to/script.py",
        "--input",
        sim_chain.sim_file.name,
        cwd=sim_chain.workdir,
    )
    assert (sim_chain.workdir / "expected_output.root").exists()
```
