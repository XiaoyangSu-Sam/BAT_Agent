# Update source in an existing environment

For a selective v0.6.1 to v0.7.0 update, see the [exact file list and Copilot prompt](updates/v0.7.0.md). It also documents the conversation-state migration and rollback limits.

Use this procedure for an existing BAT Agent/Harness project with a working, approved Python environment, when the source update is permitted by your organization. It is a normal application update: security policies and file-source metadata stay intact. Changing from ZIP to Git or copying text does not establish approval or guarantee execution.

## 1. Keep the working environment

Stop the old application normally. Keep its project folder and virtual environment at their current locations. Do not create a new .venv, copy Python executables, move the existing environment, or start an interpreter that was blocked.

In PowerShell, record the full path to the existing approved interpreter. Use the actual path from the working project:

~~~powershell
$BatPython = Read-Host "Full path to the existing approved python.exe"
& $BatPython -c "import sys; print(sys.executable); print(sys.version)"
~~~

Python 3.11+ is required. If the existing environment is older, ask for an approved compatible environment. Do not change application-control settings.

## 2. Review and bring in the source update

Use your normal approved source-review/import workflow to bring the selected BAT Agent version into a branch of your existing Enterprise repository. Review the update before replacing files. The source tree contains Python, HTML, CSS and JavaScript files; it does not contain .venv, Python executables or an installer.

Back up the old application and local data outside the repository first. Keep that backup private. A Git commit alone does not back up ignored configuration, Skills or conversation data.

The automated option is scripts/deploy.py from the reviewed source tree. Run it with $BatPython, first without --apply, following [Setup](setup.md). It preserves the destination's .venv and does not create an environment or install packages.

For manual replacement, use this checklist:

| Item in the existing dedicated Harness project | Action |
| --- | --- |
| agent_harness/ | Back up the old directory, then replace it completely. Include static/ and its bundled JS files; do not merge stale modules. |
| docs/, scripts/, web/ | Back up and replace the product directories. Preserve any unrelated custom work separately. web/ is build source; no frontend build is needed to run. |
| README.md, COPILOT_SETUP.md, SECURITY.md, CHANGELOG.md | Replace with the product documents. |
| pyproject.toml, uv.lock, .python-version | Replace together in a dedicated Harness repository. If this repository contains another application too, reconcile its package metadata first. Do not run synchronization just because a lock file changed. |
| SOURCE-MANIFEST.json | Copy with the same release; hashes describe the unmodified source files. |
| .gitignore, .gitattributes | Merge the source rules while retaining organization-specific rules. |
| .git/, .github/, AGENTS.md, .venv/ | Keep in place. |
| skills/, workspace/ | Keep existing user content. Add only missing sample files if useful. |
| config/*.yaml.example | Copy examples only; they are not active configuration. |
| config/model.yaml, config/environment.yaml, config/execution.yaml | Keep valid BAT Agent configuration. For a different old application, archive these privately and configure again. |
| .harness/ | Keep for a compatible BAT Agent update. For an unrelated old session database, archive privately and start with fresh local state. |

Keep endpoint addresses, credentials, private Skills, workspace files and development notes out of the Enterprise source commit as appropriate to your organization's rules. Never include them in public source.

## 3. Check before installing anything

Open a terminal in the updated project folder. Use the same $BatPython variable:

~~~powershell
& $BatPython scripts/check_environment.py
~~~

If the report says ok: true, proceed directly to startup. Installing the BAT Agent distribution is not required to run its module from the source root when its dependencies are already installed.

If required dependencies are missing or incompatible, stop and review the package changes. Use the approved dependency-management workflow for this environment. Installing or upgrading packages can affect other applications that share it. Do not run uv sync on a shared environment merely to launch this update.

If pip installation into this environment is approved and necessary, the project supports:

~~~powershell
& $BatPython -m pip install -e .
& $BatPython scripts/check_environment.py
~~~

Use the configured approved package source. Notebook/Playwright dependencies are only needed by the corresponding tools/Skills.

## 4. Start from the updated source root

~~~powershell
& $BatPython -m agent_harness
~~~

Open http://127.0.0.1:8765. Use --port 8766 only if the default port is occupied. The process uses $BatPython; this command does not create an environment, download Python or install packages.

Without model configuration, choose Open workspace without a model. Then configure the real connection locally and run Test connection. Verify one small approved Skill after basic startup succeeds.

If endpoint protection blocks the existing approved interpreter or updated source, stop that operation and give the event details to IT for review. Do not remove source markings, rename executables or change locations to evade an application rule. A working old environment alone does not prove that every code update is authorized.
