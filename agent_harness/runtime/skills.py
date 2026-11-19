from pathlib import Path
import yaml
from .paths import inside, text_file, walk
from ..errors import HarnessError

class SkillRegistry:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.skills, self.warnings = {}, []
        self.refresh()

    def refresh(self):
        self.skills, self.warnings = {}, []
        if not self.root.exists():
            return
        for folder in sorted(self.root.iterdir()):
            if not folder.is_dir() or folder.is_symlink():
                continue
            try:
                p = inside(self.root, folder.name + "/SKILL.md", True)
                _, content = text_file(p)
                meta = {}
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) != 3:
                        raise ValueError("frontmatter")
                    meta = yaml.safe_load(parts[1]) or {}
                    if not isinstance(meta, dict):
                        raise ValueError("metadata")
                lines = content.splitlines()
                name = meta.get("name") or next((s.lstrip("# ").strip() for s in lines if s.startswith("#")), folder.name)
                description = meta.get("description") or next((s for s in lines if s.strip() and not s.startswith("#")), "")
                self.skills[folder.name] = {"id": folder.name, "name": str(name),
                                           "description": str(description)[:1000], "root": folder}
            except Exception:
                self.warnings.append({"id": folder.name, "error": "Missing or invalid SKILL.md"})
            if len(self.skills) >= 200:
                self.warnings.append({"error": "Skill catalog capped at 200 entries"})
                break

    def list_skills(self):
        return {"skills": [{k: v for k,v in s.items() if k != "root"} for s in self.skills.values()],
                "warnings": self.warnings}

    def get(self, skill_id):
        if skill_id not in self.skills:
            raise HarnessError("unknown_skill", "Unknown skill id. Use list_skills.", "tool")
        return self.skills[skill_id]

    def read_skill(self, skill_id):
        s = self.get(skill_id)
        raw, content = text_file(inside(s["root"], "SKILL.md", True))
        resources = [p.relative_to(s["root"]).as_posix() for p in walk(s["root"])]
        import hashlib
        return {"skill_id": skill_id, "sha256":hashlib.sha256(raw).hexdigest(), "instructions": content[:30000],
                "truncated": len(content)>30000, "resources": resources[:200],
                "usage": "Use read_skill_resource or run_python_script with this skill_id. Execution cwd is the workspace."}

    def read_skill_resource(self, skill_id, path):
        s = self.get(skill_id)
        raw, content = text_file(inside(s["root"], path, True))
        import hashlib
        return {"skill_id": skill_id, "path": path, "sha256":hashlib.sha256(raw).hexdigest(), "content": content[:30000],
                "truncated": len(content)>30000}

    def executable(self, skill_id, path, suffix):
        base = self.get(skill_id)["root"]
        p = inside(base, path, True)
        allowed = "scripts" if suffix == ".py" else "notebooks"
        if p.suffix != suffix or not p.is_relative_to(base / allowed):
            raise HarnessError("skill_path_denied", f"Use a {suffix} file under the skill's {allowed}/ directory.", "tool")
        return p

    def write_skill_file(self, skill_id, path, content, expected_sha256=""):
        import re
        from .files import FileTools
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", skill_id):
            raise HarnessError("invalid_skill_id", "Use letters, numbers, hyphens or underscores for the skill id.", "tool")
        relative = Path(path)
        if path != "SKILL.md" and (len(relative.parts) < 2 or relative.parts[0] not in ("scripts", "notebooks", "references")):
            raise HarnessError("skill_path_denied", "Write SKILL.md or a file under scripts/, notebooks/ or references/.", "tool")
        # Resolve against the registry root first, including new folders and traversal checks.
        inside(self.root, skill_id + "/" + path)
        base = self.root / skill_id
        if path != "SKILL.md" and skill_id not in self.skills:
            raise HarnessError("unknown_skill", "Create a valid SKILL.md first.", "tool")
        if path == "SKILL.md":
            if not content.strip():
                raise HarnessError("invalid_skill", "Skill instructions cannot be empty.", "tool")
            if content.startswith("---"):
                parts = content.split("---", 2)
                try:
                    if len(parts) != 3 or not isinstance(yaml.safe_load(parts[1]), dict):
                        raise ValueError()
                except (ValueError, yaml.YAMLError):
                    raise HarnessError("invalid_skill", "The YAML frontmatter must be a valid mapping.", "tool")
        result = FileTools(base, self.root.parent / ".harness").write_file(path, content, expected_sha256)
        self.refresh()
        return {**result, "skill_id":skill_id, "scope":"skill", "registered":skill_id in self.skills}
