import pytest

from users_micro.services.gemini_service import gemini_service
from users_micro.schemas.ai_tutor_schemas import TutorTurn


def test_normalise_tutor_turn_payload_basic():
    raw = {
        "narration": "That's right! Now, let's think about what those materials are made of.",
        "comprehension_check": ["Is milk a mixture?"],
        "follow_up_prompts": "What happens if you pour juice into a bowl? | Name a solid.",
        "checkpoint": {
            "required": False,
            "checkpoint_type": "reflection",
            "instructions": "",
            "criteria": []
        },
        "advance_segment": True,
    }

    payload = gemini_service._normalise_tutor_turn_payload(raw)

    # Should coerce comprehension_check to string or None
    assert payload["comprehension_check"] is None or isinstance(payload["comprehension_check"], str)

    # Should split follow ups into a list of strings
    assert isinstance(payload["follow_up_prompts"], list)
    assert all(isinstance(x, str) for x in payload["follow_up_prompts"]) \
        or payload["follow_up_prompts"] == []

    # Non-required checkpoint should be omitted
    assert payload["checkpoint"] is None

    # It must be possible to construct a TutorTurn from normalised payload
    _ = TutorTurn(**payload)


def test_normalise_tutor_turn_payload_with_checkpoint():
    raw = {
        "narration": "Take a photo of a solid and a liquid.",
        "comprehension_check": None,
        "follow_up_prompts": ["What is a gas?"],
        "checkpoint": {
            "required": True,
            "checkpoint_type": "photo",
            "instructions": "Take a photo showing a solid and a liquid.",
            "criteria": [
                "Shows a solid",
                "Shows a liquid in a container"
            ]
        },
        "advance_segment": False,
    }

    payload = gemini_service._normalise_tutor_turn_payload(raw)

    # Required checkpoint should be preserved and well-formed
    cp = payload["checkpoint"]
    assert isinstance(cp, dict)
    assert cp["required"] is True
    assert cp["checkpoint_type"] in {"photo", "reflection", "quiz"}
    assert isinstance(cp["instructions"], str) and cp["instructions"].strip() != ""

    # TutorTurn model should accept the payload
    _ = TutorTurn(**payload)
