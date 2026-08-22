"""Gemini function-calling loop for the travel chatbot."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from chatbot.rag.rag_chain import get_chat_model, normalize_answer
from chatbot.tools.mapbox_client import MapboxToolClient
from chatbot.tools.models import ChatSource
from chatbot.tools.registry import ToolExecution, ToolRegistry
from chatbot.tools.rag_tool import SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME


SYSTEM_PROMPT = """Bạn là trợ lý du lịch tiếng Việt sử dụng các tool được cung cấp.

Quy tắc bắt buộc:
- Knowledge Base đã được backend truy vấn mặc định và đặt trong RAG context trước câu hỏi người dùng; không gọi lại search_travel_knowledge bằng function calling.
- Nếu RAG context có thông tin liên quan, phải ưu tiên sử dụng thông tin đó để trả lời và không được mâu thuẫn với nó.
- RAG context không bắt buộc phải đủ 100%. Khi context thiếu hoặc không liên quan, được dùng thêm kiến thức đáng tin cậy của mô hình để giải thích, tư vấn và hoàn thiện câu trả lời; không bịa thông tin khi không chắc chắn.
- Không nhắc đến các thuật ngữ kỹ thuật như RAG, context, chunk hay tên tool trong câu trả lời cho người dùng.
- Dùng các Mapbox tool cho địa điểm, địa chỉ, POI, category hoặc tọa độ.
- Phân biệt rõ hai kiểu tìm Mapbox: chỉ dùng mapbox_forward_search khi người dùng nêu tên riêng, địa chỉ hoặc một POI cụ thể; không đưa nguyên câu hỏi tư vấn, cảm xúc, mùa hay thời điểm vào q.
- Khi người dùng hỏi mở như "nên đi đâu", mô tả hoạt động, không khí hoặc thời điểm mong muốn, phải chọn địa điểm theo ngữ nghĩa: gọi mapbox_list_categories, đọc danh sách trả về, chọn đúng 3 canonical category_id khác nhau và phù hợp nhất với ý định chính, rồi gọi mapbox_category_search một lần cho từng category đã chọn.
- Với kết quả của mỗi mapbox_category_search, chỉ chọn và hiển thị POI có rating lớn hơn 4.0 khi Mapbox thực sự cung cấp rating trong feature tương ứng của rawResponse. Không tự tạo rating; nếu Mapbox không cung cấp rating hoặc không có POI nào đạt điều kiện, phải nói rõ là chưa tìm thấy kết quả đủ điều kiện.
- Chọn category theo ý định chính, không theo từ khóa phụ. Ví dụ "chill, lãng mạn, đi chơi buổi đêm" ưu tiên nhóm giải trí ban đêm, bar, nhạc sống, quán cà phê hoặc điểm ngắm cảnh nếu các category đó có trong kết quả; không chọn cửa hàng, siêu thị, cửa hàng thực phẩm hay nhà hàng nếu người dùng không hỏi mua sắm hoặc ăn uống.
- Các cụm chỉ mùa như "mùa thu" là bối cảnh để tư vấn và trình bày, không phải lý do chọn category cửa hàng hoa hay cửa hàng thực phẩm.
- category_id phải đúng một canonicalId có trong kết quả mapbox_list_categories gần nhất. Giữ địa danh người dùng nêu ở bộ lọc near của mapbox_category_search, không biến địa danh đó thành loại hình trải nghiệm.
- Có thể gọi nhiều tool tuần tự khi câu hỏi cần kết hợp Knowledge Base và dữ liệu địa điểm.
- Có thể bổ sung kiến thức phổ biến về địa điểm từ mô hình, nhưng địa chỉ cụ thể, tọa độ, giờ mở cửa, số điện thoại, website và dữ liệu có thể thay đổi phải lấy từ tool result; không tự tạo các chi tiết này.
- Nếu tool báo arguments không hợp lệ, sửa arguments và thử lại khi còn lượt.
- Nếu không tìm thấy dữ liệu, nói rõ là chưa tìm thấy; không suy đoán.
- Khi hiển thị các địa điểm tìm được từ Mapbox, hãy trình bày từng địa điểm riêng và luôn kèm địa chỉ đầy đủ nếu có.
- Với mỗi địa điểm, ưu tiên địa chỉ từ results[].fullAddress. Đọc giờ mở cửa, phone và website từ feature tương ứng trong rawResponse, bao gồm properties và properties.metadata.
- Giờ mở cửa phải được rút gọn, dễ đọc, ví dụ "07:00–22:00" hoặc "T2–CN: 07:00–22:00", nhưng phải giữ đúng dữ liệu tool cung cấp.
- Chỉ hiển thị dòng Giờ mở cửa, Điện thoại hoặc Website khi field tương ứng thực sự có giá trị; không tự suy đoán và không ghi nội dung thay thế như "không có thông tin".
- Trả lời bằng tiếng Việt, tự nhiên, sáng tạo và plain text; không dùng bảng hoặc Markdown phức tạp.
"""

RAG_CONTEXT_TEMPLATE = """Đây là kết quả Knowledge Base đã được truy vấn tự động cho câu hỏi hiện tại.
Hãy dùng nội dung này làm nguồn ưu tiên nếu nó liên quan. Nếu nội dung trống, thiếu hoặc không liên quan, hãy bỏ qua phần không phù hợp và dùng thêm kiến thức đáng tin cậy của mô hình.
Không nhắc đến Knowledge Base, RAG context hoặc JSON trong câu trả lời.

