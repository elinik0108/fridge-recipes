""" sanity check """

import os
os.environ.setdefault("MODEL_PATH", "yolov8n.onnx")
import sys
from handler import infer

if len(sys.argv) < 2:
    print("Usage: python local_test.py <path-to-image>")
    sys.exit(1)

with open(sys.argv[1], "rb") as f:
    result = infer(f.read())

print(f"Detections: {len(result['detections'])}")
for d in result["detections"]:
    print(f"  {d['label']:20s} {d['confidence']:.3f}")
print(f"Summary: {result['summary']}")