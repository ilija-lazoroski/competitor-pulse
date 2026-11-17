# Competitor Pulse

## Configuration

Configure the backend before anything else: it does not start until its required settings are
set. Settings come from `CP_*` environment variables, or from a `.env` file whose path is in
`CP_CONFIG_PATH`.

All options, with their defaults and which ones are required, are listed in
[CONFIGURATION.md](CONFIGURATION.md).
```

Or start from the example file, which has the local development values:

```bash
cp .env.example .env
export CP_CONFIG_PATH=.env
```

## Development setup

Install [pre-commit](https://pre-commit.com) once per machine, then enable the hooks in each clone:

```bash
pipx install pre-commit   # or: brew install pre-commit
pre-commit install        # installs the pre-commit, prepare-commit-msg and commit-msg hooks
```

If `pre-commit install` refuses because `core.hooksPath` is set (e.g. by the old commit-guard tool),
remove the global hook path first:

```bash
git config --global --unset core.hooksPath
```
