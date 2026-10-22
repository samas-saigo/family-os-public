"""Local read-only tools; Gmail OAuth/access requires explicit CLI invocation."""
import argparse
from dataclasses import asdict
import json
import logging
import os
import sys
from sqlalchemy import select, func
from .connectors import FixtureConnector
from .db import create_db
from .ingestion import ingest
from .registry import get_account, load_registry
from . import services, analysis_services, audit_services, coverage_services, review_terminal
from .audit import HumanLabels, CandidateThresholds
from .errors import IngestionError
from .schema import source_record, raw_source_record, source_account

def _show_failed_identity(command, error):
    identity = getattr(error, "verified_identity", None)
    labels = {"ingest-gmail": "Authenticated read-only mailbox",
              "ingest-outlook": "Authenticated Microsoft account",
              "ingest-google-calendar": "Authenticated primary Calendar identity"}
    if command in labels and isinstance(identity, str):
        print(f"{labels[command]}: {identity}", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Family OS read-only ingestion tools")
    commands = parser.add_subparsers(dest="command", required=True)
    registry = commands.add_parser("register", help="Load a local household account registry")
    registry.add_argument("config")
    fixture = commands.add_parser("ingest-fixture", help="Ingest synthetic JSON without network calls")
    fixture.add_argument("--household", required=True)
    fixture.add_argument("--account", required=True)
    fixture.add_argument("--file", required=True)
    fixture.add_argument("--page-size", type=int, default=100)
    status = commands.add_parser("status", help="Show aggregate counts without household content")
    status.add_argument("--household", required=True)
    connect = commands.add_parser("gmail-connect", help="Explicit local read-only OAuth into OS keyring")
    connect.add_argument("--household", required=True)
    connect.add_argument("--account", required=True)
    connect.add_argument("--client-file", required=True)
    gmail = commands.add_parser("ingest-gmail", help="Read Gmail metadata using an existing keyring connection")
    gmail.add_argument("--household", required=True)
    gmail.add_argument("--account", required=True)
    gmail.add_argument("--query", default="newer_than:365d -in:spam -in:trash")
    gmail.add_argument("--page-size", type=int, default=25)
    gmail.add_argument("--max-pages", type=int, default=100)
    outlook_connect = commands.add_parser("outlook-connect", help="Explicit public-client Microsoft sign-in into OS keyring")
    outlook_connect.add_argument("--household", required=True)
    outlook_connect.add_argument("--account", required=True)
    outlook_connect.add_argument("--client-id", required=True)
    outlook_connect.add_argument("--authority", default="https://login.microsoftonline.com/common")
    outlook = commands.add_parser("ingest-outlook", help="Read basic metadata with existing Microsoft keyring binding")
    outlook.add_argument("--household", required=True)
    outlook.add_argument("--account", required=True)
    outlook.add_argument("--include-folder", action="append", default=[])
    outlook.add_argument("--exclude-folder", action="append", default=[])
    outlook.add_argument("--page-size", type=int, default=25)
    outlook.add_argument("--max-pages", type=int, default=100)
    calendar_connect = commands.add_parser("google-calendar-connect", help="Explicit Calendar desktop OAuth into separate OS keyring")
    calendar_connect.add_argument("--household", required=True)
    calendar_connect.add_argument("--account", required=True)
    calendar_connect.add_argument("--client-file", required=True)
    for name in ("ingest-google-calendar", "google-calendar-resync"):
        calendar = commands.add_parser(name, help="Read Calendar metadata or explicitly reset one cursor stream")
        calendar.add_argument("--household", required=True)
        calendar.add_argument("--account", required=True)
        calendar.add_argument("--include-calendar", action="append", default=[])
        calendar.add_argument("--exclude-calendar", action="append", default=[])
        if name == "ingest-google-calendar":
            calendar.add_argument("--page-size", type=int, default=25)
            calendar.add_argument("--max-pages", type=int, default=100)
        else:
            target = calendar.add_mutually_exclusive_group(required=True)
            target.add_argument("--calendar-list", action="store_true")
            target.add_argument("--calendar-id")
    drive_connect = commands.add_parser("google-drive-connect", help="Explicit metadata-only Drive OAuth into separate OS keyring")
    drive_connect.add_argument("--household", required=True)
    drive_connect.add_argument("--account", required=True)
    drive_connect.add_argument("--client-file", required=True)
    for name in ("ingest-google-drive", "google-drive-resync", "google-drive-policy"):
        drive = commands.add_parser(name, help="Drive metadata ingestion or explicit local state transformation")
        drive.add_argument("--household", required=True)
        drive.add_argument("--account", required=True)
        drive.add_argument("--include-shared-drive", action="append", default=[])
        if name == "ingest-google-drive":
            drive.add_argument("--page-size", type=int, default=25)
            drive.add_argument("--max-pages", type=int, default=100)
        elif name == "google-drive-resync":
            target = drive.add_mutually_exclusive_group(required=True)
            target.add_argument("--personal", action="store_true")
            target.add_argument("--shared-drive")
        else:
            drive.add_argument("--previous-shared-drive", action="append", default=[])
    review = commands.add_parser("metadata-review", help="Interactive local metadata review; sensitive terminal output")
    review.add_argument("--household", required=True)
    review.add_argument("--since", required=True, help="Inclusive UTC date YYYY-MM-DD")
    review.add_argument("--until", help="Exclusive UTC date YYYY-MM-DD; defaults to tomorrow UTC")
    review.add_argument("--limit", type=int, default=15)
    review.add_argument("--provider", choices=("gmail", "outlook", "google_calendar", "google_drive"))
    review.add_argument("--include-labeled", action="store_true")
    review.add_argument("--classification-config", default="config/classification.yaml")
    review.add_argument("--rules-config", default="config/metadata-classifier.yaml")
    analysis = commands.add_parser("analyze-metadata", help="Classify persisted metadata locally; aggregate output only")
    analysis.add_argument("--household", required=True)
    target = analysis.add_mutually_exclusive_group(required=True)
    target.add_argument("--limit", type=int)
    target.add_argument("--source", help="Explicitly analyze one locally inspected source; safe IDs only")
    analysis.add_argument("--classification-config", default="config/classification.yaml")
    analysis.add_argument("--rules-config", default="config/metadata-classifier.yaml")
    for name in ("metadata-coverage", "metadata-coverage-sample"):
        coverage = commands.add_parser(name, help="Local rule coverage diagnosis; no provider access")
        coverage.add_argument("--household", required=True)
        coverage.add_argument("--limit", required=True, type=int)
        coverage.add_argument("--classification-config", default="config/classification.yaml")
        coverage.add_argument("--rules-config", default="config/metadata-classifier.yaml")
    for name in ("metadata-audit-list", "metadata-audit-label", "metadata-audit-metrics", "metadata-audit-simulate"):
        audit = commands.add_parser(name, help="Explicit local classifier evaluation; no provider access")
        audit.add_argument("--household", required=True)
        audit.add_argument("--classification-config", default="config/classification.yaml")
        if name != "metadata-audit-label":
            audit.add_argument("--rules-config", default="config/metadata-classifier.yaml")
        if name == "metadata-audit-list":
            audit.add_argument("--limit", required=True, type=int)
            audit.add_argument("--strategy", choices=("unlabeled", "needs_review", "accepted", "balanced"), default="unlabeled")
        elif name == "metadata-audit-label":
            audit.add_argument("--analysis", required=True)
            audit.add_argument("--relevance", required=True, choices=("relevant", "irrelevant", "uncertain"))
            audit.add_argument("--domain-category")
            audit.add_argument("--domain-subcategory")
            audit.add_argument("--action", required=True, choices=("required", "not_required", "uncertain"))
        elif name == "metadata-audit-simulate":
            for dimension in ("relevance", "domain", "action"):
                audit.add_argument("--" + dimension + "-threshold", required=True, type=float)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    engine = None
    try:
        if args.command == "metadata-review":
            review_terminal.require_interactive()
        engine = create_db(os.environ.get("DATABASE_URL") or "sqlite:///data/family-os.sqlite3")
        if args.command == "metadata-review":
            review_terminal.run_review(engine, args.household, since=args.since, until=args.until, limit=args.limit,
                provider=args.provider, include_labeled=args.include_labeled,
                classification_path=args.classification_config, rules_path=args.rules_config)
        elif args.command == "register":
            load_registry(engine, args.config)
            print("Registry loaded")
        elif args.command.startswith("metadata-coverage"):
            options = dict(classification_path=args.classification_config, rules_path=args.rules_config)
            if args.command == "metadata-coverage-sample":
                print("LOCAL SENSITIVE OUTPUT: minimized household metadata; do not share or upload.", file=sys.stderr)
                result = coverage_services.coverage_sample(engine, args.household, limit=args.limit, **options)
            else:
                result = coverage_services.coverage_diagnostics(engine, args.household, limit=args.limit, **options)
            print(json.dumps(result, sort_keys=True, allow_nan=False))
        elif args.command == "analyze-metadata" and args.source:
            result = coverage_services.analyze_metadata_source(engine, args.household, args.source,
                classification_path=args.classification_config, rules_path=args.rules_config)
            print(json.dumps(result, sort_keys=True))
        elif args.command == "analyze-metadata":
            result = analysis_services.analyze_metadata(engine, args.household, limit=args.limit,
                classification_path=args.classification_config, rules_path=args.rules_config)
            print(json.dumps(asdict(result)))
        elif args.command == "metadata-audit-label":
            result = audit_services.append_label(engine, args.household, args.analysis,
                HumanLabels(args.relevance, args.domain_category, args.domain_subcategory, args.action),
                classification_path=args.classification_config)
            print(json.dumps(asdict(result), sort_keys=True))
        elif args.command.startswith("metadata-audit-"):
            options = dict(classification_path=args.classification_config, rules_path=args.rules_config)
            if args.command == "metadata-audit-list":
                result = asdict(audit_services.audit_list(engine, args.household, limit=args.limit, strategy=args.strategy, **options))
            elif args.command == "metadata-audit-metrics":
                result = audit_services.audit_metrics(engine, args.household, **options)
            else:
                result = audit_services.audit_simulate(engine, args.household,
                    CandidateThresholds(args.relevance_threshold, args.domain_threshold, args.action_threshold), **options)
            print(json.dumps(result, sort_keys=True, allow_nan=False))
        elif args.command == "ingest-fixture":
            result = ingest(engine, args.household, args.account,
                            FixtureConnector(args.file, args.page_size))
            print(json.dumps(asdict(result)))
        elif args.command == "gmail-connect":
            from .gmail_auth import connect_account
            with engine.connect() as connection:
                account = get_account(connection, args.household, args.account)
            if account.provider != "gmail" or not account.enabled:
                raise ValueError("Expected an enabled Gmail source account")
            identity = connect_account(account, args.client_file)
            print(f"Connected read-only mailbox: {identity}")
        elif args.command == "outlook-connect":
            from .outlook_auth import connect_account
            from .outlook_identity import require_outlook_account
            with engine.connect() as connection:
                account = get_account(connection, args.household, args.account)
            require_outlook_account(account)
            connect_account(account, args.client_id, args.authority)
            print("Connected with delegated Mail.ReadBasic")
        elif args.command == "google-calendar-connect":
            from .google_calendar_auth import connect_account
            from .google_calendar_identity import require_calendar_account
            with engine.connect() as connection:
                account = get_account(connection, args.household, args.account)
            require_calendar_account(account)
            connect_account(account, args.client_file)
            print("Connected with CalendarList and events read-only scopes")
        elif args.command == "google-drive-connect":
            from .google_drive_auth import connect_account
            from .google_drive_identity import require_drive_account
            with engine.connect() as connection:
                account = get_account(connection, args.household, args.account)
            require_drive_account(account)
            connect_account(account, args.client_file,
                display=lambda email: print(f"Authenticated Drive email: {email}", flush=True))
            print("Connected with drive.metadata.readonly")
        elif args.command == "ingest-gmail":
            outcome = services.ingest_gmail(engine, args.household, args.account,
                query=args.query, page_size=args.page_size, max_pages=args.max_pages)
            print(f"Authenticated read-only mailbox: {outcome.verified_identity}", flush=True)
            print(json.dumps(asdict(outcome.ingestion)))
        elif args.command == "ingest-outlook":
            outcome = services.ingest_outlook(engine, args.household, args.account,
                include_folder=args.include_folder, exclude_folder=args.exclude_folder,
                page_size=args.page_size, max_pages=args.max_pages)
            print(f"Authenticated Microsoft account: {outcome.verified_identity}", flush=True)
            print(json.dumps(asdict(outcome.ingestion)))
        elif args.command == "ingest-google-calendar":
            outcome = services.ingest_google_calendar(engine, args.household, args.account,
                include_calendar=args.include_calendar, exclude_calendar=args.exclude_calendar,
                page_size=args.page_size, max_pages=args.max_pages)
            print(f"Authenticated primary Calendar identity: {outcome.verified_identity}", flush=True)
            print(json.dumps(asdict(outcome.ingestion)))
        elif args.command == "ingest-google-drive":
            outcome = services.ingest_google_drive(engine, args.household, args.account,
                include_shared_drive=args.include_shared_drive,
                page_size=args.page_size, max_pages=args.max_pages)
            print(json.dumps(asdict(outcome.ingestion)))
        elif args.command == "google-calendar-resync":
            services.resync_google_calendar(engine, args.household, args.account,
                include_calendar=args.include_calendar, exclude_calendar=args.exclude_calendar,
                calendar_id=args.calendar_id)
            print("Calendar stream reset; historical records retained")
        elif args.command == "google-drive-resync":
            services.resync_google_drive(engine, args.household, args.account,
                include_shared_drive=args.include_shared_drive, drive_id=args.shared_drive)
            print("Drive state updated; historical records retained")
        elif args.command == "google-drive-policy":
            services.migrate_google_drive_policy(engine, args.household, args.account,
                previous_shared_drive=args.previous_shared_drive,
                include_shared_drive=args.include_shared_drive)
            print("Drive state updated; historical records retained")
        else:
            with engine.connect() as connection:
                counts = {table.name: connection.scalar(select(func.count()).select_from(table)
                          .where(table.c.household_id == args.household))
                          for table in (source_account, raw_source_record, source_record)}
            print(json.dumps(counts))
        return 0
    except review_terminal.ReviewTerminalError as error:
        logging.error("%s", error)
        return 1
    except IngestionError as error:
        _show_failed_identity(args.command, error)
        # Only our public safe categories; never stringify provider exceptions.
        logging.error("%s", error)
        return 1
    except Exception as error:
        _show_failed_identity(args.command, error)
        # SQL/connection/provider errors may contain private values. Keep CLI output safe.
        logging.error("Operation failed. Check migrations, registry, database, and connector configuration.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()

if __name__ == "__main__":
    raise SystemExit(main())
