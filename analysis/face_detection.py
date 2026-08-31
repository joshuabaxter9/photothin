try:
	import cv2
except ImportError:
	cv2 = None

try:
	from ultralytics import YOLO
except ImportError:
	YOLO = None


_person_model = None


def detect_faces(rgb_pixels):
	if cv2 is None or not hasattr(cv2, "CascadeClassifier"):
		return 0
	if not hasattr(cv2, "data") or not hasattr(cv2.data, "haarcascades"):
		return 0

	gray_pixels = cv2.cvtColor(rgb_pixels, cv2.COLOR_RGB2GRAY)
	cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
	try:
		face_cascade = cv2.CascadeClassifier(cascade_path)
		test = face_cascade.empty()
		if test:
			return 0
	except Exception:
		return 0

	faces = face_cascade.detectMultiScale(
		gray_pixels,
		scaleFactor=1.1,
		minNeighbors=5,
		minSize=(30, 30),
	)
	return len(faces)


def detect_people(rgb_pixels, confidence=0.25):
	global _person_model

	if YOLO is None:
		return 0

	try:
		if _person_model is None:
			_person_model = YOLO("yolo11n.pt")
		result = _person_model(rgb_pixels, verbose=False)[0]
		return sum(
			1
			for class_id, score in zip(
				result.boxes.cls.tolist(), result.boxes.conf.tolist()
			)
			if int(class_id) == 0 and score >= confidence
		)
	except (OSError, RuntimeError, ValueError):
		return 0