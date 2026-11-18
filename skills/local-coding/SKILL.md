---
name: local-coding
description: Read, modify and verify a local Python project, or run the offline coding demonstration.
---
# Local coding workflow
1. Inspect workspace files with list_files, search_files and read_file.
2. For existing files, preserve unrelated changes and pass the current SHA256 when editing.
3. Make one small change using edit_file, or create a new file using write_file.
4. Run the relevant script or test with run_python_script or run_command.
5. Read stdout, stderr and the exit code. Fix the cause of failures and verify again.
6. Report the paths changed and actual verification result.
The offline demo creates demo_hello.py and demo_result.json in the workspace.
Loading this skill does not execute anything. All execution goes through the normal tool registry.
