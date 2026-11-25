import json
import os
import platform
import sys
from pathlib import Path
from typing import Optional

import rich_click as click
from octopi import cli_context


@click.group(context_settings=cli_context, name="mcp", hidden=True)
def mcp_cli():
    """Octopi MCP server (legacy commands; use `octopi agents install` instead)."""
    pass


@mcp_cli.command("start", hidden=True)
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio", show_default=True, help="MCP transport")
@click.option("--port", type=int, default=8000, show_default=True, help="Port for SSE transport")
def mcp_start(transport: str, port: int) -> None:
    """Start the octopi MCP server (called by Claude — not for direct use)."""
    from octopi.mcp.server import mcp

    if transport == "sse":
        mcp.run(transport="sse", port=port)
    else:
        mcp.run(transport="stdio")


def _get_config_path(target: str, project_path: Optional[Path] = None) -> Path:
    if target == "code-global":
        return Path.home() / ".claude.json"
    elif target == "code-project":
        base = project_path or Path.cwd()
        return base / ".mcp.json"
    else:  # desktop
        system = platform.system()
        if system == "Darwin":
            return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        elif system == "Windows":
            appdata = os.getenv("APPDATA", "")
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
        else:
            return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _target_display(target: str) -> str:
    return {
        "desktop": "Claude Desktop",
        "code-global": "Claude Code (global)",
        "code-project": "Claude Code (project)",
    }.get(target, target)


SERVER_MODULE = "octopi.mcp.server"


def read_config(config_path: Path) -> dict:
    """Read a Claude JSON config; returns {} if it doesn't exist. Raises on unreadable files."""
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return json.load(f)


def register_server(config_path: Path, server_name: str = "octopi", python_path: Optional[str] = None,
                    force: bool = False) -> tuple:
    """Add the octopi MCP server to a Claude config. Returns (status, message), status in
    {'installed', 'unchanged', 'skipped', 'error'}."""
    python_path = python_path or sys.executable
    entry = {"command": python_path, "args": ["-m", SERVER_MODULE], "env": {}}
    try:
        config = read_config(config_path)
    except (json.JSONDecodeError, OSError) as e:
        if not force:
            return "error", f"cannot read {config_path} ({e}); use --force to overwrite"
        config = {}

    servers = config.setdefault("mcpServers", {})
    if servers.get(server_name) == entry:
        return "unchanged", f"already registered in {config_path}"
    if server_name in servers and not force:
        return "skipped", f"a different '{server_name}' entry exists in {config_path} (use --force to overwrite)"

    servers[server_name] = entry
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    except OSError as e:
        return "error", f"cannot write {config_path} ({e})"
    return "installed", f"registered in {config_path}"


def unregister_server(config_path: Path, server_name: str = "octopi") -> tuple:
    """Remove a server entry from a Claude config. Returns (status, message)."""
    try:
        config = read_config(config_path)
    except (json.JSONDecodeError, OSError) as e:
        return "error", f"cannot read {config_path} ({e})"
    servers = config.get("mcpServers", {})
    if server_name not in servers:
        return "absent", f"not registered in {config_path}"
    del servers[server_name]
    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    except OSError as e:
        return "error", f"cannot write {config_path} ({e})"
    return "removed", f"removed from {config_path}"


def server_registered(config_path: Path, server_name: str = "octopi") -> bool:
    try:
        return server_name in read_config(config_path).get("mcpServers", {})
    except (json.JSONDecodeError, OSError):
        return False


