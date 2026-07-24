"""
Trains two models from telecom.db and saves them to ml_models/saved/:

1. churn_xgb.pkl   - XGBoost classifier predicting churn risk (0/1)
2. package_rf.pkl  - Random Forest classifier predicting recommended
                      plan tier (Basic / Standard / Premium)

LABELS ARE RULE-BASED, NOT REAL OUTCOMES (yet):
  - Churn label: 1 if a customer has 2+ complaints with status='Open' AND
    priority='High', else 0. This is a reasonable proxy for "at risk" but
    is not an actual observed churn event.
  - Package tier label: derived from a scoring rule over data allowance,
    minutes, and balance (see build_tier_label below), not from real
    upgrade/purchase history.

Replace both label sources with real historical outcomes as soon as
they're available - swap out `build_churn_label` / `build_tier_label`,
retrain, and the rest of the pipeline (features, saving, predictors.py)
stays the same.

Run:
    cd backend
    python data_pipeline/train_models.py
"""
import sys
import os
import sqlite3
import warnings
from pathlib import Path

import joblib
import pandas as pd
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

_THIS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _THIS_DIR.parent
_PROJECT_ROOT = _BACKEND_DIR.parent

# Load backend/.env so TELECOM_DB_PATH is picked up consistently, whether
# this script is run directly or via `railway ssh`.
load_dotenv(dotenv_path=_BACKEND_DIR / ".env")

# Same TELECOM_DB_PATH override as generate_training_data.py and
# connection.py's DATABASE_URL - keep all three in agreement in production
# rather than relying on relative parent-chain guessing.
_DEFAULT_DB_PATH = _PROJECT_ROOT / "telecom.db"
DB_PATH = Path(os.getenv("TELECOM_DB_PATH", str(_DEFAULT_DB_PATH)))
SAVE_DIR = _BACKEND_DIR / "ml_models" / "saved"
CHURN_MODEL_PATH = SAVE_DIR / "churn_xgb.pkl"
PACKAGE_MODEL_PATH = SAVE_DIR / "package_rf.pkl"

# Feature column order - predictors.py MUST build feature vectors using this
# exact order for both models, or predictions will be silently wrong.
CHURN_FEATURE_COLUMNS = [
    "balance",
    "data_gb",
    "has_unlimited_data",
    "minutes_remaining",
    "total_complaints",
    "open_complaints",
    "high_priority_complaints",
    "billing_complaints",
    "network_complaints",
]

PACKAGE_FEATURE_COLUMNS = [
    "balance",
    "data_gb",
    "has_unlimited_data",
    "minutes_remaining",
]


def parse_data_gb(data_remaining: str) -> float:
    if data_remaining is None:
        return 0.0
    cleaned = str(data_remaining).strip().lower()
    if cleaned == "unlimited":
        return 999.0
    try:
        return float(cleaned.replace("gb", "").strip())
    except ValueError:
        return 0.0


def load_raw_tables():
    if not DB_PATH.exists():
        print(f"ERROR: database not found at {DB_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(str(DB_PATH))
    customers = pd.read_sql("SELECT * FROM customers", conn)
    complaints = pd.read_sql("SELECT * FROM complaints", conn)
    conn.close()
    return customers, complaints


def build_features(customers: pd.DataFrame, complaints: pd.DataFrame) -> pd.DataFrame:
    df = customers.copy()
    df["data_gb"] = df["data_remaining"].apply(parse_data_gb)
    df["has_unlimited_data"] = (df["data_remaining"].str.lower() == "unlimited").astype(int)

    agg = complaints.groupby("customer_id").agg(
        total_complaints=("ticket_id", "count"),
        open_complaints=("status", lambda s: (s == "Open").sum()),
        high_priority_complaints=("priority", lambda s: (s == "High").sum()),
        billing_complaints=("issue_type", lambda s: (s == "Billing").sum()),
        network_complaints=("issue_type", lambda s: (s == "Network").sum()),
    ).reset_index()

    df = df.merge(agg, on="customer_id", how="left")
    count_cols = ["total_complaints", "open_complaints", "high_priority_complaints",
                  "billing_complaints", "network_complaints"]
    df[count_cols] = df[count_cols].fillna(0).astype(int)

    return df


def build_churn_label(customers: pd.DataFrame, complaints: pd.DataFrame) -> pd.Series:
    """Rule-based placeholder label: 2+ Open + High priority complaints."""
    open_high = complaints[(complaints["status"] == "Open") & (complaints["priority"] == "High")]
    flagged_ids = set(open_high.groupby("customer_id").size()[lambda s: s >= 2].index)
    return customers["customer_id"].isin(flagged_ids).astype(int)


def build_tier_label(df: pd.DataFrame) -> pd.Series:
    """Rule-based placeholder label mirroring the scoring logic used to
    generate the synthetic training data (see generate_training_data.py's
    choose_plan_tier). Replace with real upgrade/purchase history labels
    once available."""
    def score_row(row):
        score = 0
        score += 2 if (row["data_gb"] >= 25 or row["has_unlimited_data"] == 1) else (1 if row["data_gb"] >= 5 else 0)
        score += 2 if row["minutes_remaining"] >= 1000 else (1 if row["minutes_remaining"] >= 300 else 0)
        score += 1 if row["balance"] >= 80 else 0
        if score >= 4:
            return "Premium"
        elif score >= 2:
            return "Standard"
        return "Basic"

    return df.apply(score_row, axis=1)


def train_churn_model(df: pd.DataFrame, labels: pd.Series):
    X = df[CHURN_FEATURE_COLUMNS]
    y = labels

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = XGBClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.1,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    print("\n=== Churn model (XGBoost) evaluation ===")
    print(classification_report(y_test, preds, zero_division=0))

    return model


def train_package_model(df: pd.DataFrame, labels: pd.Series):
    X = df[PACKAGE_FEATURE_COLUMNS]
    y = labels

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        random_state=42,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    print("\n=== Package tier model (Random Forest) evaluation ===")
    print(classification_report(y_test, preds, zero_division=0))

    return model


def main():
    print(f"Reading data from: {DB_PATH}")
    customers, complaints = load_raw_tables()
    print(f"Loaded {len(customers)} customers, {len(complaints)} complaints")

    df = build_features(customers, complaints)

    churn_labels = build_churn_label(customers, complaints)
    print(f"Churn label distribution:\n{churn_labels.value_counts()}")

    tier_labels = build_tier_label(df)
    print(f"\nPackage tier label distribution:\n{tier_labels.value_counts()}")

    churn_model = train_churn_model(df, churn_labels)
    package_model = train_package_model(df, tier_labels)

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": churn_model, "feature_columns": CHURN_FEATURE_COLUMNS},
        CHURN_MODEL_PATH,
    )
    joblib.dump(
        {"model": package_model, "feature_columns": PACKAGE_FEATURE_COLUMNS},
        PACKAGE_MODEL_PATH,
    )
    print(f"\nSaved churn model to: {CHURN_MODEL_PATH}")
    print(f"Saved package model to: {PACKAGE_MODEL_PATH}")


if __name__ == "__main__":
    main()