"""Keep the UI conversation history separate from the LLM context window."""

from collections.abc import Sequence

from .semantic import ConversationMessage


MAX_LLM_HISTORY_TURNS = 3
MAX_LLM_HISTORY_MESSAGES = MAX_LLM_HISTORY_TURNS * 2


def recent_complete_turns(
    messages: Sequence[ConversationMessage],
) -> tuple[ConversationMessage, ...]:
    """Return the latest complete user/assistant pairs in display order."""

    turns: list[tuple[ConversationMessage, ConversationMessage]] = []
    index = len(messages) - 1
    while index > 0 and len(turns) < MAX_LLM_HISTORY_TURNS:
        user = messages[index - 1]
        assistant = messages[index]
        if user.role == "user" and assistant.role == "assistant":
            turns.insert(0, (user, assistant))
            index -= 2
            continue
        index -= 1

    return tuple(message for turn in turns for message in turn)


__all__ = [
    "MAX_LLM_HISTORY_MESSAGES",
    "MAX_LLM_HISTORY_TURNS",
    "recent_complete_turns",
]
