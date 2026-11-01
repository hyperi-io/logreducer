# Testing

The general rules are hyperi-ai's testing standard (`standards/universal/testing.md` in hyperi-ai). This page covers what logreducer does on top of them.

| Level | Runs | Command |
|---|---|---|
| core | locally, every push and PR | `hyperi-ci run test`, or `uv run pytest` |
| full | nightly (`schedule` in `.github/workflows/ci.yml`) and before every release (`test.full.required_for_release: true`) | `hyperi-ci run test --tier full` |

`addopts` deselects nothing, so core and full run the same tests today. The full tier is what a release waits on. A test that grows slow enough to move out of core gets a marker and an `addopts -m` deselect, and full still runs it.

ClickHouse and Kafka are the run's shared services from scalo-py's test plugin, loaded in `tests/conftest.py`. That's one container per service per run, shared by every xdist worker, with a database or topics of its own for each test. The images, the naming and the clean-up are scalo-py's, in its `tests/TESTING.md`. `HYPERI_TEST_*` settings point a local run at an existing ClickHouse or Kafka instead.

PostgreSQL (`postgres:16.6`) and MySQL (`mysql:8.4.5`) are throwaway testcontainers in `tests/integration/conftest.py`, because the plugin doesn't provide them. Each starts once per session and stops when it ends. `LOGREDUCER_KEEP_CONTAINERS=1` leaves them running, and without Docker those tests skip. Unit tests (`tests/unit/`) use no container.
