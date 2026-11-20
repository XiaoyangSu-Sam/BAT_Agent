# BAT Agent

v0.6.0 · Internal preview · From BAT Team

A local coding workbench with files and conversation on the left, a code editor in the center, and registered Skills in a side panel. The interface is English.

- Chat with an OpenAI-compatible model; API keys are optional.
- Read, edit and save files with conflict protection.
- Create, register, read and execute Skills, Python scripts and optional notebooks.
- Review execution approvals, results and local conversation history.
- See connection diagnostics, request status, model time and available context usage.

## Start

Use an approved Python 3.11+ environment. In the project folder:

~~~powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e .
./.venv/Scripts/python.exe scripts/check_environment.py
./.venv/Scripts/python.exe -m agent_harness
~~~

Open **http://127.0.0.1:8765**. Keep the terminal open; Ctrl+C stops the app. If you already have an environment, use its Python instead. See [Setup](docs/setup.md) for uv, approved package sources, offline installation and updating an existing folder.

No Node, npm or browser download is needed to run the workbench. Python dependencies must already be installed or available from your approved package source.

## Connect or explore

Click **Open workspace without a model** to browse files, edit code and inspect Skills before configuring a model.

To chat, enter your **Endpoint**, optionally enter an **API Key**, and use **Find models** to choose a model. If listing is unavailable, enter the name supplied by your service owner. Click **Test connection**, then **Open workspace**. Saved connections appear in a dropdown.

Replies arrive asynchronously as complete messages. **Show model reasoning** displays only text actually returned by the model service. **Model time** includes network and server waiting; it excludes tools and approval waits. The context ring displays known usage; unavailable data is marked unknown.

## Help

[中文说明](README.zh-CN.md) · [Setup and updates](docs/setup.md) · [Copilot setup instructions](COPILOT_SETUP.md) · [User guide](docs/user-guide.md) · [Connection help](docs/connections.md) · [Skills](docs/skills.md) · [Configuration/API](docs/configuration-api.md) · [Startup checklist](docs/deployment-checklist.md) · [Security](SECURITY.md) · [Changes](CHANGELOG.md)

BAT Agent is a local, single-user application. Approved scripts run with your account's permissions. Keep configuration, conversations, private Skills and workspace data out of published source.
