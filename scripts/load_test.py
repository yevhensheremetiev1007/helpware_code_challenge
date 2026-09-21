"""Reproduction scripts.

  python -m scripts.load_test interactive
  python -m scripts.load_test batch
  python -m scripts.load_test webhook

interactive  Twenty supervisors press "re-score" at the same moment. This is
             what the dashboard does, including its one retry on failure.

batch        What the nightly scheduled job does at 02:00 UTC. It asks for
             everything the tenant closed in the last 24 hours and posts the
             whole set to /v1/batches.

webhook      What an integrated client helpdesk does as conversations close.
"""

import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from rubric.db.base import SessionLocal
from rubric.db import repositories
from rubric.db.models import Tenant

BASE = "http://nginx"
TIMEOUT = 130


def _tenants() -> list[Tenant]:
    db = SessionLocal()
    try:
        return list(db.query(Tenant).order_by(Tenant.slug).all())
    finally:
        db.close()


def _conversations(tenant_id, limit: int | None = None):
    db = SessionLocal()
    try:
        rows = repositories.conversations_closed_since(db, tenant_id, hours=24)
        return [c.id for c in (rows[:limit] if limit else rows)]
    finally:
        db.close()


def _rubric_id(tenant_id):
    db = SessionLocal()
    try:
        rubric = repositories.get_default_rubric(db, tenant_id)
        return str(rubric.id) if rubric else None
    finally:
        db.close()


def interactive() -> None:
    """Twenty concurrent re-score requests, with the dashboard's single retry."""
    tenants = _tenants()
    tenant = tenants[0]
    ids = _conversations(tenant.id, limit=20)
    headers = {"X-Tenant-Slug": tenant.slug}

    print(f"20 concurrent re-score requests for {tenant.slug}\n")

    def one(conversation_id):
        # The dashboard uses TanStack Query with retry: 1, so a failed request
        # is sent a second time.
        for attempt in (1, 2):
            started = time.monotonic()
            try:
                with httpx.Client(timeout=TIMEOUT) as client:
                    response = client.post(
                        f"{BASE}/v1/conversations/{conversation_id}/score",
                        json={"priority": "interactive"},
                        headers=headers,
                    )
                elapsed = time.monotonic() - started
                if response.status_code < 400:
                    return f"  {str(conversation_id)[:8]}  {response.status_code} in {elapsed:5.1f}s"
                if attempt == 2:
                    return f"  {str(conversation_id)[:8]}  {response.status_code} in {elapsed:5.1f}s  (after retry)"
            except httpx.HTTPError as exc:
                if attempt == 2:
                    return f"  {str(conversation_id)[:8]}  {type(exc).__name__}"
        return None

    with ThreadPoolExecutor(max_workers=20) as pool:
        for line in pool.map(one, ids):
            print(line)

    print("\nNow check the load balancer:  make health")


def batch() -> None:
    """What the nightly job does."""
    for tenant in _tenants():
        ids = _conversations(tenant.id)
        if not ids:
            continue
        rubric_id = _rubric_id(tenant.id)
        print(f"{tenant.slug}: submitting {len(ids)} conversations")
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(
                f"{BASE}/v1/batches",
                json={"rubric_id": rubric_id, "conversation_ids": [str(i) for i in ids]},
                headers={"X-Tenant-Slug": tenant.slug},
            )
        print(f"  {response.status_code} {response.text[:120]}")

    print("\nThe batch runs in the background. Watch it with:  make logs")
    print("When it has settled, run:  make score-report")


def webhook() -> None:
    """What an integrated helpdesk does as conversations close."""
    rng = random.Random(7)
    for tenant in _tenants():
        db = SessionLocal()
        try:
            if not tenant.webhook_enabled:
                print(f"{tenant.slug}: not integrated, skipping")
                continue
            rows = repositories.conversations_closed_since(db, tenant.id, hours=24)
        finally:
            db.close()

        sample = rows[: min(40, len(rows))]
        print(f"{tenant.slug}: replaying {len(sample)} close events")

        def one(conversation):
            with httpx.Client(timeout=TIMEOUT) as client:
                try:
                    response = client.post(
                        f"{BASE}/v1/webhooks/conversation-closed",
                        json={
                            "external_id": conversation.external_id,
                            "channel": conversation.channel,
                            "closed_at": conversation.closed_at.isoformat(),
                            "transcript": conversation.transcript,
                        },
                        headers={"X-Tenant-Slug": tenant.slug},
                    )
                    return response.status_code
                except httpx.HTTPError as exc:
                    return type(exc).__name__

        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(one, sample))
        ok = sum(1 for r in results if r == 202)
        print(f"  {ok}/{len(results)} accepted")
        rng.random()

    print("\nWhen it has settled, run:  make score-report")


COMMANDS = {"interactive": interactive, "batch": batch, "webhook": webhook}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[sys.argv[1]]()
