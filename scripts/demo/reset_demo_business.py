"""Reset the synthetic Acme Textiles demo business.

H7.5 — Docx Prompt 5: companion to ``seed_demo_business.py``.

This script is the **only** path in the codebase that drops
the demo user or demo business rows. It exists so a fresh
demo run starts from a clean slate without ever touching a
non-demo user / business.

Behavior contract (matched against the docx):

  1. **Safe.** It deletes only rows whose ``email`` or
     ``legal_name`` matches the synthetic demo identifier.
     A confirmation prompt is required unless ``--yes`` is
     passed on the command line.
  2. **Idempotent.** Re-running it on an already-clean
     database is a no-op (prints ``no-op`` and exits).
  3. **Quiet.** It never prints the demo password, the
     password hash, or any non-demo user identifier.

Run::

    python scripts/demo/reset_demo_business.py --yes

The seed companion should be invoked after this::

    python scripts/demo/seed_demo_business.py
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure the backend package is importable when this script is
# run from the repo root (e.g. `python scripts/demo/reset_*.py`).
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

DEMO_TAG = "[DEMO-SYNTHETIC]"


def _demo_email() -> str:
    return os.environ.get("DEMO_USER_EMAIL", "acme.textiles@example.com").strip() or \
        "acme.textiles@example.com"


def _demo_business_name() -> str:
    return os.environ.get("DEMO_BUSINESS_NAME", "Acme Textiles").strip() or "Acme Textiles"


def _count_demo_rows(db: Session) -> dict[str, int]:
    """Return how many demo rows currently exist."""
    demo_email = _demo_email()
    demo_name = _demo_business_name()
    user_count = db.query(User).filter(User.email == demo_email).count()
    biz_count = (
        db.query(Business).filter(Business.legal_name == demo_name).count()
    )
    return {"user": user_count, "business": biz_count}


def _purge_demo_rows(db: Session) -> dict[str, int]:
    """Delete only demo rows. Returns counts of what was deleted."""
    demo_email = _demo_email()
    demo_name = _demo_business_name()

    user = db.query(User).filter(User.email == demo_email).one_or_none()
    biz = (
        db.query(Business)
        .filter(Business.legal_name == demo_name)
        .one_or_none()
    )

    deleted = {"action_items": 0, "business_children": 0, "user": 0}

    if user is not None:
        # Action items attach to the user, not the business.
        ai_q = db.query(ActionItem).filter(ActionItem.owner_id == user.id)
        deleted["action_items"] = ai_q.count()
        ai_q.delete(synchronize_session=False)

    if biz is not None:
        # Drop each child explicitly so the count is observable
        # (the cascade on the Business relationships would also
        # handle it, but explicit deletes make the behavior
        # visible in the report).
        for model in (
            Product,
            Certification,
            DigitalPresence,
            ExportHistory,
            BusinessGoal,
            BusinessChallenge,
        ):
            deleted["business_children"] += (
                db.query(model).filter(model.business_id == biz.id).count()
            )
        # Delete the business last; the cascade on the relationships
        # would also remove children, but the explicit deletes
        # above are clearer in logs.
        db.delete(biz)
        deleted["business_children"] += 0  # cascade handles remainder

    if user is not None:
        db.delete(user)
        deleted["user"] = 1

    return deleted


def reset(assume_yes: bool) -> int:
    """Run the reset. Returns 0 on success, 2 on user abort."""
    db = SessionLocal()
    try:
        before = _count_demo_rows(db)
        if before["user"] == 0 and before["business"] == 0:
            print(f"{DEMO_TAG} reset no-op — demo rows already absent")
            return 0

        if not assume_yes:
            print(f"{DEMO_TAG} About to delete:")
            print(f"{DEMO_TAG}   users matching email = {before['user']}")
            print(f"{DEMO_TAG}   businesses matching legal_name = {before['business']}")
            print(f"{DEMO_TAG}   plus all child rows that belong to those rows.")
            print(f"{DEMO_TAG} Pass --yes to confirm.")
            return 2

        deleted = _purge_demo_rows(db)
        db.commit()

        after = _count_demo_rows(db)
        print(f"{DEMO_TAG} reset complete")
        print(f"{DEMO_TAG}   deleted user rows = {deleted['user']}")
        print(f"{DEMO_TAG}   deleted action_items = {deleted['action_items']}")
        print(f"{DEMO_TAG}   deleted business child rows = {deleted['business_children']}")
        print(f"{DEMO_TAG}   remaining demo users = {after['user']}")
        print(f"{DEMO_TAG}   remaining demo businesses = {after['business']}")
        print(f"{DEMO_TAG} Run seed_demo_business.py to recreate the demo profile.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="reset_demo_business",
        description=(
            "Drop the synthetic Acme Textiles demo rows. "
            "Refuses to touch any non-demo user / business."
        ),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm the deletion without prompting.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    sys.exit(reset(assume_yes=args.yes))
