# BizTrack PRO: AI-Powered Business Intelligence Dashboard

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0-black.svg)
![Status](https://img.shields.io/badge/Status-Complete-success.svg)

BizTrack PRO is a comprehensive, real-time business intelligence platform designed to empower small to medium-sized businesses. It transforms standard data management into a proactive, intelligent system that provides predictive insights, automates complex analysis, and offers a conversational interface to your business data.

---

## ✨ Key Features

BizTrack PRO integrates a multi-layered AI engine to deliver actionable intelligence at every level of your business operations.

### 📈 Level 1: Real-Time Intelligence

-   **Live Dashboard "Trading Board"**: The main dashboard features a real-time header displaying today's revenue, transaction count, and average sale value, updating automatically every 5 seconds.
-   **Live Transaction Feed**: See sales as they happen with a live feed of the most recent transactions.
-   **Hourly Sales Chart**: Visualize sales performance over the last 24 hours with a dynamic, auto-updating chart.

### 🤖 Level 2: AI-Powered Assistance & Automation

-   **AI-Assisted Product Creation**: When adding a new product, the AI instantly analyzes the name to suggest:
    -   An accurate **category** with a confidence score.
    -   A competitive **price** based on real-world web scraping and internal data.
    -   An optimal initial **stock quantity**.
-   **Intelligent CRM View**: The customers page automatically calculates and displays key metrics like **Total Spend** and **Last Purchase Date**, and assigns a **VIP** badge to high-value customers.
-   **Smart Performance Metrics**: The products table automatically displays a "🔥 Fast" or "🐢 Slow" moving status for each item based on its sales velocity compared to the store average.

### 🔮 Level 3: Predictive Analytics & Forecasting

-   **Interactive Sales Forecasting**: On the AI Insights page, select any product to generate a 7-day sales forecast, complete with trend analysis (increasing, stable, decreasing) and a confidence score.
-   **Proactive Reorder Alerts**: The system automatically identifies products at risk of stocking out, calculates a precise reorder point, and flags items with "Critical" or "High" urgency on the dashboard.

### 💬 Level 4: Conversational Business Intelligence

-   **Global AI Chat Assistant**: A floating chat widget is available on every page, allowing you to ask complex questions in plain English.
-   **Natural Language Queries**: Get instant, formatted answers to commands like:
    -   `"show low stock"`
    -   `"forecast sales for product 5"`
    -   `"who are my top sellers?"`

### ⚙️ Core Business Management

-   **Full CRUD Functionality**: Robust and intuitive interfaces for managing Products, Customers, Invoices, and Payroll.
-   **Secure Authentication**: A complete and secure user management system with:
    -   Strong password hashing (`pbkdf2:sha256`).
    -   "Remember Me" functionality.
    -   Account lockout after failed attempts.
    -   A secure, token-based "Forgot Password" flow.
-   **Database Utilities**: Easily backup the entire database or import/export tables from/to CSV files directly from the UI.

---

## 🛠️ Tech Stack

| Category      | Technology                                                                                             |
| :------------ | :----------------------------------------------------------------------------------------------------- |
| **Backend**   | Python 3.10+, Flask, Flask-WTF (Forms & CSRF), Flask-Limiter (Rate Limiting)                             |
| **Frontend**  | HTML5, CSS3 (with a modern dark theme), JavaScript (ES6+), Chart.js (Charts), Bootstrap 5 (Responsive UI) |
| **Database**  | SQLite                                                                                                 |
| **AI Engine** | Custom logic using `re` and `statistics`, Web Scraping with `requests` and `BeautifulSoup`               |

---

## 🚀 Getting Started

Follow these steps to get BizTrack PRO running on your local machine.

### Prerequisites

-   Python 3.10 or higher
-   `pip` (Python package installer)

### Installation

1.  **Clone the repository:**
    ```sh
    git clone <your-repository-url>
    cd BizTrack_PRO
    ```

2.  **Create and activate a virtual environment:**
    ```sh
    # For Windows
    python -m venv venv
    .\venv\Scripts\activate

    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the required packages:**
    ```sh
    pip install -r requirements.txt
    ```

4.  **(Optional) Install development packages:**
    For linting, formatting, and security audits, install the development dependencies.
    ```sh
    pip install -r dev-requirements.txt
    ```

### Running the Application

1.  **Start the Flask server:**
    ```sh
    flask run
    ```

2.  **Access the application:**
    Open your web browser and navigate to `http://127.0.0.1:5000`.

3.  **Login:**
    The application will create a default administrator account on the first run.
    -   **Username:** `admin`
    -   **Password:** `admin123`

    > **Security Warning:** It is highly recommended to register a new admin account and delete the default one for any real-world use.

---

## 📖 Usage Guide

### Dashboard

The main dashboard provides a real-time overview of your business. Key metrics on the "Trading Board" update every 5 seconds. Low-stock alerts are prominently displayed for immediate action.

### AI-Powered Product Creation

1.  Navigate to the **Products** page.
2.  In the "Add Product" form, start typing a product name (e.g., "Organic Green Tea").
3.  Watch as the AI automatically fills in the **Category**, **Quantity**, and **Price** fields and provides a detailed suggestion card.

### Interactive Forecasting

1.  Go to the **AI Insights** page.
2.  In the "7-Day Sales Forecast" card, start typing a product name.
3.  Select a product from the dropdown to instantly generate and view its sales forecast chart.

### AI Chat Assistant

1.  Click the floating robot icon in the bottom-right corner of any page.
2.  Type a command into the chat window. Try one of these:
    -   `show low stock`
    -   `forecast sales for product 1`
    -   `who are my top sellers?`
    -   `help` (to see more commands)

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome. Feel free to check the issues page if you want to contribute.

## 📜 License

This project is licensed under the MIT License. See the `LICENSE` file for details.