Kết quả truy vấn:
{rag_result}
"""

RAG_UNAVAILABLE_CONTEXT = """Knowledge Base tạm thời không truy xuất được cho câu hỏi hiện tại. Hãy tiếp tục trả lời bằng kiến thức đáng tin cậy của mô hình và các Mapbox tool nếu phù hợp; không thông báo lỗi kỹ thuật này cho người dùng."""

FINAL_SYNTHESIS_INSTRUCTION = """Hãy trả lời câu hỏi ban đầu ngay bây giờ. Ưu tiên RAG context và các tool result đã có, đồng thời có thể bổ sung kiến thức đáng tin cậy của mô hình khi các nguồn đó chưa đủ. Không gọi thêm tool, không bịa thông tin, tuân thủ quy tắc hiển thị chi tiết địa điểm trong system prompt và dùng plain text tiếng Việt."""

TOOL_BUDGET_ERROR = "tool_budget_exceeded"


class ToolInfrastructureError(RuntimeError):
    """Raised when every requested tool failed for infrastructure reasons."""


@dataclass(frozen=True)
class ChatOrchestratorResult:
    answer: str
    sources: list[ChatSource]


class ChatOrchestrator:
    """Run Gemini tool decisions until it returns text or exhausts the budget."""

    def __init__(
        self,
        chat_model: Any,
        registry: ToolRegistry,
        *,
        max_tool_calls: int | None = None,
    ) -> None:
        resolved_max_calls = (
            settings.CHATBOT_MAX_TOOL_CALLS
            if max_tool_calls is None
            else max_tool_calls
        )
        if isinstance(resolved_max_calls, bool) or not isinstance(
            resolved_max_calls,
            int,
        ):
            raise ValueError("max_tool_calls must be an integer")
        if resolved_max_calls <= 0:
            raise ValueError("max_tool_calls must be greater than zero")

        self._chat_model = chat_model
        mapbox_tools = [
            tool
            for tool in registry.langchain_tools
            if tool.name != SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME
        ]
        self._tool_model = chat_model.bind_tools(mapbox_tools)
        self._registry = registry
        self._max_tool_calls = resolved_max_calls

    def answer(self, question: str) -> ChatOrchestratorResult:
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("question must not be empty")

        executions: list[ToolExecution] = []
        sources: list[ChatSource] = []
        source_keys: set[str] = set()
        executed_calls = 0

        rag_execution = self._registry.execute(
            SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME,
            {"query": cleaned_question},
        )
        self._append_unique_sources(
            rag_execution.sources,
            sources,
            source_keys,
        )
        messages: list[Any] = [
            SystemMessage(content=SYSTEM_PROMPT),
            SystemMessage(content=self._rag_context_content(rag_execution)),
            HumanMessage(content=cleaned_question),
        ]

        while True:
            response = self._invoke_ai_message(self._tool_model, messages)
            self._print_function_calling_response(response)
            messages.append(response)
            tool_calls = response.tool_calls

            if not tool_calls:
                self._raise_if_all_tools_had_system_failures(executions)
                return ChatOrchestratorResult(
                    answer=self._normalized_response_text(response),
                    sources=sources,
                )

            budget_exhausted = False
            for tool_call in tool_calls:
                call_id = str(
                    tool_call.get("id")
                    or f"tool-call-{executed_calls + 1}"
                )
                name = str(tool_call.get("name") or "")

                if executed_calls >= self._max_tool_calls:
                    messages.append(
                        ToolMessage(
                            content=self._budget_error_content(),
                            tool_call_id=call_id,
                            name=name or None,
                            status="error",
                        )
                    )
                    budget_exhausted = True
                    continue

                executed_calls += 1
                execution = self._registry.execute(name, tool_call.get("args", {}))
                executions.append(execution)
                self._append_unique_sources(
                    execution.sources,
                    sources,
                    source_keys,
                )
                messages.append(
                    ToolMessage(
                        content=execution.content,
                        tool_call_id=call_id,
                        name=name or None,
                        status="success" if execution.success else "error",
                    )
                )

            if executed_calls >= self._max_tool_calls or budget_exhausted:
                self._raise_if_all_tools_had_system_failures(executions)
                final_messages = [
                    *messages,
                    HumanMessage(content=FINAL_SYNTHESIS_INSTRUCTION),
                ]
                final_response = self._invoke_ai_message(
                    self._chat_model,
                    final_messages,
                )
                return ChatOrchestratorResult(
                    answer=self._normalized_response_text(final_response),
                    sources=sources,
                )

    @staticmethod
    def _invoke_ai_message(model: Any, messages: list[Any]) -> AIMessage:
        response = model.invoke(messages)
        if not isinstance(response, AIMessage):
            raise RuntimeError("Gemini returned an unsupported response type")
        return response

    @staticmethod
    def _print_function_calling_response(response: AIMessage) -> None:
        """Print only Gemini's bound-model response, never the request messages."""
        response_json = json.dumps(
            response.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        output = f"Gemini function-calling response:\n{response_json}\n"
        stdout_buffer = getattr(sys.stdout, "buffer", None)
        if stdout_buffer is not None:
            stdout_buffer.write(output.encode("utf-8"))
            stdout_buffer.flush()
            return
        print(output, end="", flush=True)

    @staticmethod
    def _rag_context_content(execution: ToolExecution) -> str:
        if not execution.success:
            return RAG_UNAVAILABLE_CONTEXT
        return RAG_CONTEXT_TEMPLATE.format(rag_result=execution.content)

    @staticmethod
    def _normalized_response_text(response: AIMessage) -> str:
        answer = response.text.strip()
        if not answer:
            raise RuntimeError("Gemini returned an empty answer")
        normalized = normalize_answer(answer)
        if not normalized:
            raise RuntimeError("Gemini returned an empty answer")
        return normalized

    @staticmethod
    def _append_unique_sources(
        new_sources: tuple[ChatSource, ...],
        sources: list[ChatSource],
        source_keys: set[str],
    ) -> None:
        for source in new_sources:
            source_key = source.model_dump_json()
            if source_key in source_keys:
                continue
            source_keys.add(source_key)
            sources.append(source)

    @staticmethod
    def _raise_if_all_tools_had_system_failures(
        executions: list[ToolExecution],
    ) -> None:
        if (
            executions
            and not any(execution.success for execution in executions)
            and all(execution.system_failure for execution in executions)
        ):
            raise ToolInfrastructureError(
                "All requested tools failed because of infrastructure errors."
            )

    @staticmethod
    def _budget_error_content() -> str:
        return json.dumps(
            {
                "success": False,
                "data": None,
                "errorCode": TOOL_BUDGET_ERROR,
                "errorMessage": "Đã đạt giới hạn số lần gọi tool.",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )


def orchestrate_chat(
    question: str,
    *,
    chat_model: Any | None = None,
    registry: ToolRegistry | None = None,
    max_tool_calls: int | None = None,
) -> ChatOrchestratorResult:
    """Run one stateless chatbot request and close owned HTTP resources."""
    active_model = chat_model or get_chat_model()
    if registry is not None:
        return ChatOrchestrator(
            active_model,
            registry,
            max_tool_calls=max_tool_calls,
        ).answer(question)

    with MapboxToolClient() as mapbox_client:
        active_registry = ToolRegistry(mapbox_client)
        return ChatOrchestrator(
            active_model,
            active_registry,
            max_tool_calls=max_tool_calls,
        ).answer(question)


__all__ = [
    "ChatOrchestrator",
    "ChatOrchestratorResult",
    "RAG_CONTEXT_TEMPLATE",
    "SYSTEM_PROMPT",
    "ToolInfrastructureError",
    "orchestrate_chat",
]
