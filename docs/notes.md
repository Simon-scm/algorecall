# Project Notes

## Features
1. Automatically save leetcode solutions in github repo
2. Save questions in postgres
3. Save solution cache in postgres
4. Recall algorithm as known with flashcards
5. Write notes and comments to solutions
6. Generate tags for solutions 

## Data model
User
- id (PK)
- github_id (unique, not null)
- github_name
- github_email
- created_at

GitHubRepository
- id (PK)
- user_id (FK User.id, uniquem not null)
- github_repository_id (unique)
- name
- created_at
- update_at

Source
- id (PK)
- name (unique)

Problem (unique: (source_id, external_id))
- id (PK)
- source_id (FK Source.id)
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

Submission (unique: (user_problem_id, external_submission_id))
- id (PK)
- user_problem_id (FK UserProblem.id)
- repository_id (FK GitHubRepository.id)
- github_path
- github_blob_sha
- external_submission_id (nullable)     
- language
- status (accepted, wrong_answer, time_limit_exceeded, memory_limit_exceeded, runtime_error)
- submitted_at

Tag (unique: (user_id, name))
- id (PK)
- user_id (FK User.id)
- name
- created_at

UserProblemTag
- user_problem_id (PK, FK UserProblem.id)
- tag (PK, FK Tag.id)

SubmissionTag
- submission_id (PK, FK Submission.id)
- tag (PK, FK Tag.id)

