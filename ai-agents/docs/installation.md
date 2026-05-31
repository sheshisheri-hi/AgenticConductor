# Installation Guide

This guide covers all ways to install Conductor packages depending on your use case.

---

## Option 1 — Local Development (Recommended for contributors)

Clone the repo and install all packages in editable mode:

```bash
git clone https://github.com/sheshisheri-hi/AgenticConductor.git
cd AgenticConductor/ai-agents

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

make setup
```

`make setup` runs `pip install -e` for all packages in dependency order:
1. `conductor-core` (base)
2. `conductor-agents` (depends on core)
3. `conductor-integrations` (depends on core)
4. `consumer-showcase` (depends on all)
5. `conductor-cli` (depends on core)

To install individually:
```bash
pip install -e "conductor-core[dev]"
pip install -e "conductor-agents[dev]"
pip install -e "conductor-integrations[dev]"
pip install -e "consumer-showcase[dev]"
pip install -e "conductor-cli[dev]"
```

> **Note:** `*.egg-info` folders created by editable installs are excluded by `.gitignore` and are safe to ignore.

---

## Option 2 — Install from GitHub (Recommended for consumers)

Install directly from the GitHub repo without cloning:

```bash
# Install a specific package
pip install "git+https://github.com/sheshisheri-hi/AgenticConductor.git#subdirectory=ai-agents/conductor-core"
pip install "git+https://github.com/sheshisheri-hi/AgenticConductor.git#subdirectory=ai-agents/conductor-agents"
pip install "git+https://github.com/sheshisheri-hi/AgenticConductor.git#subdirectory=ai-agents/conductor-integrations"
pip install "git+https://github.com/sheshisheri-hi/AgenticConductor.git#subdirectory=ai-agents/conductor-cli"
```

Pin to a specific release tag:
```bash
pip install "git+https://github.com/sheshisheri-hi/AgenticConductor.git@v1.0.0#subdirectory=ai-agents/conductor-core"
```

Or pin in `requirements.txt`:
```
git+https://github.com/sheshisheri-hi/AgenticConductor.git@v1.0.0#subdirectory=ai-agents/conductor-core
git+https://github.com/sheshisheri-hi/AgenticConductor.git@v1.0.0#subdirectory=ai-agents/conductor-agents
```

---

## Option 3 — Publish to Artifactory / PyPI (Production/Enterprise)

Use this when:
- Multiple teams consume these packages **without cloning the repo**
- You need **pinned versioned releases** (`pip install conductor-core==1.2.0`)
- CI/CD pipelines of downstream projects need `pip install conductor-core`

### Build packages

```bash
cd ai-agents
pip install build

# Build each package
python -m build conductor-core/
python -m build conductor-agents/
python -m build conductor-integrations/
python -m build conductor-cli/
```

### Publish to Artifactory

```bash
pip install twine

twine upload \
  --repository-url https://your-artifactory.example.com/artifactory/api/pypi/python-local/ \
  --username $ARTIFACTORY_USER \
  --password $ARTIFACTORY_TOKEN \
  conductor-core/dist/*
```

### Publish to public PyPI

```bash
twine upload conductor-core/dist/*
```

### Install from Artifactory

After publishing, consumers install with:
```bash
pip install conductor-core \
  --index-url https://your-artifactory.example.com/artifactory/api/pypi/python-local/simple/
```

Or configure `pip.conf`:
```ini
[global]
index-url = https://your-artifactory.example.com/artifactory/api/pypi/python-local/simple/
```

---

## GitHub Actions CI/CD — Auto-publish on tag

Add `.github/workflows/publish.yml` to auto-publish when you push a version tag (`v1.0.0`):

```yaml
name: Publish packages

on:
  push:
    tags: ["v*"]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install build twine
      - name: Build all packages
        run: |
          cd ai-agents
          python -m build conductor-core/
          python -m build conductor-agents/
          python -m build conductor-integrations/
          python -m build conductor-cli/
      - name: Publish to Artifactory
        env:
          ARTIFACTORY_USER: ${{ secrets.ARTIFACTORY_USER }}
          ARTIFACTORY_TOKEN: ${{ secrets.ARTIFACTORY_TOKEN }}
        run: |
          cd ai-agents
          for pkg in conductor-core conductor-agents conductor-integrations conductor-cli; do
            twine upload \
              --repository-url https://your-artifactory.example.com/artifactory/api/pypi/python-local/ \
              --username $ARTIFACTORY_USER --password $ARTIFACTORY_TOKEN \
              $pkg/dist/*
          done
```

---

## Package dependency tree

```
conductor-cli
    └── conductor-core

consumer-showcase
    ├── conductor-core
    ├── conductor-agents
    └── conductor-integrations

conductor-agents
    └── conductor-core

conductor-integrations
    └── conductor-core

conductor-core
    (no internal deps)
```

Always install `conductor-core` first.
