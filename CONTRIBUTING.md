# Contribution guidelines

> **This is an unofficial project.** It is not affiliated with, endorsed by, or supported by
> Dimplex, Glen Dimplex Heating & Ventilation, or the Glen Dimplex Group. The protocol was
> recovered by reverse-engineering the official Dimplex Control app. No Dimplex code is
> included or redistributed.
>
> Contributions must respect that boundary: describe behaviour observed from the official app
> or from your own hardware, and cite decompiled findings as notes — but do not commit
> decompiled Dimplex source, proprietary assets, APK binaries, or credentials to this
> repository.

Contributing to this project should be as easy and transparent as possible.

## Development setup

```bash
# Install Poetry (https://python-poetry.org/docs/#installation), then:
poetry install
```

This will install the library, all dev dependencies (pytest, ruff,
pre-commit, mypy) into a project-local venv.

## Local checks

Before opening a PR, make sure all of these pass locally:

```bash
poetry run ruff check dimplex_controller tests
poetry run ruff format --check dimplex_controller tests
poetry run mypy
poetry run pytest
```

Or, install the pre-commit hooks once and let them run on every commit:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

The hooks cover whitespace, file endings and formatting (`ruff`, `ruff-format`,
the `pre-commit-hooks` set). **mypy and pytest run in CI but are not hooks**, so
the four commands above are still yours to run before opening a PR.

Ruff's effective pin is the `ruff-pre-commit` `rev:` in
`.pre-commit-config.yaml`: pre-commit provisions that version, and the CI `lint`
job installs the same one. The `ruff` requirement in `pyproject.toml` is a
compatible range for `poetry run ruff`, so the hook revision is what the repo
agrees on.

## Optional: open a PR automatically on push

`.githooks/post-push` opens a PR for the branch you just pushed, using
`gh pr create --fill` with the latest commit message as the title. It is opt-in
per clone — nothing enables it for you:

```console
$ git config core.hooksPath .githooks
```

It needs the [GitHub CLI](https://cli.github.com/) installed and authenticated
(`gh auth login`), and it skips `main`. Because it opens the PR immediately, it
suits a branch-per-PR workflow where you are happy to review on GitHub rather
than before pushing.

## Pull requests

1. Fork the repo and create your branch from `main`.
2. If you've changed something, update the README / docstrings.
3. Use a [Conventional Commit](https://www.conventionalcommits.org/) PR title
   (`fix:`, `feat:`, `chore:` …) — this drives the automated changelog/release
   via release-please.
4. Issue that pull request!

### Required checks before merge to `main`

The `main` branch ruleset requires:

* a **pull request** (squash merge only; no force-push / branch delete)
* a green **`ci`** status check
* **signed commits** (repo-wide rule on all branches)

When your PR changes library code (`dimplex_controller/`), tests, lockfiles, or
`.github/workflows/test.yml`, CI runs **lint**, **pre-commit**, and **pytest**
on Python 3.10–3.13. The aggregate `ci` job fails unless all of those succeed.

Docs-only PRs still get a green `ci` without the full matrix.

## Releases

Releases are managed by [release-please](https://github.com/googleapis/release-please).
Merging a release-please PR will:

* tag the release on `main`
* publish the new version to PyPI via the `publish-to-pypi.yml` workflow
  (uses the `pypi` environment, requires the trusted-publisher OIDC trust to
  be configured in PyPI project settings).

## Any contributions you make will be under the MIT Software License

In short, when you submit code changes, your submissions are understood to be
under the same [MIT License](http://choosealicense.com/licenses/mit/) that
covers the project.
