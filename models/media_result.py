from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MediaResult:
	path: Path
	width: int
	height: int
	brightness: float
	sharpness: float
	underexposed_fraction: float
	overexposed_fraction: float
	technical_quality_score: float
	interest_score: float
	uniqueness_score: float
	metadata_context_score: float
	final_score: float
	classification: str
	perceptual_hash: str = ""
	reasons: list[str] = field(default_factory=list)
