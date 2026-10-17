import os
import sys
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from analysis.device import get_device

try:
	import cv2
except ImportError:
	cv2 = None


# Detection runs on a copy whose longest side is at most this many pixels.
# Haar face detection on full-resolution phone photos is slow and finds many
# false "faces" in fine texture such as brick or grass. YOLO resizes to 640
# internally, so giving it a smaller image only skips work.
DETECTION_MAX_SIDE = 1024

# MediaPipe rates each eye from 0 (open) to 1 (closed). Squinting into the sun
# while smiling scores up to about 0.5, so closed starts a bit above that.
EYE_CLOSED_THRESHOLD = 0.6

# Haar candidates are checked on a crop this many pixels wide, with half a
# face width of margin so the whole head is in view.
FACE_CHECK_WIDTH = 256

_person_model = None
_ultralytics_missing = False
_face_cascade = None
_face_landmarker = None
_mediapipe_missing = False


def downscale_for_detection(rgb_pixels, max_side=DETECTION_MAX_SIDE):
	"""Return a copy shrunk so its longest side is at most max_side pixels."""
	height, width = rgb_pixels.shape[:2]
	longest_side = max(height, width)
	if cv2 is None or longest_side <= max_side:
		return rgb_pixels
	scale = max_side / longest_side
	new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
	return cv2.resize(rgb_pixels, new_size, interpolation=cv2.INTER_AREA)


def _get_face_cascade():
	"""Load the Haar face model once per process and reuse it."""
	global _face_cascade

	if _face_cascade is not None:
		return _face_cascade
	if cv2 is None or not hasattr(cv2, "CascadeClassifier"):
		return None
	if not hasattr(cv2, "data") or not hasattr(cv2.data, "haarcascades"):
		return None

	cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
	try:
		cascade = cv2.CascadeClassifier(cascade_path)
		if cascade.empty():
			return None
	except Exception:
		return None

	_face_cascade = cascade
	return _face_cascade


def _haar_face_boxes(small_pixels):
	face_cascade = _get_face_cascade()
	if face_cascade is None:
		return []
	gray_pixels = cv2.cvtColor(small_pixels, cv2.COLOR_RGB2GRAY)
	faces = face_cascade.detectMultiScale(
		gray_pixels,
		scaleFactor=1.1,
		minNeighbors=5,
		minSize=(30, 30),
	)
	return [tuple(int(value) for value in box) for box in faces]


def _face_landmarker_path():
	return Path(__file__).resolve().parent.parent / "face_landmarker.task"


@contextmanager
def _quiet_native_stderr():
	"""Hide what native code writes to stderr.

	MediaPipe prints several lines of setup notes and warnings when a model
	loads, from C++ where Python's logging settings can't reach them.
	"""
	sys.stderr.flush()
	saved_stderr = os.dup(2)
	try:
		with open(os.devnull, "w") as devnull:
			os.dup2(devnull.fileno(), 2)
		yield
	finally:
		os.dup2(saved_stderr, 2)
		os.close(saved_stderr)


def _get_face_landmarker():
	"""Load the MediaPipe face landmarker on first use, or None if unavailable."""
	global _face_landmarker, _mediapipe_missing

	if _face_landmarker is None and not _mediapipe_missing:
		model_path = _face_landmarker_path()
		try:
			from mediapipe.tasks.python import BaseOptions, vision
		except ImportError:
			_mediapipe_missing = True
			return None
		if not model_path.is_file():
			_mediapipe_missing = True
			return None
		options = vision.FaceLandmarkerOptions(
			base_options=BaseOptions(model_asset_path=str(model_path)),
			output_face_blendshapes=True,
			num_faces=10,
		)
		with _quiet_native_stderr():
			_face_landmarker = vision.FaceLandmarker.create_from_options(options)
	return _face_landmarker


def _find_landmarked_faces(landmarker, rgb_pixels):
	"""Return (center_x, center_y, eye_closed_score) for each face found.

	The eye score is the more open of the two eyes, so a face only counts as
	eyes closed when both eyes are closed.
	"""
	import mediapipe as mp

	image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb_pixels))
	result = landmarker.detect(image)
	height, width = rgb_pixels.shape[:2]
	faces = []
	for landmarks, blendshapes in zip(result.face_landmarks, result.face_blendshapes):
		scores = {category.category_name: category.score for category in blendshapes}
		xs = [landmark.x for landmark in landmarks]
		ys = [landmark.y for landmark in landmarks]
		faces.append((
			(min(xs) + max(xs)) / 2 * width,
			(min(ys) + max(ys)) / 2 * height,
			min(scores["eyeBlinkLeft"], scores["eyeBlinkRight"]),
		))
	return faces


