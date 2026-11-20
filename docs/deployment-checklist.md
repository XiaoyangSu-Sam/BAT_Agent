# Startup checklist

- Run scripts/check_environment.py with the interpreter that will start BAT Agent.
- Confirm /health reports the expected version and the connection page opens.
- Enter the workspace without a model; open, edit and save a disposable UTF-8 file.
- Confirm a complete Skill folder appears in Registered Skills after Refresh Skills.
- Configure a real model locally, with or without an API key as required, and run Test connection.
- Use Find models if the service supports it; otherwise enter its supplied identifier.
- Run Test model and tools before asking the model to edit files.
- Send a small chat request; check readable output, status and model time.
- Read a small Skill, approve its script execution and verify actual results.
- Restart the server and confirm local conversations persist.

Context usage and reasoning appear only when supplied or configured. A missing field is not evidence of a failed connection. For errors, use [Connection help](connections.md). Keep acceptance results and private network details local.
