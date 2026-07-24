"""
Generates a synthetic telecom.db with ~250 customers and their complaints,
matching the exact schema of database/models.py, for training the churn and
package-recommendation models.

This is placeholder/prototyping data - swap in real historical data with
actual outcomes (real churn events, real upgrade/downgrade history) as soon
as it's available. The rule-based patterns baked in here exist only so the
models have something coherent to learn from before real labels exist.

Run:
    python data_pipeline/generate_training_data.py
Produces: telecom.db (at the project root, same location the app already uses)
"""
import random
import sqlite3
import datetime
import os
from pathlib import Path

from dotenv import load_dotenv
from faker import Faker

# Load backend/.env so TELECOM_DB_PATH (and anything else) is picked up
# consistently, whether this script is run directly or via `railway ssh`.
_THIS_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=_THIS_DIR.parent / ".env")

fake = Faker()
random.seed(42)
Faker.seed(42)

# Default assumes local dev layout (repo_root/telecom.db, this script three
# levels under repo_root). In production, DO NOT rely on that - set
# TELECOM_DB_PATH explicitly to an absolute path (matching connection.py's
# DATABASE_URL) so this script and the running app always agree on which
# file they're reading/writing, regardless of the container's working
# directory or folder layout.
_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "telecom.db"
OUTPUT_DB_PATH = Path(os.getenv("TELECOM_DB_PATH", str(_DEFAULT_DB_PATH)))
NUM_CUSTOMERS = 260

ISSUE_TYPES = ["Billing", "Network", "Technical", "Package"]
PRIORITIES = ["Low", "Medium", "High"]
STATUSES = ["Open", "In Progress", "Resolved", "Closed"]

DESCRIPTION_TEMPLATES = {
    "Billing": [
        "Charged twice for the standard monthly subscription payment",
        "Unexpected charge appeared on this month's bill",
        "Requesting a refund for an incorrect billing amount",
        "Autopay deducted the wrong amount from the account",
    ],
    "Network": [
        "Internet connection is down",
        "Slow internet speed during peak hours",
        "Frequent call drops in the service area",
        "No signal since this morning",
    ],
    "Technical": [
        "Router keeps disconnecting every few hours",
        "Unable to activate new SIM card",
        "App login keeps failing",
        "Voicemail setup is not working",
    ],
    "Package": [
        "Data allowance depleted faster than expected",
        "Requesting to switch to a higher tier plan",
        "Package benefits not reflecting after renewal",
        "Confused about current plan's included minutes",
    ],
}


def parse_data_gb(data_remaining: str) -> float:
    if data_remaining.strip().lower() == "unlimited":
        return 999.0
    return float(data_remaining.replace("GB", "").strip())


def choose_plan_tier(data_gb: float, minutes: int, balance: float) -> str:
    """Rule used only to generate a plausible ground-truth label for this
    synthetic dataset - replace with real historical upgrade/purchase
    outcomes once available."""
    score = 0
    score += 2 if data_gb >= 25 or data_gb == 999.0 else (1 if data_gb >= 5 else 0)
    score += 2 if minutes >= 1000 else (1 if minutes >= 300 else 0)
    score += 1 if balance >= 80 else 0

    if score >= 4:
        return "Premium"
    elif score >= 2:
        return "Standard"
    return "Basic"


def generate_customers(n):
    customers = []
    for i in range(1, n + 1):
        customer_id = f"CUST-{1000 + i}"
        name = fake.name()

        # Usage profile drives both data_remaining/minutes AND the
        # ground-truth tier label together, so the two stay consistent.
        tier_seed = random.choices(
            ["Basic", "Standard", "Premium"], weights=[0.4, 0.4, 0.2]
        )[0]

        if tier_seed == "Basic":
            data_gb = round(random.uniform(0.5, 6), 1)
            minutes = random.randint(10, 350)
            balance = round(random.uniform(5, 60), 2)
        elif tier_seed == "Standard":
            data_gb = round(random.uniform(5, 30), 1)
            minutes = random.randint(200, 1100)
            balance = round(random.uniform(30, 120), 2)
        else:  # Premium
            data_gb = 999.0 if random.random() < 0.5 else round(random.uniform(25, 60), 1)
            minutes = random.randint(900, 3000)
            balance = round(random.uniform(80, 400), 2)

        data_remaining = "Unlimited" if data_gb == 999.0 else f"{data_gb} GB"
        actual_tier = choose_plan_tier(data_gb, minutes, balance)

        customers.append({
            "customer_id": customer_id,
            "name": name,
            "balance": balance,
            "data_remaining": data_remaining,
            "minutes_remaining": minutes,
            "_tier_label": actual_tier,  # not written to DB, used for QA only
        })
    return customers


