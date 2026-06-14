#!/usr/bin/env python3
"""ERPClaw Module Manager — local/offline management of bundled modules.

Air-gapped: this manager performs NO network activity. It reads the bundled
registry (scripts/module_registry.json), lists/inspects locally-present
modules, removes them, and rebuilds the action cache. There is no git-clone
install, no remote registry fetch, and no foundation reconciliation — modules
ship bundled with the install and are tracked in the
erpclaw_module / erpclaw_module_action tables.

Usage: python3 module_manager.py --action <action-name> [--flags ...]
Output: JSON to stdout, exit 0 on success, exit 1 on error.
"""
import argparse
import ast
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Shared library imports
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.expanduser("~/.openclaw/erpclaw/lib"))
from erpclaw_lib.db import get_connection
from erpclaw_lib.response import ok, err, rows_to_list, row_to_dict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODULES_DIR = os.path.expanduser("~/.openclaw/erpclaw/modules")

# OpenClaw's agent / `openclaw skills list` only discovers skills under
# `~/.openclaw/workspace/skills/`. Modules installed by this manager
# also need to be published there so the agent can invoke their actions
# (otherwise the agent reports "no integration set up" even though the
# module is installed and working from the CLI). Symlinks are rejected
# by the openclaw skills subsystem with `reason=symlink-escape`, so we
# do a plain copy. Confirmed empirically 2026-04-25 against the live
# agent on the OpenClaw Ubuntu server.
OPENCLAW_WORKSPACE_SKILLS_DIR = os.path.expanduser(
    "~/.openclaw/workspace/skills"
)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(SCRIPT_DIR, "module_registry.json")


def _now_iso():
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_registry(force_refresh=False):
    """Load the bundled local registry (scripts/module_registry.json).

    Offline / air-gapped: no network, no on-disk cache, no signature
    verification. `force_refresh` is accepted for API compatibility with
    existing callers but is a no-op (there is nothing to refresh from).
    """
    try:
        with open(REGISTRY_PATH, "rb") as f:
            return json.loads(f.read())
    except (OSError, json.JSONDecodeError):
        return {"version": "0.0.0", "modules": {}}


def _registry_to_dict(registry):
    """Convert registry modules (dict-keyed or list) to {name: info} dict."""
    modules_raw = registry.get("modules", {})
    if isinstance(modules_raw, dict):
        result = {}
        for name, info in modules_raw.items():
            info_copy = dict(info)
            info_copy.setdefault("name", name)
            result[name] = info_copy
        return result
    # List format (fallback)
    return {m["name"]: m for m in modules_raw}


def _get_installed_modules(conn):
    """Return dict of installed module names -> row dicts."""
    rows = conn.execute("SELECT * FROM erpclaw_module").fetchall()
    return {row["name"]: dict(row) for row in rows}


# ---------------------------------------------------------------------------
# Action cache builder — uses AST parsing (safe, no side effects)
# ---------------------------------------------------------------------------

def _extract_actions_via_ast(script_path):
    """Extract action names from a module's db_query.py using AST parsing.

    Looks for top-level assignments to ACTIONS, ACTION_MAP, and ALIASES dicts.
    Extracts the string keys from each. This is safer than importing the module
    since it avoids executing any code or triggering import side effects.
    """
    if not os.path.isfile(script_path):
        return set()

    try:
        with open(script_path, "r") as f:
            source = f.read()
        tree = ast.parse(source, filename=script_path)
    except (SyntaxError, OSError):
        return set()

    target_names = {"ACTIONS", "ACTION_MAP", "ALIASES"}
    all_actions = set()

    for node in ast.iter_child_nodes(tree):
        # Match: ACTIONS = { ... }
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in target_names:
                    all_actions |= _extract_dict_keys(node.value)
        # Match: ACTIONS.update({ ... }) — Pattern B merge from domain modules
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if (isinstance(call.func, ast.Attribute)
                    and call.func.attr == "update"
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id in target_names
                    and call.args):
                all_actions |= _extract_dict_keys(call.args[0])

    # Remove 'status' to avoid collision — each module has its own status
    all_actions.discard("status")
    return all_actions


