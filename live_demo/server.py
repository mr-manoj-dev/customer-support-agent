"""FastAPI server for E-Commerce Customer Support Live Agent Desk."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

APP_DIR = Path(__file__).resolve().parents[1]
DEMO_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _load_dotenv() -> None:
    env_path = APP_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

from google.genai import types  # noqa: E402
from agent import MODEL, run_support_workflow  # noqa: E402
from order_directory import (  # noqa: E402
    execute_order_mutation,
    get_customer_orders,
    list_all_customers,
    list_all_orders,
    lookup_customer,
    lookup_order,
    normalize_order_number,
)
from policies import build_resolution_markdown, validate_order_eligibility  # noqa: E402

if str(DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(DEMO_DIR))

from live_tools import (  # noqa: E402
    LIVE_MODEL_ID,
    TOOL_NAMES,
    VOICE_NAME,
    build_live_config,
    scheduling_for,
    tool_headline,
)

GENAI_CLIENT = None
logger = logging.getLogger(__name__)
FRAME_MAX_AGE_SECONDS = 12.0


def _cors_origins() -> list[str]:
    raw = os.getenv("SUPPORT_CORS_ORIGINS", "")
    if raw.strip():
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return ["http://127.0.0.1:4188", "http://localhost:4188"]


def _is_vertex_ai() -> bool:
    return (
        os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in ("true", "1")
        and bool(os.getenv("GOOGLE_CLOUD_PROJECT"))
    )


def _has_api_key() -> bool:
    return _is_vertex_ai() or bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))


def _client():
    global GENAI_CLIENT
    if not _has_api_key():
        raise HTTPException(
            status_code=503,
            detail=(
                "Missing authentication. Configure Vertex AI or set GOOGLE_API_KEY in "
                f"{APP_DIR / '.env'}."
            ),
        )
    if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
    try:
        from google import genai
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="Missing google-genai package. Run pip install -r requirements.txt.",
        ) from exc
    if GENAI_CLIENT is None:
        GENAI_CLIENT = genai.Client()
    return GENAI_CLIENT


def _live_client():
    if _is_vertex_ai():
        from google import genai
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        if location == "global":
            location = "us-central1"
        return genai.Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=location,
        )
    return _client()


@dataclass
class SupportSession:
    session_id: str
    customer: dict[str, Any] | None = None
    active_order: dict[str, Any] | None = None
    transcript: list[dict[str, str]] = field(default_factory=list)
    tool_activity: list[dict[str, Any]] = field(default_factory=list)
    evidence_photos: list[dict[str, Any]] = field(default_factory=list)
    camera_notes: list[str] = field(default_factory=list)
    actions_taken: list[dict[str, Any]] = field(default_factory=list)
    last_workflow_key: str | None = None
    last_workflow: dict[str, Any] | None = None
    last_frame: bytes | None = None
    last_frame_at: float = 0.0


sessions: dict[str, SupportSession] = {}

app = FastAPI(title="Apex E-Commerce Customer Support Live Desk API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


def _current_ui_state(session: SupportSession) -> dict[str, Any]:
    order = session.active_order
    cust = session.customer
    eligibility = validate_order_eligibility(order, "delivery_status") if order else {}
    packet_md = build_resolution_markdown(
        order=order,
        customer=cust,
        intent="general_support",
        eligibility=eligibility,
        actions_taken=session.actions_taken,
        camera_notes=session.camera_notes,
    )

    return {
        "session_id": session.session_id,
        "customer": cust,
        "active_order": order,
        "eligibility": eligibility,
        "transcript": session.transcript,
        "tool_activity": session.tool_activity,
        "evidence_photos": session.evidence_photos,
        "camera_notes": session.camera_notes,
        "actions_taken": session.actions_taken,
        "ticket_markdown": packet_md,
    }


# REST Endpoints
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "has_auth": _has_api_key(),
        "live_model": LIVE_MODEL_ID,
        "voice": VOICE_NAME,
        "workflow_model": MODEL,
    }


@app.get("/api/customers")
async def get_customers():
    return list_all_customers()


@app.get("/api/customers/{customer_id}/orders")
async def get_orders_by_customer(customer_id: str):
    return get_customer_orders(customer_id)


@app.get("/api/orders/{order_number}")
async def get_order_details(order_number: str):
    order = lookup_order(order_number)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    eligibility = validate_order_eligibility(order, "delivery_status")
    return {"order": order, "eligibility": eligibility}


@app.post("/api/sessions")
async def create_session():
    sid = uuid.uuid4().hex[:8]
    # Default initial customer: Sarah Jenkins
    default_cust = lookup_customer("Sarah Jenkins")
    default_order = lookup_order("ORD-94301")
    session = SupportSession(
        session_id=sid,
        customer=default_cust,
        active_order=default_order,
    )
    sessions[sid] = session
    return {
        "session_id": sid,
        "has_api_key": _has_api_key(),
        "live_model": LIVE_MODEL_ID,
        "state": _current_ui_state(session),
    }


@app.post("/api/select_customer")
async def select_customer(payload: dict[str, str]):
    sid = payload.get("session_id")
    cust_id = payload.get("customer_id")
    session = sessions.get(sid)
    if not session:
        session = SupportSession(session_id=sid or uuid.uuid4().hex[:8])
        if sid:
            sessions[sid] = session

    cust = lookup_customer(cust_id or "")
    if cust:
        session.customer = cust
        orders = get_customer_orders(cust["customer_id"])
        if orders:
            session.active_order = orders[0]
    return _current_ui_state(session)


@app.post("/api/select_order")
async def select_order(payload: dict[str, str]):
    sid = payload.get("session_id")
    order_num = payload.get("order_number")
    session = sessions.get(sid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    order = lookup_order(order_num or "")
    if order:
        session.active_order = order
    return _current_ui_state(session)


@app.post("/api/actions")
async def execute_action(payload: dict[str, Any]):
    sid = payload.get("session_id")
    action = payload.get("action")
    params = payload.get("params", {})
    session = sessions.get(sid)
    result = execute_order_mutation(action or "", params)
    if session and result.get("success"):
        session.actions_taken.append(result)
        if session.active_order and session.active_order.get("order_number") == params.get("order_number"):
            session.active_order = lookup_order(session.active_order["order_number"])
    return {"result": result, "state": _current_ui_state(session) if session else {}}


# WebSocket Live Voice & Vision Gateway
@app.websocket("/ws/live")
async def live_voice(websocket: WebSocket):
    await websocket.accept()
    sid = uuid.uuid4().hex[:8]
    default_cust = lookup_customer("Sarah Jenkins")
    default_order = lookup_order("ORD-94301")
    session = SupportSession(session_id=sid, customer=default_cust, active_order=default_order)
    sessions[sid] = session

    if not _has_api_key():
        await websocket.send_json(
            {
                "type": "error",
                "message": f"Missing authentication. Add GOOGLE_API_KEY to {APP_DIR / '.env'}.",
            }
        )
        await websocket.close()
        return

    try:
        client = _live_client()
    except Exception as exc:
        await websocket.send_json({"type": "error", "message": f"Client initialization failed: {exc}"})
        await websocket.close()
        return

    await websocket.send_json(
        {
            "type": "session",
            "session_id": sid,
            "model": LIVE_MODEL_ID,
            "voice": VOICE_NAME,
            "state": _current_ui_state(session),
        }
    )

    config = build_live_config()

    try:
        async with client.aio.live.connect(model=LIVE_MODEL_ID, config=config) as live_session:

            async def handle_tool_call(call) -> tuple[dict[str, Any], bool]:
                name = call.name
                args = dict(call.args or {})
                start_time = time.time()
                entry_id = uuid.uuid4().hex[:8]
                entry = {
                    "id": entry_id,
                    "name": name,
                    "args": args,
                    "headline": tool_headline(name, args),
                    "phase": "running",
                }
                session.tool_activity.append(entry)
                await websocket.send_json({"type": "tool", **entry})

                result: dict[str, Any] = {}
                urgent = False

                if name == "lookup_customer":
                    q = args.get("query", "")
                    cust = lookup_customer(q)
                    if not cust and session.customer:
                        # Fallback to active session customer for queries like "which is my latest order"
                        cust = session.customer
                    if cust:
                        session.customer = cust
                        orders = get_customer_orders(cust["customer_id"])
                        if orders and not session.active_order:
                            session.active_order = orders[0]
                        result = {
                            "found": True,
                            "customer_id": cust["customer_id"],
                            "full_name": cust["full_name"],
                            "loyalty_tier": cust["loyalty_tier"],
                            "total_orders": len(orders),
                            "latest_order": {
                                "order_number": orders[0]["order_number"],
                                "status": orders[0]["status"],
                                "order_date": orders[0]["order_date"],
                                "total_amount": orders[0]["total_amount"],
                                "items": [i["name"] for i in orders[0].get("items", [])],
                                "carrier": orders[0]["carrier"],
                                "tracking_number": orders[0]["tracking_number"],
                                "estimated_delivery": orders[0]["estimated_delivery"],
                            } if orders else None,
                            "recent_orders": [
                                {
                                    "order_number": o["order_number"],
                                    "status": o["status"],
                                    "order_date": o["order_date"],
                                    "total": o["total_amount"],
                                    "items": [i["name"] for i in o.get("items", [])],
                                }
                                for o in orders[:3]
                            ],
                        }
                    else:
                        result = {"found": False, "message": f"Customer '{q}' not found."}

                elif name == "lookup_order":
                    num = str(args.get("order_number", "")).strip()
                    if num.lower() in ("", "latest", "current", "my order", "none") and session.customer:
                        orders = get_customer_orders(session.customer["customer_id"])
                        ord_rec = orders[0] if orders else None
                    else:
                        ord_rec = lookup_order(num)
                    if ord_rec:
                        session.active_order = ord_rec
                        cust = lookup_customer(ord_rec["customer_id"])
                        if cust:
                            session.customer = cust
                        result = {
                            "found": True,
                            "order_number": ord_rec["order_number"],
                            "status": ord_rec["status"],
                            "carrier": ord_rec["carrier"],
                            "tracking_number": ord_rec["tracking_number"],
                            "estimated_delivery": ord_rec["estimated_delivery"],
                            "delivery_window": ord_rec.get("delivery_window"),
                            "items": ord_rec.get("items", []),
                            "shipping_address": ord_rec.get("shipping_address"),
                            "cancellation_allowed": ord_rec.get("cancellation_allowed", False),
                            "return_allowed": ord_rec.get("return_allowed", False),
                            "latest_milestone": ord_rec.get("milestones", [{}])[-1] if ord_rec.get("milestones") else {},
                        }
                    else:
                        result = {"found": False, "message": f"Order '{num}' was not found in directory."}

                elif name == "pin_damaged_item_photo":
                    obs = args.get("observation", "Visible package damage observed.")
                    cust_desc = args.get("customer_description", "")
                    confirmed = bool(args.get("confirmed", True))
                    item_name = args.get("item_name", "Package / Product")

                    photo_id = f"photo-{len(session.evidence_photos) + 1}"
                    now_str = time.strftime("%I:%M:%S %p")
                    session.camera_notes.append(f"{now_str} - {obs} ({'Confirmed on camera' if confirmed else 'Unconfirmed'})")

                    data_url = None
                    if session.last_frame and (time.time() - session.last_frame_at) <= FRAME_MAX_AGE_SECONDS:
                        data_url = f"data:image/jpeg;base64,{base64.b64encode(session.last_frame).decode('ascii')}"

                    photo_card = {
                        "id": photo_id,
                        "observation": obs,
                        "customer_description": cust_desc,
                        "confirmed": confirmed,
                        "item_name": item_name,
                        "captured_at": now_str,
                        "data_url": data_url or "assets/package_placeholder.png",
                    }
                    session.evidence_photos.append(photo_card)
                    result = {
                        "photo_pinned": True,
                        "photo_id": photo_id,
                        "confirmed": confirmed,
                        "auto_replacement_eligible": session.active_order and session.active_order.get("total_amount", 0) <= 150.0,
                    }

                elif name == "process_order_action":
                    action = args.get("action", "")
                    num = args.get("order_number", "")
                    details = args.get("details", "")
                    mutation_res = execute_order_mutation(
                        action,
                        {"order_number": num, "reason": details, "new_address": details},
                    )
                    if mutation_res.get("success"):
                        session.actions_taken.append(mutation_res)
                        if session.active_order and session.active_order.get("order_number") == num:
                            session.active_order = lookup_order(num)
                    if action == "escalate_to_supervisor":
                        urgent = True
                    result = mutation_res

                elif name == "sync_support_ticket":
                    result = {
                        "synced": True,
                        "active_order": session.active_order.get("order_number") if session.active_order else None,
                        "customer": session.customer.get("full_name") if session.customer else None,
                    }

                duration_ms = int((time.time() - start_time) * 1000)
                entry.update(
                    {
                        "phase": "done",
                        "duration_ms": duration_ms,
                        "headline": tool_headline(name, args, result),
                        "scheduling": "INTERRUPT" if urgent else "WHEN_IDLE",
                    }
                )
                await websocket.send_json({"type": "tool", **entry})
                await websocket.send_json({"type": "state", "state": _current_ui_state(session)})
                return result, urgent

            pending_input = ""
            pending_output = ""

            async def receive_from_browser():
                nonlocal session
                while True:
                    msg = await websocket.receive_json()
                    mtype = msg.get("type")

                    if mtype == "audio":
                        data_b64 = msg.get("data")
                        if data_b64:
                            raw_pcm = base64.b64decode(data_b64)
                            await live_session.send_realtime_input(
                                audio=types.Blob(data=raw_pcm, mime_type="audio/pcm;rate=16000")
                            )

                    elif mtype == "frame":
                        data_b64 = msg.get("data")
                        if data_b64:
                            frame_bytes = base64.b64decode(data_b64)
                            session.last_frame = frame_bytes
                            session.last_frame_at = time.time()
                            await live_session.send_realtime_input(
                                video=types.Blob(data=frame_bytes, mime_type="image/jpeg")
                            )

                    elif mtype == "text":
                        text = str(msg.get("text", "")).strip()
                        if text:
                            session.transcript.append({"speaker": "Customer", "text": text})
                            await websocket.send_json({"type": "state", "state": _current_ui_state(session)})
                            await live_session.send_client_content(
                                turns=types.Content(role="user", parts=[types.Part(text=text)]),
                                turn_complete=True,
                            )

                    elif mtype == "select_customer":
                        cid = msg.get("customer_id")
                        c = lookup_customer(cid or "")
                        if c:
                            session.customer = c
                            ords = get_customer_orders(c["customer_id"])
                            if ords:
                                session.active_order = ords[0]
                        await websocket.send_json({"type": "state", "state": _current_ui_state(session)})

                    elif mtype == "select_order":
                        onum = msg.get("order_number")
                        o = lookup_order(onum or "")
                        if o:
                            session.active_order = o
                        await websocket.send_json({"type": "state", "state": _current_ui_state(session)})

            async def finalize_input(reason: str = "finished") -> None:
                nonlocal pending_input
                finished = pending_input.strip()
                if not finished:
                    return
                pending_input = ""
                session.transcript.append({"speaker": "Customer", "text": finished})
                await websocket.send_json(
                    {"type": "transcript", "speaker": "Customer", "text": finished, "final": True, "reason": reason}
                )

            async def finalize_output(reason: str = "finished") -> None:
                nonlocal pending_output
                finished = pending_output.strip()
                if not finished:
                    return
                pending_output = ""
                session.transcript.append({"speaker": "Agent", "text": finished})
                await websocket.send_json(
                    {"type": "transcript", "speaker": "Agent", "text": finished, "final": True, "reason": reason}
                )

            async def receive_from_gemini():
                nonlocal pending_input, pending_output
                while True:
                    turn = live_session.receive()
                    async for response in turn:
                        if response.tool_call and response.tool_call.function_calls:
                            await finalize_input("tool_call")
                            for call in response.tool_call.function_calls:
                                res_payload, urgent = await handle_tool_call(call)
                                await live_session.send_tool_response(
                                    function_responses=[
                                        types.FunctionResponse(
                                            name=call.name,
                                            id=call.id,
                                            response=res_payload,
                                            scheduling=scheduling_for(urgent=urgent),
                                        )
                                    ]
                                )

                        server_content = response.server_content
                        if not server_content:
                            continue

                        # Live input transcription (user speech)
                        if server_content.input_transcription and server_content.input_transcription.text:
                            text = server_content.input_transcription.text
                            pending_input += text
                            await websocket.send_json(
                                {
                                    "type": "transcript",
                                    "speaker": "Customer",
                                    "text": pending_input,
                                    "final": bool(getattr(server_content.input_transcription, "finished", False)),
                                }
                            )
                            if getattr(server_content.input_transcription, "finished", False):
                                await finalize_input("input_transcription_finished")

                        # Live output transcription (agent speech)
                        if server_content.output_transcription and server_content.output_transcription.text:
                            await finalize_input("model_started_response")
                            text = server_content.output_transcription.text
                            pending_output += text
                            await websocket.send_json(
                                {
                                    "type": "transcript",
                                    "speaker": "Agent",
                                    "text": pending_output,
                                    "final": bool(getattr(server_content.output_transcription, "finished", False)),
                                }
                            )
                            if getattr(server_content.output_transcription, "finished", False):
                                await finalize_output("output_transcription_finished")

                        # Audio and text parts from model turn
                        if server_content.model_turn:
                            await finalize_input("model_audio_started")
                            for part in server_content.model_turn.parts or []:
                                if getattr(part, "thought", False) and part.text:
                                    continue
                                if part.text and not server_content.output_transcription:
                                    pending_output += part.text
                                    await websocket.send_json(
                                        {
                                            "type": "transcript",
                                            "speaker": "Agent",
                                            "text": pending_output,
                                            "final": False,
                                        }
                                    )
                                if part.inline_data and isinstance(part.inline_data.data, bytes):
                                    audio_b64 = base64.b64encode(part.inline_data.data).decode("ascii")
                                    await websocket.send_json({"type": "audio", "data": audio_b64})

                        if server_content.interrupted:
                            pending_output = ""
                            await websocket.send_json({"type": "interrupted"})

                        if (
                            getattr(server_content, "generation_complete", False)
                            or getattr(server_content, "turn_complete", False)
                        ):
                            await finalize_output("turn_complete")
                            await websocket.send_json({"type": "state", "state": _current_ui_state(session)})

            tasks = {
                asyncio.create_task(receive_from_browser()),
                asyncio.create_task(receive_from_gemini()),
            }
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            for t in pending:
                with contextlib.suppress(asyncio.CancelledError):
                    await t
            for t in done:
                t.result()

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as exc:
        logger.error(f"Error in Live voice loop: {exc}", exc_info=True)
        with contextlib.suppress(Exception):
            await websocket.send_json({"type": "error", "message": f"Gemini Live error: {exc}"})


# Serve static web frontend
app.mount("/", StaticFiles(directory=str(DEMO_DIR), html=True), name="static")
