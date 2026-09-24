"""Unit tests for e-commerce customer support policies and order operations."""

import unittest
from datetime import datetime

from order_directory import (
    execute_order_mutation,
    get_customer_orders,
    lookup_customer,
    lookup_order,
    normalize_order_number,
)
from policies import validate_order_eligibility

REFERENCE_DATE = datetime(2026, 9, 20)


class TestSupportPolicies(unittest.TestCase):

    def test_order_number_normalization(self):
        self.assertEqual(normalize_order_number("ORD-88219"), "ORD-88219")
        self.assertEqual(normalize_order_number("ord 88219"), "ORD-88219")
        self.assertEqual(normalize_order_number("88219"), "ORD-88219")
        self.assertEqual(normalize_order_number("order-88219"), "ORD-88219")

    def test_customer_lookup(self):
        sarah = lookup_customer("Sarah Jenkins")
        self.assertIsNotNone(sarah)
        self.assertEqual(sarah["customer_id"], "CUST-1001")
        self.assertEqual(sarah["loyalty_tier"], "Gold VIP")

        cust_by_email = lookup_customer("marcus.vance@example.com")
        self.assertIsNotNone(cust_by_email)
        self.assertEqual(cust_by_email["full_name"], "Marcus Vance")

        cust_by_phone = lookup_customer("206-555-0173")
        self.assertIsNotNone(cust_by_phone)
        self.assertEqual(cust_by_phone["full_name"], "Elena Rostova")

    def test_customer_orders_retrieval(self):
        orders = get_customer_orders("CUST-1001")
        self.assertGreaterEqual(len(orders), 3)
        order_nums = [o["order_number"] for o in orders]
        self.assertIn("ORD-88219", order_nums)
        self.assertIn("ORD-94301", order_nums)
        self.assertIn("ORD-71042", order_nums)

    def test_return_within_window_eligibility(self):
        # ORD-88219 was delivered on 2026-09-17 (3 days ago relative to Sep 20)
        order = lookup_order("ORD-88219")
        self.assertIsNotNone(order)
        res = validate_order_eligibility(order, "request_return", today=REFERENCE_DATE)
        self.assertTrue(res["is_within_return_window"])
        self.assertEqual(res["days_since_delivery"], 3)
        self.assertEqual(len(res["blockers"]), 0)

    def test_return_expired_window_eligibility(self):
        # ORD-71042 was delivered on 2026-07-16 (66 days ago)
        order = lookup_order("ORD-71042")
        self.assertIsNotNone(order)
        res = validate_order_eligibility(order, "request_return", today=REFERENCE_DATE)
        self.assertFalse(res["is_within_return_window"])
        self.assertGreater(res["days_since_delivery"], 30)
        self.assertTrue(any("expired" in b.lower() for b in res["blockers"]))

    def test_order_cancellation_processing_order(self):
        # ORD-33018 is in processing status
        order = lookup_order("ORD-33018")
        self.assertIsNotNone(order)
        res = validate_order_eligibility(order, "order_cancellation", today=REFERENCE_DATE)
        self.assertTrue(res["is_cancellable"])

        # Perform actual cancellation mutation
        mutation = execute_order_mutation("cancel_order", {"order_number": "ORD-33018"})
        self.assertTrue(mutation["success"])
        self.assertEqual(mutation["refund_amount"], 349.00)

        # Check updated order state
        updated = lookup_order("ORD-33018")
        self.assertEqual(updated["status"], "cancelled")

    def test_order_cancellation_shipped_order_rejected(self):
        # ORD-88219 is delivered, should NOT be cancellable
        order = lookup_order("ORD-88219")
        res = validate_order_eligibility(order, "order_cancellation", today=REFERENCE_DATE)
        self.assertFalse(res["is_cancellable"])

        mutation = execute_order_mutation("cancel_order", {"order_number": "ORD-88219"})
        self.assertFalse(mutation["success"])
        self.assertIn("cannot cancel", mutation["error"].lower())

    def test_damaged_item_replacement_under_150(self):
        # ORD-62184 dinnerware total is $118 (< $150 threshold)
        order = lookup_order("ORD-62184")
        self.assertIsNotNone(order)
        res = validate_order_eligibility(order, "complaint_damaged", today=REFERENCE_DATE)
        self.assertTrue(res["is_replacement_eligible"])

        mutation = execute_order_mutation("issue_replacement", {"order_number": "ORD-62184", "reason": "Shattered plates"})
        self.assertTrue(mutation["success"])
        self.assertIn("REP-", mutation["replacement_id"])


if __name__ == "__main__":
    unittest.main()
