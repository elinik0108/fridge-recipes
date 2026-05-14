
import io
import json
import os
import urllib.parse
from typing import Any

import boto3
import numpy as np
import onnxruntime as ort
from PIL import Image

# ----- Configuration -----
MODEL_PATH = os.getenv("MODEL_PATH", "/var/task/yolov8n.onnx")
CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", "0.25"))
IOU_THRESHOLD = float(os.getenv("IOU_THRESHOLD", "0.45"))
INPUT_SIZE = 640
DYNAMO_TABLE = os.getenv("DYNAMO_TABLE", "fridge-scans")
USER_ID = "local"

# COCO class names — what YOLOv8n is trained on.
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]

session = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])
input_name = session.get_inputs()[0].name

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(DYNAMO_TABLE)


def preprocess(image: Image.Image) -> tuple[np.ndarray, float, tuple[int, int]]:
    orig_w, orig_h = image.size
    scale = min(INPUT_SIZE / orig_w, INPUT_SIZE / orig_h)
    new_w, new_h = int(orig_w * scale), int(orig_h * scale)

    resized = image.resize((new_w, new_h), Image.BILINEAR)
    padded = Image.new("RGB", (INPUT_SIZE, INPUT_SIZE), (114, 114, 114))
    padded.paste(resized, ((INPUT_SIZE - new_w) // 2, (INPUT_SIZE - new_h) // 2))

    arr = np.array(padded, dtype=np.float32) / 255.0  # HWC, [0, 1]
    arr = arr.transpose(2, 0, 1)[None]                 # NCHW
    return arr, scale, (orig_w, orig_h)


def nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list[int]:
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[1:][iou < iou_threshold]
    return keep


def postprocess(output: np.ndarray) -> list[dict]:
    pred = output[0].transpose()
    boxes_xywh = pred[:, :4]
    class_scores = pred[:, 4:]

    max_scores = class_scores.max(axis=1)
    class_ids = class_scores.argmax(axis=1)

    mask = max_scores >= CONF_THRESHOLD
    if not mask.any():
        return []

    boxes_xywh = boxes_xywh[mask]
    max_scores = max_scores[mask]
    class_ids = class_ids[mask]

    cx, cy, w, h = boxes_xywh.T
    boxes_xyxy = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)

    keep = nms(boxes_xyxy, max_scores, IOU_THRESHOLD)

    return [
        {"label": COCO_CLASSES[int(class_ids[i])], "confidence": round(float(max_scores[i]), 3)}
        for i in keep
    ]


def infer(image_bytes: bytes) -> dict:
    """Pure inference — no AWS, just bytes in, structured detections out."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor, _scale, _orig = preprocess(image)
    output = session.run(None, {input_name: tensor})[0]
    detections = postprocess(output)

    summary: dict[str, int] = {}
    for d in detections:
        summary[d["label"]] = summary.get(d["label"], 0) + 1

    return {"detections": detections, "summary": summary}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point — expects an S3 ObjectCreated event."""
    print(f"Event: {json.dumps(event)}")

    try:
        record = event["Records"][0]
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
    except (KeyError, IndexError) as e:
        return {"statusCode": 400, "error": f"Not an S3 event: {e}"}

    obj = s3.get_object(Bucket=bucket, Key=key)
    image_bytes = obj["Body"].read()

    result = infer(image_bytes)

    # Convention: "uploads/<scan_id>.jpg" or whatever
    scan_id = key.rsplit("/", 1)[-1].rsplit(".", 1)[0]

    table.put_item(Item={
        "pk": f"USER#{USER_ID}",
        "sk": f"SCAN#{scan_id}",
        "summary": result["summary"],
    })

    print(f"Saved scan {scan_id} with {sum(result['summary'].values())} detections")
    return {"statusCode": 200, "scan_id": scan_id, **result}