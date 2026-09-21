"""Load test data.

  python -m scripts.seed

Set SEED_CONVERSATIONS to change the size. The default of 2000 is about five
percent of a production night, which keeps the reproduction steps to minutes
instead of hours.

The service has been in production for eleven days, so the seed also creates
some history: a set of older conversations that were already scored. These sit
outside the 24 hour window the nightly job looks at, so they give the review
queue something to show without changing what the reproduction scripts do.
"""

import hashlib
import os
import random
from datetime import datetime, timedelta, timezone

from rubric.db.base import SessionLocal
from rubric.db.models import (
    CategoryScore,
    Conversation,
    Rubric,
    RubricCategory,
    RubricVersion,
    Score,
    Tenant,
)

TOTAL = int(os.getenv("SEED_CONVERSATIONS", "2000"))

# Conversations from earlier in the week that already have a score.
HISTORY = int(os.getenv("SEED_HISTORY", "120"))

MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"

TENANTS = [
    # slug, name, share of volume, webhook integrated
    ("acme", "Acme Logistics", 0.60, True),
    ("globex", "Globex Retail", 0.25, True),
    ("initech", "Initech Software", 0.15, False),
]

CATEGORIES = [
    ("Greeting", "Did the agent greet the customer by name and state their own name?"),
    ("Empathy", "Did the agent acknowledge how the customer felt before solving the problem?"),
    ("Resolution", "Was the customer's problem actually solved during this conversation?"),
    ("Compliance", "Did the agent read the required disclosure before taking payment details?"),
    ("Closing", "Did the agent confirm there was nothing else and thank the customer?"),
]

OPENERS = [
    "Hi, my order has not arrived and it was due on Tuesday.",
    "Hello, I was charged twice for the same subscription.",
    "Good morning, I need to change the delivery address on order 88213.",
    "Hi there, the item I received is damaged.",
    "Hello, I cannot log in to my account and the reset email never arrives.",
]

REPLIES = [
    "Thank you for contacting us. I am sorry about that. Let me look into it now.",
    "I understand, and I can see the problem on my side. I will fix it for you.",
    "That sounds frustrating. Give me one moment while I check the details.",
    "I have found the order. I am going to arrange a replacement today.",
]


def transcript(rng: random.Random) -> str:
    lines = [f"Customer: {rng.choice(OPENERS)}"]
    for _ in range(rng.randint(2, 5)):
        lines.append(f"Agent: {rng.choice(REPLIES)}")
        lines.append(f"Customer: {rng.choice(['Thanks.', 'Okay.', 'How long will that take?'])}")
    lines.append("Agent: Is there anything else I can help you with today?")
    lines.append("Customer: No, that is all. Thank you.")
    return "\n".join(lines)


def main() -> None:
    rng = random.Random(20260814)
    db = SessionLocal()

    slugs = [slug for slug, _, _, _ in TENANTS]
    existing = db.query(Tenant).filter(Tenant.slug.in_(slugs)).count()
    if existing:
        print(f"{existing} of the seed tenants already exist, nothing to do")
        print("run 'make reset && make up' first if you want to start over")
        return

    now = datetime.now(timezone.utc)

    for slug, name, share, webhook in TENANTS:
        tenant = Tenant(slug=slug, name=name, webhook_enabled=webhook)
        db.add(tenant)
        db.flush()

        rubric = Rubric(tenant_id=tenant.id, name=f"{name} QA rubric", active_version=1)
        db.add(rubric)
        db.flush()

        version = RubricVersion(rubric_id=rubric.id, version=1, created_by="oleksandr")
        db.add(version)
        db.flush()

        categories = [
            RubricCategory(
                rubric_version_id=version.id,
                name=cat_name,
                weight=1,
                scoring_instructions=instructions,
            )
            for cat_name, instructions in CATEGORIES
        ]
        db.add_all(categories)
        # The session runs with autoflush off, so flush to give these rows ids
        # before anything reads them back.
        db.flush()

        count = int(TOTAL * share)
        for i in range(count):
            # Spread yesterday's conversations across the working day.
            closed = now - timedelta(hours=rng.uniform(1, 23))
            db.add(
                Conversation(
                    tenant_id=tenant.id,
                    external_id=f"{slug}-{i:06d}",
                    channel=rng.choice(["chat", "email", "voice"]),
                    closed_at=closed,
                    transcript=transcript(rng),
                )
            )
        # History. These closed two to five days ago, so the nightly job's
        # 24 hour window does not pick them up, but the review queue shows them.
        history_count = max(1, int(HISTORY * share))

        for i in range(history_count):
            closed = now - timedelta(days=rng.uniform(2, 5))
            conversation = Conversation(
                tenant_id=tenant.id,
                external_id=f"{slug}-hist-{i:05d}",
                channel=rng.choice(["chat", "email", "voice"]),
                closed_at=closed,
                transcript=transcript(rng),
            )
            db.add(conversation)
            db.flush()

            values = {c.name: float(rng.randint(55, 95)) for c in categories}
            total = round(sum(values.values()) / len(values), 2)
            prompt_hash = hashlib.sha256(
                f"{conversation.external_id}|{version.id}".encode()
            ).hexdigest()

            score = Score(
                tenant_id=tenant.id,
                conversation_id=conversation.id,
                rubric_version_id=version.id,
                total=total,
                model_id=MODEL_ID,
                prompt_hash=prompt_hash,
                created_at=closed + timedelta(minutes=rng.uniform(5, 90)),
            )
            db.add(score)
            db.flush()

            for category in categories:
                db.add(
                    CategoryScore(
                        score_id=score.id,
                        rubric_category_id=category.id,
                        value=values[category.name],
                        justification=(
                            f"The agent scored {values[category.name]:.0f} "
                            f"on {category.name.lower()}."
                        ),
                    )
                )

        print(
            f"{slug}: {count} conversations closed in the last 24h, "
            f"{history_count} older ones already scored, "
            f"webhook={'yes' if webhook else 'no'}"
        )

    db.commit()
    db.close()
    print(
        f"\nseeded {TOTAL} recent conversations and {HISTORY} scored older ones "
        f"across {len(TENANTS)} tenants"
    )
    print("the review queue at http://localhost:5173 now has rows to work with")


if __name__ == "__main__":
    main()