@mcp_cli.command("install", hidden=True)
@click.option(
    "--target", "-t",
    type=click.Choice(["desktop", "code-global", "code-project"]),
    default="code-project",
    show_default=True,
    help="Where to register: Claude Desktop, global Claude Code, or project-specific",
)
@click.option(
    "--project-path", "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Project directory for --target code-project (defaults to cwd)",
)
@click.option("--server-name", "-n", default="octopi", show_default=True, help="Name for the MCP server entry")
@click.option("--python-path", "-py", default=None, help="Path to Python executable (defaults to current Python)")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing entry if present")
def mcp_install(target: str, project_path: Optional[Path], server_name: str, python_path: Optional[str], force: bool) -> None:
    """Register octopi as an MCP server (deprecated: use `octopi agents install`)."""
    click.echo("Note: `octopi mcp install` is deprecated; `octopi agents install` sets up the skill and MCP together.")
    config_path = _get_config_path(target, project_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if not python_path:
        python_path = sys.executable

    config: dict = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            if not force:
                click.echo(f"Error reading existing config: {e}")
                click.echo("   Use --force to overwrite.")
                sys.exit(1)
            click.echo(f"Warning: existing config unreadable, starting fresh: {e}")

    config.setdefault("mcpServers", {})

    if server_name in config["mcpServers"] and not force:
        click.echo(f"Server '{server_name}' already registered in {config_path}")
        click.echo("   Use --force to overwrite or choose a different --server-name.")
        sys.exit(1)

    config["mcpServers"][server_name] = {
        "command": python_path,
        "args": ["-m", "octopi.mcp.server"],
        "env": {},
    }

    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    except OSError as e:
        click.echo(f"Error writing config: {e}")
        sys.exit(1)

    target_name = _target_display(target)
    click.echo(f"Registered '{server_name}' in {target_name}")
    click.echo(f"   Config: {config_path}")
    click.echo(f"   Command: {python_path} -m octopi.mcp.server")
    click.echo()
    if target == "desktop":
        click.echo("   Restart Claude Desktop to apply.")
    elif target == "code-global":
        click.echo("   Start a new Claude Code session to apply.")
    else:
        proj = project_path or Path.cwd()
        click.echo(f"   Open Claude Code in {proj} to apply.")


@mcp_cli.command("status", hidden=True)
@click.option(
    "--target",
    type=click.Choice(["desktop", "code-global", "code-project"]),
    default="code-project",
    show_default=True,
)
@click.option("--project-path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path))
def mcp_status(target: str, project_path: Optional[Path]) -> None:
    """Show octopi MCP server registration status."""
    config_path = _get_config_path(target, project_path)
    target_name = _target_display(target)

    click.echo(f"MCP status — {target_name}")
    click.echo(f"  Config: {config_path}")
    click.echo(f"  Exists: {'yes' if config_path.exists() else 'no'}")

    if not config_path.exists():
        click.echo()
        click.echo(f"  Run: octopi mcp install --target {target}")
        return

    try:
        with open(config_path) as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        click.echo(f"  Error reading config: {e}")
        return

    servers = config.get("mcpServers", {})
    octopi_servers = {k: v for k, v in servers.items() if "octopi" in k.lower()}

    if octopi_servers:
        for name, entry in octopi_servers.items():
            cmd = entry.get("command", "?")
            args = " ".join(entry.get("args", []))
            click.echo(f"  {name}: {cmd} {args}")
    else:
        click.echo("  No octopi MCP server registered")
        click.echo(f"  Run: octopi mcp install --target {target}")


@mcp_cli.command("uninstall", hidden=True)
@click.option(
    "--target",
    type=click.Choice(["desktop", "code-global", "code-project"]),
    default="code-project",
    show_default=True,
)
@click.option("--project-path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path))
@click.option("--server-name", required=True, help="Name of the MCP server entry to remove")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def mcp_uninstall(target: str, project_path: Optional[Path], server_name: str, force: bool) -> None:
    """Remove an octopi MCP server entry from Claude configuration."""
    config_path = _get_config_path(target, project_path)

    if not config_path.exists():
        click.echo(f"No config found at {config_path}")
        sys.exit(1)

    try:
        with open(config_path) as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        click.echo(f"Error reading config: {e}")
        sys.exit(1)

    servers = config.get("mcpServers", {})
    if server_name not in servers:
        click.echo(f"Server '{server_name}' not found in {config_path}")
        sys.exit(1)

    if not force:
        click.confirm(f"Remove '{server_name}' from {_target_display(target)}?", abort=True)

    del servers[server_name]

    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    except OSError as e:
        click.echo(f"Error writing config: {e}")
        sys.exit(1)

    click.echo(f"Removed '{server_name}' from {config_path}")
    if target == "desktop":
        click.echo("   Restart Claude Desktop to apply.")
    else:
        click.echo("   Start a new Claude Code session to apply.")
