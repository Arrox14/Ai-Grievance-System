import math
import os
import tempfile
import threading
import time
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any
import uuid

import cv2
import numpy as np
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from ultralytics import YOLO

from app.services.files import MAX_UPLOAD_BYTES, UPLOAD_TYPES


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
MAX_IMAGE_PIXELS = 40_000_000
IMAGE_FORMATS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".bmp": "BMP",
    ".gif": "GIF",
}
LIVE_FRAME_MAX_BYTES = 512 * 1024
LIVE_FRAME_MAX_WIDTH = 640
LIVE_FRAME_MAX_HEIGHT = 480
LIVE_INFERENCE_INTERVAL_SECONDS = 1.0
LIVE_MAX_CONCURRENT_INFERENCES = 2
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi"}
MAX_VIDEO_DURATION_SECONDS = 120
MAX_VIDEO_FRAMES = 18_000
MAX_VIDEO_SAMPLED_FRAMES = 600
VIDEO_SIGNATURES = {
    ".mp4": UPLOAD_TYPES[".mp4"][1],
    ".mov": UPLOAD_TYPES[".mov"][1],
    ".avi": UPLOAD_TYPES[".avi"][1],
}


def load_yolo_model(weights_path: str | os.PathLike) -> YOLO:
    weights = Path(weights_path)
    if not weights.is_file():
        raise FileNotFoundError(f"YOLO model weights not found: {weights}")
    return YOLO(str(weights))


def read_image(image_path: str | os.PathLike) -> np.ndarray:
    path = Path(image_path)
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only image files can be analyzed")
    try:
        file_size = path.stat().st_size
    except OSError as error:
        raise HTTPException(status_code=400, detail="Could not read image file") from error
    if file_size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 10 MB or smaller")

    try:
        with path.open("rb") as image_file:
            contents = image_file.read(MAX_UPLOAD_BYTES + 1)
    except OSError as error:
        raise HTTPException(status_code=400, detail="Could not read image file") from error
    return decode_image_bytes(contents, path.suffix.lower(), MAX_UPLOAD_BYTES)


def decode_image_bytes(
    contents: bytes,
    extension: str,
    max_bytes: int,
    max_width: int | None = None,
    max_height: int | None = None,
) -> np.ndarray:
    extension = extension.lower()
    if extension not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported image format")
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail="Image frame is too large")
    if not contents:
        raise HTTPException(status_code=400, detail="Image file cannot be empty")
    _, signature_check = UPLOAD_TYPES[extension]
    if not signature_check(contents):
        raise HTTPException(
            status_code=400,
            detail="Image content does not match its extension",
        )
    try:
        with Image.open(BytesIO(contents)) as source_image:
            if source_image.format != IMAGE_FORMATS[extension]:
                raise HTTPException(
                    status_code=400,
                    detail="Image content does not match its extension",
                )
            width, height = source_image.size
            if (
                width <= 0
                or height <= 0
                or width * height > MAX_IMAGE_PIXELS
                or (max_width is not None and width > max_width)
                or (max_height is not None and height > max_height)
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Image dimensions are not supported",
                )
            source_image.verify()
    except HTTPException:
        raise
    except (
        OSError,
        ValueError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
    ) as error:
        raise HTTPException(status_code=400, detail="Could not decode image file") from error
    try:
        image = cv2.imdecode(np.frombuffer(contents, dtype=np.uint8), cv2.IMREAD_COLOR)
    except cv2.error as error:
        raise HTTPException(status_code=400, detail="Could not decode image file") from error
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        raise HTTPException(status_code=400, detail="Could not decode image file")
    return image


class LiveInferenceLimiter:
    def __init__(
        self,
        minimum_interval: float = LIVE_INFERENCE_INTERVAL_SECONDS,
        max_concurrent: int = LIVE_MAX_CONCURRENT_INFERENCES,
    ):
        self.minimum_interval = minimum_interval
        self.max_concurrent = max_concurrent
        self._lock = threading.Lock()
        self._last_request: dict[int, float] = {}
        self._active = 0

    def acquire(self, user_id: int) -> bool:
        now = time.monotonic()
        with self._lock:
            previous = self._last_request.get(user_id)
            if previous is not None and now - previous < self.minimum_interval:
                return False
            if self._active >= self.max_concurrent:
                return False
            self._last_request[user_id] = now
            self._active += 1
            stale_before = now - 300
            self._last_request = {
                key: timestamp
                for key, timestamp in self._last_request.items()
                if timestamp >= stale_before
            }
            return True

    def release(self) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)


