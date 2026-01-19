"""License file generator for Infrahub.

This script generates signed license files for customers.
For the PoC, it uses HMAC-SHA256 signing. In production, this would be
replaced with RSA signing using OpsMill's private key.

Usage:
    python -m infrahub.license.generator \
        --customer "Acme Corp" \
        --deployment-id "550e8400-e29b-41d4-a716-446655440001" \
        --product-tier medium \
        --support-tier advanced \
        --start-date 2025-01-01 \
        --end-date 2026-01-01 \
        --signing-key "your-secret-key" \
        --output license.json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID, uuid4


def create_signing_data(
    license_id: UUID,
    customer_name: str,
    deployment_id: UUID,
    product_tier: str,
    support_tier: str,
    start_date: date,
    end_date: date,
    issued_at: datetime,
) -> str:
    """Create the canonical string representation for signing.

    Args:
        license_id: Unique license identifier.
        customer_name: Customer organization name.
        deployment_id: Bound Infrahub instance ID.
        product_tier: Product tier (small/medium/large).
        support_tier: Support tier (basic/advanced/24x7).
        start_date: License effective date.
        end_date: License expiration date.
        issued_at: When license was generated.

    Returns:
        Canonical string for signing.
    """
    parts = [
        str(license_id),
        customer_name,
        str(deployment_id),
        product_tier,
        support_tier,
        start_date.isoformat(),
        end_date.isoformat(),
        issued_at.isoformat(),
    ]
    return "|".join(parts)


def sign_license(signing_data: str, secret_key: str) -> str:
    """Sign the license data using HMAC-SHA256.

    Args:
        signing_data: The canonical string to sign.
        secret_key: The secret key for HMAC.

    Returns:
        Base64-encoded signature.
    """
    signature = hmac.new(
        secret_key.encode("utf-8"),
        signing_data.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(signature).decode("utf-8")


def generate_license(
    customer_name: str,
    deployment_id: str | UUID,
    product_tier: str,
    support_tier: str,
    start_date: date,
    end_date: date,
    signing_key: str,
    license_id: str | UUID | None = None,
) -> dict:
    """Generate a complete signed license file.

    Args:
        customer_name: Customer organization name.
        deployment_id: UUID of the Infrahub deployment.
        product_tier: Product tier (small/medium/large).
        support_tier: Support tier (basic/advanced/24x7).
        start_date: License effective date.
        end_date: License expiration date.
        signing_key: Secret key for signing.
        license_id: Optional license ID (generated if not provided).

    Returns:
        Complete license file as a dictionary.
    """
    if license_id is None:
        license_id = uuid4()
    elif isinstance(license_id, str):
        license_id = UUID(license_id)

    if isinstance(deployment_id, str):
        deployment_id = UUID(deployment_id)

    issued_at = datetime.now(tz=UTC)

    # Create signing data
    signing_data = create_signing_data(
        license_id=license_id,
        customer_name=customer_name,
        deployment_id=deployment_id,
        product_tier=product_tier,
        support_tier=support_tier,
        start_date=start_date,
        end_date=end_date,
        issued_at=issued_at,
    )

    # Sign the license
    signature = sign_license(signing_data, signing_key)

    return {
        "license_id": str(license_id),
        "customer_name": customer_name,
        "deployment_id": str(deployment_id),
        "product_tier": product_tier,
        "support_tier": support_tier,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "issued_at": issued_at.isoformat(),
        "signature": signature,
    }


def main() -> int:
    """Main entry point for the license generator."""
    parser = argparse.ArgumentParser(description="Generate a signed Infrahub license file")
    parser.add_argument("--customer", required=True, help="Customer organization name")
    parser.add_argument("--deployment-id", required=True, help="UUID of the Infrahub deployment")
    parser.add_argument(
        "--product-tier",
        required=True,
        choices=["small", "medium", "large"],
        help="Product tier",
    )
    parser.add_argument(
        "--support-tier",
        required=True,
        choices=["basic", "advanced", "24x7"],
        help="Support tier",
    )
    parser.add_argument(
        "--start-date",
        required=True,
        help="License start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="License end date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--signing-key",
        required=True,
        help="Secret key for HMAC signing",
    )
    parser.add_argument(
        "--license-id",
        help="Optional license ID (UUID generated if not provided)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="license.json",
        help="Output file path (default: license.json)",
    )

    args = parser.parse_args()

    try:
        start_date = date.fromisoformat(args.start_date)
        end_date = date.fromisoformat(args.end_date)
    except ValueError as e:
        print(f"Error parsing dates: {e}", file=sys.stderr)
        return 1

    try:
        license_data = generate_license(
            customer_name=args.customer,
            deployment_id=args.deployment_id,
            product_tier=args.product_tier,
            support_tier=args.support_tier,
            start_date=start_date,
            end_date=end_date,
            signing_key=args.signing_key,
            license_id=args.license_id,
        )
    except ValueError as e:
        print(f"Error generating license: {e}", file=sys.stderr)
        return 1

    output_path = Path(args.output)
    with output_path.open("w") as f:
        json.dump(license_data, f, indent=2)

    print(f"License generated: {output_path}")
    print(f"  License ID: {license_data['license_id']}")
    print(f"  Customer: {license_data['customer_name']}")
    print(f"  Deployment ID: {license_data['deployment_id']}")
    print(f"  Valid: {license_data['start_date']} to {license_data['end_date']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
