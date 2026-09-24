"""Gemini 3.8 Live configuration and background tool contracts for E-Commerce Customer Support."""

from __future__ import annotations

import os
from typing import Any
from google.genai import types


def _default_live_model() -> str:
    if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in ("true", "1"):
        return "gemini-live-2.5-flash-native-audio"
    return "gemini-3.8-live"


LIVE_MODEL_ID = os.getenv("SUPPORT_GEMINI_LIVE_MODEL") or _default_live_model()
VOICE_NAME = os.getenv("SUPPORT_VOICE", "Aoede")

TOOL_NAMES = [
    "lookup_customer",
    "lookup_order",
    "sync_support_ticket",
    "pin_damaged_item_photo",
    "process_order_action",
]

SYSTEM_INSTRUCTION = """
You are the friendly, expert live voice customer support assistant for Apex Commerce, an online retail store.
Speak naturally, warmly, and concisely. Keep responses conversational and brief (one or two sentences at a time).
The customer is listening via real-time audio, and their support dashboard updates as you assist them.
Narrate brief asides as you assist, such as "Let me pull up your order right away" or "Checking your tracking now."

You work with background tools that execute while you talk (behavior NON_BLOCKING):
1. lookup_customer:
   - Call this as soon as the customer mentions their name, email, or phone number.
   - When it returns, warmly greet them by first name and confirm their recent orders.
2. lookup_order:
   - Call this as soon as an order number is mentioned (e.g. ORD-88219, ORD-94301).
   - When it returns, summarize the current status, delivery ETA, and carrier tracking concisely.
3. sync_support_ticket:
   - Evaluates business rules on the conversation and any camera observations.
   - Call it every turn or two when the customer describes an issue, asks for a return, or shares facts.
4. pin_damaged_item_photo:
   - If a customer reports a damaged, shattered, or defective item, invite them to show it on camera ("If you'd like, tap 'Show camera' and hold it up—I can inspect it right now").
   - When you can see the package or damaged product in the camera feed, describe what you actually see in one concrete sentence and call pin_damaged_item_photo.
   - If the damage is clear, set confirmed=true. If blurry or unclear, set confirmed=false and ask them to tilt or bring it closer.
   - Under $150, damaged items qualify for instant free replacement without returning broken parts.
5. process_order_action:
   - Call this to execute resolutions:
     • 'cancel_order': If an order is still in 'processing' (e.g. ORD-33018). Confirms 100% instant refund.
     • 'initiate_return': For orders delivered within the 30-day return window. Generates return label and asks if they prefer original payment or store credit with a 10% bonus.
     • 'issue_replacement': For confirmed damaged items or missing goods. Ships expedited replacement.
     • 'update_shipping_address': If the order has not shipped yet.
     • 'issue_courtesy_credit': For severe transit delays (e.g. $15 store credit).
     • 'escalate_to_supervisor': If requested by the customer or if complex fraud/high-value policy exception occurs.

Policies & Business Rules:
- Return Window: 30 days from delivery. If expired (>30 days, like ORD-71042), explain politely that the standard return window has passed, but provide their 1-year manufacturer warranty details.
- Cancellations: Only allowed while status is 'processing'. If already shipped/delivered, let them know they can initiate a return upon delivery.
- Empathy: If a customer is frustrated (e.g. delayed package or missing item), acknowledge it sincerely and provide proactive tracking details or credit.
""".strip()


def _string_param(description: str) -> types.Schema:
    return types.Schema(type=types.Type.STRING, description=description)


