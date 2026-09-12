"""
Fake LLM test double — used throughout the Gate 4 agent tests because this sandbox's
network egress cannot reach Google's Gemini API (see app/agents/llm_client.py's
docstring for the full explanation). Mimics exactly the two calls agents make:
`llm.with_structured_output(schema)` and the resulting runnable's `.ainvoke(messages)`,
which returns a canned Pydantic instance (or raises, for failure-path tests).

These tests prove the agents' OWN logic (deterministic-rules-first, retries, structured
validation, AgentExecution logging) is correct. They do NOT prove the real Gemini
integration works — that requires a real GOOGLE_API_KEY and a manual smoke test.
"""


class _FakeStructuredRunnable:
    def __init__(self, canned_result=None, raise_exc=None):
        self._canned = canned_result
        self._raise_exc = raise_exc

    async def ainvoke(self, messages):
        if self._raise_exc:
            raise self._raise_exc
        return self._canned


class FakeLLM:
    def __init__(self, canned_result=None, raise_exc=None):
        self._canned = canned_result
        self._raise_exc = raise_exc

    def with_structured_output(self, schema):
        return _FakeStructuredRunnable(self._canned, self._raise_exc)


class FakeEmbedder:
    """
    Deterministic fake embedder for tests: maps text containing certain known keywords to
    fixed vectors, so Chroma's cosine-distance-based classification (matched/weak/missing
    in app/agents/skill_gap.py) can be tested predictably without a real embedding model.
    This sandbox cannot reach Google's embedding API — see app/retrieval/embeddings.py.

    Vectors are chosen so, against Chroma's cosine distance:
    - "python" vs "python" -> distance 0.0 -> MATCHED (<= MATCH_THRESHOLD 0.25)
    - "python" vs "django" -> distance ~0.35 -> WEAK (> 0.25, <= WEAK_THRESHOLD 0.45)
    - "python" vs "aws" -> distance 1.0 (orthogonal) -> MISSING (> 0.45)
    - anything unrecognized -> the default vector, also orthogonal to every bucket -> MISSING
    These exact distance values are asserted directly in tests/test_vector_store.py so a
    change to this fake (or to Chroma's distance formula) is caught, not silently assumed.
    """

    _BUCKETS = {
        "python": [1.0, 0.0, 0.0, 0.0],
        "django": [0.65, 0.76, 0.0, 0.0],
        "aws": [0.0, 0.0, 1.0, 0.0],
    }
    _DEFAULT = [0.0, 0.0, 0.0, 1.0]

    def _vector_for(self, text: str) -> list[float]:
        lowered = text.lower()
        for keyword, vector in self._BUCKETS.items():
            if keyword in lowered:
                return vector
        return self._DEFAULT

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector_for(t) for t in texts]

    async def aembed_query(self, text: str) -> list[float]:
        return self._vector_for(text)
