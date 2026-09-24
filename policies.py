"""Deterministic business rules and policies for e-commerce customer support."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

try:
    from .schemas import (
        EligibilityValidation,
        OrderItem,
        OrderRecord,
        SupportActionRecord,
        SupportIntentClassification,
        SupportQueryNarrative,
        SupportResolutionPacket,
    )
except ImportError:
    from schemas import (
        EligibilityValidation,
        OrderItem,
        OrderRecord,
        SupportActionRecord,
        SupportIntentClassification,
        SupportQueryNarrative,
        SupportResolutionPacket,
    )

REFERENCE_DATE = datetime(2026, 9, 20)


def parse_date_safe(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str[:10], "%Y-%m-%d")
        except ValueError:
            continue
    return None


def validate_order_eligibility(
    order: Optional[dict[str, Any]],
    intent: str,
    today: datetime = REFERENCE_DATE,
) -> dict[str, Any]:
    """Evaluate deterministic policies for returns, cancellations, address changes, and replacements."""
    if not order:
        return {
            "order_found": False,
            "is_within_return_window": False,
            "days_since_delivery": None,
            "is_cancellable": False,
            "is_address_changeable": False,
            "is_replacement_eligible": False,
            "eligible_items_for_return": [],
            "validation_messages": ["Order was not found in directory."],
            "blockers": ["Need valid order number or tracking number."],
        }

    status = order.get("status", "unknown").lower()
    delivered_date = parse_date_safe(order.get("delivered_date"))
    days_since_delivery = None
    if delivered_date:
        days_since_delivery = (today - delivered_date).days

    # Return eligibility: delivered within 30 days and item is returnable
    return_window = order.get("return_window_days", 30)
    is_within_return_window = (
        status == "delivered"
        and days_since_delivery is not None
        and days_since_delivery <= return_window
    )

    eligible_items = []
    for item in order.get("items", []):
        if item.get("is_returnable", True) and not item.get("is_final_sale", False):
            eligible_items.append(item.get("name", item.get("sku", "Item")))

    # Cancellation eligibility: only while in processing
    is_cancellable = status == "processing"

    # Address change: only while in processing
    is_address_changeable = status == "processing"

    # Damaged item replacement eligibility: under $150 auto-approved
    total_amount = float(order.get("total_amount", 0.0))
    is_replacement_eligible = total_amount <= 150.0

    messages = []
    blockers = []

    if intent in ("request_return", "request_exchange"):
        if status != "delivered":
            messages.append(f"Order cannot be returned because it has not been delivered yet (current status: {status}).")
            blockers.append("Wait for package delivery before initiating a return.")
        elif not is_within_return_window:
            messages.append(
                f"Standard 30-day return window expired on {order.get('return_deadline', 'past date')}. "
                f"Delivered {days_since_delivery} days ago. Manufacturer warranty or store credit exception applies."
            )
            blockers.append("Return window expired (> 30 days). Requires warranty referral or manager credit exception.")
        else:
            remaining = return_window - (days_since_delivery or 0)
            messages.append(f"Eligible for return or exchange! {remaining} days remaining in return window.")

    elif intent == "order_cancellation":
        if is_cancellable:
            messages.append("Order is currently in 'processing' and is 100% eligible for immediate cancellation and full refund.")
        else:
            messages.append(f"Cannot cancel order directly because status is already '{status}'. After delivery, the customer may request a return.")
            blockers.append("Order has already shipped/delivered. Await delivery to return.")

    elif intent == "address_change":
        if is_address_changeable:
            messages.append("Order has not shipped yet; address update can be applied directly.")
        else:
            messages.append(f"Package already dispatched with {order.get('carrier', 'carrier')}. Carrier delivery intercept or hold at location required.")
            blockers.append("Order dispatched; courier hold or reroute required.")

    elif intent == "complaint_damaged":
        messages.append("Damage reported. Customer can show item on camera for instant verification.")
        if is_replacement_eligible:
            messages.append("Order value is under $150: eligible for instant free replacement without returning broken items.")
        else:
            messages.append("High-value item ($150+): visual damage inspection required before supervisor replacement approval.")

    elif intent == "delivery_status":
        messages.append(f"Current status: {status.upper()}. Carrier: {order.get('carrier')} ({order.get('tracking_number')}).")

    return {
        "order_found": True,
        "is_within_return_window": is_within_return_window,
        "days_since_delivery": days_since_delivery,
        "is_cancellable": is_cancellable,
        "is_address_changeable": is_address_changeable,
        "is_replacement_eligible": is_replacement_eligible,
        "eligible_items_for_return": eligible_items,
        "validation_messages": messages,
        "blockers": blockers,
    }


def build_resolution_markdown(
    order: Optional[dict[str, Any]],
    customer: Optional[dict[str, Any]],
    intent: str,
    eligibility: dict[str, Any],
    actions_taken: list[dict[str, Any]],
    camera_notes: list[str],
) -> str:
    """Generate a clean CRM support ticket markdown summary."""
    cust_name = customer.get("full_name", "Customer") if customer else (order.get("customer_name") if order else "Customer")
    cust_tier = customer.get("loyalty_tier", "Standard") if customer else "Standard"
    order_num = order.get("order_number", "Unspecified") if order else "Unspecified"
    carrier = order.get("carrier", "N/A") if order else "N/A"
    tracking = order.get("tracking_number", "N/A") if order else "N/A"
    status = order.get("status", "Unknown") if order else "Unknown"
    eta = order.get("estimated_delivery", "N/A") if order else "N/A"

    lines = [
        f"# Customer Support Ticket: {order_num}",
        f"**Customer:** {cust_name} ({cust_tier})",
        f"**Intent:** `{intent}` | **Status:** `{status.upper()}`",
        f"**Carrier:** {carrier} | **Tracking:** `{tracking}`",
        f"**ETA / Delivery:** {eta}",
        "",
        "## Policy Evaluation",
    ]

    for msg in eligibility.get("validation_messages", []):
        lines.append(f"- {msg}")

    if eligibility.get("blockers"):
        lines.append("")
        lines.append("### Blockers & Next Actions")
        for b in eligibility.get("blockers", []):
            lines.append(f"- ⚠️ {b}")

    if camera_notes:
        lines.append("")
        lines.append("## Visual Camera Evidence (AI Inspected)")
        for note in camera_notes:
            lines.append(f"- 📷 {note}")

    if actions_taken:
        lines.append("")
        lines.append("## Actions Executed")
        for act in actions_taken:
            title = act.get("title", act.get("action_type", "Action"))
            desc = act.get("description", act.get("message", ""))
            ref = f" (Ref: {act['reference_id']})" if act.get("reference_id") else ""
            lines.append(f"- **{title}**{ref}: {desc}")

    lines.append("")
    lines.append("---")
    lines.append("*Generated by Apex Commerce AI Support Agent*")

    return "\n".join(lines)
