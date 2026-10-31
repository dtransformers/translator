"""Complexity scoring must spread plain text across the range so routing can reach the LLM."""
import pytest

from app.core.config import settings
from app.pipeline import complexity
from app.pipeline.translation import routes_to_llm

# Raw readability regression outputs measured from v-urushkin/xlm-roberta-base-readability
# (higher = easier to read).
MEASURED_READABILITY = {
    "Thank you for dining with us tonight.": 0.118,
    "The cat sat on the mat. It was happy.": 0.690,
    "Notwithstanding the foregoing, the licensee shall indemnify the licensor "
    "against any and all liabilities arising hereunder.": -1.426,
    "Our omnichannel CDP leverages first-party data to orchestrate "
    "hyper-personalized, attribution-driven retention funnels.": -2.652,
}
SIMPLE = ["Thank you for dining with us tonight.", "The cat sat on the mat. It was happy."]
HARD = [t for t in MEASURED_READABILITY if t not in SIMPLE]


@pytest.fixture(autouse=True)
def measured_readability(mocker):
    complexity._cache.clear()
    mocker.patch.object(complexity, "_load_models")
    mocker.patch.object(complexity, "_readability_raw", side_effect=lambda text: MEASURED_READABILITY.get(text))
    # Keep the LLM tiebreaker out of these tests: it needs a live provider
    mocker.patch.object(complexity, "_get_llm_fallback_score", side_effect=lambda text, score: score)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", HARD)
async def test_hard_plain_text_routes_to_llm(text):
    score = await complexity.calculate_complexity_score(text)
    assert score >= settings.COMPLEXITY_THRESHOLD
    assert routes_to_llm(text, score)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", SIMPLE)
async def test_simple_text_stays_on_machine_translation(text):
    score = await complexity.calculate_complexity_score(text)
    assert score < settings.COMPLEXITY_THRESHOLD
    assert not routes_to_llm(text, score)


@pytest.mark.asyncio
async def test_harder_readability_means_higher_score():
    scores = [await complexity.calculate_complexity_score(t) for t in sorted(MEASURED_READABILITY, key=MEASURED_READABILITY.get, reverse=True)]
    assert scores == sorted(scores)


def test_readability_points_cover_full_band():
    assert complexity._readability_points(1.0) == 0
    assert complexity._readability_points(-3.0) == complexity.READABILITY_MAX_POINTS
    assert complexity._readability_points(5.0) == 0
    assert complexity._readability_points(-9.0) == complexity.READABILITY_MAX_POINTS
    assert complexity._readability_points(None) == 0
