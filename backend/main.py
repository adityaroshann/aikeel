"""AIkeel API. Local:  uvicorn main:app --reload   (from backend/)"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yaml
from pydantic import BaseModel, Field, ValidationError

from server import copilot as cp
from server.core import check, onboard, parse_profile
from server.workspace import Source, SourceError, customer_dir, engine_fingerprint, list_workspaces

app = FastAPI(title="AIkeel API", version="0.2.0")

origins = [o.strip() for o in os.environ.get("AIKEEL_WEB_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_origin_regex=os.environ.get("AIKEEL_WEB_ORIGIN_REGEX"),
                   allow_methods=["GET", "POST"], allow_headers=["content-type"])


class OnboardReq(Source):
    use_claude: bool = False


class CheckReq(Source):
    profile_yaml: str


class ChatMsg(BaseModel):
    role: str
    content: str


class CopilotReq(Source):
    profile_yaml: str
    messages: list[ChatMsg] = Field(default_factory=list)


# best-effort per-instance limiter for the public copilot (serverless: not global, good enough)
_hits: dict[str, deque] = defaultdict(deque)
RATE_N, RATE_WINDOW = int(os.environ.get("AIKEEL_RATE_N", "30")), 600


def _limited(ip: str) -> bool:
    now, q = time.time(), _hits[ip]
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_N:
        return True
    q.append(now)
    return False


def _profile(text: str):
    try:
        return parse_profile(text)
    except (ValidationError, ValueError, AttributeError, TypeError, yaml.YAMLError) as e:
        raise HTTPException(422, f"profile is not valid: {e}") from None


@app.get("/api/health")
def health():
    return {"ok": True, "copilot": cp.available(), "model": cp.MODEL, "engine": engine_fingerprint()}


@app.get("/api/workspaces")
def workspaces():
    return {"workspaces": list_workspaces(), "engine": engine_fingerprint()}


@app.post("/api/onboard")
def onboard_ep(req: OnboardReq):
    try:
        with customer_dir(req) as (cdir, cust):
            return onboard(cdir, cust, use_claude=req.use_claude)
    except SourceError as e:
        raise HTTPException(400, str(e)) from None
    except ValueError as e:
        raise HTTPException(422, f"could not read these files: {e}") from None


@app.post("/api/check")
def check_ep(req: CheckReq):
    profile = _profile(req.profile_yaml)
    try:
        with customer_dir(req) as (cdir, _):
            return check(cdir, profile)
    except SourceError as e:
        raise HTTPException(400, str(e)) from None
    except (FileNotFoundError, KeyError, ValueError) as e:
        raise HTTPException(422, f"profile does not match these files: {e}") from None


@app.post("/api/copilot")
def copilot_ep(req: CopilotReq, request: Request):
    profile = _profile(req.profile_yaml)
    if not cp.available():
        raise HTTPException(503, "copilot is offline (no API key configured)")
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0]
    if _limited(ip):
        raise HTTPException(429, "too many questions; give it a few minutes")
    try:
        ctx = customer_dir(req)
        cdir, cust = ctx.__enter__()
    except SourceError as e:
        raise HTTPException(400, str(e)) from None

    def events():
        try:
            bot = cp.Copilot(cdir, cust, profile)
            for ev in bot.stream([m.model_dump() for m in req.messages]):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:  # never leave the client hanging
            yield f"data: {json.dumps({'type': 'error', 'message': f'copilot failed: {type(e).__name__}'})}\n\n"
        finally:
            ctx.__exit__(None, None, None)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
