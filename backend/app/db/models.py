from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    PrimaryKeyConstraint,
    SmallInteger,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


# Association Tables
user_problem_tag = Table(
    "user_problem_tag",
    Base.metadata,
    Column(
        "user_problem_id",
        BigInteger,
        ForeignKey(
            "user_problem.id",
            ondelete="CASCADE",
            name="fk_user_problem_tag_user_problem",
        ),
        nullable=False,
    ),
    Column(
        "tag_id",
        BigInteger,
        ForeignKey(
            "tag.id",
            ondelete="CASCADE",
            name="fk_user_problem_tag_tag",
        ),
        nullable=False,
    ),
    PrimaryKeyConstraint(
        "user_problem_id",
        "tag_id",
    ),
)


submission_tag = Table(
    "submission_tag",
    Base.metadata,
    Column(
        "submission_id",
        BigInteger,
        ForeignKey(
            "submission.id",
            ondelete="CASCADE",
            name="fk_submission_tag_submission",
        ),
        nullable=False,
    ),
    Column(
        "tag_id",
        BigInteger,
        ForeignKey(
            "tag.id",
            ondelete="CASCADE",
            name="fk_submission_tag_tag",
        ),
        nullable=False,
    ),
    PrimaryKeyConstraint(
        "submission_id",
        "tag_id",
    ),
)


# User
class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    github_name: Mapped[str]
    github_email: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


    github_repository: Mapped[GithubRepository | None] = relationship(
        back_populates="user"
    )
    user_problems: Mapped[list[UserProblem]] = relationship(
        back_populates="user"
    )
    tags: Mapped[list[Tag]] = relationship(
        back_populates="user"
    )


# Problem Source (LeetCode, Codeforces, ...)
class Source(Base):
    __tablename__ = "source"

    id: Mapped[int] = mapped_column( BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)


    problems: Mapped[list[Problem]] = relationship(
        back_populates="source"
    )


# GitHub Repository of Users
class GithubRepository(Base):
    __tablename__ = "github_repository"

    id: Mapped[int] = mapped_column( BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "app_user.id",
            ondelete="CASCADE",
            name="fk_github_repository_user",
        ),
        unique=True,
    )
    github_repository_id: Mapped[int] = mapped_column(BigInteger, nunique=True)
    name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


    user: Mapped[AppUser] = relationship(
        back_populates="github_repository",
    )
    submissions: Mapped[list[Submission]] = relationship(
        back_populates="repository",
    )


# The specific coding problems (from all connected sources)
class Problem(Base):
    __tablename__ = "problem"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "external_id",
            name="uq_problem_source_external_id",
        )
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True) 
    source_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "source.id",
            ondelete="RESTRICT",
            name="fk_problem_source",
        ),
    )
    external_id: Mapped[str]
    problem_title: Mapped[str]
    slug: Mapped[str | None]
    source_url: Mapped[str]


    source: Mapped[Source] = relationship(
        back_populates="problems"
    )
    leetcode_content: Mapped[LeetcodeProblemContent | None] = relationship(
        back_populates="problem"
    )
    user_problems: Mapped[list[UserProblem]] = relationship(
        back_populates="problem"
    )


# Content of Leetcode problems
class LeetcodeProblemContent(Base):
    __tablename__ = "leetcode_problem_content"
    __table_args__ = (
        CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_leetcode_problem_content_difficulty",
        )
    )

    problem_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "problem.id",
            ondelete="CASCADE",
            name="fk_leetcode_problem_content_problem",
        ),
        primary_key=True,
    )
    difficulty: Mapped[str]
    examples: Mapped[Any] = mapped_column(JSONB)
    constraints: Mapped[Any] = mapped_column(JSONB)
    description: Mapped[str]


    problem: Mapped[Problem] = relationship(
        back_populates="leetcode_content"
    )


# Problems a user tried to solve
class UserProblem(Base):
    __tablename__ = "user_problem"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "problem_id",
            name="uq_user_problem_user_problem",
        ),
        CheckConstraint(
            "status IN ('attempted', 'solved')",
            name="ck_user_problem_status",
        ),
        CheckConstraint(
            "confidence BETWEEN 1 AND 5",
            name="ck_user_problem_confidence",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "app_user.id",
            ondelete="CASCADE",
            name="fk_user_problem_user",
        ),
    )
    problem_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "problem.id",
            ondelete="RESTRICT",
            name="fk_user_problem_problem",
        ),
    )
    status: Mapped[str]
    confidence: Mapped[int | None] = mapped_column(SmallInteger)
    comment: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


    user: Mapped[AppUser] = relationship(
        back_populates="user_problems",
    )
    problem: Mapped[Problem] = relationship(
        back_populates="user_problems",
    )
    submissions: Mapped[list[Submission]] = relationship(
        back_populates="user_problem",
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary=user_problem_tag,
        back_populates="user_problems",
    )


# User specific tags
class Tag(Base):
    __tablename__ = "tag"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "name",
            name="uq_tag_user_name",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "app_user.id",
            ondelete="CASCADE",
            name="fk_tag_user",
        ),
    )
    name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


    user: Mapped[AppUser] = relationship(
        back_populates="tags",
    )
    user_problems: Mapped[list[UserProblem]] = relationship(
        secondary=user_problem_tag,
        back_populates="tags",
    )
    submissions: Mapped[list[Submission]] = relationship(
        secondary=submission_tag,
        back_populates="tags",
    )


# All submissions from a user to his tried problems
class Submission(Base):
    __tablename__ = "submission"
    __table_args__ = (
        UniqueConstraint(
            "user_problem_id",
            "external_submission_id",
            name="uq_submission_user_problem_external_id",
        ),
        UniqueConstraint(
            "repository_id",
            "github_path",
            name="uq_submission_repository_path",
        ),
        CheckConstraint(
            """
            status IN (
                'accepted',
                'wrong_answer',
                'time_limit_exceeded',
                'memory_limit_exceeded',
                'runtime_error'
            )
            """,
            name="ck_submission_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_problem_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "user_problem.id",
            ondelete="CASCADE",
            name="fk_submission_user_problem",
        ),
    )
    repository_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "github_repository.id",
            ondelete="SET NULL",
            name="fk_submission_repository",
        ),
    )
    github_path: Mapped[str]
    github_blob_sha: Mapped[str | None]
    external_submission_id: Mapped[str | None]
    language: Mapped[str]
    status: Mapped[str]
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


    user_problem: Mapped[UserProblem] = relationship(
        back_populates="submissions",
    )
    repository: Mapped[GithubRepository | None] = relationship(
        back_populates="submissions",
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary=submission_tag,
        back_populates="submissions",
    )