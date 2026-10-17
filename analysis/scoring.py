from models.media_result import MediaResult

# Photos scoring at or above KEEP_SCORE are kept automatically, and photos
# below DISCARD_SCORE are discarded automatically. Everything in between is
# reviewed.
KEEP_SCORE = 70
DISCARD_SCORE = 50

# A face makes a photo much more likely to be worth keeping, unless everyone
# in it has their eyes closed.
FACE_BONUS = 20.0
EYES_CLOSED_PENALTY = 20.0


def score_image(
	*,
	path,
	width,
	height,
	brightness,
	contrast=0.0,
	significance_score=50.0,
	sharpness,
	underexposed_fraction,
	overexposed_fraction,
	uniqueness_score=50.0,
	perceptual_hash="",
	face_count=0,
	person_count=0,
	eyes_closed=False,
	extra_reasons=None,
):
	reasons = []
	resolution_score = min(100.0, (width * height) / 2_000_000 * 100)
	sharpness_score = min(100.0, sharpness / 500.0 * 100)
	contrast_score = max(0.0, 100.0 - abs(contrast - 48.0) * 2.5)
	exposure_score = max(
		0.0,
		100.0
		- underexposed_fraction * 200.0
		- overexposed_fraction * 200.0,
	)
	technical_quality_score = round(
		resolution_score * 0.20
		+ sharpness_score * 0.40
		+ contrast_score * 0.20
		+ exposure_score * 0.20,
		2,
	)

	if sharpness < 40:
		reasons.append("blurry")
	if contrast < 18:
		reasons.append("low_contrast")
		if sharpness < 80:
			reasons.append("accidental_shot")
	if brightness < 45 or underexposed_fraction > 0.35:
		reasons.append("too_dark")
	if brightness > 215 or overexposed_fraction > 0.35:
		reasons.append("overexposed")
	if min(width, height) < 500:
		reasons.append("low_resolution")
	if face_count:
		reasons.append("contains_face")
	if eyes_closed:
		reasons.append("eyes_closed")
	if person_count or face_count:
		reasons.append("contains_person")
	if significance_score >= 60:
		reasons.append("scenic")
	if significance_score <= 35:
		reasons.append("low_significance")
	if extra_reasons:
		reasons.extend(reason for reason in extra_reasons if reason not in reasons)

	interest_score = min(100.0, 50.0 + face_count * 5.0 + person_count * 5.0)
	metadata_context_score = 50.0
	final_score = (
		technical_quality_score * 0.55
		+ significance_score * 0.20
		+ interest_score * 0.15
		+ uniqueness_score * 0.07
		+ metadata_context_score * 0.03
	)
	if eyes_closed:
		final_score -= EYES_CLOSED_PENALTY
	elif face_count:
		final_score += FACE_BONUS
	final_score = round(max(0.0, min(100.0, final_score)), 2)

	if final_score >= KEEP_SCORE:
		classification = "KEEP"
	elif final_score < DISCARD_SCORE:
		classification = "DISCARD_CANDIDATE"
	else:
		classification = "REVIEW"

	return MediaResult(
		path=path,
		width=width,
		height=height,
		brightness=round(brightness, 2),
		contrast=round(contrast, 2),
		significance_score=round(significance_score, 2),
		sharpness=round(sharpness, 2),
		underexposed_fraction=round(underexposed_fraction, 4),
		overexposed_fraction=round(overexposed_fraction, 4),
		technical_quality_score=technical_quality_score,
		interest_score=interest_score,
		uniqueness_score=uniqueness_score,
		metadata_context_score=metadata_context_score,
		final_score=final_score,
		classification=classification,
		perceptual_hash=perceptual_hash,
		face_count=face_count,
		person_count=person_count,
		eyes_closed=eyes_closed,
		reasons=reasons,
	)