def _extract_dict_keys(node):
    """Extract string keys from a Dict AST node."""
    keys = set()
    if isinstance(node, ast.Dict):
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.add(key.value)
    return keys


def _extract_actions_via_regex(script_path):
    """Fallback: extract action names using regex on the source text.

    Matches patterns like:
        "action-name": some_function,
        'action-name': some_function,
    within ACTIONS = { ... } blocks.
    """
    if not os.path.isfile(script_path):
        return set()

    try:
        with open(script_path, "r") as f:
            source = f.read()
    except OSError:
        return set()

    actions = set()
    # Find ACTIONS = { ... } block (and ACTION_MAP, ALIASES)
    for var_name in ("ACTIONS", "ACTION_MAP", "ALIASES"):
        pattern = rf'{var_name}\s*=\s*\{{([^}}]*)\}}'
        match = re.search(pattern, source, re.DOTALL)
        if match:
            block = match.group(1)
            # Extract quoted string keys
            actions |= set(re.findall(r'["\']([a-z][a-z0-9\-]+)["\']', block))
        # Also match .update({...})
        pattern_update = rf'{var_name}\.update\(\s*\{{([^}}]*)\}}\s*\)'
        for m in re.finditer(pattern_update, source, re.DOTALL):
            block = m.group(1)
            actions |= set(re.findall(r'["\']([a-z][a-z0-9\-]+)["\']', block))

    actions.discard("status")
    return actions


def build_action_cache(conn, module_name, install_path):
    """Scan a module's db_query.py and cache its action names.

    Uses AST parsing as the primary method, falling back to regex if AST
    yields no results (e.g., dynamically constructed dicts).
    Also scans sibling .py files in scripts/ for domain modules that
    define their own ACTIONS dicts (merged via ACTIONS.update()).

    Returns the number of actions cached.
    """
    script_path = os.path.join(install_path, "scripts", "db_query.py")

    all_actions = _extract_actions_via_ast(script_path)
    if not all_actions:
        all_actions = _extract_actions_via_regex(script_path)

    # Also scan sibling domain modules in scripts/ directory
    scripts_dir = os.path.join(install_path, "scripts")
    if os.path.isdir(scripts_dir):
        for fname in os.listdir(scripts_dir):
            if fname.endswith(".py") and fname != "db_query.py":
                domain_path = os.path.join(scripts_dir, fname)
                domain_actions = _extract_actions_via_ast(domain_path)
                if not domain_actions:
                    domain_actions = _extract_actions_via_regex(domain_path)
                all_actions |= domain_actions

    if not all_actions:
        return 0

    # Clear existing cache for this module and insert fresh
    conn.execute(
        "DELETE FROM erpclaw_module_action WHERE module_name = ?",
        (module_name,)
    )
    conn.executemany(
        "INSERT OR REPLACE INTO erpclaw_module_action (module_name, action_name) VALUES (?, ?)",
        [(module_name, a) for a in sorted(all_actions)]
    )
    conn.commit()

    # Check for action name collisions with other modules (non-fatal warning)
    collisions = conn.execute(
        """SELECT action_name, module_name FROM erpclaw_module_action
           WHERE action_name IN ({}) AND module_name != ?""".format(
            ",".join("?" for _ in all_actions)),
        list(all_actions) + [module_name]
    ).fetchall()
    if collisions:
        import sys as _sys
        for c in collisions:
            _sys.stderr.write(
                f"[module-manager] WARNING: action '{c['action_name']}' in '{module_name}' "
                f"collides with '{c['module_name']}'\n"
            )

    return len(all_actions)


# ---------------------------------------------------------------------------
# SKILL.md regeneration — appends installed module actions to deployed SKILL.md
# ---------------------------------------------------------------------------

