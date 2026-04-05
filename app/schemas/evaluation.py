"""Evaluator and optimizer structured outputs."""

from typing import Literal

from pydantic import BaseModel, Field


class CriterionScore(BaseModel):
    """Score for one evaluation dimension."""

    criterion: Literal[
        "missing_information",
        "redundancy",
        "weak_reasoning",
        "unsupported_claims",
        "poor_structure",
    ]
    score: int = Field(..., ge=1, le=5, description="1 = severe issue, 5 = no issue.")
    notes: str = Field(..., description="Concrete, actionable notes for this criterion.")


class EvaluationResult(BaseModel):
    """Structured critique of the aggregated draft."""

    criteria: list[CriterionScore] = Field(default_factory=list)
    overall_quality: int = Field(..., ge=1, le=5)
    missing_information: list[str] = Field(default_factory=list)
    redundancy_issues: list[str] = Field(default_factory=list)
    weak_reasoning: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    structure_issues: list[str] = Field(default_factory=list)
    recommended_improvements: list[str] = Field(
        default_factory=list,
        description="Specific edits to apply in refinement.",
    )
    should_refine: bool = Field(
        ...,
        description="True if draft should be revised before returning to the user.",
    )


class RefinedOutput(BaseModel):
    """Optimizer structured response."""

    revised_answer: str = Field(..., description="Improved final narrative.")
    change_summary: str = Field(..., description="What changed vs prior draft and why.")