def _check_candidate(landmarker, rgb_pixels, box, scale):
	"""Confirm a Haar face on a full-resolution crop. Returns its eye score or None.

	Haar finds faces MediaPipe misses, such as a face turned to the side, but
	also "faces" in fences, trees and hair. MediaPipe rejects those.
	"""
	x, y, w, h = (round(value * scale) for value in box)
	margin = w // 2
	crop = rgb_pixels[max(0, y - margin):y + h + margin, max(0, x - margin):x + w + margin]
	crop_height = max(1, round(FACE_CHECK_WIDTH * crop.shape[0] / crop.shape[1]))
	crop = cv2.resize(crop, (FACE_CHECK_WIDTH, crop_height), interpolation=cv2.INTER_AREA)
	faces = _find_landmarked_faces(landmarker, crop)
	return faces[0][2] if faces else None


def analyze_faces(rgb_pixels):
	"""Count faces and check whether everyone has their eyes closed.

	Returns (face_count, eyes_closed). MediaPipe finds faces in the whole
	photo, and Haar candidates it missed are checked one by one on a crop.
	eyes_closed is True only when there is at least one face and every face
	has both eyes closed. Without MediaPipe, faces are counted with Haar alone
	and eyes are never judged closed.
	"""
	small_pixels = downscale_for_detection(rgb_pixels)
	haar_boxes = _haar_face_boxes(small_pixels)
	landmarker = _get_face_landmarker()
	if landmarker is None:
		return len(haar_boxes), False

	faces = _find_landmarked_faces(landmarker, small_pixels)
	eye_scores = [eye_score for _, _, eye_score in faces]
	scale = rgb_pixels.shape[1] / small_pixels.shape[1]
	for box in haar_boxes:
		x, y, w, h = box
		already_found = any(
			x <= center_x <= x + w and y <= center_y <= y + h
			for center_x, center_y, _ in faces
		)
		if already_found:
			continue
		eye_score = _check_candidate(landmarker, rgb_pixels, box, scale)
		if eye_score is not None:
			eye_scores.append(eye_score)

	eyes_closed = bool(eye_scores) and all(
		score >= EYE_CLOSED_THRESHOLD for score in eye_scores
	)
	return len(eye_scores), eyes_closed


def detect_faces(rgb_pixels):
	return analyze_faces(rgb_pixels)[0]


def _yolo_weights_path():
	"""Use the weights in the project root, so the working folder doesn't matter."""
	project_weights = Path(__file__).resolve().parent.parent / "yolo11n.pt"
	return project_weights if project_weights.is_file() else Path("yolo11n.pt")


def _get_person_model():
	"""Load YOLO on first use.

	ultralytics is imported here instead of at the top of the file so that
	worker processes import it only after worker_setup has given them their
	own settings folder.
	"""
	global _person_model, _ultralytics_missing

	if _person_model is None and not _ultralytics_missing:
		try:
			from ultralytics import YOLO
		except ImportError:
			_ultralytics_missing = True
			return None
		_person_model = YOLO(str(_yolo_weights_path()))
	return _person_model


def detect_people(rgb_pixels, confidence=0.25):
	try:
		person_model = _get_person_model()
		if person_model is None:
			return 0
		small_pixels = downscale_for_detection(rgb_pixels)
		device = get_device()
		try:
			# Half precision is about twice as fast on a GPU and doesn't
			# change which people are found. CPUs don't support it.
			result = person_model(
				small_pixels, device=device, half=device == "cuda", verbose=False
			)[0]
		except RuntimeError:
			if device == "cpu":
				raise
			# Out of GPU memory: count the people on the CPU rather than
			# report none.
			result = person_model(small_pixels, device="cpu", verbose=False)[0]
		return sum(
			1
			for class_id, score in zip(
				result.boxes.cls.tolist(), result.boxes.conf.tolist()
			)
			if int(class_id) == 0 and score >= confidence
		)
	except (OSError, RuntimeError, ValueError):
		return 0