def _regenerate_skill_md(conn):
    """Regenerate the deployed SKILL.md with installed module actions appendix.

    Reads the source SKILL.md as a template, appends an auto-generated section
    listing all installed module actions, and writes to the deployed location.
    The source template is the installed skill's SKILL.md (without the appendix).
    """
    # Find the deployed SKILL.md path
    deployed_path = os.path.expanduser("~/clawd/skills/erpclaw/SKILL.md")
    # Source template is in the same skill directory
    source_path = os.path.join(SCRIPT_DIR, "..", "SKILL.md")

    # Use source if it exists, otherwise use deployed as template
    template_path = source_path if os.path.isfile(source_path) else deployed_path
    if not os.path.isfile(template_path):
        return  # No SKILL.md to regenerate

    try:
        with open(template_path, "r") as f:
            content = f.read()
    except OSError:
        return

    # Strip any existing auto-generated appendix
    marker = "## Installed Module Actions"
    if marker in content:
        content = content[:content.index(marker)].rstrip() + "\n"

    # Query installed modules and their actions
    rows = conn.execute(
        """SELECT ma.module_name, ma.action_name, m.display_name, m.action_count
           FROM erpclaw_module_action ma
           JOIN erpclaw_module m ON m.name = ma.module_name
           WHERE m.install_status = 'installed' AND m.is_active = 1
           ORDER BY ma.module_name, ma.action_name"""
    ).fetchall()

    if not rows:
        # No modules installed — write template without appendix
        if os.path.isfile(deployed_path):
            try:
                with open(deployed_path, "w") as f:
                    f.write(content)
            except OSError:
                pass
        return

    # Group actions by module
    module_actions = {}
    module_display = {}
    module_counts = {}
    for r in rows:
        mod = r["module_name"]
        module_actions.setdefault(mod, []).append(r["action_name"])
        module_display[mod] = r["display_name"]
        module_counts[mod] = r["action_count"] or len(module_actions[mod])

    # Read module descriptions from SKILL.md files for context
    def _get_module_desc(module_name):
        """Read first line of description from module's SKILL.md."""
        for base in [os.path.join(MODULES_DIR, module_name),
                     os.path.join(SCRIPT_DIR, "..", "..", module_name)]:
            skill_path = os.path.join(base, "SKILL.md")
            if os.path.isfile(skill_path):
                try:
                    with open(skill_path, "r") as f:
                        for line in f:
                            if line.startswith("description:"):
                                desc = line.split(":", 1)[1].strip().strip(">").strip()
                                if desc:
                                    return desc[:120]
                except OSError:
                    pass
        return ""

    # Build appendix
    appendix = f"\n\n{marker}\n"
    appendix += "<!-- AUTO-GENERATED — do not edit manually. Regenerated on module install/uninstall. -->\n\n"

    for mod in sorted(module_actions.keys()):
        actions = module_actions[mod]
        display = module_display.get(mod, mod)
        count = len(actions)
        desc = _get_module_desc(mod)

        appendix += f"### {display} ({count} actions)\n"
        if desc:
            appendix += f"{desc}\n"

        # Show key actions (up to 10)
        key_actions = actions[:10]
        appendix += f"Key actions: {', '.join(f'`{a}`' for a in key_actions)}"
        if len(actions) > 10:
            appendix += f", ... (+{len(actions) - 10} more)"
        appendix += "\n\n"

    # Write to deployed path
    deployed_dir = os.path.dirname(deployed_path)
    if os.path.isdir(deployed_dir):
        try:
            with open(deployed_path, "w") as f:
                f.write(content + appendix)
        except OSError:
            pass  # Non-fatal — skill still works, just without action discovery


# ---------------------------------------------------------------------------
# Action: remove-module
# ---------------------------------------------------------------------------

