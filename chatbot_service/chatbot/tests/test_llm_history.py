from chatbot.llm_history import recent_complete_turns
from chatbot.semantic import ConversationMessage


def test_recent_complete_turns_keeps_only_latest_three_pairs():
    messages = [
        ConversationMessage(role="user", content=f"Q{index}")
        if index % 2 == 1
        else ConversationMessage(role="assistant", content=f"A{index // 2}")
        for index in range(1, 9)
    ]

    result = recent_complete_turns(messages)

    assert [(item.role, item.content) for item in result] == [
        ("user", "Q3"),
        ("assistant", "A2"),
        ("user", "Q5"),
        ("assistant", "A3"),
        ("user", "Q7"),
        ("assistant", "A4"),
    ]


def test_recent_complete_turns_ignores_pending_user_message():
    messages = [
        ConversationMessage(role="user", content="Q1"),
        ConversationMessage(role="assistant", content="A1"),
        ConversationMessage(role="user", content="Pending"),
    ]

    assert recent_complete_turns(messages) == (
        ConversationMessage(role="user", content="Q1"),
        ConversationMessage(role="assistant", content="A1"),
    )
