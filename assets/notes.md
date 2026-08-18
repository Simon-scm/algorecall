# Project Notes
# Concept

**AlgoRecall** is a web application for collecting, reviewing, and learning from coding-problem submissions across platforms such as LeetCode and Codeforces.

The core idea is to separate the **shared problem/domain data** from the **user-owned code artifacts**:

- **PostgreSQL is the source of truth for AlgoRecall's domain model and application state.**
- **GitHub is used as external storage for user-owned submission code and detailed submission notes.**

A problem is stored only once per source/platform. For example, LeetCode problem `#200` exists only once in the `Problem` table, regardless of how many AlgoRecall users have solved it.

The relationship between a user and a problem is represented by a separate `UserProblem` entity. This does not duplicate the problem itself; it stores user-specific information about that problem, such as:

- status (`attempted`, `solved`, ...)
- confidence
- comments
- personal labels
- review state/history

A user may have multiple submissions for the same problem. These are represented as `Submission` entities linked to `UserProblem`.

The `Submission` table stores the factual/structured information about a submission, for example:

- internal submission ID
- related `UserProblem`
- external submission ID, if available
- submission status
- programming language
- submission timestamp
- GitHub repository/path reference
- optional complexity metadata

The actual source code and detailed submission notes are stored in the user's GitHub repository rather than duplicated as authoritative content in PostgreSQL.

A GitHub file is therefore an **artifact referenced by a database entity**, not the identity of that entity.

Example:

```text
PostgreSQL

Submission #481
- user_problem_id: 52
- status: accepted
- language: python
- github_path: leetcode/two-sum/submission-481.py
```

```text
GitHub

algorecall/
└── leetcode/
    └── two-sum/
        ├── submission-481.py
        └── submission-481.md
```

If a user manually deletes or changes a submission artifact on GitHub, the corresponding database entity does not automatically cease to exist. AlgoRecall can instead mark the GitHub artifact as unavailable and show something such as:

> Submission exists, but the associated GitHub content could not be found.

The user can then explicitly decide whether the submission should also be removed from AlgoRecall.

GitHub webhooks can later be used to synchronize external repository changes with AlgoRecall. They may trigger:

- insertion of newly discovered submissions
- updates to existing submission references/state
- marking deleted GitHub artifacts as missing

Webhooks are therefore a synchronization mechanism, while PostgreSQL remains authoritative for AlgoRecall's domain state.

Problem content is stored in PostgreSQL as well, so that AlgoRecall can display and review problems without depending on GitHub.

The model deliberately separates common problem metadata from source-specific content.

Example:

```text
Source
- id
- name

Problem
- id
- source_id
- external_id
- problem_title
- slug
- source_url

LeetcodeProblemContent
- problem_id
- difficulty
- description
- examples
- constraints

CodeforcesProblemContent
- problem_id
- source-specific fields...
```

The pair `(source_id, external_id)` must be unique so that the same problem from the same platform can only exist once.

Source-specific content tables allow AlgoRecall to support platforms with different problem structures without forcing all platform-specific fields into one generic table.

The current core relationships are conceptually:

```text
Source 1 ───── n Problem

Problem 1 ───── 0..1 LeetcodeProblemContent
Problem 1 ───── 0..1 CodeforcesProblemContent
                 ...

User 1 ───── n UserProblem
Problem 1 ───── n UserProblem

UserProblem 1 ───── n Submission
UserProblem 1 ───── n Review
```

The intended architecture is therefore:

```text
                         GitHub
                  user-owned artifacts
                  code + detailed notes
                           ▲
                           │
                           │ references / sync
                           │
React ─────── FastAPI ─────┼───── PostgreSQL
                           │       source of truth
                           │       for AlgoRecall
                           │
                     GitHub Webhooks
```

GitHub authentication should later be used for user login and repository access. AlgoRecall should create or connect to a dedicated repository in the user's own GitHub account.

The application should not depend on LeetCode or any other single problem platform as its foundation. External platforms are treated as sources that can later feed problems and submissions into the same domain model.

# Features

## Core problem library

- Store each coding problem once per source/platform.
- Support multiple sources such as LeetCode and Codeforces.
- Store shared problem metadata in PostgreSQL.
- Store source-specific problem content in dedicated source-specific tables.
- Display the problem directly inside AlgoRecall.
- Keep a link back to the original source.

## User-specific problem state

Each user can maintain their own relationship to a shared problem through `UserProblem`.

Planned fields/features include:

- attempted/solved status
- confidence rating
- personal comment
- personal labels
- timestamps
- recall/review state

The same `Problem` can therefore be shared by all users while every user keeps independent learning state.

## Submissions

Users can have multiple submissions per problem.

A submission can contain structured metadata such as:

- submission status
- language
- external submission ID
- submission timestamp
- time complexity
- space complexity
- GitHub artifact path/reference

`Submission` should be linked to `UserProblem` rather than duplicating `user_id` and `problem_id`.

Example:

