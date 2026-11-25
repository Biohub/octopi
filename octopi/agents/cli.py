"""`octopi agents`: install the octopi skill and MCP server for AI coding agents in one step.

What gets installed:
  * Skill (agentskills.io format) -> .claude/skills/octopi (Claude Code) and/or
    .agents/skills/octopi (Codex and other Agent Skills clients)
  * MCP server -> Claude Code (~/.claude.json or ./.mcp.json), Codex (`codex mcp add`, user-level),
    and optionally Claude Desktop
"""
import filecmp
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path
from typing import Optional

import rich_click as click
from octopi import cli_context
from octopi.mcp import cli as mcp_config

SKILL_NAME = "octopi"
SERVER_NAME = "octopi"

# Skills directory (relative to $HOME or the project root) for each agent family.
AGENT_DIRS = {
    "claude": ".claude",   # Claude Code
    "agents": ".agents",   # Codex and other Agent Skills clients
}
AGENTS = [*AGENT_DIRS, "all"]


# ============================================================================
# Skill helpers
# ============================================================================


def bundled_skill_dir() -> Path:
    return Path(str(resources.files("octopi.skills") / SKILL_NAME))


def _skill_files(src: Path) -> list:
    return sorted(p.name for p in src.iterdir() if p.is_file() and p.suffix == ".md")


def _selected_agents(agent: str) -> list:
    return list(AGENT_DIRS) if agent == "all" else [agent]


def _base(target: str, project_path: Optional[Path]) -> Path:
    return Path.home() if target == "global" else (project_path or Path.cwd())


def skill_dir(base: Path, agent: str) -> Path:
    return base / AGENT_DIRS[agent] / "skills" / SKILL_NAME


def skill_state(dest: Path) -> str:
    """'missing', 'current', or 'outdated' relative to the bundled skill."""
    if not dest.exists():
        return "missing"
    src = bundled_skill_dir()
    _, mismatch, errors = filecmp.cmpfiles(src, dest, _skill_files(src), shallow=False)
    return "outdated" if (mismatch or errors) else "current"


def install_skill(dest: Path, force: bool) -> tuple:
    if dest.is_symlink() or dest.is_file():
        return "skipped", f"{dest} is a symlink or file, not managed by octopi"
    state = skill_state(dest)
    if state == "current":
        return "unchanged", f"already up to date at {dest}"
    if state == "outdated" and not force:
        return "skipped", f"older or modified copy at {dest} (use --force to overwrite)"
    src = bundled_skill_dir()
    dest.mkdir(parents=True, exist_ok=True)
    for name in _skill_files(src):
        shutil.copy2(src / name, dest / name)
    return "installed", f"installed to {dest}"


def remove_skill(dest: Path) -> tuple:
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.exists():
        shutil.rmtree(dest)
    else:
        return "absent", f"not installed at {dest}"
    return "removed", f"removed {dest}"


# ============================================================================
# MCP helpers
# ============================================================================


def claude_code_mcp_path(target: str, project_path: Optional[Path]) -> Path:
    return mcp_config._get_config_path("code-global" if target == "global" else "code-project", project_path)


def claude_desktop_mcp_path() -> Path:
    return mcp_config._get_config_path("desktop")


def _codex(*args) -> Optional[subprocess.CompletedProcess]:
    if shutil.which("codex") is None:
        return None
    return subprocess.run(["codex", "mcp", *args], capture_output=True, text=True, timeout=60)


def codex_registered() -> Optional[bool]:
    """True/False, or None if the Codex CLI isn't installed."""
    result = _codex("get", SERVER_NAME)
    return None if result is None else result.returncode == 0


def install_codex_mcp(python_path: str, force: bool) -> tuple:
    registered = codex_registered()
    if registered is None:
        return "skipped", "Codex CLI not found (skill still works; MCP is optional)"
    if registered and not force:
        return "unchanged", "already registered in Codex (use --force to re-register)"
    if registered:
        _codex("remove", SERVER_NAME)
    result = _codex("add", SERVER_NAME, "--", python_path, "-m", mcp_config.SERVER_MODULE)
    if result.returncode != 0:
        return "error", (result.stderr or result.stdout).strip()
    return "installed", "registered in Codex (~/.codex/config.toml)"


def remove_codex_mcp() -> tuple:
    registered = codex_registered()
    if not registered:
        return "absent", "not registered in Codex"
    result = _codex("remove", SERVER_NAME)
    if result.returncode != 0:
        return "error", (result.stderr or result.stdout).strip()
    return "removed", "removed from Codex"


# ============================================================================
# CLI
# ============================================================================

_SYMBOL = {"installed": "✓", "removed": "✓", "unchanged": "•", "absent": "•", "skipped": "!", "error": "✗"}


