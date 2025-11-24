from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from biztrack import (
    set_db_file,
    init_db,
    seed_default_data,
    remove_duplicates,
    ensure_invoice_schema,
    export_sales_csv,
    create_flask_app,
    run_tk_gui,
    admin_exists,
    set_admin_password_interactive,
    login,
    interactive_menu,
    FLASK_AVAILABLE,
)


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="BizTrack — CLI entrypoint")
    parser.add_argument("--db", help="Path to DB file", default=None)
    parser.add_argument("--no-seed", action="store_true", help="Don't seed sample data")
    parser.add_argument("--web", action="store_true", help="Run Flask web app")
    parser.add_argument("--gui", action="store_true", help="Run Tkinter GUI (if available)")
    parser.add_argument("--port", type=int, default=5000, help="Port for web server (default: 5000)")
    parser.add_argument("--export", nargs="?", const="auto_export.csv", help="Export sales CSV and exit")
    args = parser.parse_args(argv)

    if args.db:
        set_db_file(args.db)

    init_db()
    if not args.no_seed:
        seed_default_data()
    remove_duplicates()
    ensure_invoice_schema()

    if args.export:
        export_sales_csv(args.export)
        return

    if args.web:
        if not FLASK_AVAILABLE:
            print("Flask not installed. Install `flask` to use web mode.")
            return
        print(f"Starting Flask app at http://127.0.0.1:{args.port}")
        app = create_flask_app()
        app.run(host="0.0.0.0", port=args.port, debug=False)
        return

    if args.gui:
        run_tk_gui()
        return

    # CLI admin flow
    if not admin_exists():
        print("No admin account found — create one now.")
        set_admin_password_interactive()

    if not login():
        print("Exiting (failed login).")
        sys.exit(1)

    interactive_menu()


if __name__ == "__main__":
    main()
