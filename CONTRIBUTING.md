# Contributing

1. Fork and clone the repo
2. `python -m venv .venv && source .venv/bin/activate`
3. `pip install -e ".[dev]"`
4. Make changes, add tests, run `pytest`
5. Open a pull request

## Good first issues

- Add `--recursive` flag to `ls` to list all objects without delimiter grouping
- Add `cp` subcommand to copy objects between buckets
- Add `rm` subcommand to delete objects (with `--dry-run` safety)
- Add `--output-format table` for a formatted table view in `ls`
