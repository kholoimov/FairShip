# FairShip tests

The `tests` directory contains two complementary test suites:

- C++ unit and I/O tests registered with CTest.
- Pytest regression tests that compare terminal output with committed
  reference files.

## C++ and CTest tests

The C++ tests are declared in `CMakeLists.txt`, built with FairShip, and run
through CTest.

Using Pixi:

```sh
pixi run test
```

Using an existing build directory:

```sh
cmake --build build
ctest --test-dir build --output-on-failure
```

To run one test by name:

```sh
ctest --test-dir build --output-on-failure -R DataClassIO
```

New C++ tests should be added as executables in `tests/CMakeLists.txt` and
registered with `add_test()`.

## FairShip regression tests

The `fairship_tests` suite runs shell-configured commands, captures their
combined standard output and standard error, and compares the result with
reference text files committed under `fairship_tests/references`.

Run the suite with:

```sh
pytest tests/fairship_tests -n auto --maxprocesses 4 --dist loadgroup
```

or:

```sh
pixi run test-fairship
```

### Adding a FairShip regression test

All FairShip regression tests are configured in
`fairship_tests/test_cases.yaml`. To add a test:

1. Add its name to the `tests` list in `test_cases.yaml`.
2. Create an executable `fairship_tests/scripts/TEST_NAME.sh` file containing
   the command.
3. Regenerate the reference files.
4. Review and commit the generated
   `fairship_tests/references/TEST_NAME.txt` file.

Test names may contain letters, numbers, dots, underscores, and hyphens.
A nonzero exit status fails the test, even if its output matches the reference.

The YAML configuration contains only test names:

```yaml
tests:
  - example
```

Tests that depend on other tests use `name` and `depends_on`:

```yaml
tests:
  - simulation
  - name: reconstruction
    depends_on:
      - simulation
```

Dependencies are executed and checked before the dependent test. Unknown
dependencies, self-dependencies, duplicate dependencies, and dependency cycles
are rejected as configuration errors. Each successfully completed test runs
only once in the pytest process.

The suite uses pytest-xdist's `loadgroup` scheduler. Dependency-connected tests
are assigned to the same worker process and run sequentially in a temporary
directory dedicated to their dependency group. Independent groups use isolated
directories and can execute concurrently.

For each test name, the harness automatically locates:

- The executable script at `fairship_tests/scripts/TEST_NAME.sh`.
- The reference output at `fairship_tests/references/TEST_NAME.txt`.

The script and reference filenames must use exactly the configured test name.

FairShip regression scripts execute in temporary working directories organized
by dependency group. Outputs from dependencies remain available to dependent
tests, unrelated groups are isolated, and generated files are not written to
the repository. Each worker's temporary root is removed when it exits.

The harness provides the repository root through the `FAIRSHIP_ROOT`
environment variable. Scripts should use it for repository-relative programs
and input files:

```sh
python "$FAIRSHIP_ROOT/macro/example.py"
```

Other relative paths resolve inside the temporary working directory.

Pass `--keep-output` to preserve that directory for inspection:

```sh
pytest tests/fairship_tests -n auto --maxprocesses 4 --dist loadgroup --keep-output
# or
pixi run pytest tests/fairship_tests -n auto --maxprocesses 4 --dist loadgroup --keep-output
```

Pytest prints retained worker-root paths at the end of the run. Each dependency
group has a named subdirectory inside its worker root. Without the flag, these
directories are removed automatically.

### Nondeterministic output

`fairship_tests/skip_patterns.conf` contains full-line wildcard patterns for
lines that should be excluded from comparison. An asterisk (`*`) matches any
text, while all other characters are matched literally. Start a block with
`test NAME` and list its patterns on the following lines. Use `test *` for
patterns that apply to every test:

```ini
test *
  Timestamp: *

test example-test
  Processing time: * s
```

Patterns must match the complete line. Keep them as narrow as possible because
matching lines are removed before validation.

### Regenerating references

After an intentional output change, regenerate all reference files with:

```sh
tests/fairship_tests/regenerate_references.sh
```

or:

```sh
pixi run regenerate-fairship-references
```

The regeneration command updates the configured reference file for every test.
Always review the resulting diff before committing it.

More implementation details are available in
[`fairship_tests/README.md`](fairship_tests/README.md).
