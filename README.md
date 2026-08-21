# AlgoRecall

AlgoRecall is a web application for collecting, organizing, and actively reviewing coding problems and submissions from platforms such as LeetCode and Codeforces.

The goal is to turn solved or attempted coding problems into a personal learning system instead of a passive submission history. AlgoRecall combines automatically captured submissions with personal organization, spaced repetition, and later an LLM-based tutor.

## Concept

AlgoRecall is built around three kinds of data:

- **Canonical problem data** is stored centrally in PostgreSQL and shared across users.
- **User-specific application state** such as confidence, comments, tags, submission metadata, and later review history is stored in PostgreSQL.
- **User-owned submission artifacts** such as source code and detailed notes are stored in a dedicated GitHub repository owned by the user.

PostgreSQL is the source of truth for the AlgoRecall domain model. GitHub acts as external storage for the user's code and detailed notes.

## Core Submission Flow

A central goal of AlgoRecall is to capture submissions from supported coding platforms automatically.

The planned flow is:

```text
User submits code on LeetCode / Codeforces / ...
                    │
                    ▼
      source-specific integration 
        e.g. browser extension
        identifies the submission
                    │
                    ▼
            AlgoRecall Backend
             /             \
            /               \
           ▼                 ▼
     PostgreSQL           GitHub
  problem/submission     source code
      metadata           + detailed notes
```

A browser extension is one possible mechanism for detecting submissions directly on supported platforms and forwarding the relevant information to the AlgoRecall backend.

The backend then:

1. identifies or creates the canonical problem,
2. stores the submission metadata in PostgreSQL,
3. writes the submission source code into the user's AlgoRecall GitHub repository,
4. stores the GitHub repository/path reference with the submission.

The platform integration is intentionally separated from the core domain so AlgoRecall can support multiple sources without depending on one specific platform implementation.

## GitHub Integration

Users authenticate with GitHub.

During onboarding, AlgoRecall initializes a dedicated repository in the user's GitHub account for storing AlgoRecall content. The user does not need to create this repository manually.

Example structure:

```text
algorecall/
└── leetcode/
    └── two-sum/
        ├── submission-1234.py
        └── submission-1234.md
        └── submission-6789.py
        └── submission-6789.md
```

The repository remains owned by the user.

## Features

### Submission Tracking

- Detect submissions on supported coding platforms.
- Import submission metadata automatically.
- Store multiple submissions for the same problem.
- Track submission result and programming language.
- Store source code in the user's AlgoRecall GitHub repository.
- Preserve links between database submissions and GitHub artifacts.

### Problem Library

- Store each problem once per source/platform.
- Either display problem content directly inside AlgoRecall or keep link to the original source.
- Support multiple platforms such as LeetCode and Codeforces.


### Custom Tags

Tags are completely user-defined.

A user can create tags independently and assign the same tag to Problems or Submissions.


### Recall and Spaced Repetition

Recall is intended to become one of AlgoRecall's central features.

A review session should initially show the problem without revealing the user's previous code.

The user can first try to recall:

- the core approach
- relevant algorithms or data structures
- important edge cases
- expected complexity
- try to solve the problem again on the given platform 

Afterwards, the previous submission and notes can be revealed.

The user rates how well the problem was remembered, and AlgoRecall schedules the next review.

### Search and Filtering

The user should be able to query his knowledge base using a variaty of parameters:

- source (LeetCode, Codeforces...)
- difficulty
- user status
- confidence
- custom tags
- language
- submission status
- due-for-review state

### LLM Tutor

A later LLM tutor should work with the user's existing AlgoRecall context rather than act as a generic coding assistant.

Relevant context may include problem content, previous submissions, GitHub notes, comments, tags, confidence, and review history.

### Backend

- Python
- FastAPI
- SQLAlchemy
- Pydantic
- PostgreSQL
- Alembic
- pytest
- uv

### Frontend

- React
- TypeScript
- Vite

### Development Infrastructure

- Docker / Docker Compose
- PostgreSQL
- Adminer
- GitHub

## Repository Structure

AlgoRecall is developed as a monorepo:

```text
algorecall/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/
│   │   ├── db/
│   │   │   ├── models/
│   │   │   └── session.py
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── services/
│   │   └── main.py
│   ├── tests/
│   ├── pyproject.toml
│   └── uv.lock
│
├── frontend/
│
├── database/
│   ├── README.md
│   └── algorecall_schema.sql
│
├── docs/
│   └── notes.md
│
├── docker-compose.yaml
├── .gitignore
└── README.md
```

Database-specific modeling decisions, constraints, and delete behavior are documented separately in `database/README.md`.

## Development Approach

Development is incremental and currently at the beginning.

Current high-level order:

```text
1. Data model and PostgreSQL schema
3. SQLAlchemy models and database sessions
4. FastAPI backend foundation
5. GitHub authentication
6. Automatic GitHub repository initialization
7. Core problem and submission workflows
8. Submission ingestion from coding platforms
9. React frontend
10. Recall / spaced repetition
11. LLM tutor
12. Additional platform integrations
13. Production deployment and hardening
```

## Current Status

AlgoRecall is currently in the foundation phase.

Established so far:

- application concept and architecture
- initial relational data model
- SQLALchemy classes
