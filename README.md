# gitbare

`gitbare` exports local Git working copies to YAML and restores them later.

## Development

```bash
uv venv
uv run python -m unittest discover -s tests -v
uv run python -m gitbare --help
```

## Installed CLI

```bash
gitbare --help
gitbare > git.yml
cat git.yml | gitbare --dry-run
gitbare --import repo.yml
gitbare --export repo.yml
```

## Remote usage

```bash
uvx --from git+https://github.com/aheimsbakk/gitbare.git gitbare --help
uvx --from git+https://github.com/aheimsbakk/gitbare.git gitbare > git.yml
cat git.yml | uvx --from git+https://github.com/aheimsbakk/gitbare.git gitbare --pull
uv tool install git+https://github.com/aheimsbakk/gitbare.git
gitbare --help
```

## Notes

- Source code lives under `src/`.
- Tests live under `tests/`.
- Export warnings and verbose logs go to `stderr`.
- `--verbose` prints ordered progress counters for each repository plus discovery mode, selected remotes, dry-run planning, restore steps, and dirty/local-only item paths.
- Backups that rely on local filesystem remotes may not restore correctly on different machines or paths.
