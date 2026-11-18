
import json
import os
import tempfile
from pathlib import Path
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import uuid4


DATABASE_FILE = Path(__file__).with_name(
    "finance_database.json"
)


# 1. LOAD DATABASE
def load_database():
    with open(DATABASE_FILE, "r", encoding="utf-8") as file:
        database = json.load(file)

    if not isinstance(database, dict):
        raise ValueError("Invalid database format")

    if not isinstance(database.get("transactions"), list):
        raise ValueError("Missing transactions list")

    return database


# 2. CLEAN TEXT
def clean_text(value):
    if not isinstance(value, str):
        return ""

    return " ".join(value.strip().split())


# 3. CLEAN AMOUNT
def clean_amount(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("Invalid amount")

    if not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("Invalid amount type")

    text = str(value).strip().replace(" ", "")

    # Accept both 25.50 and 25,50
    text = text.replace(",", ".")

    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise ValueError("Amount must be numeric")

    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be positive")

    cents = amount * 100

    if cents != cents.to_integral_value():
        raise ValueError("Maximum two decimal places")

    return int(cents)


# 4. CLEAN DATE
def clean_date(value):
    if value is None or value == "":
        return date.today().isoformat()

    if not isinstance(value, str):
        raise ValueError("Invalid date type")

    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        raise ValueError("Date must be YYYY-MM-DD")


# 5. CATEGORIZE MERCHANT
def categorize_merchant(merchant, database):
    merchant = clean_text(merchant).casefold()

    rules = database.get("merchant_category_rules", [])

    for rule in rules:
        keyword = clean_text(
            rule.get("keyword", "")
        ).casefold()

        if keyword and keyword in merchant:
            return rule["category_id"]

    # Default: Other expenses
    for category in database.get("categories", []):
        if (
            category.get("name") == "Други разходи"
            and category.get("type") == "expense"
        ):
            return category["id"]

    return None


# 6. CLEAN AND CATEGORIZE PIPELINE
def clean_and_categorize(raw_transaction, database):
    if not isinstance(raw_transaction, dict):
        raise ValueError("Transaction must be an object")

    merchant = clean_text(
        raw_transaction.get("merchant_name")
    )

    transaction_type = clean_text(
        raw_transaction.get("type")
    ).lower()

    if not merchant:
        raise ValueError("Merchant or source is required")

    if transaction_type not in ("income", "expense"):
        raise ValueError("Type must be income or expense")

    amount_cents = clean_amount(
        raw_transaction.get("amount")
    )

    transaction_date = clean_date(
        raw_transaction.get("transaction_date")
    )

    description = clean_text(
        raw_transaction.get("description", "")
    )

    user_id = raw_transaction.get("user_id")
    account_id = raw_transaction.get("account_id")

    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or user_id <= 0
    ):
        raise ValueError("Valid user_id required")

    if (
        isinstance(account_id, bool)
        or not isinstance(account_id, int)
        or account_id <= 0
    ):
        raise ValueError("Valid account_id required")

    # Check account ownership
    account_exists = any(
        account.get("id") == account_id
        and account.get("user_id") == user_id
        for account in database.get("accounts", [])
    )

    if not account_exists:
        raise ValueError("Account does not belong to user")

    # Automatic categorization
    if transaction_type == "expense":
        category_id = categorize_merchant(
            merchant, database
        )
    else:
        category_id = next(
            (
                c["id"]
                for c in database.get("categories", [])
                if c.get("name") == "Други приходи"
                and c.get("type") == "income"
            ),
            None
        )

    transaction = {
        "id": str(uuid4()),
        "user_id": user_id,
        "account_id": account_id,
        "merchant_name": merchant,
        "amount_cents": amount_cents,
        "type": transaction_type,
        "category_id": category_id,
        "description": description,
        "transaction_date": transaction_date
    }

    return transaction


# 7. CHECK DUPLICATES
def find_duplicates(transaction, existing_transactions):
    duplicates = []

    for existing in existing_transactions:
        if not isinstance(existing, dict):
            continue

        same_user = (
            existing.get("user_id")
            == transaction["user_id"]
        )

        same_account = (
            existing.get("account_id")
            == transaction["account_id"]
        )

        same_merchant = (
            clean_text(
                existing.get("merchant_name")
            ).casefold()
            == transaction["merchant_name"].casefold()
        )

        same_amount = (
            existing.get("amount_cents")
            == transaction["amount_cents"]
        )

        same_date = (
            existing.get("transaction_date")
            == transaction["transaction_date"]
        )

        same_type = (
            existing.get("type")
            == transaction["type"]
        )

        if all([
            same_user,
            same_account,
            same_merchant,
            same_amount,
            same_date,
            same_type
        ]):
            duplicates.append(existing)

    return duplicates


# 8. SAVE DATABASE
def save_database(database):
    # Atomic replacement avoids partially written JSON.
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=DATABASE_FILE.parent,
            suffix=".tmp",
            delete=False
        ) as file:
            temp_path = Path(file.name)

            json.dump(
                database,
                file,
                ensure_ascii=False,
                indent=4
            )

        os.replace(temp_path, DATABASE_FILE)

    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


# 9. COMPLETE PROCESS
def process_transaction(raw_transaction, allow_duplicate=False):
    database = load_database()

    # Clean, validate and categorize
    transaction = clean_and_categorize(
        raw_transaction, database
    )

    # Detect duplicates
    duplicates = find_duplicates(
        transaction,
        database["transactions"]
    )

    if duplicates and not allow_duplicate:
        return {
            "success": False,
            "reason": "possible_duplicate",
            "transaction": transaction
        }

    # Save
    database["transactions"].append(transaction)
    save_database(database)

    return {
        "success": True,
        "transaction": transaction
    }
