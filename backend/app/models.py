from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Kind = Literal["article", "course", "document", "webinar", "podcast", "glossary", "calculator"]


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Literal["idea", "start", "growth"] | None = None
    industry: str | None = Field(default=None, max_length=100)
    experience: Literal["beginner", "experienced"] | None = None
    format: Kind | None = None
    urgency: Literal["quick", "deep"] | None = None


    @field_validator("industry")
    @classmethod
    def normalize_industry(cls, value):
        if value and value.casefold().translate(str.maketrans({"с": "c", "а": "a", "е": "e", "о": "o"})) == "horeca":
            return "HoReCa"
        return value


class Material(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    source_type: Kind
    title: str
    description: str = ""
    topics: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    stage: list[str] = Field(default_factory=list)
    difficulty: Literal["beginner", "experienced"] | None = None
    access: Literal["free", "paid", "subscription", "unknown"] = "unknown"
    price: int | None = Field(default=None, ge=0)
    duration: str | None = None
    url: str | None = None
    published: bool = True
    provenance: Literal["synthetic", "organizer"] = "synthetic"
    demo_content: str | None = None
    related_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def protect_content(self):
        if self.demo_content and (self.provenance != "synthetic" or self.access != "free"):
            raise ValueError("Only original free demo content may be included")
        return self

    @field_validator("url")
    @classmethod
    def safe_url(cls, value):
        if value is not None:
            from urllib.parse import urlparse

            parsed = urlparse(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                raise ValueError("Only absolute HTTP(S) source links are allowed")
        return value


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(default="", max_length=1500)
    profile: Profile = Field(default_factory=Profile)
    limit: int = Field(default=5, ge=1, le=10)


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material_id: str = Field(max_length=100)
    signal: Literal["helpful", "not_relevant", "known", "completed", "reset"]


class Recommendation(BaseModel):
    material: Material
    reasons: list[str]
    next_action: str
    phase: str
    score: float
    rank_score: float
    signals: dict[str, float]


class Route(BaseModel):
    match_scope: Literal["task", "general"] = "task"
    route_id: str
    algorithm: str
    query: str
    profile: Profile
    items: list[Recommendation]
    clarification: str | None = None
    notice: str | None = None
    catalog_mode: str
    catalog_version: str
    elapsed_ms: float
    excluded_count: int
    candidate_count: int
    active_profile_fields: list[str]


class HistoryImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    catalog_version: str = Field(pattern=r"^[0-9a-f]{16}$")
    completed_material_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("completed_material_ids")
    @classmethod
    def unique_ids(cls, values):
        if len(values) != len(set(values)) or any(len(v) > 100 for v in values):
            raise ValueError("History IDs must be unique and bounded")
        return values
