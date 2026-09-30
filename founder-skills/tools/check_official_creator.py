#!/usr/bin/env python3
"""Run pinned official skill creation tools in a temporary build directory."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen

BASE = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run([sys.executable, *map(str, args)], check=True)


def main():
    manifest = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))
    creator = manifest["official_creator"]
    commit = creator["commit"]
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise ValueError("Official creator must be pinned to a full commit SHA.")
    prefix = (f"https://raw.githubusercontent.com/{creator['repository']}/{commit}/"
              f"{creator['path']}/scripts/")
    with tempfile.TemporaryDirectory(prefix="founder-official-") as temporary:
        workspace = Path(temporary)
        tools_dir = workspace / "creator"
        tools_dir.mkdir()
        for filename in ("init_skill.py", "generate_openai_yaml.py", "quick_validate.py"):
            with urlopen(prefix + filename, timeout=30) as response:
                content = response.read()
            (tools_dir / filename).write_bytes(content)
        for item in manifest["skills"]:
            source = BASE / item["path"]
            arguments = []
            for key, value in item["interface"].items():
                arguments.extend(["--interface", f"{key}={value}"])
            run(tools_dir / "init_skill.py", item["name"], "--path", workspace / "built",
                "--resources", "references", *arguments)
            built = workspace / "built" / item["name"]
            if (built / "agents" / "openai.yaml").read_text(encoding="utf-8") != (
                    source / "agents" / "openai.yaml").read_text(encoding="utf-8"):
                raise ValueError(f"Generated UI does not match: {item['name']}")
            shutil.copy2(source / "SKILL.md", built / "SKILL.md")
            shutil.copytree(source / "references", built / "references", dirs_exist_ok=True)
            run(tools_dir / "quick_validate.py", built)
            run(tools_dir / "quick_validate.py", source)
    print(f"Official initialization, interface generation and validation passed at {commit}.")


if __name__ == "__main__":
    main()
