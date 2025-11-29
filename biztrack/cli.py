# cli.py
import argparse
import sys
import logging
from biztrack.webapp import create_flask_app
from biztrack.biztrack_db import (
    execute_query,
    insert_invoice_and_sales,
    remove_duplicates,
    backup_db,
)

# Configure logger
logger = logging.getLogger("cli")
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

def list_products():
    rows = execute_query("SELECT id, name, category, qty, price FROM products;", fetch=True)
    print("ID | Name | Category | Qty | Price")
    for r in rows or []:
        print(f"{r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]}")

def add_product(args):
    execute_query(
        "INSERT INTO products (name, category, qty, price) VALUES (?, ?, ?, ?);",
        (args.name, args.category or "", args.qty, args.price),
        commit=True
    )
    logger.info(f"Added product: {args.name} (qty={args.qty}, price={args.price})")

def list_customers():
    rows = execute_query("SELECT id, name, phone, email FROM customers;", fetch=True)
    print("ID | Name | Phone | Email")
    for r in rows or []:
        print(f"{r[0]} | {r[1]} | {r[2]} | {r[3]}")

def create_invoice(args):
    """
    Create an invoice for a customer.
    Items should be provided as: pid:qty:price
    """
    items = []
    for item_str in args.items:
        try:
            pid_str, qty_str, price_str = item_str.split(":")
            pid = int(pid_str)
            qty = int(qty_str)
            price = float(price_str)
            items.append({"pid": pid, "qty": qty, "price": price})
        except ValueError:
            logger.error(f"Invalid item format: {item_str}. Expected pid:qty:price")
            sys.exit(1)

    invoice_id = insert_invoice_and_sales(args.customer_id, items)
    if invoice_id:
        logger.info(f"Invoice created successfully with ID: {invoice_id}")
    else:
        logger.error("Failed to create invoice")

def dedupe_products():
    remove_duplicates()
    logger.info("Duplicate cleanup complete")

def run_web(args):
    try:
        from biztrack.webapp import create_flask_app
        app = create_flask_app()
        logger.info(f"Starting web server on port {args.port}")
        app.run(port=args.port)
    except ImportError:
        logger.error("Flask not installed or webapp.py missing")

def run_backup(args):
    path = backup_db()
    if path:
        logger.info(f"Backup created: {path}")
    else:
        logger.error("Backup failed")
        
def run_compute_daily_store(args):
    # This functionality is now part of the app's startup logic
    # and can be triggered via a dedicated CLI command if needed.
    logger.info("Daily metrics computation can be triggered via a Flask CLI command or a scheduled job.")
    
def run_patch_schema(args):
    from biztrack.biztrack_db import migrate_schema
    migrate_schema()
    logger.info("Schema patched successfully")

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(prog="biztrack", description="BizTrack PRO CLI")
    sub = parser.add_subparsers(title="commands", dest="command")
    
    
    metrics_store = sub.add_parser("compute-daily-store", help="[DEPRECATED] Compute today's store metrics")
    metrics_store.set_defaults(func=run_compute_daily_store)
    
    patch_parser = sub.add_parser("patch-schema", help="Patch missing columns in DB")
    patch_parser.set_defaults(func=run_patch_schema)

    # Web
    web_parser = sub.add_parser("web", help="Run the web server")
    web_parser.add_argument("--port", type=int, default=5000)
    web_parser.set_defaults(func=run_web)

    # Products
    p_list = sub.add_parser("list-products", help="List all products")
    p_list.set_defaults(func=lambda args: list_products())

    p_add = sub.add_parser("add-product", help="Add a new product")
    p_add.add_argument("--name", required=True, help="Product name")
    p_add.add_argument("--category", help="Product category")
    p_add.add_argument("--qty", type=int, required=True, help="Quantity")
    p_add.add_argument("--price", type=float, required=True, help="Unit price")
    p_add.set_defaults(func=add_product)

    # Customers
    c_list = sub.add_parser("list-customers", help="List all customers")
    c_list.set_defaults(func=lambda args: list_customers())

    # Invoices
    inv_parser = sub.add_parser("create-invoice", help="Create invoice (items as pid:qty:price)")
    inv_parser.add_argument("--customer-id", type=int, required=True)
    inv_parser.add_argument("--items", nargs="+", required=True)
    inv_parser.set_defaults(func=create_invoice)

    # Dedupe
    dedupe_parser = sub.add_parser("dedupe-products", help="Remove duplicate products/customers")
    dedupe_parser.set_defaults(func=lambda args: dedupe_products())

    # Backup
    backup_parser = sub.add_parser("backup", help="Create a database backup")
    backup_parser.set_defaults(func=run_backup)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # The 'web' command handles its own app creation.
    if args.command == 'web':
        args.func(args)
    else:
        # All other commands need an application context to interact with the database.
        app = create_flask_app()
        with app.app_context():
            args.func(args)

if __name__ == "__main__":
    main()
