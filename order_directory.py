"""Mock e-commerce order directory & customer CRM.

Provides rich realistic test data across 5 customers and 11 orders covering:
- In-transit and out-for-delivery tracking with live carrier milestones
- Returns within the 30-day window (with label/QR generation)
- Expired return window (>30 days) with warranty guidance
- Damaged item complaints with visual inspection capability
- Missing item and delivery complaints
- Pre-delivery cancellation and shipping address updates
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Optional

# Reference date representing 'today' for deterministic demo tests
REFERENCE_DATE = datetime(2026, 9, 20)

CUSTOMERS: dict[str, dict[str, Any]] = {
    "CUST-1001": {
        "customer_id": "CUST-1001",
        "full_name": "Sarah Jenkins",
        "email": "sarah.jenkins@example.com",
        "phone": "415-555-0142",
        "loyalty_tier": "Gold VIP",
        "shipping_address": "742 Evergreen Terrace, Apt 4B, San Francisco, CA 94107",
        "total_orders": 3,
        "notes": ["Gold VIP member since 2024", "Prefers contactless delivery at front desk"],
    },
    "CUST-1002": {
        "customer_id": "CUST-1002",
        "full_name": "Marcus Vance",
        "email": "marcus.vance@example.com",
        "phone": "312-555-0188",
        "loyalty_tier": "Standard",
        "shipping_address": "1204 N Milwaukee Ave, Unit 2, Chicago, IL 60622",
        "total_orders": 2,
        "notes": ["New customer", "Building has secure callbox: #1204"],
    },
    "CUST-1003": {
        "customer_id": "CUST-1003",
        "full_name": "Elena Rostova",
        "email": "elena.rostova@example.com",
        "phone": "206-555-0173",
        "loyalty_tier": "Silver",
        "shipping_address": "88 Pine St, Suite 1400, Seattle, WA 98101",
        "total_orders": 2,
        "notes": ["Commercial office address; deliver M-F 9am-5pm"],
    },
    "CUST-1004": {
        "customer_id": "CUST-1004",
        "full_name": "David Kim",
        "email": "david.kim@example.com",
        "phone": "512-555-0195",
        "loyalty_tier": "Platinum",
        "shipping_address": "402 W 8th St, Austin, TX 78701",
        "total_orders": 2,
        "notes": ["Platinum member", "Reported porch theft in neighborhood previously"],
    },
    "CUST-1005": {
        "customer_id": "CUST-1005",
        "full_name": "Aisha Patel",
        "email": "aisha.patel@example.com",
        "phone": "646-555-0164",
        "loyalty_tier": "Standard",
        "shipping_address": "350 5th Ave, Floor 18, New York, NY 10118",
        "total_orders": 2,
        "notes": ["Express shipping preference"],
    },
}

ORDERS: dict[str, dict[str, Any]] = {
    # Customer 1: Sarah Jenkins
    "ORD-88219": {
        "order_number": "ORD-88219",
        "customer_id": "CUST-1001",
        "customer_name": "Sarah Jenkins",
        "order_date": "2026-09-14",
        "status": "delivered",
        "carrier": "FedEx",
        "tracking_number": "FDX-994821034",
        "estimated_delivery": "2026-09-17",
        "delivery_window": "Delivered Sep 17 at 11:42 AM",
        "delivered_date": "2026-09-17",
        "shipping_address": "742 Evergreen Terrace, Apt 4B, San Francisco, CA 94107",
        "payment_method": "Apple Pay (Visa ...4242)",
        "total_amount": 299.99,
        "return_window_days": 30,
        "return_deadline": "2026-10-17",
        "cancellation_allowed": False,
        "return_allowed": True,
        "items": [
            {
                "sku": "AUD-WH-1000",
                "name": "AuraWave Pro Wireless ANC Headphones",
                "category": "Electronics",
                "quantity": 1,
                "unit_price": 299.99,
                "is_returnable": True,
                "is_final_sale": False,
                "image_emoji": "🎧",
                "status_tag": "Delivered 3 days ago - Returnable",
            }
        ],
        "milestones": [
            {"timestamp": "2026-09-14 14:10", "status": "Order Placed", "location": "Online Store", "description": "Order confirmed and payment verified."},
            {"timestamp": "2026-09-15 08:30", "status": "Shipped", "location": "Fulfillment Center, Reno NV", "description": "Package picked up by FedEx."},
            {"timestamp": "2026-09-16 19:22", "status": "In Transit", "location": "FedEx Sorting Facility, Oakland CA", "description": "Arrived at destination sorting hub."},
            {"timestamp": "2026-09-17 07:45", "status": "Out for Delivery", "location": "San Francisco CA", "description": "Loaded onto delivery van with driver Alex."},
            {"timestamp": "2026-09-17 11:42", "status": "Delivered", "location": "San Francisco CA", "description": "Delivered to mailroom / front desk reception."},
        ],
        "driver_notes": "Left with building concierge Marcus at front desk.",
        "notes": ["Eligible for 30-day return or instant exchange until Oct 17, 2026."],
    },
    "ORD-94301": {
        "order_number": "ORD-94301",
        "customer_id": "CUST-1001",
        "customer_name": "Sarah Jenkins",
        "order_date": "2026-09-18",
        "status": "out_for_delivery",
        "carrier": "UPS",
        "tracking_number": "1Z999AA10123456784",
        "estimated_delivery": "Today (Sep 20) by 2:30 PM",
        "delivery_window": "1:00 PM - 3:00 PM",
        "delivered_date": None,
        "shipping_address": "742 Evergreen Terrace, Apt 4B, San Francisco, CA 94107",
        "payment_method": "Apple Pay (Visa ...4242)",
        "total_amount": 164.50,
        "return_window_days": 30,
        "return_deadline": "30 days after delivery",
        "cancellation_allowed": False,
        "return_allowed": False,
        "items": [
            {
                "sku": "KTC-ESP-500",
                "name": "Barista Precision Coffee Maker",
                "category": "Kitchen",
                "quantity": 1,
                "unit_price": 139.50,
                "is_returnable": True,
                "is_final_sale": False,
                "image_emoji": "☕",
                "status_tag": "On Delivery Truck",
            },
            {
                "sku": "COF-ORG-250",
                "name": "Single-Origin Ethiopian Roast Beans (2 lb)",
                "category": "Grocery",
                "quantity": 1,
                "unit_price": 25.00,
                "is_returnable": False,
                "is_final_sale": True,
                "image_emoji": "🫘",
                "status_tag": "On Delivery Truck - Final Sale",
            },
        ],
        "milestones": [
            {"timestamp": "2026-09-18 10:15", "status": "Order Placed", "location": "Online Store", "description": "Order confirmed."},
            {"timestamp": "2026-09-18 17:00", "status": "Shipped", "location": "Fulfillment Hub, Stockton CA", "description": "Scanned into UPS network."},
            {"timestamp": "2026-09-19 22:30", "status": "In Transit", "location": "UPS Hub, San Francisco CA", "description": "Sorted and prepped for dispatch."},
            {"timestamp": "2026-09-20 07:15", "status": "Out for Delivery", "location": "San Francisco CA", "description": "Out for delivery today with courier Carlos (3 stops away)."},
        ],
        "driver_notes": "Estimated delivery window: 1:00 PM - 3:00 PM today.",
        "notes": ["Live courier tracking active: vehicle is approximately 3 stops away."],
    },
    "ORD-71042": {
        "order_number": "ORD-71042",
        "customer_id": "CUST-1001",
        "customer_name": "Sarah Jenkins",
        "order_date": "2026-07-10",
        "status": "delivered",
        "carrier": "FedEx",
        "tracking_number": "FDX-771920194",
        "estimated_delivery": "2026-07-16",
        "delivery_window": "Delivered Jul 16 at 2:15 PM",
        "delivered_date": "2026-07-16",
        "shipping_address": "742 Evergreen Terrace, Apt 4B, San Francisco, CA 94107",
        "payment_method": "Apple Pay (Visa ...4242)",
        "total_amount": 499.00,
        "return_window_days": 30,
        "return_deadline": "2026-08-15",
        "cancellation_allowed": False,
        "return_allowed": False,  # EXPIRED return window (>65 days)
        "items": [
            {
                "sku": "HME-ROB-900",
                "name": "RoboClean Smart LiDAR Vacuum & Mop",
                "category": "Home Appliances",
                "quantity": 1,
                "unit_price": 499.00,
                "is_returnable": True,
                "is_final_sale": False,
                "image_emoji": "🤖",
                "status_tag": "Delivered 65 days ago - Return Window Expired",
            }
        ],
        "milestones": [
            {"timestamp": "2026-07-10 11:00", "status": "Order Placed", "location": "Online Store", "description": "Order confirmed."},
            {"timestamp": "2026-07-16 14:15", "status": "Delivered", "location": "San Francisco CA", "description": "Delivered to front door."},
        ],
        "driver_notes": "Delivered to customer porch.",
        "notes": [
            "Delivered over 65 days ago; 30-day standard return window closed on Aug 15, 2026.",
            "Covered under manufacturer 1-year limited warranty until July 16, 2027.",
        ],
    },

    # Customer 2: Marcus Vance
    "ORD-51920": {
        "order_number": "ORD-51920",
        "customer_id": "CUST-1002",
        "customer_name": "Marcus Vance",
        "order_date": "2026-09-16",
        "status": "in_transit",
        "carrier": "DHL Express",
        "tracking_number": "DHL-391820491",
        "estimated_delivery": "2026-09-22 (Delayed from Sep 19)",
        "delivery_window": "Pending weather clearance",
        "delivered_date": None,
        "shipping_address": "1204 N Milwaukee Ave, Unit 2, Chicago, IL 60622",
        "payment_method": "Mastercard (...8831)",
        "total_amount": 220.00,
        "return_window_days": 30,
        "return_deadline": "30 days after delivery",
        "cancellation_allowed": False,
        "return_allowed": False,
        "items": [
            {
                "sku": "APP-PRK-300",
                "name": "Nordic Peak Expedition Down Parka (Size L, Navy)",
                "category": "Apparel",
                "quantity": 1,
                "unit_price": 220.00,
                "is_returnable": True,
                "is_final_sale": False,
                "image_emoji": "🧥",
                "status_tag": "In Transit - Weather Delay",
            }
        ],
        "milestones": [
            {"timestamp": "2026-09-16 16:30", "status": "Order Placed", "location": "Online Store", "description": "Order confirmed."},
            {"timestamp": "2026-09-17 09:00", "status": "Shipped", "location": "Distribution Center, Columbus OH", "description": "In transit with DHL."},
            {"timestamp": "2026-09-18 14:00", "status": "In Transit", "location": "DHL Regional Sort Facility, O'Hare Chicago IL", "description": "Arrived at Chicago regional terminal."},
            {"timestamp": "2026-09-19 06:30", "status": "Exception / Delay", "location": "Chicago IL", "description": "Severe regional weather advisory. Transit flight delayed."},
        ],
        "driver_notes": "Weather hold in Midwest transit corridor. Courier reschedules delivery for Sep 22.",
        "notes": ["Customer eligible for $15 shipping delay courtesy store credit."],
    },
    "ORD-62184": {
        "order_number": "ORD-62184",
        "customer_id": "CUST-1002",
        "customer_name": "Marcus Vance",
        "order_date": "2026-09-16",
        "status": "delivered",
        "carrier": "UPS",
        "tracking_number": "1Z888XX1928374615",
        "estimated_delivery": "2026-09-19",
        "delivery_window": "Delivered Sep 19 at 4:30 PM",
        "delivered_date": "2026-09-19",
        "shipping_address": "1204 N Milwaukee Ave, Unit 2, Chicago, IL 60622",
        "payment_method": "Mastercard (...8831)",
        "total_amount": 118.00,
        "return_window_days": 30,
        "return_deadline": "2026-10-19",
        "cancellation_allowed": False,
        "return_allowed": True,
        "items": [
            {
                "sku": "HOM-PLT-16P",
                "name": "Artisan Stoneware 16-Piece Dinnerware Set",
                "category": "Home & Kitchen",
                "quantity": 1,
                "unit_price": 118.00,
                "is_returnable": True,
                "is_final_sale": False,
                "image_emoji": "🍽️",
                "status_tag": "Delivered Yesterday - Damaged Goods Reported",
            }
        ],
        "milestones": [
            {"timestamp": "2026-09-16 11:20", "status": "Order Placed", "location": "Online Store", "description": "Order confirmed."},
            {"timestamp": "2026-09-17 14:00", "status": "Shipped", "location": "Warehouse, Indianapolis IN", "description": "Shipped with fragile handling."},
            {"timestamp": "2026-09-19 16:30", "status": "Delivered", "location": "Chicago IL", "description": "Delivered to apartment building lobby."},
        ],
        "driver_notes": "Package left inside secure vestibule.",
        "notes": [
            "Customer reports shattered plates upon unboxing. Box arrived with crushed corner.",
            "Visual camera inspection recommended. Damaged items under $150 qualify for instant free replacement without returning hazardous broken ceramic.",
        ],
    },

    # Customer 3: Elena Rostova
    "ORD-33018": {
        "order_number": "ORD-33018",
        "customer_id": "CUST-1003",
        "customer_name": "Elena Rostova",
        "order_date": "2026-09-20",  # Placed today!
        "status": "processing",
        "carrier": "FedEx Ground",
        "tracking_number": "FDX-PENDING-33018",
        "estimated_delivery": "2026-09-24",
        "delivery_window": "Preparing for shipment",
        "delivered_date": None,
        "shipping_address": "88 Pine St, Suite 1400, Seattle, WA 98101",
        "payment_method": "Corporate Amex (...1009)",
        "total_amount": 349.00,
        "return_window_days": 30,
        "return_deadline": "30 days after delivery",
        "cancellation_allowed": True,  # Processing -> Cancellable!
        "return_allowed": False,
        "items": [
            {
                "sku": "OFF-CHR-88",
                "name": "ErgoFlex High-Back Mesh Desk Chair",
                "category": "Office Furniture",
                "quantity": 1,
                "unit_price": 349.00,
                "is_returnable": True,
                "is_final_sale": False,
                "image_emoji": "🪑",
                "status_tag": "Processing - Cancellable",
            }
        ],
        "milestones": [
            {"timestamp": "2026-09-20 08:30", "status": "Order Placed", "location": "Online Store", "description": "Order received. Inventory allocated."},
            {"timestamp": "2026-09-20 09:00", "status": "Processing", "location": "Fulfillment Center, Kent WA", "description": "Queued for packing. Has not yet shipped."},
        ],
        "driver_notes": "Not yet dispatched to carrier.",
        "notes": [
            "Status is PROCESSING: Customer can cancel for an immediate 100% refund or update the delivery address before shipment.",
        ],
    },
    "ORD-21980": {
        "order_number": "ORD-21980",
        "customer_id": "CUST-1003",
        "customer_name": "Elena Rostova",
        "order_date": "2026-09-05",
        "status": "delivered",
        "carrier": "USPS Priority",
        "tracking_number": "940011189922319082",
        "estimated_delivery": "2026-09-08",
        "delivery_window": "Delivered Sep 8 at 1:10 PM",
        "delivered_date": "2026-09-08",
        "shipping_address": "88 Pine St, Suite 1400, Seattle, WA 98101",
        "payment_method": "Corporate Amex (...1009)",
        "total_amount": 140.00,
        "return_window_days": 30,
        "return_deadline": "2026-10-08",
        "cancellation_allowed": False,
        "return_allowed": True,
        "items": [
            {
                "sku": "FTW-RUN-09",
                "name": "AeroStride Velocity Road Runners (Women Size 9)",
                "category": "Footwear",
                "quantity": 1,
                "unit_price": 140.00,
                "is_returnable": True,
                "is_final_sale": False,
                "image_emoji": "👟",
                "status_tag": "Delivered 12 days ago - Returnable / Exchangeable",
            }
        ],
        "milestones": [
            {"timestamp": "2026-09-05 13:00", "status": "Order Placed", "location": "Online Store", "description": "Order confirmed."},
            {"timestamp": "2026-09-08 13:10", "status": "Delivered", "location": "Seattle WA", "description": "Delivered to commercial mail center."},
        ],
        "driver_notes": "Delivered to mail center clerk.",
        "notes": ["Customer may request size exchange (e.g. Size 9.5) or standard return."],
    },

    # Customer 4: David Kim
    "ORD-44912": {
        "order_number": "ORD-44912",
        "customer_id": "CUST-1004",
        "customer_name": "David Kim",
        "order_date": "2026-09-17",
        "status": "delivered",
        "carrier": "FedEx",
        "tracking_number": "FDX-449128821",
        "estimated_delivery": "2026-09-20",
        "delivery_window": "Delivered today at 10:15 AM",
        "delivered_date": "2026-09-20",
        "shipping_address": "402 W 8th St, Austin, TX 78701",
        "payment_method": "Visa Platinum (...9012)",
        "total_amount": 549.99,
        "return_window_days": 30,
        "return_deadline": "2026-10-20",
        "cancellation_allowed": False,
        "return_allowed": True,
        "items": [
            {
                "sku": "TEC-MON-4K",
                "name": "UltraView 32-inch 4K Studio Display",
                "category": "Electronics",
                "quantity": 1,
                "unit_price": 549.99,
                "is_returnable": True,
                "is_final_sale": False,
                "image_emoji": "🖥️",
                "status_tag": "Marked Delivered Today - Customer Cannot Locate",
            }
        ],
        "milestones": [
            {"timestamp": "2026-09-17 15:40", "status": "Order Placed", "location": "Online Store", "description": "Order verified."},
            {"timestamp": "2026-09-18 10:00", "status": "Shipped", "location": "Dallas TX Hub", "description": "In transit with FedEx."},
            {"timestamp": "2026-09-20 08:30", "status": "Out for Delivery", "location": "Austin TX", "description": "Out for delivery with FedEx courier."},
            {"timestamp": "2026-09-20 10:15", "status": "Delivered", "location": "Austin TX", "description": "Delivered to front porch."},
        ],
        "driver_notes": "Delivered to front porch steps.",
        "notes": [
            "Customer reports package is missing from porch despite delivery confirmation.",
            "High value ($550). Requires driver GPS verification, carrier tracer ticket, or replacement escalation.",
        ],
    },
    "ORD-10499": {
        "order_number": "ORD-10499",
        "customer_id": "CUST-1004",
        "customer_name": "David Kim",
        "order_date": "2026-09-20",
        "status": "processing",
        "carrier": "UPS Ground",
        "tracking_number": "1Z-PENDING-10499",
        "estimated_delivery": "2026-09-25",
        "delivery_window": "Processing at warehouse",
        "delivered_date": None,
        "shipping_address": "402 W 8th St, Austin, TX 78701",
        "payment_method": "Visa Platinum (...9012)",
        "total_amount": 189.00,
        "return_window_days": 30,
        "return_deadline": "30 days after delivery",
        "cancellation_allowed": True,
        "return_allowed": False,
        "items": [
            {
                "sku": "KEY-MEC-RGB",
                "name": "Vortex Stealth Mechanical Keyboard (Brown Switches)",
                "category": "Electronics",
                "quantity": 1,
                "unit_price": 189.00,
                "is_returnable": True,
                "is_final_sale": False,
                "image_emoji": "⌨️",
                "status_tag": "Processing - Cancellable",
            }
        ],
        "milestones": [
            {"timestamp": "2026-09-20 12:00", "status": "Order Placed", "location": "Online Store", "description": "Order received."},
        ],
        "driver_notes": None,
        "notes": ["Recently placed order, ready for fulfillment."],
    },

    # Customer 5: Aisha Patel
    "ORD-77621": {
        "order_number": "ORD-77621",
        "customer_id": "CUST-1005",
        "customer_name": "Aisha Patel",
        "order_date": "2026-09-12",
        "status": "delivered",
        "carrier": "UPS",
        "tracking_number": "1Z776A1029384756",
        "estimated_delivery": "2026-09-15",
        "delivery_window": "Delivered Sep 15 at 3:45 PM",
        "delivered_date": "2026-09-15",
        "shipping_address": "350 5th Ave, Floor 18, New York, NY 10118",
        "payment_method": "Mastercard (...5519)",
        "total_amount": 410.00,
        "return_window_days": 30,
        "return_deadline": "2026-10-15",
        "cancellation_allowed": False,
        "return_allowed": True,
        "items": [
            {
                "sku": "CLO-SWT-CSH",
                "name": "Mongolian Cashmere Crewneck Sweater (Camel, M)",
                "category": "Apparel",
                "quantity": 1,
                "unit_price": 195.00,
                "is_returnable": True,
                "is_final_sale": False,
                "image_emoji": "🧶",
                "status_tag": "Reported Missing from Package",
            },
            {
                "sku": "CLO-DNM-SLM",
                "name": "Selvedge Slim Fit Denim (Indigo 28x32)",
                "category": "Apparel",
                "quantity": 1,
                "unit_price": 135.00,
                "is_returnable": True,
                "is_final_sale": False,
                "image_emoji": "👖",
                "status_tag": "Received",
            },
            {
                "sku": "ACC-BLT-LTH",
                "name": "Full-Grain Italian Leather Belt",
                "category": "Accessories",
                "quantity": 1,
                "unit_price": 80.00,
                "is_returnable": True,
                "is_final_sale": False,
                "image_emoji": "🥋",
                "status_tag": "Received",
            },
        ],
        "milestones": [
            {"timestamp": "2026-09-12 18:00", "status": "Order Placed", "location": "Online Store", "description": "Order confirmed."},
            {"timestamp": "2026-09-15 15:45", "status": "Delivered", "location": "New York NY", "description": "Delivered to mailroom reception."},
        ],
        "driver_notes": "Delivered to office building mail intake.",
        "notes": [
            "Customer reports package arrived with only 2 of 3 items (cashmere sweater missing from box).",
            "Warehouse packing slip shows item was checked, but customer box was missing item. Eligible for instant expedited reshipment or refund of $195.00.",
        ],
    },
    "ORD-80312": {
        "order_number": "ORD-80312",
        "customer_id": "CUST-1005",
        "customer_name": "Aisha Patel",
        "order_date": "2026-09-18",
        "status": "shipped",
        "carrier": "FedEx 2Day",
        "tracking_number": "FDX-803129910",
        "estimated_delivery": "Tomorrow (Sep 21) by 4:30 PM",
        "delivery_window": "In transit",
        "delivered_date": None,
        "shipping_address": "350 5th Ave, Floor 18, New York, NY 10118",
        "payment_method": "Mastercard (...5519)",
        "total_amount": 129.99,
        "return_window_days": 30,
        "return_deadline": "30 days after delivery",
        "cancellation_allowed": False,
        "return_allowed": False,
        "items": [
            {
                "sku": "IOT-HUB-PRO",
                "name": "Nexus Smart Home Automation Bridge",
                "category": "Smart Home",
                "quantity": 1,
                "unit_price": 129.99,
                "is_returnable": True,
                "is_final_sale": False,
                "image_emoji": "📡",
                "status_tag": "Shipped - Arriving Tomorrow",
            }
        ],
        "milestones": [
            {"timestamp": "2026-09-18 20:00", "status": "Order Placed", "location": "Online Store", "description": "Order confirmed."},
            {"timestamp": "2026-09-19 11:30", "status": "Shipped", "location": "Distribution Center, Newark NJ", "description": "Departed facility on route to destination hub."},
        ],
        "driver_notes": "On schedule for delivery tomorrow.",
        "notes": ["Tracking active, arriving tomorrow."],
    },
}


def normalize_order_number(value: str) -> str:
    """Normalize spoken or typed order number string (e.g. 'ORD 88219', '88219', 'order-88219')."""
    raw = str(value or "").strip().upper()
    digits_only = re.sub(r"[^0-9]", "", raw)
    if digits_only and len(digits_only) == 5:
        return f"ORD-{digits_only}"
    clean = re.sub(r"[^A-Z0-9]", "", raw)
    if clean.startswith("ORD") and len(clean) >= 8:
        return f"ORD-{clean[3:]}"
    return clean


def lookup_order(order_identifier: str) -> dict[str, Any] | None:
    """Lookup order by normalized number or tracking code."""
    target = normalize_order_number(order_identifier)
    if target in ORDERS:
        return ORDERS[target]

    # Try raw lookup
    clean_str = str(order_identifier or "").strip().upper()
    for order in ORDERS.values():
        if order["order_number"].upper() == clean_str:
            return order
        if order["tracking_number"].upper() == clean_str:
            return order
        if order["order_number"].replace("-", "").upper() == clean_str.replace("-", ""):
            return order

    return None


def lookup_customer(query: str) -> dict[str, Any] | None:
    """Lookup customer by ID, name, email, or phone number."""
    clean = str(query or "").strip().lower()
    if not clean:
        return None

    # Exact ID match
    for cid, cust in CUSTOMERS.items():
        if cid.lower() == clean:
            return cust

    # Email match
    for cust in CUSTOMERS.values():
        if clean in cust["email"].lower():
            return cust

    # Phone match
    phone_digits = re.sub(r"[^0-9]", "", clean)
    if len(phone_digits) >= 7:
        for cust in CUSTOMERS.values():
            if phone_digits in re.sub(r"[^0-9]", "", cust["phone"]):
                return cust

    # Full name or partial name match
    for cust in CUSTOMERS.values():
        cust_name = cust["full_name"].lower()
        if clean in cust_name or cust_name in clean:
            return cust

    return None


def get_customer_orders(customer_id: str) -> list[dict[str, Any]]:
    """Retrieve all orders associated with a customer ID, ordered by date descending."""
    matches = [o for o in ORDERS.values() if o["customer_id"] == customer_id]
    return sorted(matches, key=lambda x: x["order_date"], reverse=True)


def list_all_customers() -> list[dict[str, Any]]:
    """Return all customer profiles for quick demo switching."""
    return list(CUSTOMERS.values())


def list_all_orders() -> list[dict[str, Any]]:
    """Return all orders in the directory."""
    return list(ORDERS.values())


def execute_order_mutation(action: str, params: dict[str, Any]) -> dict[str, Any]:
    """Perform real-time actions on the mock order database (cancel, return, address change)."""
    order_num = params.get("order_number")
    order = lookup_order(order_num)
    if not order:
        return {"success": False, "error": f"Order {order_num} not found."}

    action = action.lower().strip()
    if action == "cancel_order":
        if order["status"] != "processing":
            return {
                "success": False,
                "error": f"Cannot cancel order {order_num}. Current status is '{order['status']}'. Orders can only be cancelled while in 'processing'.",
            }
        order["status"] = "cancelled"
        order["cancellation_allowed"] = False
        order["notes"].append(f"Cancelled by customer support on {datetime.now().strftime('%Y-%m-%d %H:%M')}. Full refund of ${order['total_amount']:.2f} issued.")
        return {
            "success": True,
            "action": "cancel_order",
            "order_number": order["order_number"],
            "refund_amount": order["total_amount"],
            "message": f"Order {order['order_number']} has been cancelled. A full refund of ${order['total_amount']:.2f} will post to {order['payment_method']} in 3-5 business days.",
        }

    elif action == "initiate_return":
        item_sku = params.get("sku")
        refund_type = params.get("refund_type", "original_payment")
        reason = params.get("reason", "Customer return request")

        return_id = f"RET-{datetime.now().strftime('%m%d')}-{order['order_number'][-4:]}"
        bonus_credit = 0.0
        if refund_type == "store_credit":
            bonus_credit = round(order["total_amount"] * 0.10, 2)

        order["status"] = "return_requested"
        order["notes"].append(f"Return {return_id} authorized for {reason}. Return label generated.")
        return {
            "success": True,
            "action": "initiate_return",
            "order_number": order["order_number"],
            "return_id": return_id,
            "refund_type": refund_type,
            "estimated_refund": order["total_amount"],
            "bonus_credit": bonus_credit,
            "instructions": f"Pre-paid FedEx return label emailed to customer. Package can be dropped at any FedEx location or drop box using QR Code {return_id}.",
        }

    elif action == "update_shipping_address":
        new_address = params.get("new_address")
        if not new_address:
            return {"success": False, "error": "New address cannot be empty."}
        if order["status"] != "processing":
            return {
                "success": False,
                "error": f"Cannot modify address on order {order_num} because status is already '{order['status']}'. Carrier reroute must be requested.",
            }
        old_address = order["shipping_address"]
        order["shipping_address"] = new_address
        order["notes"].append(f"Shipping address updated from '{old_address}' to '{new_address}'.")
        return {
            "success": True,
            "action": "update_shipping_address",
            "order_number": order["order_number"],
            "new_address": new_address,
            "message": f"Shipping address for order {order['order_number']} has been successfully updated to {new_address}.",
        }

    elif action == "issue_replacement":
        reason = params.get("reason", "Damaged goods replacement")
        rep_id = f"REP-{datetime.now().strftime('%m%d')}-{order['order_number'][-4:]}"
        order["notes"].append(f"Free replacement order {rep_id} expedited: {reason}.")
        return {
            "success": True,
            "action": "issue_replacement",
            "order_number": order["order_number"],
            "replacement_id": rep_id,
            "shipping_speed": "FedEx Priority Overnight",
            "message": f"Free replacement {rep_id} approved and dispatched via FedEx Priority Overnight. No return of damaged item required.",
        }

    elif action == "issue_courtesy_credit":
        amount = float(params.get("amount", 15.0))
        reason = params.get("reason", "Customer appeasement for shipping delay")
        credit_id = f"CRD-{datetime.now().strftime('%m%d%H%M')}"
        return {
            "success": True,
            "action": "issue_courtesy_credit",
            "credit_id": credit_id,
            "amount": amount,
            "message": f"Appeasement store credit of ${amount:.2f} has been added to customer account: {reason}.",
        }

    return {"success": False, "error": f"Unknown action '{action}'."}
