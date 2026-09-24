"""ADK hybrid workflow graph for E-Commerce Customer Support."""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from typing import Any, AsyncGenerator, Callable

from google.adk.agents import BaseAgent, LlmAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from pydantic import BaseModel, ConfigDict
from typing_extensions import override

try:
    from .order_directory import lookup_customer, lookup_order
    from .policies import build_resolution_markdown, validate_order_eligibility
    from .schemas import (
        EligibilityValidation,
        OrderRecord,
        SupportIntentClassification,
        SupportQueryNarrative,
        SupportResolutionPacket,
    )
except ImportError:
    from order_directory import lookup_customer, lookup_order
    from policies import build_resolution_markdown, validate_order_eligibility
    from schemas import (
        EligibilityValidation,
        OrderRecord,
        SupportIntentClassification,
        SupportQueryNarrative,
        SupportResolutionPacket,
    )


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

MODEL = os.getenv(
    "SUPPORT_MODEL",
    "gemini-2.5-flash"
    if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in ("true", "1")
    else "gemini-3.8-flash",
)
APP_NAME = "ecommerce_customer_support_agent"


def _content(text: str) -> genai_types.Content:
    return genai_types.Content(role="model", parts=[genai_types.Part(text=text)])


def _state_event(author: str, text: str, updates: dict[str, Any]) -> Event:
    return Event(
        author=author,
        content=_content(text),
        actions=EventActions(state_delta=updates),
    )


class FunctionNode(BaseAgent):
    """Deterministic node that reads and updates session state."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    handler: Callable[[InvocationContext], dict[str, Any]]
    output_key: str
    summary: str

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        result = self.handler(ctx)
        ctx.session.state[self.output_key] = result
        yield _state_event(self.name, self.summary, {self.output_key: result})


class FinalResolutionNode(FunctionNode):
    """Generates the final support ticket packet and markdown."""

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        result = self.handler(ctx)
        updates = {self.output_key: result, "final_markdown": result.get("markdown", "")}
        ctx.session.state.update(updates)
        yield _state_event(self.name, result.get("markdown", ""), updates)


def _validate_eligibility_handler(ctx: InvocationContext) -> dict[str, Any]:
    narrative = ctx.session.state.get("normalized_query", {})
    order_num = narrative.get("order_number", "")
    order = lookup_order(order_num)
    intent = narrative.get("inferred_intent", "delivery_status")
    return validate_order_eligibility(order, intent)


def _final_resolution_handler(ctx: InvocationContext) -> dict[str, Any]:
    narrative = ctx.session.state.get("normalized_query", {})
    classification = ctx.session.state.get("intent_classification", {})
    eligibility = ctx.session.state.get("eligibility_validation", {})
    order_num = narrative.get("order_number", "")
    order = lookup_order(order_num)
    cust = lookup_customer(narrative.get("customer_name") or (order.get("customer_id") if order else ""))
    camera_notes = narrative.get("camera_observations", [])
    actions = ctx.session.state.get("actions_taken", [])

    markdown = build_resolution_markdown(
        order=order,
        customer=cust,
        intent=narrative.get("inferred_intent", "delivery_status"),
        eligibility=eligibility,
        actions_taken=actions,
        camera_notes=camera_notes,
    )

    return {
        "order_number": order_num,
        "customer_id": cust.get("customer_id", "GUEST") if cust else "GUEST",
        "customer_name": cust.get("full_name", narrative.get("customer_name", "Customer")) if cust else "Customer",
        "intent": narrative.get("inferred_intent", "delivery_status"),
        "resolution_status": "resolved_automated" if actions else "action_in_progress",
        "summary": narrative.get("issue_description", "Customer support query"),
        "actions_taken": actions,
        "next_customer_steps": [m for m in eligibility.get("validation_messages", [])],
        "supervisor_notes": "Supervisor escalation flagged" if classification.get("requires_supervisor") else None,
        "audit_trail": [f"Evaluated policy for {narrative.get('inferred_intent')}"],
        "markdown": markdown,
    }


def create_normalizer() -> LlmAgent:
    return LlmAgent(
        name="NormalizeSupportQuery",
        model=MODEL,
        description="Extracts structured customer and order facts from support dialogue.",
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
        instruction="""