```text
User
 └── UserProblem
      ├── Submission #1
      ├── Submission #2
      ├── Submission #3
      └── Review history
```

The name `Submission` is preferred over `Solution`, because submissions may also represent failed attempts such as:

- accepted
- wrong answer
- time limit exceeded
- runtime error
- other source-specific result states

## GitHub-backed user content

AlgoRecall stores user-created submission artifacts in a repository owned by the user.

Examples:

- source code
- detailed solution notes
- explanations
- implementation-specific observations

GitHub provides:

- user ownership of their code
- version history
- commits
- portability outside AlgoRecall
- direct access to stored solutions

PostgreSQL stores references to these artifacts but remains authoritative for the existence and metadata of AlgoRecall submissions.

## GitHub synchronization

Later, GitHub webhooks can synchronize repository changes back into AlgoRecall.

Possible cases:

- a new submission file appears → create/update a `Submission`
- an existing file changes → update cached/reference information
- a file is deleted → mark its artifact as missing
- a repository/path changes → reconcile the stored reference

Deleting a GitHub artifact should not automatically delete the corresponding submission from PostgreSQL.

AlgoRecall can instead show the missing state and allow the user to explicitly remove the database record.

## Recall and spaced repetition

A central feature of AlgoRecall is reviewing previously solved problems.

A separate `Review` entity should store review history instead of only keeping a single `last_reviewed` value.

Possible structure:

```text
Review
- id
- user_problem_id
- reviewed_at
- rating
- next_review_at
```

The application can then provide a daily review queue such as:

```text
Today's Reviews

1. Number of Islands
2. LRU Cache
3. Merge Intervals
4. Course Schedule
```

During a recall session, AlgoRecall should initially show the problem without immediately revealing the old submission.

The user can first try to remember:

- the core idea
- the relevant algorithm/data structure
- the expected complexity
- edge cases

Afterwards the user can reveal their previous submission and notes.

The user rates how well the problem was remembered, and AlgoRecall calculates the next review date.

A simple first version may use intervals such as:

```text
Forgot       → review tomorrow
Difficult    → review in 3 days
Remembered   → review in 7 days
Easy         → review in 21 days
```

This can later be replaced by a more sophisticated spaced-repetition algorithm.

## Tags and personal labels

Tags and labels still need to be modeled explicitly.

They should likely be separated into two concepts:

- **Problem tags**: objective/problem-level concepts such as `Graph`, `DFS`, `Array`, `Dynamic Programming`
- **User labels**: personal labels such as `redo`, `hard-for-me`, `interview`, `favorite`

Both should be modeled relationally through separate tables/join tables rather than stored as unstructured sets if they need to be queried efficiently.

## Search and filtering

AlgoRecall should later allow filtering by attributes such as:

- source
- difficulty
- problem tags
- personal labels
- status
- confidence
- due-for-review state
- language
- submission result

## LLM tutor

A later phase can add an LLM-based tutor that uses the user's AlgoRecall context.

Potential modes:

- Socratic hints without revealing the solution
- interview simulation
- recall questioning
- explanation of previous mistakes
- comparison of multiple submissions
- identification of recurring algorithmic patterns

The LLM should use relevant context such as:

- problem content
- previous submissions
- detailed GitHub notes
- user comments
- confidence
- review history
- tags/labels

## External platform integration

AlgoRecall should initially work without automatic platform synchronization.

Later integrations may import data from sources such as:

- LeetCode
- Codeforces
- HackerRank
- other coding platforms

A future flow could be:

```text
Accepted submission on external platform
        ↓
integration/import
        ↓
store code artifact in user's GitHub repository
        ↓
GitHub webhook / import service
        ↓
create or update Submission in PostgreSQL
```

The exact integration mechanism must remain separate from the core AlgoRecall domain so that the application continues to function even if an external platform changes or becomes unavailable.


## Features
1. Automatically save leetcode solutions in github repo
2. Save questions in postgres
3. Save solution cache in postgres
4. Recall algorithm as known with flashcards
5. Write notes and comments to solutions
6. Generate tags for solutions 

## Data model
Labels und Tags modellieren!

User
- id (PK)
- github_id (unique, not null)
- github_name
- github_email
- created_at

Source
- id (PK)
- name (unique)

Problem (unique: (source_id, external_id))
- id (PK)
- source_id (FK Source.id)
- source_name (FK Source.name)
- external_id
- problem_title
- slug
- source_url

LeetcodeProblemContent
- problem_id (PK, FK Problem.id)
- difficulty
- description
- examples
- constraints

CodeforesProblemContent
- ...
- ...

UserProblem (unique: (user_id, problem_id))
- id (PK)
- user_id (FK User.id)
- problem_id (FK Problem.id)
- status (solved or attempted)
- confidence
- comment
- created_at

Submission
- id (user kann mehrere Lösungen pro Problem haben)
- user_problem_id (FK UserProblem.id)
- github_repository_id
- github_path
- github_sha
- external_submission_id (nullable)
- language
- status (accepted, wrong_answer, TLE, MLE, runtime_error)
- submitted_at