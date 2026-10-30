"""Seed the synthetic Acme Textiles demo business.

H7.5 — Docx Prompt 5: "Create one synthetic business ... Label
it clearly as synthetic demo data."

This script is **idempotent** and **safe**:

  - Re-running it updates the existing demo user + business
    rather than creating duplicates.
  - It NEVER deletes a non-demo user / business. The
    ``reset_demo_business.py`` script is the dedicated reset
    tool and is the only path that drops the demo row.
  - Credentials come from environment variables; the password
    is never echoed to stdout or to the log.
  - The script prints only the synthetic user/business
    identifiers so the operator can copy them into the demo
    run.

Run::

    python scripts/demo/seed_demo_business.py

Environment::

    DEMO_USER_EMAIL       (default: acme.textiles@example.com)
    DEMO_USER_PASSWORD    (default: AcmeDemoPass1)
    DEMO_USER_FULL_NAME   (default: Acme Textiles — Demo Owner)
    DEMO_BUSINESS_NAME    (default: Acme Textiles)
    DEMO_TARGET_REVENUE   (default: 30000000 — ₹3 Crore in INR)
    DEMO_CURRENT_REVENUE  (default: 18000000 — ₹1.8 Crore in INR)

The revenue defaults are in paise (1 INR = 100 paise) because
the upstream schema stores money as a numeric. ₹1.8 Crore =
₹18,000,000 = 1,800,000,000 paise.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

# Ensure the backend package is importable when this script is
# run from the repo root (e.g. `python scripts/demo/seed_*.py`).
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy.orm import Session  # noqa: E402

from app.models.action_item import ActionItem  # noqa: E402
from app.models.business import Business  # noqa: E402
from app.models.business_challenge import BusinessChallenge  # noqa: E402
from app.models.business_goal import BusinessGoal  # noqa: E402
from app.models.certification import Certification  # noqa: E402
from app.models.digital_presence import DigitalPresence  # noqa: E402
from app.models.export_history import ExportHistory  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.user import User  # noqa: E402
from app.utils.database import SessionLocal  # noqa: E402
from app.utils.security import hash_password  # noqa: E402

DEMO_TAG = "[DEMO-SYNTHETIC]"


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


def _env(name: str, default: str) -> str:
    """Return the env var or the default, stripped."""
    val = os.environ.get(name, "").strip()
    return val or default


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name, "").strip()
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


# Acme Textiles — the synthetic demo profile from docx P5 Part 1.
DEMO_EMAIL = _env("DEMO_USER_EMAIL", "acme.textiles@example.com")
DEMO_PASSWORD = _env("DEMO_USER_PASSWORD", "AcmeDemoPass1")
DEMO_FULL_NAME = _env("DEMO_USER_FULL_NAME", "Acme Textiles — Demo Owner")
DEMO_BUSINESS_NAME = _env("DEMO_BUSINESS_NAME", "Acme Textiles")
DEMO_CURRENT_REVENUE = _env_int("DEMO_CURRENT_REVENUE", 18000000)
DEMO_TARGET_REVENUE = _env_int("DEMO_TARGET_REVENUE", 30000000)
DEMO_CURRENCY = _env("DEMO_CURRENCY", "INR")
DEMO_ESTABLISHED_YEAR = _env_int("DEMO_ESTABLISHED_YEAR", 2014)
DEMO_EMPLOYEE_COUNT = _env_int("DEMO_EMPLOYEE_COUNT", 12)
DEMO_INDUSTRY = _env("DEMO_INDUSTRY", "Textile Manufacturing")
DEMO_SUB_INDUSTRY = _env("DEMO_SUB_INDUSTRY", "Knitted garments")
DEMO_CITY = _env("DEMO_CITY", "Tirupur")
DEMO_STATE = _env("DEMO_STATE", "Tamil Nadu")
DEMO_COUNTRY = _env("DEMO_COUNTRY", "India")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _get_or_create_user(db: Session) -> User:
    """Return the demo user, creating it on first run.

    The user is *only* matched by email; the password hash is
    refreshed on every run so a fresh deployment starts from
    the documented password. No other users are touched.
    """
    user = db.query(User).filter(User.email == DEMO_EMAIL).one_or_none()
    if user is None:
        user = User(
            email=DEMO_EMAIL,
            full_name=DEMO_FULL_NAME,
            password_hash=hash_password(DEMO_PASSWORD),
            is_active=True,
        )
        db.add(user)
        db.flush()
    else:
        # Refresh the password hash so a fresh deployment
        # starts from the documented credential. No other
        # fields are touched.
        user.password_hash = hash_password(DEMO_PASSWORD)
        user.is_active = True
        db.flush()
    return user


def _get_or_create_business(db: Session, owner: User) -> Business:
    """Return the demo business, creating it on first run."""
    biz = (
        db.query(Business)
        .filter(Business.owner_id == owner.id, Business.legal_name == DEMO_BUSINESS_NAME)
        .one_or_none()
    )
    if biz is None:
        biz = Business(
            owner_id=owner.id,
            legal_name=DEMO_BUSINESS_NAME,
            trade_name="Acme Textiles (Demo)",
            industry=DEMO_INDUSTRY,
            sub_industry=DEMO_SUB_INDUSTRY,
            business_type="Private Limited",
            established_year=DEMO_ESTABLISHED_YEAR,
            employee_count=DEMO_EMPLOYEE_COUNT,
            annual_revenue=DEMO_CURRENT_REVENUE,
            revenue_currency=DEMO_CURRENCY,
            description=(
                f"{DEMO_BUSINESS_NAME} is a synthetic demo company. "
                "It manufactures knitted garments in Tirupur and "
                "supplies domestic textile buyers. The biggest "
                "operational risk today is supplier dependency on "
                "two large yarn vendors."
            ),
            country=DEMO_COUNTRY,
            state_region=DEMO_STATE,
            city=DEMO_CITY,
            production_capacity="Approx 18,000 units / month",
            production_capacity_unit="garments / month",
            capacity_utilization_pct=68,
            monthly_production_units=12000,
            is_completed=True,
        )
        db.add(biz)
        db.flush()
    else:
        # Refresh fields that drive scoring. Do NOT touch the
        # owner_id (never reassign ownership).
        biz.industry = DEMO_INDUSTRY
        biz.sub_industry = DEMO_SUB_INDUSTRY
        biz.established_year = DEMO_ESTABLISHED_YEAR
        biz.employee_count = DEMO_EMPLOYEE_COUNT
        biz.annual_revenue = DEMO_CURRENT_REVENUE
        biz.revenue_currency = DEMO_CURRENCY
        biz.is_completed = True
        db.flush()
    return biz


def _ensure_digital_presence(db: Session, biz: Business) -> None:
    """One-to-one child. Replace existing row to keep idempotent."""
    dp = (
        db.query(DigitalPresence)
        .filter(DigitalPresence.business_id == biz.id)
        .one_or_none()
    )
    if dp is None:
        db.add(
            DigitalPresence(
                business_id=biz.id,
                website_url="https://acme-textiles.example.com",
                linkedin_url="https://www.linkedin.com/company/acme-textiles-demo",
                facebook_url=None,
                instagram_url=None,
                twitter_url=None,
                youtube_url=None,
                has_ecommerce=False,  # docx Part 1: "no e-commerce"
                ecommerce_platform=None,
                uses_digital_marketing=False,
                uses_cloud_systems=False,
            )
        )
    else:
        dp.website_url = "https://acme-textiles.example.com"
        dp.linkedin_url = "https://www.linkedin.com/company/acme-textiles-demo"
        dp.has_ecommerce = False
        dp.uses_digital_marketing = False
        dp.uses_cloud_systems = False
    db.flush()


def _ensure_products(db: Session, biz: Business) -> None:
    """Replace products with the canonical demo set."""
    db.query(Product).filter(Product.business_id == biz.id).delete()
    db.add_all(
        [
            Product(
                business_id=biz.id,
                name="Cotton Crew-Neck T-Shirt",
                category="Apparel",
                hs_code="6109.10",
                description="Unisex cotton crew-neck, 180 GSM, classic fit.",
                unit_price=180.0,
                currency=DEMO_CURRENCY,
                monthly_volume=6500,
                is_exported=False,
            ),
            Product(
                business_id=biz.id,
                name="Polyester Blend Track Pants",
                category="Apparel",
                hs_code="6103.43",
                description="Lightweight track pants for the domestic sportswear market.",
                unit_price=320.0,
                currency=DEMO_CURRENCY,
                monthly_volume=3500,
                is_exported=False,
            ),
            Product(
                business_id=biz.id,
                name="Organic Cotton Romper (Export Sample)",
                category="Apparel",
                hs_code="6111.20",
                description="Small export trial order — 2 SKUs, EU buyer.",
                unit_price=540.0,
                currency=DEMO_CURRENCY,
                monthly_volume=2000,
                is_exported=True,  # the only export item
            ),
        ]
    )
    db.flush()


def _ensure_certifications(db: Session, biz: Business) -> None:
    """Replace certifications with the canonical demo set."""
    db.query(Certification).filter(Certification.business_id == biz.id).delete()
    db.add_all(
        [
            Certification(
                business_id=biz.id,
                name="Udyam Registration (MSME)",
                issuing_body="Ministry of MSME, Government of India",
                issued_date=date(2018, 4, 12),
                expiry_date=None,
                certificate_number="UDYAM-TN-33-0012345",
            ),
            Certification(
                business_id=biz.id,
                name="GST Registration",
                issuing_body="Government of India",
                issued_date=date(2018, 5, 1),
                expiry_date=None,
                certificate_number="33ABCDE1234F1Z5",
            ),
        ]
    )
    db.flush()


def _ensure_export_history(db: Session, biz: Business) -> None:
    """Replace export history with the canonical demo set."""
    db.query(ExportHistory).filter(ExportHistory.business_id == biz.id).delete()
    db.add_all(
        [
            ExportHistory(
                business_id=biz.id,
                destination_country="Germany",
                product_category="Apparel",
                first_export_date=date(2024, 9, 15),
                annual_export_value=4_500_000.0,  # ₹45 Lakh
                currency=DEMO_CURRENCY,
                iec_number="0399DEMO0001",
            ),
        ]
    )
    db.flush()


def _ensure_goals(db: Session, biz: Business) -> None:
    """Replace goals with the canonical demo set."""
    db.query(BusinessGoal).filter(BusinessGoal.business_id == biz.id).delete()
    db.add_all(
        [
            BusinessGoal(
                business_id=biz.id,
                title=f"Grow annual revenue to ₹{DEMO_TARGET_REVENUE // 10000000} Cr",
                description=(
                    "Reach the next revenue band without increasing "
                    "supplier dependency beyond 2 vendors."
                ),
                timeframe="12m",
                priority="high",
                target_date=date(2027, 8, 5),
            ),
            BusinessGoal(
                business_id=biz.id,
                title="Add an export customer in the EU",
                description="Convert the German sample order into a standing customer.",
                timeframe="9m",
                priority="high",
                target_date=date(2027, 5, 5),
            ),
            BusinessGoal(
                business_id=biz.id,
                title="Launch D2C ecommerce for repeat domestic buyers",
                description="Open a Shopify storefront for direct B2C sales.",
                timeframe="6m",
                priority="medium",
                target_date=date(2027, 2, 5),
            ),
        ]
    )
    db.flush()


def _ensure_challenges(db: Session, biz: Business) -> None:
    """Replace challenges with the canonical demo set."""
    db.query(BusinessChallenge).filter(BusinessChallenge.business_id == biz.id).delete()
    db.add_all(
        [
            BusinessChallenge(
                business_id=biz.id,
                title="High supplier dependency",
                description=(
                    "Two yarn vendors supply 78% of raw material; "
                    "any disruption will halt production within 3 weeks."
                ),
                severity="critical",
                category="supply_chain",
            ),
            BusinessChallenge(
                business_id=biz.id,
                title="Limited digital presence",
                description=(
                    "No ecommerce and no digital marketing means new "
                    "buyer discovery is slow and reliant on trade shows."
                ),
                severity="high",
                category="digital",
            ),
            BusinessChallenge(
                business_id=biz.id,
                title="Single export customer",
                description=(
                    "All export revenue is from one German buyer; "
                    "loss of that customer would cut revenue by 25%."
                ),
                severity="high",
                category="export",
            ),
        ]
    )
    db.flush()


def _ensure_action_items(db: Session, owner: User) -> None:
    """Replace action items for the demo owner with the canonical set."""
    db.query(ActionItem).filter(ActionItem.owner_id == owner.id).delete()
    db.add_all(
        [
            ActionItem(
                owner_id=owner.id,
                title="Identify and onboard 2 backup yarn vendors",
                description=(
                    "Shortlist yarn suppliers outside the current "
                    "Tirupur cluster and request samples."
                ),
                category="Operations",
                priority="High",
                due_date="2026-09-15",
                is_completed=False,
            ),
            ActionItem(
                owner_id=owner.id,
                title="Set up Shopify D2C storefront",
                description="Build the storefront with the top 3 SKUs.",
                category="Digital",
                priority="High",
                due_date="2026-10-30",
                is_completed=False,
            ),
            ActionItem(
                owner_id=owner.id,
                title="Apply for ZED certification subsidy",
                description=(
                    "Use the matched ZED scheme on the Schemes tab."
                ),
                category="Compliance",
                priority="Medium",
                due_date="2026-11-30",
                is_completed=False,
            ),
            ActionItem(
                owner_id=owner.id,
                title="Pitch the organic-cotton romper to 3 EU buyers",
                category="Sales",
                priority="Medium",
                due_date="2026-12-15",
                is_completed=False,
            ),
        ]
    )
    db.flush()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def seed() -> int:
    """Run the seed. Returns the demo user's id."""
    db = SessionLocal()
    try:
        user = _get_or_create_user(db)
        biz = _get_or_create_business(db, user)
        _ensure_digital_presence(db, biz)
        _ensure_products(db, biz)
        _ensure_certifications(db, biz)
        _ensure_export_history(db, biz)
        _ensure_goals(db, biz)
        _ensure_challenges(db, biz)
        _ensure_action_items(db, user)
        db.commit()
        # Print ONLY the synthetic identifiers. Never the
        # password, never the password hash.
        print(f"{DEMO_TAG} demo_user_id = {user.id}")
        print(f"{DEMO_TAG} demo_user_email = {user.email}")
        print(f"{DEMO_TAG} demo_business_id = {biz.id}")
        print(f"{DEMO_TAG} demo_business_name = {biz.legal_name}")
        print(f"{DEMO_TAG} target_revenue = {DEMO_TARGET_REVENUE} {DEMO_CURRENCY}")
        print(f"{DEMO_TAG} current_revenue = {DEMO_CURRENT_REVENUE} {DEMO_CURRENCY}")
        print(f"{DEMO_TAG} employees = {DEMO_EMPLOYEE_COUNT}")
        print(f"{DEMO_TAG} location = {DEMO_CITY}, {DEMO_STATE}, {DEMO_COUNTRY}")
        print(f"{DEMO_TAG} products = 3, certifications = 2, goals = 3, challenges = 3, action_items = 4")
        return user.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
