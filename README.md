##BizTrack PRO

**A modern, lightweight inventory-and-sales management web + CLI application for small businesses.**

---
Self-taught • Zero prior experience • No laptop • 100 % passing tests

<p align="center">
  <img src="screenshots/logo.png" alt="BizTrack PRO Logo" width="500>
</p>

---

## 🚀 What It Does  
- Manage **Products**, **Customers**, **Sales**, and **Payroll** from a unified interface.  
- Two modes:  
  - CLI mode (for terminals)  
  - Web mode (browser-based, fully secured with login)  
- Export and import CSVs, backup the database, receipts, etc.  
- Built in Python using SQLite, Flask, Bootstrap 5 — minimal dependencies.

---

## 🔐 New in this Version (v2.x)  
- Polished web UI with modern dark theme and glass-morphism styling.  
- Web authentication: admin login, session-based access control.  
- Role-ready design for deployment and real-world use (e.g., in cloud or on-prem).  
- Improved code structure, database API stable, easier for customization and freelance work.

---

## 🧩 Features Summary  
| Feature           | Description                                 |
|-------------------|---------------------------------------------|
| Products          | Add, list, update, delete products          |
| Customers         | Manage your customers and their contact info|
| Sales             | Record sales, link to product & customer    |
| Payroll           | Manage employees and salary items           |
| Web Interface     | Browser UI (login required)                 |
| CLI Interface     | Terminal version for quick operations       |
| Export/Backup     | CSV export, DB backup built-in              |

---

## 🛠️ Getting Started  
1. Clone the repo:  
   ```bash
   git clone https://github.com/kalinoosi681-droid/BizTrack_PRO.git
   cd BizTrack_PRO
   ```
2. Create a virtual environment and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Seed the database (will auto-create tables if needed).

Launch web mode:
```bash
python biztrack.py --web
```

Then navigate to http://127.0.0.1:5000/login to log in.

5. Use CLI mode:
```bash
python biztrack.py
```

Quick Start (CLI)
------------------

Run the command-line interface (default):

```
python biztrack.py
```

Run tests:

```
python -m pip install -r requirements.txt
python -m pytest -q
```

Run the web app locally:

```
python biztrack.py --web --port 5000
```

Notes:
- For PDF generation install `reportlab`.
- Optionally install `twilio` to enable SMS notifications.
🔧 Configuration

Database file: biztrack.db by default (in project root).

Admin login: The first run creates the admin user entry (or you can use CLI mode to add one).

Static assets: Place your company logo (biztrack_logo.png) in static/ folder.

Customisation: You can modify INDEX_HTML, LOGIN_HTML, or extract templates into .html files for custom themes.

Running Tests

We provide tests for core database logic. To run them:
```bash
pytest -q
```

All tests pass under the current version.

📄 License

Distributed under the MIT License.

Contribution

Contributions are welcome: new features, improved UI, bug fixes.
Please open an issue or submit a pull request.

🧠 About the Developer

Built by Kali Noosi.
I’m a freelance Backend Dev & web design developer specialising in Python tools for business workflows.