def remove_module(args):
    """Remove an installed module.

    Checks that no other installed modules depend on this one before removal.
    Deletes the module directory and database records, but preserves any
    tables/data the module created (no DROP TABLE).
    """
    module_name = args.module_name
    if not module_name:
        err("--module-name is required")

    conn = get_connection()

    # Check module exists
    row = conn.execute(
        "SELECT * FROM erpclaw_module WHERE name = ?",
        (module_name,)
    ).fetchone()
    if not row:
        err(f"Module '{module_name}' is not installed")

    # Check reverse dependencies — are any other installed modules depending on this one?
    installed = _get_installed_modules(conn)
    dependents = []
    for name, mod in installed.items():
        if name == module_name:
            continue
        requires = json.loads(mod.get("requires_json") or "[]")
        if module_name in requires:
            dependents.append(name)

    if dependents:
        err(
            f"Cannot remove '{module_name}': required by {', '.join(dependents)}",
            suggestion=f"Remove dependent modules first: {', '.join(dependents)}"
        )

    install_path = os.path.expanduser(row["install_path"])

    # Mark as removing
    conn.execute(
        "UPDATE erpclaw_module SET install_status = 'removing', updated_at = ? WHERE name = ?",
        (_now_iso(), module_name)
    )
    conn.commit()

    # Delete action cache
    conn.execute("DELETE FROM erpclaw_module_action WHERE module_name = ?", (module_name,))

    # Delete module record
    conn.execute("DELETE FROM erpclaw_module WHERE name = ?", (module_name,))
    conn.commit()

    # Remove directory
    if install_path and os.path.isdir(install_path):
        shutil.rmtree(install_path, ignore_errors=True)

    # Also remove the workspace-skills mirror so OpenClaw stops listing it.
    workspace_dest = os.path.join(OPENCLAW_WORKSPACE_SKILLS_DIR, module_name)
    if os.path.isdir(workspace_dest):
        shutil.rmtree(workspace_dest, ignore_errors=True)

    # Regenerate SKILL.md without removed module
    _regenerate_skill_md(conn)

    ok({
        "module": module_name,
        "removed": True,
        "note": "Module directory and records removed. Database tables are preserved.",
    })


# ---------------------------------------------------------------------------
# Action: list-modules
# ---------------------------------------------------------------------------

def list_modules(args):
    """List all installed and active modules."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT name, display_name, version, category, action_count,
                  tables_created, installed_at, updated_at, git_commit, install_status
           FROM erpclaw_module
           WHERE is_active = 1
           ORDER BY category, name"""
    ).fetchall()

    modules = rows_to_list(rows)

    # Enrich with action count from cache (authoritative source)
    for mod in modules:
        count = conn.execute(
            "SELECT COUNT(*) as cnt FROM erpclaw_module_action WHERE module_name = ?",
            (mod["name"],)
        ).fetchone()
        mod["cached_actions"] = count["cnt"] if count else 0

    ok({
        "modules": modules,
        "total": len(modules),
    })


# ---------------------------------------------------------------------------
# Action: available-modules
# ---------------------------------------------------------------------------

def available_modules(args):
    """Browse the module catalog, cross-referenced with install status."""
    registry = _load_registry()
    conn = get_connection()
    installed = _get_installed_modules(conn)

    category_filter = getattr(args, "category", None)
    search_query = getattr(args, "search", None)

    results = []
    for mod in _registry_to_dict(registry).values():
        # Filter by category
        if category_filter and mod.get("category") != category_filter:
            continue

        # Filter by search query
        if search_query:
            query_lower = search_query.lower()
            searchable = " ".join([
                mod.get("name", ""),
                mod.get("display_name", ""),
                mod.get("description", ""),
                " ".join(mod.get("tags", [])),
            ]).lower()
            if query_lower not in searchable:
                continue

        entry = {
            "name": mod["name"],
            "display_name": mod.get("display_name", mod["name"]),
            "description": mod.get("description", ""),
            "category": mod.get("category", "expansion"),
            "version": mod.get("version", "0.0.0"),
            "tags": mod.get("tags", []),
            "requires": mod.get("requires", []),
        }

        # Cross-reference with installed modules
        if mod["name"] in installed:
            inst = installed[mod["name"]]
            entry["installed"] = True
            entry["installed_version"] = inst["version"]
            entry["install_status"] = inst["install_status"]
        else:
            entry["installed"] = False

        results.append(entry)

    ok({
        "modules": results,
        "total": len(results),
        "filters": {
            "category": category_filter,
            "search": search_query,
        },
    })


