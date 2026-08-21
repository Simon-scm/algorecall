# AlgoRecall Database

This document describes the current PostgreSQL data model and the main database-specific design decisions for AlgoRecall.

## Responsibility

PostgreSQL is the source of truth for AlgoRecall's domain model and application state.

It stores:

- users
- GitHub repository metadata
- coding-platform sources
- canonical problems
- source-specific problem content
- user/problem relationships
- submission metadata
- custom tags and assignments

Submission source code and detailed submission notes are stored externally in the user's AlgoRecall GitHub repository and referenced from PostgreSQL.

## Current Tables

```text
app_user
github_repository
source
problem
leetcode_problem_content
user_problem
submission
tag
user_problem_tag
submission_tag
```

A future recall implementation will add a separate `review` model.

## app_user

Stores the AlgoRecall user mapped to a GitHub account.

```text
id              BIGINT PK
github_id       BIGINT UNIQUE NOT NULL
github_name     TEXT NOT NULL
github_email    TEXT NULL
created_at      TIMESTAMPTZ NOT NULL
```

`github_id` is the stable external identifier. `github_name` is metadata and may change.

Deleting an `app_user` cascades to user-owned application state such as `github_repository`, `user_problem`, and `tag`.

## github_repository

Stores metadata for the repository initialized by AlgoRecall in the user's GitHub account.

```text
id                      BIGINT PK
user_id                 BIGINT FK UNIQUE NOT NULL
github_repository_id    BIGINT UNIQUE NOT NULL
name                    TEXT NOT NULL
created_at              TIMESTAMPTZ NOT NULL
updated_at              TIMESTAMPTZ NOT NULL
```

Current assumptions:

- each AlgoRecall user has at most one connected AlgoRecall repository,
- AlgoRecall initializes the repository during onboarding,
- the repository remains owned by the user,
- the user may rename it later,
- `github_repository_id` remains the stable identity,
- repository-name changes can later be synchronized using GitHub webhooks.

`ON DELETE CASCADE` is used from `github_repository.user_id` to `app_user`.

## source

Represents an external coding-problem platform.

```text
id      BIGINT PK
name    TEXT UNIQUE NOT NULL
```

Examples:

```text
leetcode
codeforces
```

Problems reference `source.id`.

`ON DELETE RESTRICT` prevents deletion of a source while problems still reference it.

## problem

Stores one canonical problem per source/platform.

```text
id              BIGINT PK
source_id       BIGINT FK NOT NULL
external_id     TEXT NOT NULL
problem_title   TEXT NOT NULL
slug            TEXT NULL
source_url      TEXT NOT NULL
```

Constraint:

```text
UNIQUE(source_id, external_id)
```

This guarantees that the same external problem from the same source is stored only once.

`external_id` is `TEXT` so sources are not required to use numeric identifiers.

## leetcode_problem_content

Stores LeetCode-specific content separately from the shared `problem` table.

```text
problem_id      BIGINT PK/FK
difficulty      TEXT NOT NULL
description     TEXT NOT NULL
examples        JSONB NOT NULL
constraints     JSONB NOT NULL
```

Difficulty is restricted to:

```text
easy
medium
hard
```

`problem_id` is both the primary key and foreign key, enforcing at most one LeetCode-content row per problem.

Deleting the parent `problem` cascades to this content row.

Additional platforms may receive their own source-specific content tables if their schemas differ meaningfully.

## user_problem

Represents the relationship between one user and one canonical problem.

```text
id            BIGINT PK
user_id       BIGINT FK NOT NULL
problem_id    BIGINT FK NOT NULL
status        TEXT NOT NULL
confidence    SMALLINT NULL
comment       TEXT NULL
created_at    TIMESTAMPTZ NOT NULL
```

Constraint:

```text
UNIQUE(user_id, problem_id)
```

This table does not duplicate a problem. It stores only user-specific state for that problem.

### Status

`status` is system-managed and is not edited manually by the user.

Initial values:

```text
attempted
solved
```

The intended invariant is:

```text
accepted submission exists
    → solved

one or more submissions exist,
but none is accepted
    → attempted
```

The application/service layer is responsible for keeping this value consistent when submissions are inserted, updated, or removed.

### Confidence

`confidence` is nullable and restricted to values from `1` to `5`.

### Delete behavior

- deleting the user → `ON DELETE CASCADE`
- deleting the referenced problem → `ON DELETE RESTRICT`

A canonical problem therefore cannot be accidentally deleted while user-specific history still references it.

## submission

Stores the domain record and structured metadata for one user submission.

```text
id                      BIGINT PK
user_problem_id         BIGINT FK NOT NULL
repository_id           BIGINT FK NULL
github_path             TEXT NOT NULL
github_blob_sha         TEXT NULL
external_submission_id  TEXT NULL
language                TEXT NOT NULL
status                  TEXT NOT NULL
submitted_at            TIMESTAMPTZ NOT NULL
created_at              TIMESTAMPTZ NOT NULL
```

Initial status values:

```text
accepted
wrong_answer
time_limit_exceeded
memory_limit_exceeded
runtime_error
```

Constraints:

