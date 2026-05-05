# Tests

Centralised test root for the project. Both human-driven smoke tests
(shell scripts that orchestrate real processes) and future
pytest-driven unit tests live here so CI can run them all from one
place.

## Layout

```
tests/
  conftest.py    pytest config shared across all suites — adds the
                 repository's bridges/ folder to PYTHONPATH so test
                 modules can `import rns_tcp_bridge` etc.
  smoke/         end-to-end smoke tests; spin up real bridge
                 processes and assert observable behaviour. Slow but
                 high signal. No mocks.
  unit/          (planned) fast pytest unit tests for individual
                 modules. Should never touch the network.
```

## Running locally

From the repository root:

```bash
pip install pytest rns
pytest tests/                          # everything
pytest tests/smoke/                    # only smoke
pytest tests/smoke/test_rns_tcp_bridge.py -v   # one file, verbose
```

## CI

Smoke tests are designed to be CI-runnable: each script provisions its
own temporary working directory under `/tmp`, never writes to the
operator's `~/.reticulum`, and tears down its background processes via
a `trap` on exit. A future GitHub Actions workflow will run them on
every push.
