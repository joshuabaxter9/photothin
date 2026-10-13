from pathlib import Path

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

_person_model = None
_ultralytics_missing = False
_face_cascade = None


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


def detect_faces(rgb_pixels):
	face_cascade = _get_face_cascade()
	if face_cascade is None:
		return 0

	small_pixels = downscale_for_detection(rgb_pixels)
	gray_pixels = cv2.cvtColor(small_pixels, cv2.COLOR_RGB2GRAY)
	faces = face_cascade.detectMultiScale(
		gray_pixels,
		scaleFactor=1.1,
		minNeighbors=5,
		minSize=(30, 30),
	)
	return len(faces)


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
