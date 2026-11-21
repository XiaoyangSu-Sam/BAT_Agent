"""Local HTTP model fixture and clean app root for browser integration checks only."""
import json
import os
from pathlib import Path
import tempfile
import threading
import uuid
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from agent_harness.server import create_app

root = Path(tempfile.mkdtemp(prefix="bat-workbench-qa-"))
(root/"workspace").mkdir()
(root/"workspace/README.md").write_text("# Browser test project\n\nOpen a file and talk to the agent.\n")
(root/"workspace/long.py").write_text("\n".join("# line "+str(i)+" "+"x"*90 for i in range(500))+"\n")
(root/"skills/local-coding").mkdir(parents=True)
(root/"skills/local-coding/SKILL.md").write_text("---\nname: Local coding\ndescription: Read, edit and run local code.\n---\nRead the file before editing.\n")
metrics = {"requests":0,"anonymous":0,"authenticated":0,"secondary_probes":0,"secondary_runs":0}
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def respond(self, code, value):
        data = json.dumps(value).encode()
        self.send_response(code); self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.path.endswith("/models"):
            return self.respond(200, {"data":[{"id":"qa-model", "context_length":32768}, {"id":"qa-model-updated","max_model_len":32768}]})
        self.respond(200, {**metrics, "root":str(root)})
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        metrics["requests"]+=1
        metrics["authenticated" if self.headers.get("Authorization") else "anonymous"]+=1
        if self.path.startswith("/bad"):
            return self.respond(401, {"error":"fixture authentication error"})
        if self.path.startswith("/secondary/"):
            if body["model"] != "qa-secondary":
                return self.respond(404, {"error":"fixture model mismatch"})
            if body.get("max_tokens", 0) <= 256:
                metrics["secondary_probes"] += 1
                if metrics["secondary_probes"] == 1:
                    return self.respond(503, {"error":"fixture temporary outage"})
            if body.get("tools"):
                metrics["secondary_runs"] += 1
        messages=body["messages"]
        if not body.get("tools"):
            reply={"role":"assistant","content":"OK"}
        else:
            last=messages[-1]
            last_user=max(i for i,m in enumerate(messages) if m["role"]=="user")
            tool_messages=[m for m in messages[last_user+1:] if m["role"]=="tool"]
            script = "qa_full_access.py" if "with Full access" in messages[last_user]["content"] else "qa_result.py"
            if last["role"]!="tool":
                name,args="write_file",{"path":script,"content":"print(6 * 7)\n"}
            elif len(tool_messages)==1:
                name,args="run_python_script",{"path":script}
            else:
                name=None
            if name:
                reply={"role":"assistant","content":None,"tool_calls":[{"id":uuid.uuid4().hex,"type":"function",
                    "function":{"name":name,"arguments":json.dumps(args)}}]}
            else:
                reply={"role":"assistant","content":f"## Result\n\nCreated and ran **{script}**. The actual output is **42**.\n\n- The script calculates 6 × 7.\n- Execution completed successfully.\n\n```python\nprint(6 * 7)\n```\n\n| Check | Result |\n| --- | --- |\n| Exit code | 0 |\n\n<img src=x onerror=window.unsafe=true>\n[Unsafe](javascript:alert(1))"}
        reply["reasoning_content"]="I will use the registered tools to verify the result."
        time.sleep(1.5 if body.get("tools") else 0.15)
        self.respond(200, {"choices":[{"message":reply,"finish_reason":"stop"}],
            "usage":{"prompt_tokens":2048,"completion_tokens":128,"total_tokens":2176}})

if __name__=="__main__":
    for key in ("AGENT_HARNESS_MODEL_PROVIDER","LLM_ENDPOINT","LLM_MODEL","LLM_API_KEY"):
        os.environ.pop(key,None)
    server=ThreadingHTTPServer(("127.0.0.1",18768),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    print("QA_ROOT="+str(root),flush=True)
    try: uvicorn.run(create_app(root),host="127.0.0.1",port=18767,access_log=False)
    finally: server.shutdown()
