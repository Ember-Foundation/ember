"""Ember CLI command implementations."""
import asyncio
import importlib
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path


def _find_ember_root() -> Path:
    import ember
    return Path(ember.__file__).parent.parent


def _load_app(spec: str | None):
    if spec is None:
        for default in ("main:app", "app:app", "application:app"):
            try:
                return _load_app(default)
            except (ImportError, AttributeError):
                continue
        raise SystemExit("Cannot find app — use --app module:attr (e.g. main:app)")
    if ":" not in spec:
        raise SystemExit(f"Invalid app spec {spec!r} — expected module:attr format")
    module_name, attr = spec.split(":", 1)
    sys.path.insert(0, os.getcwd())
    mod = importlib.import_module(module_name)
    return getattr(mod, attr)


def cmd_version():
    from ember.__version__ import __version__
    print(f"Ember {__version__}")


def cmd_new(args):
    name = args.name
    port = args.port

    project_dir = Path(name)
    if project_dir.exists():
        raise SystemExit(f"Directory '{name}' already exists.")

    project_dir.mkdir(parents=True)

    (project_dir / "main.py").write_text(textwrap.dedent(f"""\
        from ember import Ember

        app = Ember()


        @app.get("/")
        async def index(request):
            return {{"message": "Hello from Ember!"}}


        @app.get("/health")
        async def health(request):
            return {{"status": "ok"}}


        if __name__ == "__main__":
            app.run(host="0.0.0.0", port={port})
    """))

    (project_dir / "requirements.txt").write_text("ember-api\n")

    print(f"  Created {name}/")
    print(f"  Created {name}/main.py")
    print(f"  Created {name}/requirements.txt")
    print("\nNext steps:")
    print(f"  cd {name}")
    print("  ember dev")


def cmd_build(args):
    ember_root = _find_ember_root()
    setup_py = ember_root / "setup.py"

    if not setup_py.exists():
        raise SystemExit(f"setup.py not found at {ember_root}")

    if args.clean:
        _clean_build(ember_root)

    cmd = [sys.executable, str(setup_py), "build_ext", "--inplace"]
    if args.jobs:
        cmd.append(f"--parallel={args.jobs}")

    print("Building Cython extensions...")
    result = subprocess.run(cmd, cwd=str(ember_root))

    if result.returncode != 0:
        raise SystemExit("Build failed.")

    print("\nBuild complete.")


def _clean_build(root: Path):
    build_dir = root / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
        print(f"  Removed {build_dir}")

    for pattern in ("*.so", "*.pyd", "*.c"):
        for f in root.rglob(pattern):
            if "build" not in f.parts and "vendor" not in f.parts:
                f.unlink()
                print(f"  Removed {f.relative_to(root)}")


def cmd_dev(args):
    sys.path.insert(0, os.getcwd())
    app = _load_app(args.app)

    print(f"  Ember dev server → http://{args.host}:{args.port}")
    print("  Press Ctrl+C to stop\n")

    app.run(host=args.host, port=args.port, workers=1, debug=True)


def cmd_start(args):
    sys.path.insert(0, os.getcwd())
    app = _load_app(args.app)

    workers = args.workers
    print(f"  Ember production server → http://{args.host}:{args.port}")
    if workers:
        print(f"  Workers: {workers}")

    app.run(host=args.host, port=args.port, workers=workers)


def cmd_routes(args):
    sys.path.insert(0, os.getcwd())
    app = _load_app(args.app)

    asyncio.run(app.initialize())

    router = app.router
    # Collect (method, route) pairs from _static and _dynamic dicts
    pairs: list[tuple[str, object]] = []
    for method_bytes, route_map in getattr(router, "_static", {}).items():
        method = method_bytes.decode() if isinstance(method_bytes, bytes) else method_bytes
        for route in route_map.values():
            pairs.append((method, route))
    for method_bytes, route_list in getattr(router, "_dynamic", {}).items():
        method = method_bytes.decode() if isinstance(method_bytes, bytes) else method_bytes
        for route in route_list:
            pairs.append((method, route))

    if not pairs:
        print("No routes registered.")
        return

    print(f"\n{'METHOD':<10} {'PATH':<45} {'HANDLER'}")
    print("─" * 80)
    for method, route in sorted(pairs, key=lambda x: str(getattr(x[1], "pattern", ""))):
        pattern = getattr(route, "pattern", str(route))
        handler = getattr(route, "handler", None)
        handler_name = handler.__name__ if callable(handler) else "?"
        suffix = "  [AI/SSE]" if getattr(route, "is_sse", False) else ""
        print(f"{method:<10} {str(pattern):<45} {handler_name}{suffix}")
    print()
