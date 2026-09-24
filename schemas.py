"""Structured data contracts for the E-Commerce Customer Support Voice Agent."""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

# Supported Customer Query Intents
SupportIntentType = Literal[
    "delivery_status",
    "transit_details",
    "request_return",
    "request_exchange",
    "complaint_damaged",
    "complaint_missing_item",
    "complaint_delayed",
    "order_cancellation",
    "address_change",
    "warranty_inquiry",
    "general_inquiry",
]

# Order Lifecycle Status
OrderStatus = Literal[
    "processing",
    "shipped",
    "in_transit",
    "out_for_delivery",
    "delivered",
    "cancelled",
    "return_requested",
    "returned",
]

UrgencyLevel = Literal["low", "medium", "high", "urgent"]

ResolutionStatus = Literal[
    "resolved_automated",
    "action_in_progress",
    "needs_customer_info",
    "escalated_supervisor",
]


class CustomerProfile(BaseModel):
    """Customer profile record from CRM."""

    customer_id: str
    full_name: str
    email: str
    phone: str
    loyalty_tier: Literal["Standard", "Silver", "Gold VIP", "Platinum"] = "Standard"
    shipping_address: str
    total_orders: int = 1
    notes: list[str] = Field(default_factory=list)


class OrderItem(BaseModel):
    """Line item in a customer order."""

    sku: str
    name: str
    category: str
    quantity: int = 1
    unit_price: float
    is_returnable: bool = True
    is_final_sale: bool = False
    image_emoji: str = "📦"
    status_tag: Optional[str] = None


class TrackingMilestone(BaseModel):
    """Single checkpoint along the package transit route."""

    timestamp: str
    status: str
    location: str
    description: str
    carrier_code: Optional[str] = None


class OrderRecord(BaseModel):
    """Order detail record with fulfillment and tracking state."""

    order_number: str
    customer_id: str
    customer_name: str
    order_date: str
    status: OrderStatus
    carrier: str
    tracking_number: str
    estimated_delivery: str
    delivery_window: Optional[str] = None
    delivered_date: Optional[str] = None
    items: list[OrderItem] = Field(default_factory=list)
    total_amount: float
    shipping_address: str
    payment_method: str = "Visa ending in 4242"
    return_window_days: int = 30
    return_deadline: Optional[str] = None
    milestones: list[TrackingMilestone] = Field(default_factory=list)
    driver_notes: Optional[str] = None
    cancellation_allowed: bool = False
    return_allowed: bool = False
    notes: list[str] = Field(default_factory=list)


class SupportQueryNarrative(BaseModel):
    """Normalized facts extracted from customer speech and camera observations."""

    customer_name: str = Field(description="Name of the customer if mentioned.")
    order_number: str = Field(description="Order number mentioned (e.g. ORD-88219).")
    email_or_phone: str = Field(description="Contact email or phone number if supplied.")
    inferred_intent: SupportIntentType = Field(description="Primary intent of the inquiry.")
    issue_description: str = Field(description="Clear factual summary of what the customer is asking or reporting.")
    item_mentioned: str = Field(description="Product or SKU the customer is referring to, if specific.")
    damaged_condition: Optional[str] = Field(
        default=None,
        description="Description of physical damage if reporting damaged goods.",
    )
    requested_action: Optional[str] = Field(
        default=None,
        description="Specific action requested (e.g. return, cancel, refund, replace, status).",
    )
    urgency: UrgencyLevel = "medium"
    camera_observations: list[str] = Field(
        default_factory=list,
        description="Notes on what the AI agent visually inspected via webcam.",
    )


class SupportIntentClassification(BaseModel):
    """Structured classification of customer intent and severity."""

    intent: SupportIntentType
    urgency: UrgencyLevel
    urgency_rationale: str
    requires_camera_inspection: bool = False
    requires_supervisor: bool = False
    customer_sentiment: Literal["positive", "neutral", "frustrated", "angry"] = "neutral"
    recommended_flow: str


class EligibilityValidation(BaseModel):
    """Deterministic validation of policies against the active order."""

    order_found: bool = False
    is_within_return_window: bool = False
    days_since_delivery: Optional[int] = None
    is_cancellable: bool = False
    is_address_changeable: bool = False
    is_replacement_eligible: bool = False
    eligible_items_for_return: list[str] = Field(default_factory=list)
    validation_messages: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class SupportActionRecord(BaseModel):
    """Record of an automated or manual action taken on the order."""

    action_type: Literal[
        "return_label_generated",
        "order_cancelled",
        "replacement_created",
        "credit_issued",
        "address_updated",
        "tracking_refreshed",
        "escalated_to_supervisor",
        "warranty_referred",
    ]
    title: str
    description: str
    reference_id: Optional[str] = None
    amount: Optional[float] = None
    status: Literal["completed", "pending", "rejected"] = "completed"
    created_at: str


class SupportResolutionPacket(BaseModel):
    """Complete support resolution packet handed off to CRM and the UI."""

    order_number: str
    customer_id: str
    customer_name: str
    intent: SupportIntentType
    resolution_status: ResolutionStatus
    summary: str
    actions_taken: list[SupportActionRecord] = Field(default_factory=list)
    next_customer_steps: list[str] = Field(default_factory=list)
    supervisor_notes: Optional[str] = None
    audit_trail: list[str] = Field(default_factory=list)
    markdown: str
