# Publishing to GitHub

Run from the repository root with the virtual environment active. Use Git so
`.gitignore` excludes environments, caches, logs, private settings, scenario
backups and temporary runs. Scientific outputs and attributed HERMES data remain.

## Local checks

```bash
python -m pip check
python -m pytest -q
node --test tests/test_exit_editor.cjs
python -m pip wheel --no-deps . --wheel-dir dist
```

On PowerShell without activation, replace `python` with `.\.venv\Scripts\python.exe`.
Node.js is only needed for editor tests. The wheel includes server HTML, JavaScript
and CSS; datasets and archived outputs remain repository assets.

## First upload

Create an empty GitHub repository in your account, then run:

```bash
git init -b main
git add .
git status --short
git diff --cached --stat
git commit -m "Initial research studio release"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

Replace the URL with your own repository. Review staged files before committing.
If the folder already has Git history, skip initialization and use its branch
and remote. Authentication is handled by your Git installation.

Preparation does not create a remote or upload files. After pushing, check the
Actions tab and README images. Remote CI can only be confirmed after GitHub
executes it. Preserve dataset attribution in THIRD_PARTY_NOTICES.md.

Guides live in `docs/`. Completed preparation notes were consolidated into
CHANGELOG.md and docs/MODEL_STATUS.md. Local studies/backups remain ignored.
BENCHMARK_REPORT.md is optional generated documentation; review before adding it.
