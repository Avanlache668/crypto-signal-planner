#!/usr/bin/env python3
"""Offline installer, structural validator and packager for the two founder skills."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import uuid
import zipfile

BASE = Path(__file__).resolve().parent
SKILLS = ("cz-strategy", "he-yi-growth")


def file_map(directory: Path) -> dict[str, str]:
    """Compare exact bytes; refuse links rather than following arbitrary inputs."""
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError(f"Expected a regular skill directory: {directory}")
    result = {}
    for entry in sorted(directory.rglob("*")):
        if entry.is_symlink():
            raise ValueError(f"Symbolic links are not supported: {entry}")
        if entry.is_file():
            relative = entry.relative_to(directory).as_posix()
            result[relative] = hashlib.sha256(entry.read_bytes()).hexdigest()
    return result


def read_flat_strings(path: Path, interface: bool = False) -> dict[str, str]:
    """Parse this package's deliberately restricted YAML subset without PyYAML."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if interface:
        if not lines or lines[0] != "interface:":
            raise ValueError(f"Missing interface mapping: {path}")
        lines = lines[1:]
    else:
        if not lines or lines[0] != "---":
            raise ValueError(f"Missing frontmatter: {path}")
        try:
            lines = lines[1:lines.index("---", 1)]
        except ValueError as exc:
            raise ValueError(f"Unclosed frontmatter: {path}") from exc
    result = {}
    for line in lines:
        match = re.fullmatch(r"(?:  )?([a-z_]+): (.+)", line)
        if not match:
            raise ValueError(f"Unsupported YAML line in {path}: {line}")
        key, raw = match.groups()
        if key in result:
            raise ValueError(f"Duplicate field in {path}: {key}")
        value = json.loads(raw) if raw.startswith('"') else raw
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Expected a nonempty string in {path}: {key}")
        result[key] = value
    return result


def validate(package: Path = BASE) -> dict:
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    if tuple(item["name"] for item in manifest["skills"]) != SKILLS:
        raise ValueError("Manifest skill list does not match this installer.")
    for item in manifest["skills"]:
        name = item["name"]
        if item["path"] != f"skills/{name}":
            raise ValueError(f"Unexpected skill path: {item['path']}")
        directory = package / item["path"]
        listing = file_map(directory)
        required = {"SKILL.md", "agents/openai.yaml",
                    "references/sources.md", "references/playbook.md",
                    "references/examples.md"}
        if set(listing) != required:
            raise ValueError(f"Unexpected skill files for {name}: {set(listing) ^ required}")
        fields = read_flat_strings(directory / "SKILL.md")
        if set(fields) != {"name", "description"} or fields["name"] != name:
            raise ValueError(f"Invalid frontmatter fields: {name}")
        if len(name) > 64 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            raise ValueError(f"Invalid name: {name}")
        description = fields["description"]
        if len(description) > 1024 or "<" in description or ">" in description:
            raise ValueError(f"Invalid description: {name}")
        text = (directory / "SKILL.md").read_text(encoding="utf-8")
        if len(text.splitlines()) >= 500 or "TODO" in text:
            raise ValueError(f"Unfinished or overly long instructions: {name}")
        for relative in re.findall(r"\]\((references/[^)]+)\)", text):
            resolved = (directory / relative).resolve()
            if not resolved.is_relative_to(directory.resolve()) or not resolved.is_file():
                raise ValueError(f"Missing or unsafe reference: {relative}")
        if set(re.findall(r"\]\((references/[^)]+)\)", text)) != {
                "references/sources.md", "references/playbook.md", "references/examples.md"}:
            raise ValueError(f"Reference discovery incomplete: {name}")
        interface = read_flat_strings(directory / "agents/openai.yaml", interface=True)
        if interface != item["interface"]:
            raise ValueError(f"Interface differs from manifest: {name}")
        if not 25 <= len(interface["short_description"]) <= 64:
            raise ValueError(f"UI description length invalid: {name}")
        if "$" + name not in interface["default_prompt"]:
            raise ValueError(f"Missing explicit skill invocation: {name}")
    return manifest


def target_roots(target: str, scope: str, workspace: Path,
                 root: Path | None = None) -> list[tuple[str, Path]]:
    if root is not None:
        if target == "both":
            raise ValueError("--root requires a single --target.")
        return [(target, root.expanduser().absolute())]
    targets = ("codex", "openclaw") if target == "both" else (target,)
    roots = []
    for host in targets:
        if scope == "project":
            directory = workspace / (".agents/skills" if host == "codex" else "skills")
        elif host == "codex":
            directory = Path.home() / ".agents" / "skills"
        else:
            state = os.environ.get("OPENCLAW_STATE_DIR")
            if os.environ.get("OPENCLAW_PROFILE") and not state:
                raise ValueError("OpenClaw profile detected. Specify its active skills directory with --root.")
            directory = (Path(state).expanduser() if state else Path.home() / ".openclaw") / "skills"
        roots.append((host, directory.expanduser().absolute()))
    return roots


