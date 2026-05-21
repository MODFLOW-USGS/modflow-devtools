"""
Command-line interface for the DFNs API.

Usage:
    python -m modflow_devtools.dfns sync
    python -m modflow_devtools.dfns info
    python -m modflow_devtools.dfns clean
"""

import argparse
import shutil
import sys

from modflow_devtools.dfns.registry import RemoteDfnRegistry


def cmd_sync(args: argparse.Namespace) -> int:
    """Sync DFN releases from GitHub release assets."""

    registries = RemoteDfnRegistry.load_default()

    try:
        for registry in registries.values():
            print(f"Syncing {registry.release_id}...")
            registry.sync(force=args.force)
            n_files = (
                len(list(registry.cache_path.glob("*.*"))) if registry.cache_path.exists() else 0
            )
            print(f"  {registry.release_id}: {n_files} files")
            print(f"Synced {registry.release_id}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_info(args: argparse.Namespace) -> int:
    """Show DFN release synchronization status."""
    registries = RemoteDfnRegistry.load_default()

    try:
        for registry in registries.values():
            cached = registry.cached_tag()
            if cached:
                _, tag = registry.release_id.split("@")
                suffix = f" ({cached})" if tag == "latest" else ""
                print(f"Cached: {registry.release_id}{suffix}")
            else:
                print(f"Not cached: {registry.release_id}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_clean(args: argparse.Namespace) -> int:
    """Clean the DFN release cache directory."""

    cache_dir = RemoteDfnRegistry.base_cache_path()
    print(f"Cleaning cache directory: {cache_dir}")
    shutil.rmtree(cache_dir, ignore_errors=True)
    print("Cache cleaned.")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m modflow_devtools.dfns",
        description="MODFLOW 6 definition file tools",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # sync
    sync_parser = subparsers.add_parser("sync", help="Sync DFN files from release assets")
    sync_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force re-download even if already cached",
    )

    # info
    subparsers.add_parser("info", help="Show cache info and sync status")

    # clean
    subparsers.add_parser("clean", help="Clean the cache")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    elif args.command == "sync":
        return cmd_sync(args)
    elif args.command == "info":
        return cmd_info(args)
    elif args.command == "clean":
        return cmd_clean(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
