from app.policy_rag import PolicyRAG


def test_policy_rag_indexed():
    rag = PolicyRAG()

    assert rag.is_indexed() is True


def test_policy_rag_room_rent_retrieval():
    rag = PolicyRAG()

    results = rag.retrieve(
        query="What is the room rent limit?",
        top_k=3,
    )

    assert len(results) > 0

    combined = "\n".join(
        result.get("content", "")
        for result in results
    ).lower()

    assert "room rent" in combined
    assert "1 percent" in combined


def test_policy_rag_waiting_period_retrieval():
    rag = PolicyRAG()

    results = rag.retrieve(
        query="What is the waiting period?",
        top_k=3,
    )

    assert len(results) > 0

    combined = "\n".join(
        result.get("content", "")
        for result in results
    ).lower()

    assert "waiting period" in combined