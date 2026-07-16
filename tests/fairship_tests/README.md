# FairShip regression tests

These pytest tests run shell scripts declared in `test_cases.yaml` and compare
their combined standard output and standard error with configured reference
files.

To add a test:

1. Add the test name to the `tests` list in `test_cases.yaml`.
2. Create an executable `scripts/TEST_NAME.sh` file containing the test
   command.
3. Run `tests/fairship_tests/regenerate_references.sh`.
4. Review and commit the generated `references/TEST_NAME.txt` file.

The YAML configuration contains only test names:

```yaml
tests:
  - example
```

To run a test only after other tests have completed successfully, use a mapping
with `name` and `depends_on`:

```yaml
tests:
  - simulation
  - name: reconstruction
    depends_on:
      - simulation
```

Dependencies may themselves have dependencies. The harness validates that
every dependency exists and rejects dependency cycles. When a dependent test
is run, all of its dependencies are executed and checked first. A successfully
completed test is run only once in the pytest process, even when multiple tests
depend on it.

The suite uses pytest-xdist with `--dist loadgroup`. Tests connected through
dependencies are assigned to the same worker process and share a temporary
directory dedicated to that dependency group. They run sequentially within the
worker, so generated files are available to dependent tests without file
races. Independent groups use separate directories and can run concurrently.

For a test named `example`, the harness automatically uses:

- `scripts/example.sh` as the executable test script.
- `references/example.txt` as the expected terminal output.

Test names may contain letters, numbers, dots, underscores, and hyphens. The
script filename and reference filename must use exactly the same test name.

Test scripts run in temporary working directories organized by dependency
group. Tests in the same dependency-connected graph share a directory, while
unrelated groups are isolated. This allows dependent tests to use files
produced by their dependencies without writing generated output into the
repository. The temporary worker root is removed when the process exits.

The harness sets `FAIRSHIP_ROOT` to the repository root. Scripts should use it
when referring to repository files:

```sh
python "$FAIRSHIP_ROOT/macro/example.py"
```

Relative input and output paths inside a test script refer to the temporary
working directory.

To preserve the working directory and inspect generated files, pass
`--keep-output` to pytest:

```sh
pytest tests/fairship_tests -n auto --maxprocesses 4 --dist loadgroup --keep-output
```

With Pixi:

```sh
pixi run pytest tests/fairship_tests -n auto --maxprocesses 4 --dist loadgroup --keep-output
```

At the end of the run, pytest prints each retained worker root. Inside it,
every dependency group has its own subdirectory named after the group's first
configured test. Without this flag, the directories are deleted automatically.

Run the tests with:

```sh
pytest tests/fairship_tests -n auto --maxprocesses 4 --dist loadgroup
# or
pixi run test-fairship
```

Regenerate every reference after an intentional output change with:

```sh
tests/fairship_tests/regenerate_references.sh
# or
pixi run regenerate-fairship-references
```

`skip_patterns.conf` contains full-line wildcard patterns for output that is
expected to vary. An asterisk (`*`) matches any text; all other characters are
matched literally. Start a block with `test NAME` and list its patterns on the
following lines. Use `test *` for patterns that apply to every test. Use this
sparingly, because skipped lines are excluded from validation.
