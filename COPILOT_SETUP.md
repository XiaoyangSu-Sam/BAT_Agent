# Set up BAT Agent with Copilot

For an existing v0.6.1 installation, use the [v0.7.0 changed-file list and update prompt](docs/updates/v0.7.0.md). Keep the [development and README rules](docs/development.md) with the imported documentation.

Open the destination project in VS Code. Give Copilot this instruction together with this file:

> Set up BAT Agent in this project using COPILOT_SETUP.md and docs/setup.md. Inspect the environment first, use approved installed tools, and perform the local checks. Keep real endpoint, API key, user information and private data out of source, commits and logs. Report actual results and anything that still needs my input. Do not commit or push environment files.

## Existing working project

When the user already has a working approved environment, use docs/existing-environment.md. Preserve the original .venv in place; select its interpreter explicitly. Do not create a replacement environment or run an installer by default. Review/import the source through the organization's normal workflow, check local prerequisites first, and start from the source root if they pass. Do not repackage, remove origin metadata or change execution paths to evade a denied operation.

## Procedure

1. Read the project's applicable AGENTS.md and organizational instructions. Confirm the destination folder and inspect uncommitted files. Do not replace or delete unrelated work.
2. If this is an extracted release to deploy into another folder, use scripts/deploy.py first without --apply. Review the reported destination, managed paths and backup location. For an unrelated old application use --reset-local to archive old configuration/state. Stop its running server before applying. If the new code is already in the destination, skip deployment.
3. Find approved Python interpreters (3.11+). Prefer the existing project environment, especially if its Skills already use installed packages such as Playwright. Do not copy another machine's .venv. Create a new environment only if needed and supported.
4. Run scripts/check_environment.py with the selected Python before installing anything. If dependencies are already present and compatible, no editable install is needed to launch from the source root. Otherwise review the required package changes and install only through the approved workflow in docs/setup.md. Preserve package source, proxy and certificates. Do not run uv sync on a shared environment. No npm, npx, frontend build or browser download is required for normal use.
5. Run scripts/check_environment.py with that Python. Resolve missing required dependencies through approved sources. Notebook and Playwright support are optional. If an operation is denied by policy or permissions, stop that operation, report the exact failing stage without secrets, and request an approved alternative; do not evade the restriction.
6. Inspect Skill folder shape: skills/<id>/SKILL.md, with its scripts/, references/ and notebooks/ beside it. Remove an accidental archive wrapper by placing the complete Skill directory at the documented location, only if those files are already authorized to access. BAT Agent does not discover .github/skills automatically. Keep private Skills untracked.
7. Launch the explicit interpreter path with -m agent_harness from the destination source root. Do not let a bare python command choose a different interpreter. Check GET /health and load the page. Enter Open workspace without a model and verify file browsing and registered Skills. Do not leave test files in the user's real work without permission; use a disposable workspace.
8. Have the user enter the real endpoint, model and optional key locally in the connection page. Do not ask them to paste secrets into chat. Test connection must make a real request; do not claim success from configuration parsing. Model listing may be unavailable; manual model entry remains supported.
9. With the user's configured connection, test one ordinary chat and Test model and tools. Then use a small approved Skill, read its instructions and script, approve execution, and verify actual output. Do not silently use --demo to stand in for a real model test.
10. Report the Python path, launch command, local page address, version, local checks passed, configured Skill interpreter, and remaining model/network/dependency issues. Keep any environment-specific notes local and ignored. Do not include private values in published documentation.

Application scripts run with the current account's permissions. A successful local startup does not prove a private endpoint or every Skill is compatible.
