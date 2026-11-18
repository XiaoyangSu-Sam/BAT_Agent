import json
import uuid

CODE = """import json
from pathlib import Path
result = {"message": "Harness local execution works", "sum": sum(range(1, 6))}
Path("demo_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))
"""

def reply(messages, tools=True):
    if not tools:
        return {"role":"assistant","content":"Offline demo provider is running. This does not test the real endpoint."}
    latest = max((i for i,m in enumerate(messages) if m["role"]=="user"), default=0)
    turn = messages[latest+1:]
    results = [m for m in turn if m["role"]=="tool"]
    step = len(results)
    sequence = [("list_skills",{}), ("read_skill",{"skill_id":"local-coding"}),
                ("read_file",{"path":"demo_hello.py"})]
    if step < 3:
        name, args = sequence[step]
    elif step == 3:
        previous = json.loads(results[-1]["content"])
        name, args = "write_file", {"path":"demo_hello.py","content":CODE,
                                  "expected_sha256":previous.get("result",{}).get("sha256","")}
    elif step == 4:
        name, args = "run_python_script", {"path":"demo_hello.py"}
    elif step == 5:
        name, args = "read_file", {"path":"demo_result.json"}
    else:
        execution = json.loads(results[4]["content"])
        ok = execution.get("ok") and execution.get("result",{}).get("ok")
        text = ("Offline demo completed: wrote demo_hello.py, executed local Python, and read demo_result.json. "
                "The calculated sum is 15. These tools really ran; model decisions were scripted."
                if ok else "Offline demo did not complete execution. Inspect the tool errors or approval decision.")
        return {"role":"assistant","content":text}
    return {"role":"assistant","content":None,"tool_calls":[{
        "id":"demo_"+uuid.uuid4().hex, "type":"function",
        "function":{"name":name,"arguments":json.dumps(args)}}]}
