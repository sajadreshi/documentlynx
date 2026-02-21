"""Evaluation metrics for Doculord question extraction and classification.

Provides scoring functions that compare extracted/classified output against
expected ground-truth values. All scores are normalized to the 0.0-1.0 range.
"""


def score_format_correctness(question_data: dict) -> float:
    """Score how well a single extracted question conforms to the required schema.

    Checks for the presence and validity of the following required fields:
      - question_text  (must be a non-empty string)
      - question_type  (must be a non-empty string)
      - question_number (must be a positive integer)

    Optional fields contribute a bonus but never cause a penalty:
      - options  (dict with at least one key when question_type is multiple_choice)
      - image_urls (list)

    Args:
        question_data: A dictionary representing a single extracted question.

    Returns:
        A float between 0.0 and 1.0 where 1.0 means fully correct format.
    """
    if not isinstance(question_data, dict):
        return 0.0

    required_fields = {
        "question_text": lambda v: isinstance(v, str) and len(v.strip()) > 0,
        "question_type": lambda v: isinstance(v, str) and len(v.strip()) > 0,
        "question_number": lambda v: isinstance(v, int) and v > 0,
    }

    total_weight = len(required_fields)
    earned = 0.0

    for field, validator in required_fields.items():
        value = question_data.get(field)
        if value is not None and validator(value):
            earned += 1.0

    # Bonus points for optional-but-useful fields (up to 0.2 extra, capped at 1.0)
    bonus = 0.0
    bonus_weight = 0.2

    # options present and well-formed for MCQ
    if question_data.get("question_type") == "multiple_choice":
        options = question_data.get("options")
        if isinstance(options, dict) and len(options) > 0:
            bonus += bonus_weight / 2
    else:
        # Non-MCQ questions get the options bonus for free (not applicable)
        bonus += bonus_weight / 2

    # image_urls present as a list
    if isinstance(question_data.get("image_urls"), list):
        bonus += bonus_weight / 2

    raw_score = (earned / total_weight) + bonus
    return min(round(raw_score, 4), 1.0)


def score_completeness(questions: list[dict], expected_count: int) -> float:
    """Score the completeness of question extraction.

    Computes the ratio of successfully extracted questions to the expected
    number. The score is capped at 1.0 (extracting more than expected does
    not yield a bonus -- over-extraction is not penalized here but also not
    rewarded).

    Args:
        questions: List of extracted question dictionaries.
        expected_count: The number of questions that should have been extracted.

    Returns:
        A float between 0.0 and 1.0 where 1.0 means all expected questions
        were extracted.
    """
    if expected_count <= 0:
        return 1.0 if len(questions) == 0 else 0.0

    ratio = len(questions) / expected_count
    return min(round(ratio, 4), 1.0)


def score_classification_accuracy(classification: dict, expected: dict) -> float:
    """Score how accurately a classification matches the expected ground truth.

    Compares the following fields (case-insensitive, stripped):
      - topic        (weight 0.40) -- primary subject area
      - difficulty   (weight 0.25) -- easy / medium / hard
      - question_type (weight 0.20) -- multiple_choice, open_ended, etc.
      - cognitive_level (weight 0.15) -- Bloom's taxonomy level

    Each field is scored as 1.0 (exact match) or 0.0 (mismatch / missing),
    then combined via weighted average.

    Args:
        classification: The classification dict produced by the system.
        expected: The ground-truth classification dict.

    Returns:
        A float between 0.0 and 1.0 where 1.0 means perfect classification.
    """
    if not isinstance(classification, dict) or not isinstance(expected, dict):
        return 0.0

    weights = {
        "topic": 0.40,
        "difficulty": 0.25,
        "question_type": 0.20,
        "cognitive_level": 0.15,
    }

    total_weight = 0.0
    earned = 0.0

    for field, weight in weights.items():
        expected_val = expected.get(field)
        if expected_val is None:
            # Field not specified in ground truth -- skip it and redistribute
            continue

        total_weight += weight
        actual_val = classification.get(field)

        if actual_val is not None:
            # Normalize both values for comparison
            norm_expected = str(expected_val).strip().lower()
            norm_actual = str(actual_val).strip().lower()
            if norm_expected == norm_actual:
                earned += weight

    if total_weight == 0.0:
        return 1.0  # Nothing to compare

    return round(earned / total_weight, 4)
