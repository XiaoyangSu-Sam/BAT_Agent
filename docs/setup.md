# Setup and updates

## Choose Python

Use an approved Python 3.11 or later (3.12 is recommended). The server and Skills use the same Python by default. Use the interpreter that already has your Skill dependencies, or set python_executable in config/execution.yaml.

Do not copy a virtual environment from another computer. Do not run dependency synchronization on a shared environment: it may remove unrelated packages. The commands below install into the selected interpreter without intentionally removing other packages.

## Install

For a new environment on Windows:

~~~powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e .
~~~

With an existing uv installation, the equivalent is:

~~~powershell
uv pip install --python .venv/Scripts/python.exe -e .
~~~

Use your organization's approved package index, proxy and certificate settings. These commands install dependencies; they do not download Python or browsers. If the network is unavailable, use an approved offline wheel directory:

~~~powershell
./.venv/Scripts/python.exe -m pip install --no-index --find-links C:/approved-wheels -e .
~~~

That directory must include all dependencies and build requirements, including hatchling and its dependencies. Do not disable TLS validation or change organizational controls to make installation succeed. If a dependency is denied, record its name and ask the environment administrator for an approved source.

For notebooks, install the optional extra with the same interpreter: python -m pip install -e ".[notebook]". A Skill that imports Playwright or another package also needs that package in its execution interpreter. Reuse an approved existing browser installation as supported by the Skill; BAT Agent does not install browsers.

## Check and run

~~~powershell
./.venv/Scripts/python.exe scripts/check_environment.py
./.venv/Scripts/python.exe -m agent_harness
~~~

The check is local only: it checks dependencies, bundled UI assets, configuration validity and direct Skill folder layout. It does not contact a model or print configuration values. Exit code 0 means local prerequisites passed, 1 means an issue needs fixing. Missing notebook/Playwright support is informational unless your Skill needs it.

Open http://127.0.0.1:8765. For a different local port, add --port 8766. Stop the terminal with Ctrl+C. Start from the project folder, or supply --root with its absolute path.

Configuration is optional. On a fresh install, use the connection page, or enter the workspace without a model. Leave API Key blank when the service does not require it. Do not copy all example YAML files blindly.

## Update or replace an existing folder

Download the release ZIP or GitHub source ZIP and extract it to a separate folder outside the destination repository. Stop the destination's running BAT Agent server yourself and close files being edited. Do not run the replacement helper while the destination is in use.

Run these commands with Python from the extracted folder, replacing the destination path:

~~~powershell
python scripts/deploy.py --target C:/work/my-project
python scripts/deploy.py --target C:/work/my-project --apply
~~~

The first command only validates and previews changes. The second makes a timestamped backup next to the destination, stages the verified files, and replaces the application code. It removes obsolete files inside managed code/documentation directories.

For a fresh configuration and conversation store, use this explicit replacement command instead:

~~~powershell
python scripts/deploy.py --target C:/work/my-project --reset-local --apply
~~~

--reset-local moves config/model.yaml, config/environment.yaml, config/execution.yaml and .harness into the backup. The new app starts with no saved connection or session state. Existing LLM_* environment variables still apply; remove obsolete overrides in the launching terminal if you intend a completely blank connection setup.

Preserved: .git, .github, AGENTS.md, .venv, existing skills/, workspace/, real configuration and .harness (unless --reset-local). Git ignore/attribute rules are merged. Only missing sample Skill/workspace files are added. All unrelated root files remain in place.

Replaced: agent_harness/, docs/, scripts/, web/ and the release's root product/package files. Private notes inside those managed directories move into the backup; put ongoing private development notes outside the repository or under ignored .harness/.

The backup is outside the destination repository and can contain private data. Never publish it. For rollback, stop the server, consult backup/DEPLOYMENT.json, remove the paths listed as installed, then restore each saved path. A failed apply attempts to undo its own changes and reports the backup location. Back up your whole repository separately if you also want to undo changes made by the application after deployment.

After replacement, use the destination's chosen interpreter to install -e ., run check_environment.py, then start -m agent_harness. Old virtual environments may need updated dependencies. An old database is not automatically converted; use --reset-local when replacing an unrelated application.

The source manifest detects missing or modified release files. It is not a signature; get the archive from a trusted source. The helper refuses links/junctions in paths it touches and refuses source/destination overlap. It does not delete unknown packages or alter Git history.

## Publish to an internal repository

Review git status before committing. Keep private connections, keys, Skills, data, logs, backups and conversation files out of Git. Existing company .github and AGENTS.md instructions remain in place. BAT Agent uses its own model connection and does not remove or override Copilot, filesystem or network policies.