# ---------------------------------------------------------------------------
# Action: module-status
# ---------------------------------------------------------------------------

def module_status(args):
    """Show detailed status for a specific installed module."""
    module_name = args.module_name
    if not module_name:
        err("--module-name is required")

    conn = get_connection()

    row = conn.execute(
        "SELECT * FROM erpclaw_module WHERE name = ?",
        (module_name,)
    ).fetchone()
    if not row:
        err(f"Module '{module_name}' is not installed")

    mod = row_to_dict(row)
    install_path = os.path.expanduser(mod["install_path"])

    # Get cached actions
    actions = conn.execute(
        "SELECT action_name FROM erpclaw_module_action WHERE module_name = ? ORDER BY action_name",
        (module_name,)
    ).fetchall()
    mod["actions"] = [a["action_name"] for a in actions]
    mod["cached_action_count"] = len(mod["actions"])

    # Parse requires_json
    mod["requires"] = json.loads(mod.get("requires_json") or "[]")
    del mod["requires_json"]

    # Check for dependents (who depends on this module)
    installed = _get_installed_modules(conn)
    dependents = []
    for name, inst in installed.items():
        if name == module_name:
            continue
        requires = json.loads(inst.get("requires_json") or "[]")
        if module_name in requires:
            dependents.append(name)
    mod["dependents"] = dependents

    # Local install presence (no network / git remote checks in this air-gapped build)
    mod["directory_exists"] = os.path.isdir(install_path)

    ok(mod)


# ---------------------------------------------------------------------------
# Action: search-modules
# ---------------------------------------------------------------------------

def search_modules(args):
    """Search the module catalog by name, description, and tags."""
    search_query = getattr(args, "search", None)
    if not search_query:
        err("--search is required")

    registry = _load_registry()
    query_lower = search_query.lower()
    query_terms = query_lower.split()

    results = []
    for mod in _registry_to_dict(registry).values():
        searchable = " ".join([
            mod.get("name", ""),
            mod.get("display_name", ""),
            mod.get("description", ""),
            " ".join(mod.get("tags", [])),
        ]).lower()

        # All terms must match
        if all(term in searchable for term in query_terms):
            results.append({
                "name": mod["name"],
                "display_name": mod.get("display_name", mod["name"]),
                "description": mod.get("description", ""),
                "category": mod.get("category", "expansion"),
                "version": mod.get("version", "0.0.0"),
                "tags": mod.get("tags", []),
            })

    ok({
        "query": search_query,
        "results": results,
        "total": len(results),
    })


# ---------------------------------------------------------------------------
# Action: rebuild-action-cache
# ---------------------------------------------------------------------------

def rebuild_action_cache(args):
    """Rebuild the entire action cache from all installed modules.

    Truncates erpclaw_module_action and re-scans every installed module's
    db_query.py. Useful after migrations, manual changes, or cache corruption.
    """
    conn = get_connection()

    # Clear entire cache
    conn.execute("DELETE FROM erpclaw_module_action")
    conn.commit()

    rows = conn.execute(
        "SELECT name, install_path FROM erpclaw_module WHERE install_status = 'installed'"
    ).fetchall()

    rebuilt = []
    errors = []
    total_actions = 0

    for row in rows:
        module_name = row["name"]
        install_path = os.path.expanduser(row["install_path"])

        if not os.path.isdir(install_path):
            errors.append({"module": module_name, "error": "Install directory missing"})
            continue

        try:
            count = build_action_cache(conn, module_name, install_path)
            # Update the action_count in the module record
            conn.execute(
                "UPDATE erpclaw_module SET action_count = ?, updated_at = ? WHERE name = ?",
                (count, _now_iso(), module_name)
            )
            conn.commit()
            rebuilt.append({"module": module_name, "action_count": count})
            total_actions += count
        except Exception as e:
            errors.append({"module": module_name, "error": str(e)})

    # Regenerate SKILL.md with updated actions
    _regenerate_skill_md(conn)

    ok({
        "rebuilt": rebuilt,
        "errors": errors,
        "total_modules": len(rebuilt),
        "total_actions": total_actions,
        "summary": f"Rebuilt cache for {len(rebuilt)} modules ({total_actions} actions), {len(errors)} errors",
    })