def generate_complaints(customers):
    complaints = []
    ticket_counter = 1

    for cust in customers:
        # ~30% of customers are "at risk": guarantee at least 2 open,
        # high-priority complaints so the churn rule has real, balanced
        # signal to learn from (rather than leaving it to chance).
        is_at_risk = random.random() < 0.30
        num_complaints = random.choices([0, 1, 2, 3, 4], weights=[0.25, 0.25, 0.2, 0.2, 0.1])[0]
        if is_at_risk:
            num_complaints = max(num_complaints, random.randint(2, 4))

        guaranteed_high_open = 2 if is_at_risk else 0

        for complaint_idx in range(num_complaints):
            issue_type = random.choice(ISSUE_TYPES)
            description = random.choice(DESCRIPTION_TEMPLATES[issue_type])

            if complaint_idx < guaranteed_high_open:
                # Force the first two complaints for at-risk customers to be
                # High priority + Open, guaranteeing the churn rule fires.
                priority = "High"
                status = "Open"
            elif is_at_risk:
                priority = random.choices(["High", "Medium", "Low"], weights=[0.5, 0.3, 0.2])[0]
                status = random.choices(["Open", "In Progress", "Resolved", "Closed"],
                                         weights=[0.4, 0.25, 0.2, 0.15])[0]
            else:
                priority = random.choices(["High", "Medium", "Low"], weights=[0.15, 0.35, 0.5])[0]
                status = random.choices(["Open", "In Progress", "Resolved", "Closed"],
                                         weights=[0.15, 0.2, 0.3, 0.35])[0]

            days_ago = random.randint(0, 180)
            created_at = datetime.datetime(2026, 7, 11) - datetime.timedelta(days=days_ago)

            ticket_id = f"CMP-2026-{ticket_counter:04d}"
            ticket_counter += 1

            complaints.append({
                "ticket_id": ticket_id,
                "customer_id": cust["customer_id"],
                "issue_type": issue_type,
                "priority": priority,
                "description": description,
                "status": status,
                "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
            })

    return complaints


def build_database(customers, complaints):
    if OUTPUT_DB_PATH.exists():
        OUTPUT_DB_PATH.unlink()

    conn = sqlite3.connect(str(OUTPUT_DB_PATH))
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id VARCHAR UNIQUE NOT NULL,
            name VARCHAR NOT NULL,
            balance FLOAT DEFAULT 0.0,
            data_remaining VARCHAR DEFAULT '0 GB',
            minutes_remaining INTEGER DEFAULT 0
        )
    """)
    cur.execute("CREATE INDEX ix_customers_customer_id ON customers (customer_id)")

    cur.execute("""
        CREATE TABLE complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id VARCHAR UNIQUE NOT NULL,
            customer_id VARCHAR NOT NULL,
            issue_type VARCHAR NOT NULL,
            priority VARCHAR NOT NULL,
            description TEXT NOT NULL,
            status VARCHAR DEFAULT 'Open',
            created_at DATETIME
        )
    """)
    cur.execute("CREATE INDEX ix_complaints_ticket_id ON complaints (ticket_id)")

    cur.executemany(
        "INSERT INTO customers (customer_id, name, balance, data_remaining, minutes_remaining) "
        "VALUES (:customer_id, :name, :balance, :data_remaining, :minutes_remaining)",
        customers,
    )
    cur.executemany(
        "INSERT INTO complaints (ticket_id, customer_id, issue_type, priority, description, status, created_at) "
        "VALUES (:ticket_id, :customer_id, :issue_type, :priority, :description, :status, :created_at)",
        complaints,
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    customers = generate_customers(NUM_CUSTOMERS)
    complaints = generate_complaints(customers)
    build_database(customers, complaints)
    print(f"Generated {len(customers)} customers and {len(complaints)} complaints")
    print(f"Database written to: {OUTPUT_DB_PATH}")