live_inference_limiter = LiveInferenceLimiter()


def _to_list(values: Any) -> list:
    if hasattr(values, "cpu"):
        values = values.cpu()
    if hasattr(values, "tolist"):
        values = values.tolist()
    return values


def detect_image(
    model: Any,
    image: np.ndarray,
    confidence: float = 0.5,
    iou: float = 0.45,
) -> tuple[list[dict], np.ndarray]:
    results = model.predict(
        source=image,
        conf=confidence,
        iou=iou,
        verbose=False,
    )
    if not results:
        return [], image.copy()

    result = results[0]
    boxes = result.boxes
    detections = []
    if boxes is not None:
        coordinates = _to_list(boxes.xyxy)
        class_ids = _to_list(boxes.cls)
        scores = _to_list(boxes.conf)
        names = result.names
        height, width = image.shape[:2]
        for coordinates_row, class_value, score_value in zip(
            coordinates, class_ids, scores
        ):
            class_id = int(class_value)
            raw_coordinates = [float(value) for value in coordinates_row]
            score = float(score_value)
            if (
                not all(math.isfinite(value) for value in raw_coordinates)
                or not math.isfinite(score)
            ):
                continue
            if isinstance(names, dict):
                class_name = names.get(class_id, str(class_id))
            else:
                class_name = names[class_id]
            x1, y1, x2, y2 = (
                min(max(float(value), 0.0), float(limit))
                for value, limit in zip(raw_coordinates, (width, height, width, height))
            )
            detections.append(
                {
                    "class_id": class_id,
                    "class_name": str(class_name),
                    "confidence": score,
                    "bounding_box": {
                        "x_min": x1,
                        "y_min": y1,
                        "x_max": x2,
                        "y_max": y2,
                    },
                }
            )
    annotated_image = result.plot() if hasattr(result, "plot") else image.copy()
    return detections, annotated_image


def encode_annotated_image(image: np.ndarray) -> bytes:
    success, encoded = cv2.imencode(".jpg", image)
    if not success:
        raise RuntimeError("Could not encode annotated image")
    return encoded.tobytes()


