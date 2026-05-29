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

from modflow_devtools.dfns.migrate import _add_args as _add_migrate_args
from modflow_devtools.dfns.migrate import migrate
from modflow_devtools.dfns.registry import RemoteDfnRegistry, add_to_user_config


def cmd_migrate(args: argparse.Namespace) -> int:
    """Migrate DFN files to a new schema version."""
    try:
        migrate(args.input, args.output, args.schema_version, args.format)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


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


def cmd_add(args: argparse.Namespace) -> int:
    """Add a DFN release to the user config and optionally sync it."""
    release_id = args.release_id
    parts = release_id.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1] or "/" not in parts[0]:
        print(
            f"Error: invalid release ID '{release_id}' (expected 'owner/name@tag')",
            file=sys.stderr,
        )
        return 1

    try:
        added = add_to_user_config(release_id)
        if added:
            print(f"Added {release_id} to user config")
        else:
            print(f"Already in user config: {release_id}")

        if not args.no_sync:
            registry = RemoteDfnRegistry(release_id=release_id)
            print(f"Syncing {release_id}...")
            registry.sync()
            n_files = (
                len(list(registry.cache_path.glob("*.*"))) if registry.cache_path.exists() else 0
            )
            print(f"  {release_id}: {n_files} files")
            print(f"Synced {release_id}")

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

    # migrate
    migrate_parser = subparsers.add_parser(
        "migrate", help="Migrate DFN files to a new schema version"
    )
    _add_migrate_args(migrate_parser)

    # add
    add_parser = subparsers.add_parser("add", help="Add a DFN release to user config")
    add_parser.add_argument(
        "release_id",
        help="Release ID in 'owner/name@tag' format",
    )
    add_parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Write to user config without downloading",
    )

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

    elif args.command == "migrate":
        return cmd_migrate(args)
    elif args.command == "add":
        return cmd_add(args)
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
