import argparse
import os

def main():
    parser = argparse.ArgumentParser(description="Local Agent Harness")
    parser.add_argument("--root", default=".", help="Project config/skills root")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--demo", action="store_true", help="Explicit offline scripted model")
    args = parser.parse_args()
    os.environ["AGENT_HARNESS_ROOT"] = os.path.abspath(args.root)
    if args.demo:
        os.environ["AGENT_HARNESS_MODEL_PROVIDER"] = "fake"
    import uvicorn
    uvicorn.run("agent_harness.server:create_app", factory=True,
                host="127.0.0.1", port=args.port, access_log=False)

if __name__ == "__main__":
    main()
