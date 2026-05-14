from datetime import datetime, timezone
from typing import List, Optional
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from pydantic import BaseModel
import boto3
from boto3.dynamodb.conditions import Key

from google import genai
from google.genai import types

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
UPLOAD_BUCKET = os.getenv("UPLOAD_BUCKET", f"fridge-uploads-{os.getenv('AWS_ACCOUNT', '')}")
DYNAMO_TABLE = os.getenv("DYNAMO_TABLE", "fridge-scans")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
PRESIGN_EXPIRY = 300
USER_ID = "local"

app = FastAPI(title="Fridge Recipe API", version="0.3.0")

s3 = boto3.client("s3", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = dynamodb.Table(DYNAMO_TABLE) # type: ignore
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


class Recipe(BaseModel):
    title: str
    ingredients: List[str]
    steps: List[str]

class RecipeRequest(BaseModel):
    ingredients: List[str]
    scan_id: Optional[str] = None
    preferences: Optional[List[str]] = None

class RecipesResponse(BaseModel):
    recipes: List[Recipe]

class PresignResponse(BaseModel):
    scan_id: str
    upload_url: str
    method: str = "PUT"
    expires_in: int

class ScanStatus(BaseModel):
    scan_id: str
    status: str  # "pending" or "ready"
    summary: Optional[dict] = None
    recipes: Optional[List[Recipe]] = None

class ScanHistoryItem(BaseModel):
    scan_id: str
    summary: dict
    recipes: Optional[List[Recipe]] = None

class HistoryResponse(BaseModel):
    scans: List[ScanHistoryItem]


@app.get("/health")
def health():
    return {"status": "ok", "bucket": UPLOAD_BUCKET, "table": DYNAMO_TABLE, "region": AWS_REGION}


@app.post("/uploads/presign", response_model=PresignResponse)
def presign_upload():
    """Mint a one-time URL the client can PUT an image to directly."""
    scan_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    key = f"uploads/{scan_id}.jpg"

    url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": UPLOAD_BUCKET, "Key": key, "ContentType": "image/jpeg"},
        ExpiresIn=PRESIGN_EXPIRY,
    )
    return PresignResponse(scan_id=scan_id, upload_url=url, expires_in=PRESIGN_EXPIRY)


@app.get("/scans/{scan_id}", response_model=ScanStatus)
def get_scan(scan_id: str):
    """Poll endpoint. Returns 'pending' until the Lambda has written results."""
    resp = table.get_item(Key={"pk": f"USER#{USER_ID}", "sk": f"SCAN#{scan_id}"})
    item = resp.get("Item")
    if item is None:
        return ScanStatus(scan_id=scan_id, status="pending")

    summary = item.get("summary")
    summary_clean = {k: int(v) for k, v in summary.items()} if summary else None

    recipes_raw = item.get("recipes")
    recipes = [Recipe(**r) for r in recipes_raw] if recipes_raw else None

    return ScanStatus(
        scan_id=scan_id,
        status="ready" if summary_clean else "pending",
        summary=summary_clean,
        recipes=recipes,
    )


@app.post("/recipes", response_model=RecipesResponse)
def recipes(req: RecipeRequest):
    if not req.ingredients:
        raise HTTPException(status_code=400, detail="No ingredients provided")
    if gemini_client is None:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    prompt_parts = [
        f"I have these ingredients available: {', '.join(req.ingredients)}.",
        "Suggest 2-3 simple recipes. Assume basic pantry staples are on hand. "
        "Keep steps concrete and short.",
    ]
    if req.preferences:
        prompt_parts.append(
            f"Preferences to honor: {', '.join(req.preferences)}."
        )
    prompt = "\n\n".join(prompt_parts)

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[Recipe],
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}")

    parsed: list[Recipe] | None = response.parsed # type: ignore
    if not parsed:
        raise HTTPException(status_code=502, detail="LLM returned no parseable result")

    if req.scan_id:
        table.update_item(
            Key={"pk": f"USER#{USER_ID}", "sk": f"SCAN#{req.scan_id}"},
            UpdateExpression="SET recipes = :r",
            ExpressionAttributeValues={":r": [r.model_dump() for r in parsed]},
        )

    return RecipesResponse(recipes=parsed)


@app.get("/history", response_model=HistoryResponse)
def history(limit: int = 20):
    resp = table.query(
        KeyConditionExpression=
            Key("pk").eq(f"USER#{USER_ID}") & Key("sk").begins_with("SCAN#"),
        ScanIndexForward=False,
        Limit=limit,
    )
    scans = []
    for item in resp.get("Items", []):
        scan_id = item["sk"].replace("SCAN#", "", 1)
        summary = item.get("summary") or {}
        summary_clean = {k: int(v) for k, v in summary.items()}
        recipes_raw = item.get("recipes")
        scans.append(ScanHistoryItem(
            scan_id=scan_id,
            summary=summary_clean,
            recipes=[Recipe(**r) for r in recipes_raw] if recipes_raw else None,
        ))
    return HistoryResponse(scans=scans)