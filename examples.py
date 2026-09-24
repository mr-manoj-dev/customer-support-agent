"""Curated test prompts and demo scenarios for E-Commerce Customer Support."""

# 1. Real-time Out-for-Delivery & Transit Check
OUT_FOR_DELIVERY_CHECK = """
Hi, this is Sarah Jenkins. I'm checking on my coffee order ORD-94301. When is it arriving today and where is the courier right now?
""".strip()

# 2. Return Request within 30-Day Window (Headphones)
RETURN_WITHIN_WINDOW = """
Hi, I'm Sarah Jenkins. I received my AuraWave headphones on order ORD-88219 three days ago. They don't fit comfortably over my ears, so I'd like to initiate a return.
""".strip()

# 3. Damaged Item Complaint with Camera Inspection (Dinnerware)
DAMAGED_ITEM_CAMERA_INSPECTION = """
Hello, my name is Marcus Vance, order ORD-62184. My ceramic dinnerware set arrived yesterday, but when I opened the box, two of the bowls and a plate were shattered. Can I show you on camera to get a replacement?
""".strip()

# 4. Pre-Delivery Order Cancellation (Chair in Processing)
PRE_DELIVERY_CANCELLATION = """
Hi, Elena Rostova here. I placed order ORD-33018 this morning for an ergonomic desk chair, but I realized I ordered the wrong color. Can you cancel the order and issue a refund before it ships?
""".strip()

# 5. Pre-Delivery Shipping Address Update
PRE_DELIVERY_ADDRESS_UPDATE = """
Hello, this is Elena Rostova regarding my chair order ORD-33018. Before it leaves the warehouse, can you update the delivery address to 1200 4th Ave, Seattle WA 98101?
""".strip()

# 6. Post-Return Window Expired (>30 Days) Warranty Inquiry
POST_RETURN_WINDOW_WARRANTY = """
Hi, Sarah Jenkins again regarding order ORD-71042. My RoboClean vacuum cleaner stopped charging yesterday. I bought it in July so I know it's past the 30-day return window, but what are my warranty or repair options?
""".strip()

# 7. Missing Item from Delivered Package Complaint
MISSING_ITEM_COMPLAINT = """
Hi, this is Aisha Patel. I received my apparel order ORD-77621 yesterday. The box contained the denim and leather belt, but the cashmere sweater was missing! Can you send a replacement right away?
""".strip()

# 8. Delivered Package Not Found (Porch Theft / Misdelivery)
LOST_PACKAGE_MISDELIVERY = """
Hi, David Kim here. My tracking for order ORD-44912 says my 4K monitor was delivered to my front porch two hours ago, but I've searched the whole porch and building and it's not here. Can you help me track it down?
""".strip()

# 9. Delayed Transit Weather Exception
TRANSIT_DELAY_WEATHER = """
Marcus Vance here. My parka order ORD-51920 was supposed to arrive two days ago and the tracking says exception in Chicago. Can you check what happened to the transit?
""".strip()

DEMO_SCENARIOS = {
    "out_for_delivery_check": {
        "title": "Delivery Status & Live ETA",
        "customer": "Sarah Jenkins",
        "order": "ORD-94301",
        "prompt": OUT_FOR_DELIVERY_CHECK,
        "description": "Checks live courier status (3 stops away), ETA window (1-3 PM), and transit milestones.",
    },
    "return_within_window": {
        "title": "Return within 30-Day Window",
        "customer": "Sarah Jenkins",
        "order": "ORD-88219",
        "prompt": RETURN_WITHIN_WINDOW,
        "description": "Checks 30-day window, offers instant store credit +10% bonus, and issues pre-paid return label.",
    },
    "damaged_item_inspection": {
        "title": "Damaged Item (Live Camera Inspection)",
        "customer": "Marcus Vance",
        "order": "ORD-62184",
        "prompt": DAMAGED_ITEM_CAMERA_INSPECTION,
        "description": "Agent inspects damaged stoneware on camera, pins photo to ticket, and auto-approves free replacement.",
    },
    "pre_delivery_cancellation": {
        "title": "Cancel Unshipped Order",
        "customer": "Elena Rostova",
        "order": "ORD-33018",
        "prompt": PRE_DELIVERY_CANCELLATION,
        "description": "Cancels processing order ORD-33018 and triggers full instant refund.",
    },
    "post_return_warranty": {
        "title": "Expired Return Window (>30 Days)",
        "customer": "Sarah Jenkins",
        "order": "ORD-71042",
        "prompt": POST_RETURN_WINDOW_WARRANTY,
        "description": "Explains 30-day return policy and connects customer to 1-year manufacturer warranty claims.",
    },
    "missing_item_complaint": {
        "title": "Missing Item in Delivery Box",
        "customer": "Aisha Patel",
        "order": "ORD-77621",
        "prompt": MISSING_ITEM_COMPLAINT,
        "description": "Logs missing cashmere sweater complaint and authorizes priority reshipment.",
    },
    "lost_package_tracer": {
        "title": "Marked Delivered But Missing",
        "customer": "David Kim",
        "order": "ORD-44912",
        "prompt": LOST_PACKAGE_MISDELIVERY,
        "description": "Opens carrier investigation tracer for porch misdelivery on $550 display.",
    },
}