# ---------------------------------------------------------------------------
# Action: list-all-actions
# ---------------------------------------------------------------------------

def list_all_actions(args):
    """Return all available actions — core + installed modules."""
    conn = get_connection()

    # Get core actions from the main ACTION_MAP
    # We need to read db_query.py to get the ACTION_MAP keys
    db_query_path = os.path.join(SCRIPT_DIR, "db_query.py")
    core_actions = _extract_actions_via_regex(db_query_path)
    # Also add MODULE_ACTIONS and ONBOARDING_ACTIONS
    core_actions |= {
        "remove-module",
        "list-modules", "available-modules", "module-status",
        "search-modules", "rebuild-action-cache",
        "list-profiles", "onboard", "list-all-actions",
    }

    # Module actions from cache
    rows = conn.execute(
        """SELECT ma.action_name, ma.module_name
           FROM erpclaw_module_action ma
           JOIN erpclaw_module m ON m.name = ma.module_name
           WHERE m.install_status = 'installed' AND m.is_active = 1
           ORDER BY ma.module_name, ma.action_name"""
    ).fetchall()

    module_actions = {}
    for r in rows:
        module_actions.setdefault(r["module_name"], []).append(r["action_name"])

    ok({
        "core_actions": sorted(core_actions),
        "core_count": len(core_actions),
        "module_actions": module_actions,
        "module_count": len(module_actions),
        "total": len(core_actions) + sum(len(v) for v in module_actions.values()),
    })


# ---------------------------------------------------------------------------
# Action: regenerate-skill-md
# ---------------------------------------------------------------------------

def regenerate_skill_md_action(args):
    """Regenerate the deployed SKILL.md with installed module actions."""
    conn = get_connection()
    _regenerate_skill_md(conn)

    # Count what was generated
    rows = conn.execute(
        """SELECT m.name, COUNT(ma.action_name) as cnt
           FROM erpclaw_module m
           LEFT JOIN erpclaw_module_action ma ON m.name = ma.module_name
           WHERE m.install_status = 'installed' AND m.is_active = 1
           GROUP BY m.name"""
    ).fetchall()

    modules = [{"module": r["name"], "actions": r["cnt"]} for r in rows]
    ok({
        "regenerated": True,
        "modules": modules,
        "total_modules": len(modules),
        "deployed_path": os.path.expanduser("~/clawd/skills/erpclaw/SKILL.md"),
    })


# ---------------------------------------------------------------------------
# Action dispatch
# ---------------------------------------------------------------------------

ACTIONS = {
    "remove-module": remove_module,
    "list-modules": list_modules,
    "available-modules": available_modules,
    "module-status": module_status,
    "search-modules": search_modules,
    "rebuild-action-cache": rebuild_action_cache,
    "list-all-actions": list_all_actions,
    "regenerate-skill-md": regenerate_skill_md_action,
}


def main():
    parser = argparse.ArgumentParser(
        description="ERPClaw Module Manager — list, inspect, and remove bundled modules (offline)"
    )
    parser.add_argument(
        "--action", required=True, choices=sorted(ACTIONS.keys()),
        help="Action to perform"
    )
    parser.add_argument(
        "--module-name",
        help="Module name (for remove, status)"
    )
    parser.add_argument(
        "--category",
        choices=["core", "expansion", "infrastructure", "vertical", "sub-vertical", "regional"],
        help="Filter by category (for available-modules)"
    )
    parser.add_argument(
        "--search",
        help="Search query (for search-modules, available-modules)"
    )

    args, _unknown = parser.parse_known_args()
    action_fn = ACTIONS.get(args.action)
    if not action_fn:
        err(f"Unknown action: {args.action}")

    try:
        action_fn(args)
    except SystemExit:
        raise
    except Exception as e:
        err(f"Unexpected error in {args.action}: {e}")


if __name__ == "__main__":
    main()

