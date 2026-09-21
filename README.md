# Vandelay Industries — "Rubric" conversation scoring service

Welcome, and thank you for doing this.

Vandelay Industries is a fictional company. The code in this repository is real,
it runs, and it has serious problems.

## What this service is

Vandelay provides customer support for several client brands. Eleven days ago
the team released **Rubric**. It scores support conversations against a quality
rubric using a language model. The goal was to let supervisors review every
conversation instead of a two percent sample.

Rubric worked well in the staging environment. It has been in production for
eleven days and it is not working well there.

## What we are asking you to do

There is more wrong with this service than fits in two hours, so we have been
specific about what we want.

### Required: make the failing tests pass

`tests/test_idempotency.py` has two failing tests. They say that submitting the
same conversation twice must not write a second score, and must not call the
model a second time. That is Art Vandelay's most urgent complaint, and it is
the part that affects what agents get paid.

```bash
make test
```

The tests are marked `xfail`, so the suite is green before you start. Delete
the markers when your fix works. The rest of the suite must keep passing.

This is the part we expect everyone to complete.

### Required: write up what else you found

Read `docs/INCIDENT.md`. It is what the on-call engineer wrote before going on
holiday. There are several other problems in here, and some of them share a
cause with the one you fixed.

In `FINDINGS.md`, tell us what is wrong, why, and in what order you would fix
it. One or two sentences per item. Bullet points are fine. We are not assessing
your writing, and we would rather have a short honest list than a long one.

This is where you show us how you think, and it counts for as much as the code.

### Optional: anything else you have time for

If you finish early, pick something from your own list and fix it. Tell us why
you picked that one. We would rather see one more thing done properly than
several started.

### Not expected

You do **not** need to fix the gateway timeouts, the nightly batch, the model
throttling, the cost reporting, or the dashboard. Notice them, write them down,
and leave them. A submission that fixes the required part well and explains the
rest clearly is a good submission.

## Rules

- **Spend no more than two hours in total.** This includes setup and reading.
  Plan about 40 minutes to read the code and run the service. This limit is
  real. We want to see how you decide what to do when time is short.
- **Use the tools you normally use.** This includes AI assistants. We use Claude
  Code every day and we would rather see how you really work. If you use an AI
  assistant, we will ask you how you directed it and how you checked its output.
- **You are not expected to fix everything.** There is more wrong here than fits
  in two hours. That is deliberate.
- **The specification is not complete.** Where something is unclear, make a
  decision and write down the assumption you made.
- **Ask us if setup does not work.** Environment problems are not part of the
  test. Send us a message and we will help.

## What to send back

Send a link to your fork, or a patch file, **at least 48 hours before our
meeting**. It should contain:

- **Your fix on a branch**, with `tests/test_idempotency.py` passing and the
  `xfail` markers removed.
- **`FINDINGS.md`** — what you found, what you fixed, and your priority list
  for what comes next.

If you run out of time in the middle of a fix, send what you have and add a note
about where you would continue. That is a good outcome, not a bad one.

## Running it

You need Docker and Docker Compose. Nothing else. There is no AWS account and no
API key involved: a stub service copies the behaviour of the real model.

```bash
cp .env.example .env
make up        # builds and starts everything
make seed      # loads test data
```

`make up` prints the URLs. The API is at http://localhost:8080 and the
supervisor screen is at http://localhost:5173. The first start takes a few
minutes because it builds images and installs frontend packages.

The review queue lists conversations that already have a score, so after
`make seed` you will see the scored history from earlier in the week, about 70
rows for the `acme` tenant. The conversations from the last 24 hours are not
scored yet: that is what the nightly job is for. Run `make repro-batch` or
`make repro-webhook` to score them.

### Reproduction steps

```bash
make repro-interactive   # 20 supervisors press "re-score" at the same time
make repro-batch         # what the nightly scheduled job does at 02:00 UTC
make repro-webhook       # what an integrated client helpdesk does
make score-report        # what ended up in the database
make health              # ask the load balancer about service health
make logs                # follow the API logs
```

Run `make` on its own to see every command.

### Two notes about the local environment

The seed data is about five percent of one production night. This keeps each
reproduction to a few minutes instead of a few hours. The stub model's
requests-per-minute limit is scaled down to match. Both can be increased:

```bash
# optional: set STUB_RPM=200 in .env first
make reset
make up
SEED_CONVERSATIONS=20000 make seed
```

The stack runs two API containers with four workers each, behind nginx. This
matches production. nginx has the same 30 second read timeout as the production
load balancer, and it removes a container from service after three failed
requests.

## How we will use our hour together

About 5 minutes to settle in, 10 minutes on your diagnosis, 20 minutes on your
code and why you made those choices, 15 minutes on what you would do next and
how you would know it worked, 5 minutes on how you approached the work, and the
last 5 minutes for your questions. Most of the time is about your reasoning,
not about syntax.

## What a good answer looks like

**The required fix works.** Both tests pass, the rest of the suite still
passes, and the fix handles the failure cases rather than only the happy path.

**The diagnosis is real.** Did you find causes rather than symptoms? Several of
the problems in here share one cause. Can you explain the evidence, including
the parts that look contradictory?

**The priorities make sense.** Is your list ordered by impact? Can you defend
the order? Did you weigh the cost of each item as well as the benefit? Did you
decide not to fix something, and can you say why?

**You were honest.** State your assumptions. Mark what you are unsure about. "I
ran out of time here and this is where I would continue" is a good sentence,
and so is "I do not know why this happens yet."

One note about scope. A submission that completes the required fix and lists
six more problems with clear reasoning is a strong submission. One that
half-fixes five things is weaker. So is one that only contains writing and no
working code.

Good luck. We are looking forward to the conversation.

## Repository layout

```
rubric/
  api/
    main.py            FastAPI application, middleware, routers
    deps.py            authentication stub, tenant lookup, database session
    schemas.py         request and response models
    routes/            scoring, scores, rubrics, queue, webhooks, health
  services/
    scoring.py         orchestration: prompt, model call, saving the result
    prompts.py         prompt template
  adapters/
    bedrock.py         model client
  workers/
    consumer.py        queue consumer
  db/
    models.py          SQLAlchemy models
    repositories.py    database access
    migrations/        Alembic migrations
  retry.py             retry helper
  telemetry.py         metrics
  config.py            settings
frontend/              React and TypeScript supervisor screen
stub_model/            stand-in for the real model
scripts/               seed data, reproduction scripts, SQL report
docs/                  specification, incident notes, and more
tests/                 the existing test suite
nginx/                 load balancer configuration
```