def tool_declarations() -> list[types.Tool]:
    """Return the non-blocking background tools for Gemini 3.8 Live."""

    lookup_cust = types.FunctionDeclaration(
        name="lookup_customer",
        description="Search customer CRM profile and order history by full name, email, or phone.",
        behavior=types.Behavior.NON_BLOCKING,
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": _string_param("Customer name, email address, or phone number.")
            },
            required=["query"],
        ),
    )

    lookup_ord = types.FunctionDeclaration(
        name="lookup_order",
        description="Retrieve full details, line items, carrier tracking milestones, and status for an order number.",
        behavior=types.Behavior.NON_BLOCKING,
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "order_number": _string_param("Order number, e.g. ORD-88219 or ORD-94301.")
            },
            required=["order_number"],
        ),
    )

    sync_ticket = types.FunctionDeclaration(
        name="sync_support_ticket",
        description="Synchronize the customer support ticket and evaluate return/cancellation eligibility in the background.",
        behavior=types.Behavior.NON_BLOCKING,
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "reason": _string_param("Short reason for syncing, e.g. 'checking return eligibility' or 'damage reported'.")
            },
        ),
    )

    pin_photo = types.FunctionDeclaration(
        name="pin_damaged_item_photo",
        description="Tape the current webcam frame into the support ticket evidence board with visual damage inspection observations.",
        behavior=types.Behavior.NON_BLOCKING,
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "observation": _string_param("One concrete sentence describing exactly what is visible on camera (e.g. 'Cracked ceramic bowl with missing shard')."),
                "customer_description": _string_param("What the customer claimed (e.g. 'shattered bowl in box')."),
                "confirmed": types.Schema(
                    type=types.Type.BOOLEAN,
                    description="True if damage is clearly visible; false if unclear, dark, or not evident.",
                ),
                "item_name": _string_param("Product name or SKU being inspected."),
            },
            required=["observation", "confirmed"],
        ),
    )

    process_act = types.FunctionDeclaration(
        name="process_order_action",
        description="Execute a customer support resolution action on an order (cancel, return label, replacement, address change, courtesy credit, supervisor escalation).",
        behavior=types.Behavior.NON_BLOCKING,
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "action": _string_param("One of: 'cancel_order', 'initiate_return', 'issue_replacement', 'update_shipping_address', 'issue_courtesy_credit', 'escalate_to_supervisor'."),
                "order_number": _string_param("The order number being modified."),
                "details": _string_param("Optional details, such as new shipping address, return reason, or credit explanation."),
            },
            required=["action", "order_number"],
        ),
    )

    return [types.Tool(function_declarations=[lookup_cust, lookup_ord, sync_ticket, pin_photo, process_act])]


def build_live_config() -> types.LiveConnectConfig:
    """Build LiveConnectConfig for Gemini 3.8 Live session."""
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=SYSTEM_INSTRUCTION,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE_NAME)
            )
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        tools=tool_declarations(),
    )


def scheduling_for(*, urgent: bool) -> types.FunctionResponseScheduling:
    if urgent:
        return types.FunctionResponseScheduling.INTERRUPT
    return types.FunctionResponseScheduling.WHEN_IDLE


def tool_headline(tool_name: str, args: dict[str, Any], result: dict[str, Any] | None = None) -> str:
    """Human-readable status summary for UI activity feed."""
    if tool_name == "lookup_customer":
        q = args.get("query", "")
        if result and result.get("found"):
            return f"Found profile for {result.get('full_name')} ({result.get('loyalty_tier')})"
        return f"Searching CRM for '{q}'"
    elif tool_name == "lookup_order":
        num = args.get("order_number", "")
        if result and result.get("found"):
            return f"Retrieved order {num} · Status: {result.get('status', '').upper()}"
        return f"Looking up order {num}"
    elif tool_name == "sync_support_ticket":
        return "Evaluating support policy & ticket resolution"
    elif tool_name == "pin_damaged_item_photo":
        confirmed = args.get("confirmed", False)
        status = "Verified on camera" if confirmed else "Unverified camera view"
        return f"Visual inspection pinned · {status}"
    elif tool_name == "process_order_action":
        action = args.get("action", "action")
        num = args.get("order_number", "")
        return f"Executing {action} on {num}"
    return tool_name
