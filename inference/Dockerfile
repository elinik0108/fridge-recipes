FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt ${LAMBDA_TASK_ROOT}/

# Upgrade pip first — the bundled version is too old to see newer wheels.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY yolov8n.onnx ${LAMBDA_TASK_ROOT}/
COPY handler.py   ${LAMBDA_TASK_ROOT}/

CMD ["handler.handler"]