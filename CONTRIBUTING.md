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
# Install uv (https://docs.astral.sh/uv/getting-started/installation/), then:
uv sync
```

`uv sync` creates `.venv`, installs the library in editable mode, and installs the
dev dependency group (pytest, ruff, mypy, pre-commit and friends) — all at the
exact versions recorded in `uv.lock`.

## Local checks

Before opening a PR, make sure all of these pass locally:

```bash
uv run ruff check dimplex_controller tests
uv run ruff format --check dimplex_controller tests
uv run mypy
uv run pytest
```

Or, install the pre-commit hooks once and let them run on every commit:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

The hooks cover whitespace, file endings and formatting (`ruff-check`,
`ruff-format`, the `pre-commit-hooks` set). **mypy and pytest run in CI but are not
hooks**, so the four commands above are still yours to run before opening a PR.

Run the hooks through `uv run`: the ruff hooks execute the environment's ruff
(`language: system`), so `uv.lock` is the single source of the ruff version — there
is no second pin in `.pre-commit-config.yaml` to drift from it.

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

The repository needs one secret for that first step to work smoothly:
**`RELEASE_PLEASE_TOKEN`**, a fine-grained PAT with `Contents: read/write` and
`Pull requests: read/write` on this repository. Without it, release-please runs as
`github-actions[bot]`, and bot-authored commits put their workflow runs into
`action_required` with no jobs created — so the release PR sits `BLOCKED` on a
required `ci` check that never runs, until someone approves the runs by hand. The
workflow falls back to the default token when the secret is absent, so adding it is
an improvement rather than a prerequisite.

## Any contributions you make will be under the MIT Software License

In short, when you submit code changes, your submissions are understood to be
under the same [MIT License](http://choosealicense.com/licenses/mit/) that
covers the project.