def install(roots: list[tuple[str, Path]], names: tuple[str, ...],
            replace: bool = False, dry_run: bool = False,
            package: Path = BASE) -> list[dict]:
    validate(package)
    plans = []
    # Preflight every destination before modifying any of them.
    for host, root in roots:
        if root.is_symlink() or (root.exists() and not root.is_dir()):
            raise ValueError(f"Expected a regular destination root: {root}")
        for name in names:
            if name not in SKILLS:
                raise ValueError(f"Unknown skill: {name}")
            source = package / "skills" / name
            destination = root / name
            src_real, dst_real = source.resolve(), destination.resolve()
            if src_real.is_relative_to(dst_real) or dst_real.is_relative_to(src_real):
                raise ValueError(f"Source and destination overlap: {destination}")
            action = "install"
            if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
                raise ValueError(f"Destination is not a regular directory: {destination}")
            if destination.exists():
                if file_map(source) == file_map(destination):
                    action = "unchanged"
                elif replace:
                    action = "replace"
                else:
                    raise ValueError(f"Existing skill differs: {destination}. Use --replace to back it up first.")
            if action == "replace":
                backup_parent = root.parent / "founder-skills-backups"
                if backup_parent.is_symlink() or (backup_parent.exists() and not backup_parent.is_dir()):
                    raise ValueError(f"Invalid backup directory: {backup_parent}")
            plans.append({"host": host, "skill": name, "source": source,
                          "destination": destination, "action": action})
    results = []
    for plan in plans:
        source = plan["source"]
        destination = plan["destination"]
        result = {key: str(value) for key, value in plan.items() if key != "source"}
        result["dry_run"] = dry_run
        if dry_run or plan["action"] == "unchanged":
            results.append(result)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".founder-stage-", dir=destination.parent))
        backup = None
        try:
            payload = stage / "payload"
            shutil.copytree(source, payload)
            if file_map(source) != file_map(payload):
                raise ValueError(f"Staged content mismatch: {source}")
            if plan["action"] == "replace":
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                backup_parent = destination.parent.parent / "founder-skills-backups"
                backup_parent.mkdir(parents=True, exist_ok=True)
                backup = backup_parent / f"{plan['skill']}-{stamp}-{uuid.uuid4().hex[:8]}"
                destination.rename(backup)
            payload.rename(destination)
            if backup is not None:
                result["backup"] = str(backup)
        except Exception:
            if backup is not None and not destination.exists():
                backup.rename(destination)
            raise
        finally:
            shutil.rmtree(stage)
        results.append(result)
    return results


def package_zip(output: Path, package: Path = BASE) -> Path:
    validate(package)
    output = output.expanduser().absolute()
    if output.exists():
        raise ValueError(f"Archive already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    entries = [package / name for name in ("README.md", "INSTALL.zh-CN.md",
               "SOURCES.md", "LICENSE", "manifest.json", "manage.py", "evals/acceptance.md")]
    entries += [entry for name in SKILLS for entry in (package / "skills" / name).rglob("*")
                if entry.is_file()]
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in sorted(entries):
            if entry.is_symlink():
                raise ValueError(f"Cannot archive symbolic link: {entry}")
            relative = "founder-skills/" + entry.relative_to(package).as_posix()
            info = zipfile.ZipInfo(relative, (2026, 10, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, entry.read_bytes())
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Validate the two skills offline.")
    installer = commands.add_parser("install", help="Copy canonical skill folders to host skill roots.")
    installer.add_argument("--target", choices=("codex", "openclaw", "both"), required=True)
    installer.add_argument("--skill", choices=SKILLS, action="append")
    installer.add_argument("--scope", choices=("user", "project"), default="user")
    installer.add_argument("--workspace", type=Path, default=Path.cwd())
    installer.add_argument("--root", type=Path, help="Custom skills root for one target.")
    installer.add_argument("--replace", action="store_true", help="Back up and replace differing installations.")
    installer.add_argument("--dry-run", action="store_true")
    packager = commands.add_parser("package", help="Create a deterministic distributable ZIP.")
    packager.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            manifest = validate()
            print(json.dumps({"valid": True, "version": manifest["version"],
                              "skills": list(SKILLS)}, ensure_ascii=False, indent=2))
        elif args.command == "package":
            print(package_zip(args.output))
        else:
            roots = target_roots(args.target, args.scope, args.workspace, args.root)
            names = tuple(dict.fromkeys(args.skill or SKILLS))
            print(json.dumps(install(roots, names, args.replace, args.dry_run),
                             ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
