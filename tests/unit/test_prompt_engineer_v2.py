import pytest

pytestmark = pytest.mark.unit


def test_photo_prompt_contains_face_reference_instruction():
    """
    V2 PromptEngineer must enforce exact face reference usage.
    This is critical for Elina's identity consistency (D-001 psychology-cinematic).
    """
    from agents.prompt_engineer import PromptEngineerAgent

    pe = PromptEngineerAgent()
    prompt = pe.generate_photo_prompt("looking out of a rainy window")

    assert isinstance(prompt, str)
    assert len(prompt) > 20
    # Must contain strict face reference instruction
    assert "STRICT INSTRUCTION: USE EXACT FACE FROM ATTACHED REFERENCE" in prompt
    # Must contain base subject identity
    assert "25-year-old" in prompt or "Iranian" in prompt or "clinical psychologist" in prompt


def test_photo_prompt_reflects_v2_psychology_identity():
    """
    Regression test for D-001: V2 identity is psychology-cinematic, not fashion quiet luxury.
    Ensures prompt reflects V2 identity and does NOT contain legacy fashion phrases.
    """
    from agents.prompt_engineer import PromptEngineerAgent

    pe = PromptEngineerAgent()
    prompt = pe.generate_photo_prompt("sitting at a dark wooden table drinking espresso")
    prompt_lower = prompt.lower()

    # Must reflect V2 psychology-cinematic identity
    has_psychology_identity = (
        "clinical psychologist" in prompt_lower
        or "25-year-old petite iranian" in prompt_lower
        or "psychological fine art photography" in prompt_lower
        or "iranian female" in prompt_lower
    )
    assert has_psychology_identity, f"Prompt should contain V2 psychology identity, got: {prompt[:200]}"

    # Must NOT contain legacy fashion-era phrases (D-001: not fashion)
    assert "quiet luxury" not in prompt_lower, "V2 prompt must NOT contain 'quiet luxury' (legacy fashion)"
    assert "trending tones" not in prompt_lower, "V2 prompt must NOT contain 'trending tones' (legacy fashion)"

    # Should be cinematic, not just fashion
    assert "cinematic" in prompt_lower or "movie still" in prompt_lower or "psychological" in prompt_lower
