"""
Ember CLI — ember <command> [options]

Commands:
  new <name>     Scaffold a new Ember project
  dev            Run dev server (pure Python, auto-reload)
  build          Compile Cython extensions
  start          Run production server (uses compiled extensions if available)
  routes         List all registered routes
  version        Show version info
"""
import argparse
import sys

from . import commands


BANNER = r"""
  ███████╗███╗   ███╗██████╗ ███████╗██████╗
  ██╔════╝████╗ ████║██╔══██╗██╔════╝██╔══██╗
  █████╗  ██╔████╔██║██████╔╝█████╗  ██████╔╝
  ██╔══╝  ██║╚██╔╝██║██╔══██╗██╔══╝  ██╔══██╗
  ███████╗██║ ╚═╝ ██║██████╔╝███████╗██║  ██║
  ╚══════╝╚═╝     ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝
  AI-API Framework  v{version}
"""


def cli():
    parser = argparse.ArgumentParser(
        prog="ember",
        description="Ember — AI-API framework CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="store_true", help="Show version and exit")

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # ── new ────────────────────────────────────────────────────────────────────
    p_new = sub.add_parser("new", help="Scaffold a new Ember project")
    p_new.add_argument("name", help="Project name")
    p_new.add_argument("--port", type=int, default=8000, help="Default port (default: 8000)")
    p_new.add_argument("--workers", type=int, default=None, help="Worker count (default: cpu+2)")

    # ── dev ────────────────────────────────────────────────────────────────────
    p_dev = sub.add_parser("dev", help="Run dev server (pure Python, auto-reload)")
    p_dev.add_argument("--host",    default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    p_dev.add_argument("--port",    type=int, default=8000, help="Bind port (default: 8000)")
    p_dev.add_argument("--app",     default=None, help="App module path e.g. main:app")
    p_dev.add_argument("--reload",  action="store_true", default=True, help="Auto-reload on change")

    # ── build ──────────────────────────────────────────────────────────────────
    p_build = sub.add_parser("build", help="Compile Cython extensions")
    p_build.add_argument("--clean",   action="store_true", help="Remove build artifacts first")
    p_build.add_argument("--annotate", action="store_true", help="Generate HTML annotation files")
    p_build.add_argument("--jobs",    type=int, default=None, help="Parallel compile jobs (default: cpu count)")

    # ── start ──────────────────────────────────────────────────────────────────
    p_start = sub.add_parser("start", help="Run production server")
    p_start.add_argument("--host",    default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    p_start.add_argument("--port",    type=int, default=8000, help="Bind port (default: 8000)")
    p_start.add_argument("--workers", type=int, default=None, help="Worker processes (default: cpu+2)")
    p_start.add_argument("--app",     default=None, help="App module path e.g. main:app")

    # ── routes ─────────────────────────────────────────────────────────────────
    p_routes = sub.add_parser("routes", help="List all registered routes")
    p_routes.add_argument("--app", default=None, help="App module path e.g. main:app")

    # ── version ────────────────────────────────────────────────────────────────
    sub.add_parser("version", help="Show version info")

    args = parser.parse_args()

    if args.version or args.command == "version":
        commands.cmd_version()
        return

    if args.command is None:
        from ember.__version__ import __version__
        print(BANNER.format(version=__version__))
        parser.print_help()
        return

    dispatch = {
        "new":    lambda: commands.cmd_new(args),
        "dev":    lambda: commands.cmd_dev(args),
        "build":  lambda: commands.cmd_build(args),
        "start":  lambda: commands.cmd_start(args),
        "routes": lambda: commands.cmd_routes(args),
    }

    fn = dispatch.get(args.command)
    if fn:
        fn()
    else:
        parser.print_help()
        sys.exit(1)
