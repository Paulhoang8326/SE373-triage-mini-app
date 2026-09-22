"""Validated Issue Triage workflow shared by the CLI and Streamlit demos."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, model_validator

COMPONENT_OWNERS = {
    "payment": "checkout-platform",
    "identity": "identity-platform",
    "search": "search-platform",
}
Component = Literal["payment", "identity", "search"]
TriageStatus = Literal["classified", "insufficient_data", "out_of_scope"]
Severity = Literal["P0", "P1", "P2", "P3"]

SYSTEM_PROMPT = """Bạn là kỹ sư phụ trách triage issue phần mềm.

Instruction cố định:
- Phân loại mức độ P0/P1/P2/P3 từ mô tả issue; P0 là nghiêm trọng nhất.
- Nếu thiếu dữ liệu quan trọng, dùng status=insufficient_data thay vì đoán.
- Nếu nội dung không phải issue phần mềm, dùng status=out_of_scope.
- Khi issue thuộc payment, identity hoặc search và cần biết team phụ trách, hãy gọi
  get_component_owner. Không tự tạo owner hoặc tự thực thi tool.
- Sau khi nhận tool result, dùng đúng owner do application trả về.
- Luôn trả lời bằng tiếng Việt ngắn gọn, dựa trên dữ liệu issue.
"""

USER_ISSUE_TEMPLATE = """<issue>
{issue}
</issue>

Hãy triage issue trên. Nếu xác định được một component được hỗ trợ, hãy dùng tool
để tra team phụ trách trước khi đưa ra kết quả cuối cùng.
"""

FUNCTION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_component_owner",
            "description": "Trả team chịu trách nhiệm cho một software component hợp lệ.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "enum": list(COMPONENT_OWNERS),
                        "description": "Component đã được nhận diện từ mô tả issue.",
                    }
                },
                "required": ["component"],
                "additionalProperties": False,
            },
        },
    }
]


class IssueTriage(BaseModel):
    """Validated machine-readable contract used by the application UI."""

    model_config = ConfigDict(extra="forbid")

    status: TriageStatus
    severity: Severity | None = None
    component: Component | None = None
    owner: str | None = None
    needs_urgent_response: bool = False
    reason: str = Field(
        min_length=1,
        description="Lý do ngắn gọn, chỉ dựa trên dữ liệu có trong issue.",
    )

    @model_validator(mode="after")
    def validate_status_fields(self) -> "IssueTriage":
        if self.status == "classified" and self.severity is None:
            raise ValueError("A classified issue must include severity.")
        if self.status != "classified" and self.severity is not None:
            raise ValueError("Only classified issues can include severity.")
        if self.component is None and self.owner is not None:
            raise ValueError("An owner requires a supported component.")
        return self


@dataclass(frozen=True)
class ToolTrace:
    """One validated model request and the application result returned to it."""

    call_id: str
    name: str
    arguments: dict[str, Any]
    result: dict[str, str]


@dataclass(frozen=True)
class TriageResult:
    """Consumer-facing result of one complete Issue Triage run."""

    tool_traces: tuple[ToolTrace, ...]
    triage: IssueTriage


def build_messages(issue: str) -> list[dict[str, str]]:
    """Keep application instructions separate from untrusted user input."""
    cleaned_issue = issue.strip()
    if not cleaned_issue:
        raise ValueError("Issue description must not be empty.")
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_ISSUE_TEMPLATE.format(issue=cleaned_issue)},
    ]


def get_component_owner(component: Component) -> str:
    """Return an owner only for application-approved components."""
    return COMPONENT_OWNERS[component]


def execute_tool_call(name: str, raw_arguments: str) -> dict[str, str]:
    """Validate tool name, JSON shape and semantic values before execution."""
    if name != "get_component_owner":
        raise ValueError(f"Tool is not allowed: {name}")

    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as error:
        raise ValueError("Tool arguments are not valid JSON.") from error
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a JSON object.")
    if set(arguments) != {"component"} or not isinstance(arguments["component"], str):
        raise ValueError("Tool arguments must contain exactly one string: component.")

    component = arguments["component"]
    if component not in COMPONENT_OWNERS:
        raise ValueError(f"Unknown component: {component}")
    return {"component": component, "owner": get_component_owner(component)}


def validate_triage_output(triage: IssueTriage, traces: tuple[ToolTrace, ...]) -> IssueTriage:
    """Ensure a component owner came only from a validated application tool result."""
    if triage.component is None:
        return triage

    matching_trace = next(
        (trace for trace in traces if trace.result["component"] == triage.component),
        None,
    )
    if matching_trace is None:
        raise ValueError("A classified component requires a validated tool result.")
    expected_owner = matching_trace.result["owner"]
    if triage.owner != expected_owner:
        raise ValueError("Model owner does not match the validated tool result.")
    return triage


def triage_issue(client: OpenAI, model: str, issue: str) -> TriageResult:
    """Run tool calling, execute approved calls, then parse Pydantic output."""
    messages: list[Any] = build_messages(issue)
    first_response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=FUNCTION_TOOLS,
        tool_choice="auto",
    )
    assistant_message = first_response.choices[0].message
    messages.append(assistant_message)

    traces: list[ToolTrace] = []
    for tool_call in assistant_message.tool_calls or []:
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as error:
            raise ValueError("Model sent malformed tool arguments.") from error
        if not isinstance(arguments, dict):
            raise ValueError("Model sent tool arguments that are not a JSON object.")

        result = execute_tool_call(tool_call.function.name, tool_call.function.arguments)
        traces.append(
            ToolTrace(
                call_id=tool_call.id,
                name=tool_call.function.name,
                arguments=arguments,
                result=result,
            )
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, ensure_ascii=False),
            }
        )

    final_response = client.beta.chat.completions.parse(
        model=model,
        messages=messages,
        response_format=IssueTriage,
    )
    parsed = final_response.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("Model did not return a structured IssueTriage response.")

    return TriageResult(
        tool_traces=tuple(traces),
        triage=validate_triage_output(parsed, tuple(traces)),
    )