```text
UNIQUE(user_problem_id, external_submission_id)
UNIQUE(repository_id, github_path)
```

`external_submission_id` is nullable so AlgoRecall can support submissions that do not originate from an integration providing a stable external ID.

PostgreSQL allows multiple `NULL` values under the normal unique constraint.

### GitHub reference

The database submission is the authoritative AlgoRecall domain entity.

The associated GitHub file stores the source-code artifact.

`repository_id` references `github_repository`, while `github_path` is relative to that repository.

Example:

```text
repository_id = 4
github_path   = leetcode/two-sum/submission-123.py
```

A repository rename therefore does not require updating every submission path.

`github_blob_sha` may later be used to identify the currently known Git blob/version of the file and detect content changes.

### Delete behavior

`user_problem_id`:

```text
ON DELETE CASCADE
```

A submission has no AlgoRecall meaning after its parent `UserProblem` is deleted.

`repository_id`:

```text
ON DELETE SET NULL
```

Removing the repository connection does not delete the factual submission record.

If the GitHub artifact is unavailable or deleted, AlgoRecall can display it as missing without automatically deleting the submission.

## tag

Stores user-defined tags.

```text
id          BIGINT PK
user_id     BIGINT FK NOT NULL
name        TEXT NOT NULL
created_at  TIMESTAMPTZ NOT NULL
```

Constraint:

```text
UNIQUE(user_id, name)
```

A tag belongs to exactly one user and can exist without currently being assigned.

Tags are not stored as arrays or lists because they need to be queried and reused relationally.

Deleting a user cascades to their tags.

## user_problem_tag

Join table for assigning a user-owned tag to a `UserProblem`.

```text
user_problem_id    BIGINT PK/FK
tag_id             BIGINT PK/FK
```

Composite primary key:

```text
PRIMARY KEY(user_problem_id, tag_id)
```

Both foreign keys use:

```text
ON DELETE CASCADE
```

No separate surrogate ID is required because the relationship itself is uniquely identified by the two foreign keys.

## submission_tag

Join table for assigning a user-owned tag to a specific submission.

```text
submission_id    BIGINT PK/FK
tag_id           BIGINT PK/FK
```

Composite primary key:

```text
PRIMARY KEY(submission_id, tag_id)
```

Both foreign keys use:

```text
ON DELETE CASCADE
```

## Tag Ownership Invariant

The current relational structure guarantees that referenced `Tag`, `UserProblem`, and `Submission` records exist, but it does not by itself guarantee that a tag belongs to the same user as the target `UserProblem` or `Submission`.

For example, the database foreign keys alone would not prevent a tag owned by user A from being assigned directly through SQL to a `UserProblem` owned by user B.

For the initial version, this ownership invariant is enforced in the application/service layer.

The schema can later be strengthened with composite ownership foreign keys if required.

## ID and Data Type Conventions

Internal IDs use:

```text
BIGINT GENERATED BY DEFAULT AS IDENTITY
```

Foreign keys use `BIGINT`.

Other conventions:

```text
GitHub IDs                 → BIGINT
external platform IDs      → TEXT
names / URLs / paths       → TEXT
long-form content          → TEXT
structured examples        → JSONB
small ratings              → SMALLINT
timestamps                 → TIMESTAMPTZ
status fields              → TEXT + CHECK
GitHub blob SHA            → TEXT
```

PostgreSQL `ENUM` types are intentionally avoided for initial status fields so supported values can be extended more easily through migrations.

## Timestamps

Creation timestamps use:

```sql
TIMESTAMPTZ NOT NULL DEFAULT now()
```

`updated_at` on `github_repository` also defaults to `now()`, but PostgreSQL does not automatically update it on every modification.

The application layer is responsible for setting `updated_at` when repository metadata changes.

## Delete Rules Summary

| Foreign key | Delete behavior |
|---|---|
| `github_repository.user_id → app_user.id` | `CASCADE` |
| `problem.source_id → source.id` | `RESTRICT` |
| `leetcode_problem_content.problem_id → problem.id` | `CASCADE` |
| `user_problem.user_id → app_user.id` | `CASCADE` |
| `user_problem.problem_id → problem.id` | `RESTRICT` |
| `tag.user_id → app_user.id` | `CASCADE` |
| `submission.user_problem_id → user_problem.id` | `CASCADE` |
| `submission.repository_id → github_repository.id` | `SET NULL` |
| `user_problem_tag.user_problem_id → user_problem.id` | `CASCADE` |
| `user_problem_tag.tag_id → tag.id` | `CASCADE` |
| `submission_tag.submission_id → submission.id` | `CASCADE` |
| `submission_tag.tag_id → tag.id` | `CASCADE` |

## Schema Lifecycle

`algorecall_schema.sql` represents the initial PostgreSQL schema and can be used to initialize a fresh local database.

Once application development introduces schema changes, Alembic migrations should become the normal mechanism for evolving existing databases.

Conceptually:

```text
database/algorecall_schema.sql
    → initial schema / reference

backend/app/db/models/
    → current SQLAlchemy representation

backend/alembic/
    → ordered schema migrations
```

Production schema updates should eventually be performed through Alembic rather than repeatedly running the initial create script.
