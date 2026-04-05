from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .ai_config import fetch_models, list_profiles, save_profile, test_profile_connection
from .compiler import compile_prompt, finalize_prompt
from .control_plane import (
    doctor_snapshot,
    finalize_run,
    launch_run,
    list_runs,
    reconcile_run,
    resume_run,
    run_detail,
    set_workspace_root,
    stream_snapshots,
    verify_run,
    workspace_snapshot,
    workspace_root,
    write_operator_request,
)
from .prompt_packs import list_pack_versions, load_overrides, save_overrides
from .shared_policy import local_mission_draft

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="LongRun Web Beta", version="0.10.0-beta.1")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


class AIProfileInput(BaseModel):
    name: str = "default"
    baseUrl: str = "https://api.zscc.in/v1"
    apiKey: str = ""
    model: str = ""
    provider: str = "openai-compatible"
    setDefault: bool = False


class DraftRequest(BaseModel):
    text: str
    previousDraft: Optional[Dict[str, Any]] = None
    interaction: str = "initial_compile"
    aiProfile: Optional[str] = None
    packVersion: str = "v1"


class FinalizePromptRequest(BaseModel):
    draft: Dict[str, Any]
    packVersion: str = "v1"


class LaunchRunRequest(BaseModel):
    prompt: str
    model: Optional[str] = None


class ResumeActionRequest(BaseModel):
    model: Optional[str] = None


class InboxRequest(BaseModel):
    type: str = "append_task"
    title: str = ""
    rawText: str
    normalizedText: str = ""
    priority: str = "normal"
    linkedDeliverables: List[str] = Field(default_factory=list)
    linkedArtifacts: List[str] = Field(default_factory=list)
    linkedWorkstream: Optional[str] = None


class FinalizeActionRequest(BaseModel):
    status: str
    headline: str


class PromptOverrideRequest(BaseModel):
    payload: Dict[str, Any]


class WorkspaceRequest(BaseModel):
    workspace: str


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "workspace": str(workspace_root()),
            "pack_versions": list_pack_versions(),
        },
    )


@app.get("/api/doctor")
def api_doctor():
    return JSONResponse(doctor_snapshot())


@app.get("/api/workspace")
def api_workspace():
    return JSONResponse(workspace_snapshot())


@app.post("/api/workspace")
def api_workspace_set(payload: WorkspaceRequest):
    try:
        return JSONResponse({"ok": True, **set_workspace_root(payload.workspace)})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/ai/profiles")
def api_ai_profiles():
    return JSONResponse(list_profiles(masked=True))


@app.post("/api/ai/profiles")
def api_ai_profiles_save(payload: AIProfileInput):
    saved = save_profile(payload.model_dump())
    return JSONResponse({"ok": True, "profile": saved, "profiles": list_profiles(masked=True)})


@app.post("/api/ai/test")
def api_ai_test(payload: AIProfileInput):
    return JSONResponse(test_profile_connection(payload.model_dump()))


@app.get("/api/ai/models")
def api_ai_models(profile: Optional[str] = None):
    return JSONResponse(fetch_models(profile))


@app.get("/api/prompt-packs")
def api_prompt_packs():
    return JSONResponse({"versions": list_pack_versions(), "overrides": load_overrides()})


@app.post("/api/prompt-packs/overrides")
def api_prompt_packs_override(payload: PromptOverrideRequest):
    save_overrides(payload.payload)
    return JSONResponse({"ok": True, "overrides": load_overrides()})


@app.post("/api/compiler/draft")
def api_compile_draft(payload: DraftRequest):
    draft = local_mission_draft(payload.text, payload.previousDraft, interaction=payload.interaction)
    return JSONResponse({"missionDraft": draft, "source": "local"})


@app.post("/api/compiler/refine")
def api_compile_refine(payload: DraftRequest):
    result = compile_prompt(
        payload.text,
        previous_draft=payload.previousDraft,
        interaction=payload.interaction,
        profile_name=payload.aiProfile,
        pack_version=payload.packVersion,
    )
    return JSONResponse(result)


@app.post("/api/compiler/finalize-prompt")
def api_finalize_prompt(payload: FinalizePromptRequest):
    return JSONResponse(finalize_prompt(payload.draft, pack_version=payload.packVersion))


@app.get("/api/runs")
def api_runs():
    return JSONResponse({"runs": list_runs()})


@app.post("/api/runs")
def api_runs_launch(payload: LaunchRunRequest):
    return JSONResponse(launch_run(payload.prompt, model=payload.model))


@app.get("/api/runs/{run_id}")
def api_run_detail(run_id: str):
    try:
        return JSONResponse(run_detail(run_id))
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/runs/{run_id}/stream")
def api_run_stream(run_id: str):
    return StreamingResponse(stream_snapshots(run_id), media_type="text/event-stream")


@app.get("/api/runs/{run_id}/operator-tasks")
def api_operator_tasks(run_id: str):
    try:
        detail = run_detail(run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return JSONResponse({"runId": run_id, "operatorTasks": detail.get("operatorTasks", [])})


@app.post("/api/runs/{run_id}/inbox")
def api_run_inbox(run_id: str, payload: InboxRequest):
    return JSONResponse(write_operator_request(run_id, payload.model_dump()))


@app.post("/api/runs/{run_id}/actions/reconcile")
def api_action_reconcile(run_id: str):
    return JSONResponse(reconcile_run(run_id))


@app.post("/api/runs/{run_id}/actions/verify")
def api_action_verify(run_id: str):
    return JSONResponse(verify_run(run_id))


@app.post("/api/runs/{run_id}/actions/resume")
def api_action_resume(run_id: str, payload: Optional[ResumeActionRequest] = None):
    return JSONResponse(resume_run(run_id, model=payload.model if payload else None))


@app.post("/api/runs/{run_id}/actions/finalize")
def api_action_finalize(run_id: str, payload: FinalizeActionRequest):
    if payload.status not in {"complete", "blocked"}:
        raise HTTPException(status_code=400, detail="invalid finalize status")
    return JSONResponse(finalize_run(run_id, status_name=payload.status, headline=payload.headline))