def _report(label: str, result: tuple) -> bool:
    status, message = result
    click.echo(f"  {_SYMBOL.get(status, '?')} {label}: {message}")
    return status not in ("skipped", "error")


def _common_options(f):
    f = click.option("--project-path", "-p",
                     type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
                     help="Project directory for --target project (defaults to cwd)")(f)
    f = click.option("--agent", "-a", type=click.Choice(AGENTS), default="all", show_default=True,
                     help="claude (Claude Code), agents (Codex and other Agent Skills clients), or all")(f)
    f = click.option("--target", "-t", type=click.Choice(["global", "project"]), default="global",
                     show_default=True, help="Set up for your user account or only the current project")(f)
    return f


@click.group(context_settings=cli_context, name="agents")
def agents_cli():
    """Set up AI coding agents (Claude Code, Codex, ...) to use octopi."""
    pass


@agents_cli.command("install")
@_common_options
@click.option("--mcp/--no-mcp", default=True, show_default=False,
              help="Register the octopi MCP server, a tool that lets agents run octopi commands. Use --no-mcp to install only the skill")
@click.option("--desktop", is_flag=True, help="Also register the MCP server in Claude Desktop")
@click.option("--python-path", "-py", default=None, help="Python used to launch the MCP server (defaults to current)")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing entries (use after upgrading octopi)")
def agents_install(target: str, agent: str, project_path: Optional[Path], mcp: bool, desktop: bool,
                   python_path: Optional[str], force: bool) -> None:
    """Install the octopi skill and MCP server for your coding agents."""
    python_path = python_path or sys.executable
    base = _base(target, project_path)
    ok = True

    click.echo("Skill")
    for a in _selected_agents(agent):
        ok &= _report(a, install_skill(skill_dir(base, a), force))

    if mcp or desktop:
        click.echo("MCP server")
    if mcp and "claude" in _selected_agents(agent):
        ok &= _report("claude", mcp_config.register_server(
            claude_code_mcp_path(target, project_path), SERVER_NAME, python_path, force))
    if mcp and "agents" in _selected_agents(agent):
        if target == "global":
            ok &= _report("codex", install_codex_mcp(python_path, force))
        else:
            _report("codex", ("skipped", "Codex MCP servers are user-level; run with --target global to register"))
    if desktop:
        ok &= _report("desktop", mcp_config.register_server(
            claude_desktop_mcp_path(), SERVER_NAME, python_path, force))

    click.echo()
    click.echo("Start a new agent session to apply" + (" (and restart Claude Desktop)." if desktop else "."))
    if not ok:
        sys.exit(1)


@agents_cli.command("status")
@_common_options
def agents_status(target: str, agent: str, project_path: Optional[Path]) -> None:
    """Show what's installed and whether it's up to date."""
    base = _base(target, project_path)
    agents = _selected_agents(agent)
    states = {"current": "up to date", "outdated": "outdated (run: octopi agents install --force)",
              "missing": "not installed"}

    click.echo(f"Skill ({target})")
    for a in agents:
        dest = skill_dir(base, a)
        click.echo(f"  {a}: {states[skill_state(dest)]}  [{dest}]")

    click.echo("MCP server")
    if "claude" in agents:
        path = claude_code_mcp_path(target, project_path)
        click.echo(f"  claude: {'registered' if mcp_config.server_registered(path, SERVER_NAME) else 'not registered'}  [{path}]")
    if "agents" in agents:
        reg = codex_registered()
        click.echo(f"  codex: {'Codex CLI not found' if reg is None else ('registered' if reg else 'not registered')}")
    desktop_path = claude_desktop_mcp_path()
    click.echo(f"  desktop: {'registered' if mcp_config.server_registered(desktop_path, SERVER_NAME) else 'not registered'}  [{desktop_path}]")


@agents_cli.command("uninstall")
@_common_options
@click.option("--desktop", is_flag=True, help="Also remove the MCP server from Claude Desktop")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def agents_uninstall(target: str, agent: str, project_path: Optional[Path], desktop: bool, force: bool) -> None:
    """Remove the octopi skill and MCP server registrations."""
    if not force:
        click.confirm(f"Remove the octopi skill and MCP server ({target}, agent={agent})?", abort=True)
    base = _base(target, project_path)
    agents = _selected_agents(agent)

    click.echo("Skill")
    for a in agents:
        _report(a, remove_skill(skill_dir(base, a)))

    click.echo("MCP server")
    if "claude" in agents:
        _report("claude", mcp_config.unregister_server(claude_code_mcp_path(target, project_path), SERVER_NAME))
    if "agents" in agents and target == "global":
        _report("codex", remove_codex_mcp())
    if desktop:
        _report("desktop", mcp_config.unregister_server(claude_desktop_mcp_path(), SERVER_NAME))

    click.echo()
    click.echo("Start a new agent session to apply.")
