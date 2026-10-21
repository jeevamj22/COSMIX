"""Request and response models for the v1 API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PreferencesIn(BaseModel):
    avoid: list[str] = Field(default_factory=list, max_length=40)
    prefer: list[str] = Field(default_factory=list, max_length=40)
    investigate: list[str] = Field(default_factory=list, max_length=40)


class ExtractIn(BaseModel):
    product_url: str = Field(min_length=4, max_length=2000)


class ParseIn(BaseModel):
    raw_ingredients: str = Field(min_length=1, max_length=20000)


class AnalysisIn(BaseModel):
    product_name: str = Field(default="", max_length=180)
    brand: str = Field(default="", max_length=180)
    source_url: str = Field(default="", max_length=2000)
    input_method: str = Field(default="manual", max_length=20)
    ingredient_text: str = Field(default="", max_length=20000)
    ingredients: list[str] | None = Field(default=None, max_length=400)
    preferences: PreferencesIn | None = None
    use_saved_preferences: bool = False
    save: bool = False
    use_model: bool = True


class ProductIn(BaseModel):
    product_name: str = Field(default="", max_length=180)
    brand: str = Field(default="", max_length=180)
    source_url: str = Field(default="", max_length=2000)
    input_method: str = Field(default="manual", max_length=20)
    ingredient_text: str = Field(default="", max_length=20000)
    ingredients: list[str] | None = Field(default=None, max_length=400)


class CompareIn(BaseModel):
    products: list[ProductIn] = Field(min_length=2, max_length=4)
    preferences: PreferencesIn | None = None


class FeedbackIn(BaseModel):
    category: str = Field(min_length=2, max_length=40)
    message: str = Field(min_length=4, max_length=4000)
    product_url: str = Field(default="", max_length=2000)
    ingredient_text: str = Field(default="", max_length=4000)
    context: str = Field(default="", max_length=2000)


class SourceOut(BaseModel):
    id: str
    title: str
    url: str = ""
    publisher: str
    kind: str
    accessed_on: str = ""


class UncertainOut(BaseModel):
    text: str
    reason: str


class NormalizedOut(BaseModel):
    original_name: str
    canonical_name: str | None = None
    ingredient_id: str | None = None
    synonyms: list[str] = []
    category: str | None = None
    function: str | None = None
    match_confidence: str
    match_source: str | None = None
    verification_status: str
    duplicate: bool = False
    may_contain: bool = False
    candidates: list[str] = []


class ParseOut(BaseModel):
    original_text: str
    normalized_ingredients: list[NormalizedOut]
    ingredient_count: int
    unknown_ingredients: list[str]
    uncertain_fragments: list[UncertainOut]
    parsing_warnings: list[str]


class ExtractOut(BaseModel):
    extraction_status: str
    product_name: str = ""
    brand: str = ""
    product_image: str = ""
    canonical_product_url: str = ""
    ingredients: list[str] = []
    ingredient_text: str = ""
    source_url: str = ""
    extraction_method: str = ""
    warnings: list[str] = []
    error_code: str | None = None
    message: str = ""


class IngredientExplanation(BaseModel):
    original_name: str
    canonical_name: str | None = None
    ingredient_id: str | None = None
    category: str | None = None
    function: str | None = None
    match_confidence: str
    match_source: str | None = None
    verification_status: str
    duplicate: bool = False
    may_contain: bool = False
    explanation: str
    evidence_level: str
    conditional_notes: list[str] = []
    source_ids: list[str] = []


class ConcernOut(BaseModel):
    ingredient: str
    ingredient_id: str
    nature: str
    concern_level: str
    evidence_level: str
    source_ids: list[str]
    limitations: str
    why_it_may_not_apply: str


class PreferenceMatchOut(BaseModel):
    ingredient: str
    preference: str
    note: str


class AnalysisOut(BaseModel):
    product_name: str = ""
    brand: str = ""
    source_url: str = ""
    input_method: str
    product_summary: str
    ingredient_count: int
    matched_count: int
    ingredients: list[IngredientExplanation]
    concerns: list[ConcernOut]
    preference_matches: list[PreferenceMatchOut]
    evidence_level: str
    sources: list[SourceOut]
    unknown_ingredients: list[str]
    limitations: list[str]
    next_steps: list[str]
    analysis_method: str
    warnings: list[str]
    saved_id: int | None = None


class CompareName(BaseModel):
    name: str
    verification_status: str
    function: str | None = None
    unverified: bool = False


class CompareUnique(BaseModel):
    product_name: str
    ingredients: list[CompareName]


class CompareFunctions(BaseModel):
    product_name: str
    functions: list[str]


class CompareConcerns(BaseModel):
    product_name: str
    concerns: list[ConcernOut]
    unknown_ingredients: list[str]


class ComparePreferences(BaseModel):
    product_name: str
    matches: list[PreferenceMatchOut]


class CompletenessOut(BaseModel):
    product_name: str
    ingredient_count: int
    matched_count: int
    unknown_count: int
    incomplete: bool


class CompareProductOut(BaseModel):
    product_name: str
    brand: str = ""
    source_url: str = ""
    ingredient_count: int
    evidence_level: str


class CompareOut(BaseModel):
    products: list[CompareProductOut]
    shared_ingredients: list[CompareName]
    unique_ingredients: list[CompareUnique]
    functions: list[CompareFunctions]
    preference_matches: list[ComparePreferences]
    concerns: list[CompareConcerns]
    source_completeness: list[CompletenessOut]
    limitations: list[str]
