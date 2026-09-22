"""Offline regression tests for validation and application-controlled tool use."""

from __future__ import annotations

import json
import unittest

from pydantic import ValidationError

from triage_workflow import IssueTriage, ToolTrace, build_messages, execute_tool_call, validate_triage_output


class TriageWorkflowTests(unittest.TestCase):
    def test_prompt_keeps_instruction_and_input_separate(self) -> None:
        messages = build_messages("Lỗi đăng nhập HTTP 503")
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("<issue>\nLỗi đăng nhập HTTP 503\n</issue>", messages[1]["content"])

    def test_tool_accepts_approved_component(self) -> None:
        result = execute_tool_call(
            "get_component_owner",
            json.dumps({"component": "payment"}),
        )
        self.assertEqual(result, {"component": "payment", "owner": "checkout-platform"})

    def test_tool_rejects_unknown_component(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown component"):
            execute_tool_call(
                "get_component_owner",
                json.dumps({"component": "billing"}),
            )

    def test_schema_requires_severity_for_classified_issue(self) -> None:
        with self.assertRaises(ValidationError):
            IssueTriage(status="classified", reason="Thiếu severity")

    def test_application_rejects_owner_not_returned_by_tool(self) -> None:
        triage = IssueTriage(
            status="classified",
            severity="P0",
            component="payment",
            owner="wrong-team",
            needs_urgent_response=True,
            reason="Thanh toán lỗi toàn bộ.",
        )
        trace = ToolTrace(
            call_id="call-1",
            name="get_component_owner",
            arguments={"component": "payment"},
            result={"component": "payment", "owner": "checkout-platform"},
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_triage_output(triage, (trace,))


if __name__ == "__main__":
    unittest.main()