You are the intake specialist for an E-Commerce AI Support Desk.
Extract the customer's facts from their inquiry and any camera observations:
- customer_name: Full name if provided.
- order_number: Order ID mentioned (e.g. ORD-88219, ORD-94301). Normalize into uppercase ORD-XXXXX format if possible.
- email_or_phone: Customer email or phone if mentioned.
- inferred_intent: One of: delivery_status, transit_details, request_return, request_exchange, complaint_damaged, complaint_missing_item, complaint_delayed, order_cancellation, address_change, warranty_inquiry, general_inquiry.
- issue_description: Clear, 1-2 sentence factual summary of what the customer reported or asked.
- item_mentioned: Specific item or product if mentioned.
- damaged_condition: Description of any broken/damaged physical items.
- requested_action: What the customer specifically wants (refund, return label, replacement, cancel, status, tracking).
- urgency: low, medium, high, or urgent.
- camera_observations: Any visual camera inspection notes from the conversation.
Output strictly conforming to the SupportQueryNarrative schema.
""",
        output_schema=SupportQueryNarrative,
        output_key="normalized_query",
    )


def create_classifier() -> LlmAgent:
    return LlmAgent(
        name="ClassifySupportIntent",
        model=MODEL,
        description="Classifies inquiry intent, sentiment, and supervisor escalation urgency.",
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
        instruction="""
You are the triaging specialist for E-Commerce Customer Support.
Analyze the normalized customer inquiry:
- intent: delivery_status, transit_details, request_return, request_exchange, complaint_damaged, complaint_missing_item, complaint_delayed, order_cancellation, address_change, warranty_inquiry, general_inquiry.
- urgency: low, medium, high, urgent.
- urgency_rationale: Brief explanation of the urgency assessment.
- requires_camera_inspection: True if customer reports damaged packaging, broken goods, or incorrect item needing visual verification.
- requires_supervisor: True only if customer explicitly demands a manager, threatens legal action, or high value fraud is suspected.
- customer_sentiment: positive, neutral, frustrated, angry.
- recommended_flow: The next best customer support flow to guide the user through.
Output strictly conforming to the SupportIntentClassification schema.
""",
        output_schema=SupportIntentClassification,
        output_key="intent_classification",
    )


def build_support_agent_workflow() -> SequentialAgent:
    normalizer = create_normalizer()
    classifier = create_classifier()
    validator = FunctionNode(
        name="ValidateOrderEligibility",
        description="Deterministic policy validation for return window, cancellation, and actions.",
        handler=_validate_eligibility_handler,
        output_key="eligibility_validation",
        summary="Evaluated e-commerce policy eligibility.",
    )
    resolution = FinalResolutionNode(
        name="BuildSupportResolutionPacket",
        description="Assembles the final support ticket packet and markdown.",
        handler=_final_resolution_handler,
        output_key="resolution_packet",
        summary="Assembled final support ticket packet.",
    )
    return SequentialAgent(
        name="CustomerSupportGraph",
        sub_agents=[normalizer, classifier, validator, resolution],
        description="Complete e-commerce customer support resolution graph.",
    )


root_agent = build_support_agent_workflow()


async def run_support_workflow(
    intake_text: str,
    session_id: str | None = None,
    actions_taken: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute the ADK support workflow on the customer transcript and camera notes."""
    service = InMemorySessionService()
    session = await service.create_session(
        app_name=APP_NAME,
        user_id="customer",
        session_id=session_id,
        state={"actions_taken": actions_taken or []},
    )
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=service)
    message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=intake_text or "Customer connected to support.")],
    )
    async for _ in runner.run_async(
        session_id=session.id,
        user_id="customer",
        new_message=message,
    ):
        pass

    latest = await service.get_session(app_name=APP_NAME, user_id="customer", session_id=session.id)
    return latest.state if latest else {}
