"""Small reusable helper functions for the consensus app."""

import random
import string


TOTAL_POINTS = 10

# The four evaluation aspects are fixed by the assignment requirements.
EVALUATION_ASPECTS = [
    {"key": "creativity", "label": "創意性"},
    {"key": "feasibility", "label": "可行性"},
    {"key": "practicality", "label": "實用性"},
    {"key": "technical_depth", "label": "技術深度"},
]


def clean_text(text):
    """Remove extra spaces around user input."""
    return text.strip()


def is_blank(text):
    """Return True when text is empty after stripping spaces."""
    return clean_text(text) == ""


def split_multiple_lines(text):
    """Split text by comma or new line, then remove blank items."""
    normalized_text = text.replace("，", ",").replace("\n", ",")
    raw_items = normalized_text.split(",")
    return [clean_text(item) for item in raw_items if not is_blank(item)]


def generate_room_code(length=5):
    """Generate a random room code using uppercase letters and digits."""
    characters = string.ascii_uppercase + string.digits
    return "".join(random.choice(characters) for _ in range(length))


def build_result_rows(results):
    """Convert SQL result tuples into beginner-friendly dictionaries."""
    rows = []

    for result in results:
        idea_title = result[0]
        scores = {
            "creativity": result[1] or 0,
            "feasibility": result[2] or 0,
            "practicality": result[3] or 0,
            "technical_depth": result[4] or 0,
        }
        total_score = sum(scores.values())

        rows.append(
            {
                "project_idea": idea_title,
                "scores": scores,
                "total_score": total_score,
            }
        )

    return rows


def aspect_chart_rows(scores):
    """Create rows for one project's charts and percentage table."""
    total_score = sum(scores.values())
    rows = []

    for aspect in EVALUATION_ASPECTS:
        key = aspect["key"]
        score = scores.get(key, 0)
        if total_score == 0:
            percentage = 0
        else:
            percentage = round(score / total_score * 100, 1)

        rows.append(
            {
                "面向": aspect["label"],
                "總分": score,
                "百分比": percentage,
            }
        )

    return rows