def analyze_video(
    video_path: str | os.PathLike,
    model: Any,
    *,
    confidence: float = 0.5,
    iou: float = 0.45,
    frame_interval: int = 30,
    include_frame_detections: bool = False,
    annotated_output_path: str | os.PathLike | None = None,
) -> dict:
    path = Path(video_path)
    extension = path.suffix.lower()
    if extension not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported video format")
    try:
        file_size = path.stat().st_size
        with path.open("rb") as video_file:
            signature = video_file.read(32)
    except OSError as error:
        raise HTTPException(status_code=400, detail="Could not read video file") from error
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Video file cannot be empty")
    if file_size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Video must be 10 MB or smaller")
    if not VIDEO_SIGNATURES[extension](signature):
        raise HTTPException(
            status_code=400,
            detail="Video content does not match its extension",
        )
    if frame_interval < 1 or frame_interval > MAX_VIDEO_FRAMES:
        raise HTTPException(status_code=422, detail="Invalid frame sampling interval")

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise HTTPException(
            status_code=400,
            detail="Video is corrupt or uses an unsupported codec",
        )

    writer = None
    temporary_output = None
    output_path = Path(annotated_output_path) if annotated_output_path else None
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        declared_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if (
            not math.isfinite(fps)
            or fps <= 0
            or declared_frames <= 0
            or width <= 0
            or height <= 0
            or width * height > MAX_IMAGE_PIXELS
        ):
            raise HTTPException(
                status_code=400,
                detail="Video metadata is invalid or unsupported",
            )
        duration = declared_frames / fps
        if duration > MAX_VIDEO_DURATION_SECONDS:
            raise HTTPException(
                status_code=413,
                detail=f"Video duration must be {MAX_VIDEO_DURATION_SECONDS} seconds or less",
            )
        estimated_samples = (declared_frames + frame_interval - 1) // frame_interval
        if declared_frames > MAX_VIDEO_FRAMES or estimated_samples > MAX_VIDEO_SAMPLED_FRAMES:
            raise HTTPException(
                status_code=413,
                detail="Video exceeds the supported frame-processing limit",
            )

        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_output = tempfile.mkstemp(
                prefix=".video-analysis-",
                suffix=f".tmp{output_path.suffix}",
                dir=str(output_path.parent),
            )
            os.close(descriptor)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(
                temporary_output,
                fourcc,
                fps,
                (width, height),
            )
            if not writer.isOpened():
                raise HTTPException(
                    status_code=415,
                    detail="The video codec is not supported for annotated output",
                )

        aggregate_counts: Counter = Counter()
        confidence_scores = []
        frame_detections = []
        sampled_frames = 0
        decoded_frames = 0
        last_annotated_frame = None
        while True:
            success, frame = capture.read()
            if not success:
                break
            if decoded_frames / fps >= MAX_VIDEO_DURATION_SECONDS:
                raise HTTPException(
                    status_code=413,
                    detail=f"Video duration must be {MAX_VIDEO_DURATION_SECONDS} seconds or less",
                )
            if frame is None or frame.shape[:2] != (height, width):
                raise HTTPException(
                    status_code=400,
                    detail="Video contains an invalid or inconsistent frame",
                )
            if decoded_frames >= MAX_VIDEO_FRAMES:
                raise HTTPException(
                    status_code=413,
                    detail="Video exceeds the supported frame-processing limit",
                )

            if decoded_frames % frame_interval == 0:
                detections, annotated_frame = detect_image(
                    model,
                    frame,
                    confidence=confidence,
                    iou=iou,
                )
                sampled_frames += 1
                for detection in detections:
                    class_key = (
                        detection["class_id"],
                        detection["class_name"],
                    )
                    aggregate_counts[class_key] += 1
                    confidence_scores.append(detection["confidence"])
                if include_frame_detections:
                    frame_detections.append(
                        {
                            "frame_index": decoded_frames,
                            "timestamp_seconds": round(decoded_frames / fps, 3),
                            "detections": detections,
                        }
                    )
                last_annotated_frame = annotated_frame

            if writer is not None and last_annotated_frame is not None:
                writer.write(last_annotated_frame)
            decoded_frames += 1

        if decoded_frames == 0:
            raise HTTPException(status_code=400, detail="Video contains no decodable frames")
        missed_frames = declared_frames - decoded_frames
        if missed_frames > max(2, math.ceil(declared_frames * 0.05)):
            raise HTTPException(
                status_code=400,
                detail="Video could not be decoded completely",
            )
        if sampled_frames == 0:
            raise HTTPException(status_code=400, detail="No video frames were sampled")
        if writer is not None:
            writer.release()
            writer = None
            if not os.path.isfile(temporary_output) or os.path.getsize(temporary_output) == 0:
                raise HTTPException(
                    status_code=415,
                    detail="Could not encode the annotated video",
                )
            os.replace(temporary_output, output_path)
            temporary_output = None

        return {
            "video_dimensions": {"width": width, "height": height},
            "duration_seconds": round(decoded_frames / fps, 3),
            "frames_processed": decoded_frames,
            "frames_sampled": sampled_frames,
            "frame_interval": frame_interval,
            "detection_counts": [
                {
                    "class_id": class_id,
                    "class_name": class_name,
                    "count": count,
                }
                for (class_id, class_name), count in sorted(aggregate_counts.items())
            ],
            "total_detections": sum(aggregate_counts.values()),
            "confidence_scores": confidence_scores,
            "frame_detections": frame_detections if include_frame_detections else None,
            "annotated_video_path": str(output_path) if output_path is not None else None,
        }
    finally:
        capture.release()
        if writer is not None:
            writer.release()
        if temporary_output and os.path.exists(temporary_output):
            os.remove(temporary_output)
