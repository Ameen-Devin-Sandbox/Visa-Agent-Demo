#!/usr/bin/env python3
"""Seed the Visa Disputes API with sample disputes for demo purposes.

Usage:
    python seed_data.py              # defaults to http://localhost:8000
    python seed_data.py --base-url http://localhost:8000
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error

SAMPLE_DISPUTES = [
    {
        "transaction": {
            "transaction_id": "TXN-FRAUD-001",
            "transaction_date": "2025-01-10",
            "processing_date": "2025-01-11",
            "amount": 2499.99,
            "currency": "USD",
            "merchant_name": "SuspiciousElectronics.com",
            "merchant_category_code": "5732",
            "merchant_country": "RO",
            "environment": "ecommerce",
            "is_recurring": False,
            "cvv_present": False,
            "three_d_secure_authenticated": False,
        },
        "cardholder": {
            "cardholder_name": "Jane Smith",
            "partial_payment_credential": "4532",
            "contact_email": "jane.smith@email.com",
            "cardholder_statement": "I did not make this purchase. I have never shopped at this merchant.",
        },
        "evidence": [
            {
                "description": "Cardholder confirmed card was in their possession",
                "evidence_type": "cardholder_declaration",
                "provided_by": "issuer",
                "is_compelling_evidence": False,
            }
        ],
        "fraud_type_code": "7",
        "priority": "2",
    },
    {
        "transaction": {
            "transaction_id": "TXN-AUTH-002",
            "transaction_date": "2025-01-12",
            "processing_date": "2025-01-13",
            "amount": 150.00,
            "currency": "USD",
            "merchant_name": "Corner Gas Station",
            "merchant_category_code": "5541",
            "merchant_country": "US",
            "environment": "card_present",
            "authorization_response_code": "05",
        },
        "cardholder": {
            "cardholder_name": "Robert Chen",
            "partial_payment_credential": "8821",
            "cardholder_statement": "My card was declined at the terminal but I was still charged.",
        },
        "priority": "3",
    },
    {
        "transaction": {
            "transaction_id": "TXN-CONSUMER-003",
            "transaction_date": "2025-01-05",
            "processing_date": "2025-01-06",
            "amount": 89.99,
            "currency": "USD",
            "merchant_name": "FashionBoutique Online",
            "merchant_category_code": "5651",
            "merchant_country": "US",
            "environment": "ecommerce",
            "cvv_present": True,
            "three_d_secure_authenticated": True,
        },
        "cardholder": {
            "cardholder_name": "Maria Garcia",
            "partial_payment_credential": "1199",
            "contact_email": "maria.garcia@email.com",
            "cardholder_statement": "I ordered a dress but never received it. Merchant is unresponsive.",
        },
        "evidence": [
            {
                "description": "Order confirmation email showing expected delivery date of Jan 10",
                "evidence_type": "purchase_receipt",
                "provided_by": "issuer",
                "is_compelling_evidence": False,
            },
            {
                "description": "Three unanswered emails to merchant support",
                "evidence_type": "communication_records",
                "provided_by": "issuer",
                "is_compelling_evidence": False,
            },
        ],
        "priority": "3",
    },
    {
        "transaction": {
            "transaction_id": "TXN-DUP-004",
            "transaction_date": "2025-01-08",
            "processing_date": "2025-01-09",
            "amount": 312.50,
            "currency": "USD",
            "merchant_name": "TechSupply Co",
            "merchant_category_code": "5045",
            "merchant_country": "US",
            "environment": "ecommerce",
        },
        "cardholder": {
            "cardholder_name": "David Park",
            "partial_payment_credential": "7703",
            "cardholder_statement": "I was charged twice for the same order. Only one item was shipped.",
        },
        "evidence": [
            {
                "description": "Bank statement showing two identical charges of $312.50 on same date",
                "evidence_type": "bank_statement",
                "provided_by": "issuer",
                "is_compelling_evidence": True,
            }
        ],
        "priority": "2",
    },
    {
        "transaction": {
            "transaction_id": "TXN-HIGHVAL-005",
            "transaction_date": "2025-01-14",
            "processing_date": "2025-01-14",
            "amount": 15750.00,
            "currency": "USD",
            "merchant_name": "LuxuryWatches.net",
            "merchant_category_code": "5944",
            "merchant_country": "HK",
            "environment": "ecommerce",
            "cvv_present": False,
            "three_d_secure_authenticated": False,
        },
        "cardholder": {
            "cardholder_name": "Emily Watson",
            "partial_payment_credential": "3356",
            "contact_email": "emily.w@email.com",
            "cardholder_statement": "I have never visited this website or purchased any watches. This is fraud.",
        },
        "fraud_type_code": "7",
        "priority": "1",
    },
]


def submit_dispute(base_url: str, dispute: dict) -> dict:
    """Submit a single dispute to the API."""
    url = f"{base_url}/api/v1/disputes"
    data = json.dumps(dispute).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed sample disputes into the API")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()

    # Check health first
    try:
        with urllib.request.urlopen(f"{args.base_url}/api/v1/health", timeout=5) as resp:
            health = json.loads(resp.read().decode("utf-8"))
            print(f"API is {health['status']} (v{health['version']}, {health['agents_loaded']} agents)")
    except urllib.error.URLError as e:
        print(f"ERROR: Cannot reach API at {args.base_url}: {e}")
        print("Make sure the backend is running: uvicorn src.app:app --reload")
        sys.exit(1)

    print(f"\nSubmitting {len(SAMPLE_DISPUTES)} sample disputes...\n")

    for i, dispute in enumerate(SAMPLE_DISPUTES, 1):
        txn = dispute["transaction"]
        ch = dispute["cardholder"]
        label = f"[{i}/{len(SAMPLE_DISPUTES)}] {txn['merchant_name']} (${txn['amount']:,.2f}) - {ch['cardholder_name']}"
        print(f"  {label}")
        try:
            result = submit_dispute(args.base_url, dispute)
            cat = result.get("category", "?")
            stage = result.get("stage", "?")
            res = result.get("resolution", "pending")
            agent = result.get("assigned_agent", "?")
            print(f"    -> Cat {cat} | {stage} | {res} | {agent}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"    -> FAILED ({e.code}): {body[:200]}")
        except Exception as e:
            print(f"    -> FAILED: {e}")

        if i < len(SAMPLE_DISPUTES):
            time.sleep(0.5)

    print("\nDone! View disputes at http://localhost:5173")


if __name__ == "__main__":
    main()
