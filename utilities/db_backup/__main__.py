import argparse
from pathlib import Path

from .neo4j_backup_runner import Neo4jBackupRunner, Neo4jRestoreRunner


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="Infrahub Database Backup and Restore Utility",
        description="Command line tool for backing up an Infrahub database and restoring it",
    )
    subparsers = parser.add_subparsers(dest="database_type", required=True)
    # memgraph_parser = subparsers.add_parser("memgraph", help="memgraph backup/restore tool")
    neo4j_parser = subparsers.add_parser("neo4j", help="Neo4J backup/restore tool")
    neo4j_subparsers = neo4j_parser.add_subparsers(dest="database_action", required=True)
    neo4j_backup_subparser = neo4j_subparsers.add_parser("backup", help="Backup Neo4J database")
    neo4j_backup_subparser.add_argument(
        "backup_directory", default="infrahub-backups", help="Where to save backup files"
    )
    neo4j_backup_subparser.add_argument(
        "--database_url", default=None, required=False, help="URL of database, null implies a local database container"
    )
    neo4j_backup_subparser.add_argument(
        "--database_backup_port", default=6362, help="Port that the database is listening on for backup commands"
    )
    neo4j_backup_subparser.add_argument(
        "--no_aggregate",
        default=False,
        action="store_true",
        help="Skip backup aggregation, potentially leaving multiple incremental backup files per database",
    )
    neo4j_backup_subparser.add_argument(
        "--quiet", default=False, action="store_true", help="Whether to output status messages to terminal"
    )
    neo4j_backup_subparser.add_argument(
        "--keep_helper_container", default=False, action="store_true", help="Keep docker container used to run backup"
    )

    neo4j_restore_subparser = neo4j_subparsers.add_parser("restore", help="Backup Neo4J database")
    neo4j_restore_subparser.add_argument(
        "backup_directory", default="infrahub-backups", help="Directory where the backup files are saved"
    )
    neo4j_restore_subparser.add_argument(
        "--database_cypher_port",
        default=7687,
        help="Port that the Infrahub database container uses for cypher connections",
    )
    neo4j_restore_subparser.add_argument(
        "--keep_helper_container", default=False, action="store_true", help="Keep docker container used to run restore"
    )
    return parser.parse_args()


def run_utility(parsed_args: argparse.Namespace) -> None:
    if parsed_args.database_type == "memgraph":
        print("Database backup and restore is not yet supported for memgraph")
        return

    backup_path = Path(parsed_args.backup_directory)
    if parsed_args.database_action == "backup":
        backup_runner = Neo4jBackupRunner(
            be_quiet=parsed_args.quiet, keep_helper_container=parsed_args.keep_helper_container
        )
        do_aggregate_backups = not parsed_args.no_aggregate
        backup_runner.backup(
            backup_path,
            parsed_args.database_url,
            parsed_args.database_backup_port,
            do_aggregate_backups=do_aggregate_backups,
        )

    elif parsed_args.database_action == "restore":
        backup_runner = Neo4jRestoreRunner(
            keep_helper_container=parsed_args.keep_helper_container,
            database_cypher_port=parsed_args.database_cypher_port,
        )
        backup_runner.restore(backup_path)


if __name__ == "__main__":
    parsed_args = parse()
    run_utility(parsed_args)
