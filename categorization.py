
import json
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

DATABASE_FILE = Path(__file__).with_name("finance_database.json")


# Automatic merchant categorization
CATEGORIES = {
    "Food": ["lidl", "kaufland", "billa",
             "ресторант", "кафе"],
    "Transport": ["shell", "omv", "eko", "taxi",
                  "такси", "гориво"],
    "Rent": ["rent", "наем"],
    "Utilities": ["vivacom", "yettel", "ток",
                  "вода", "интернет"],
    "Shopping": ["zara", "ikea", "emag", "магазин"],
    "Entertainment": ["netflix", "spotify", "кино"]
}


def categorize_merchant(merchant):
    name = merchant.casefold().strip()

    for category, keywords in CATEGORIES.items():
        if any(word in name for word in keywords):
            return category

    return "Other"


def clean_amount(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("Invalid amount")

    if not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("Invalid amount type")

    text = str(value).strip().replace(" ", "")

    # Accept 25.50 and 25,50
    text = text.replace(",", ".")

    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise ValueError("Amount must be a number")

    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be positive")

    if amount.as_tuple().exponent < -2:
        raise ValueError("Use at most two decimal places")

    return amount


def clean_date(value):
    if not isinstance(value, str):
        raise ValueError("Invalid date")

    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError:
        raise ValueError("Use YYYY-MM-DD date format")

    return parsed.isoformat()


# Reusable cleaning and categorization pipeline
def clean_and_categorize(transaction):
    if not isinstance(transaction, dict):
        raise ValueError("Transaction must be an object")

    merchant = transaction.get("merchant")

    if not isinstance(merchant, str) or not merchant.strip():
        raise ValueError("Merchant is required")

    transaction_type = transaction.get("type")

    if transaction_type not in ("income", "expense"):
        raise ValueError("Invalid transaction type")

    amount = clean_amount(transaction.get("amount"))
    transaction_date = clean_date(transaction.get("date"))

    category = (
        categorize_merchant(merchant)
        if transaction_type == "expense"
        else "Income"
    )

    return {
        "merchant": merchant.strip(),
        "amount": str(amount),
        "date": transaction_date,
        "type": transaction_type,
        "category": category
    }


def load_database():
    if not DATABASE_FILE.exists():
        raise FileNotFoundError(
            "finance_database.json was not found"
        )

    with open(DATABASE_FILE, "r", encoding="utf-8") as file:
        database = json.load(file)

    if not isinstance(database, dict):
        raise ValueError("Invalid database structure")

    if not isinstance(database.get("transactions"), list):
        raise ValueError("Missing transactions list")

    return database


def save_database(database):
    # Write to a temporary file first
    temporary = DATABASE_FILE.with_suffix(".tmp")

    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(
            database,
            file,
            ensure_ascii=False,
            indent=4
        )

    temporary.replace(DATABASE_FILE)


def add_transaction():
    print("\n--- Add transaction ---")

    print("1. Income")
    print("2. Expense")

    choice = input("Choose type: ").strip()

    if choice == "1":
        transaction_type = "income"
    elif choice == "2":
        transaction_type = "expense"
    else:
        print("Invalid choice")
        return

    merchant = input("Merchant / Source: ")
    amount = input("Amount (EUR): ")

    transaction_date = input(
        "Date YYYY-MM-DD (Enter for today): "
    ).strip()

    if not transaction_date:
        transaction_date = date.today().isoformat()

    raw_transaction = {
        "merchant": merchant,
        "amount": amount,
        "date": transaction_date,
        "type": transaction_type
    }

    try:
        transaction = clean_and_categorize(raw_transaction)
        database = load_database()

        # Check duplicates
        for existing in database["transactions"]:
            if not isinstance(existing, dict):
                continue

            if (
                existing.get("merchant", "").strip().casefold()
                == transaction["merchant"].casefold()
                and str(existing.get("amount")) == transaction["amount"]
                and existing.get("date") == transaction["date"]
                and existing.get("type") == transaction["type"]
            ):
                print("Possible duplicate transaction!")
                confirm = input("Save anyway? (y/n): ").lower()

                if confirm != "y":
                    return

                break

        # Generate a unique transaction ID
        from uuid import uuid4
        transaction["transaction_id"] = str(uuid4())

        database["transactions"].append(transaction)
        save_database(database)

        print("\nTransaction saved!")
        print("Category:", transaction["category"])
        print("Amount:", transaction["amount"], "EUR")

    except (ValueError, FileNotFoundError, json.JSONDecodeError) as error:
        print("Error:", error)


def view_transactions():
    try:
        database = load_database()
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as error:
        print("Error:", error)
        return

    transactions = database["transactions"]

    if not transactions:
        print("\nNo transactions yet.")
        return

    print("\n--- Your transactions ---")

    for transaction in transactions:
        print(
            transaction.get("date"),
            "|",
            transaction.get("merchant"),
            "|",
            transaction.get("amount"),
            "EUR |",
            transaction.get("category")
        )


def main():
    while True:
        print("\n===== FINANCE APP =====")
        print("1. Add transaction")
        print("2. View transactions")
        print("3. Exit")

        choice = input("Choose option: ").strip()

        if choice == "1":
            add_transaction()
        elif choice == "2":
            view_transactions()
        elif choice == "3":
            print("Goodbye!")
            break
        else:
            print("Invalid option")


if __name__ == "__main__":
    main()
