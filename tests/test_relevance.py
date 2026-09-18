from elise_memory.relevance import ConversationMemoryRequest, context_keys_for_conversation


def test_relevance_is_explicit_ordered_and_deduplicated():
    result = context_keys_for_conversation(
        ConversationMemoryRequest(
            house_keys=["preferred_name", "kitchen_light", "preferred_name"],
            temporal_keys=["current_topic", "current_topic"],
        )
    )

    assert [(item.kind, item.key) for item in result] == [
        ("house", "preferred_name"),
        ("house", "kitchen_light"),
        ("temporal", "current_topic"),
    ]


def test_relevance_does_not_infer_or_expand_keys():
    result = context_keys_for_conversation(
        ConversationMemoryRequest(house_keys=["lamp_salon"])
    )

    assert [(item.kind, item.key) for item in result] == [("house", "lamp_salon")]
