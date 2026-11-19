import inspect
from jsonschema import Draft202012Validator
from .files import FileTools
from .processes import ProcessTools
from ..errors import HarnessError

S = {"type": "string"}
def string(maximum=10000, minimum=0):
    return dict(type="string", minLength=minimum, maxLength=maximum)

class ToolRegistry:
    def __init__(self, settings, skills):
        self.entries = {}
        self.files = FileTools(settings.workspace, settings.state_dir)
        self.processes = ProcessTools(settings.workspace, settings.execution, skills)
        def add(name, desc, properties, required, fn, kind="read"):
            schema = dict(type="object", properties=properties, required=required, additionalProperties=False)
            self.entries[name] = dict(description=desc, schema=schema, fn=fn, kind=kind)
        path = string(1000, 1)
        sha = {"type":"string", "pattern":"^(|[a-f0-9]{64})$"}
        add("list_files", "List files under a workspace directory.", {"path":path}, [], self.files.list_files)
        add("read_file", "Read UTF-8 text and its SHA256 before editing.",
            {"path":path, "start_line":{"type":"integer","minimum":1},
             "end_line":{"type":"integer","minimum":1}}, ["path"], self.files.read_file)
        add("search_files", "Search literal text in workspace files.",
            {"query":string(500,1),"path":path}, ["query"], self.files.search_files)
        add("write_file", "Create a file; overwrite requires the current SHA256 from read_file.",
            {"path":path,"content":string(1000000),"expected_sha256":sha},
            ["path","content"], self.files.write_file, "write")
        add("edit_file", "Replace exactly one occurrence of old_text. Requires current SHA256.",
            {"path":path,"old_text":string(100000,1),"new_text":string(100000),"expected_sha256":sha},
            ["path","old_text","new_text","expected_sha256"], self.files.edit_file, "write")
        add("list_skills", "List installed skill ids and descriptions.", {}, [], skills.list_skills)
        add("read_skill", "Load instructions and resource names for an installed skill.",
            {"skill_id":path}, ["skill_id"], skills.read_skill)
        add("read_skill_resource", "Read a skill resource relative to its own directory.",
            {"skill_id":path,"path":path}, ["skill_id","path"], skills.read_skill_resource)
        add("write_skill_file", "Create or update SKILL.md or a skill resource. Existing files require SHA256 from read_skill/read_skill_resource. Registers valid skills immediately.",
            {"skill_id":string(80,1), "path":path, "content":string(1000000), "expected_sha256":sha},
            ["skill_id","path","content"], skills.write_skill_file, "write")
        args = {"type":"array","items":string(10000),"maxItems":100}
        add("run_python_script", "Execute Python in the workspace, optionally from an installed skill's scripts/.",
            {"path":path,"args":args,"skill_id":string(200)}, ["path"],
            self.processes.run_python_script, "execute")
        add("run_command", "Run argv without a shell. cwd is workspace-relative. Commands access your user account.",
            {"argv":dict(args,minItems=1),"cwd":path}, ["argv"], self.processes.run_command, "execute")
        add("run_notebook", "Execute a notebook and save a separate output copy. Requires optional notebook dependencies.",
            {"path":path,"skill_id":string(200)}, ["path"], self.processes.run_notebook, "execute")

    def schemas(self):
        return [{"type":"function","function":{"name":name,"description":e["description"],
                  "parameters":e["schema"]}} for name,e in self.entries.items()]

    def validate(self, name, args):
        if name not in self.entries:
            raise HarnessError("unknown_tool", "Unknown tool name.", "tool")
        errors = list(Draft202012Validator(self.entries[name]["schema"]).iter_errors(args))
        if errors:
            raise HarnessError("invalid_tool_arguments", "Arguments do not match the tool schema.", "tool",
                               fields=[".".join(map(str,e.path)) or "(root)" for e in errors[:5]])
        return self.entries[name]

    async def call(self, name, args):
        entry = self.validate(name, args)
        result = entry["fn"](**args)
        return await result if inspect.isawaitable(result) else result
