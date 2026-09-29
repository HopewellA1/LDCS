"""
Turns a student's raw answers into a score for each domain.

Every scorer returns the same small shape so the rest of the app never
has to care which domain it is looking at:

    {
        "score":   <int 0-100>,       # percentage
        "flagged": <bool>,            # True when below PASS_THRESHOLD
        "detail":  [ {"label": ..., "value": ...}, ... ],  # shown to people
    }

The scoring is deliberately simple, rule-based, and explainable — every
number in "detail" says how the score was reached. (A machine-learning
model could later replace these functions without changing anything that
calls them, as long as it returns the same shape.)
"""

from django.utils import timezone

from .content import (
    GRAMMAR_QUESTIONS,
    MATH_QUESTIONS,
    MEMORY_SEQUENCES,
    PASS_THRESHOLD,
    READING_QUESTIONS,
    SCENARIO_QUESTIONS,
    TYPING_SENTENCE,
)
from . import writing_check
from .models import DomainResult, ScreeningSession


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def _percent(part, whole):
    """Turn part-of-whole into a rounded percentage (0 when whole is 0)."""
    if whole == 0:
        return 0
    return round(part / whole * 100)


def _result(score, detail):
    """Build the standard result dict and decide the flag from the score."""
    return {
        "score": score,
        "flagged": score < PASS_THRESHOLD,
        "detail": detail,
    }


def _similarity(target, typed):
    """
    How closely `typed` matches `target`, as a percentage.

    Compares character by character over the longer of the two strings, so
    both wrong letters and a wrong length lower the score.
    """
    length = max(len(target), len(typed)) or 1
    matches = sum(1 for a, b in zip(target, typed) if a == b)
    return _percent(matches, length)


# ---------------------------------------------------------------------------
# One scorer per domain
# ---------------------------------------------------------------------------

def score_math(correct, total=None):
    """Numeracy: straightforward share of correct answers."""
    # `total` is the number of questions actually asked this attempt (questions
    # are now drawn from a larger pool); it falls back to the original length.
    total = total if total is not None else len(MATH_QUESTIONS)
    score = _percent(correct, total)
    detail = [{"label": "Correct answers", "value": f"{correct}/{total}"}]
    return _result(score, detail)


def score_scenario(correct, total=None):
    """Executive function: straightforward share of correct answers."""
    total = total if total is not None else len(SCENARIO_QUESTIONS)
    score = _percent(correct, total)
    detail = [{"label": "Correct answers", "value": f"{correct}/{total}"}]
    return _result(score, detail)


def score_memory(correct, longest, total=None):
    """Working memory: share of digit sequences recalled correctly."""
    total = total if total is not None else len(MEMORY_SEQUENCES)
    score = _percent(correct, total)
    detail = [
        {"label": "Sequences recalled correctly", "value": f"{correct}/{total}"},
        {"label": "Longest correct sequence",
         "value": f"{longest} digits" if longest else "None"},
    ]
    return _result(score, detail)


def score_reading(correct, wpm, total=None):
    """
    Reading fluency: blends comprehension with reading speed.

    - Comprehension is the share of questions answered correctly (weight 70%).
    - Speed is words-per-minute measured against 180 wpm as "full marks",
      capped at 100 (weight 30%).
    """
    total = total if total is not None else len(READING_QUESTIONS)
    comprehension = _percent(correct, total)

    speed = max(0, min(100, round(wpm / 180 * 100)))
    score = round(comprehension * 0.7 + speed * 0.3)

    detail = [
        {"label": "Comprehension accuracy", "value": f"{correct}/{total} ({comprehension}%)"},
        {"label": "Reading speed", "value": f"{wpm} words/min"},
    ]
    return _result(score, detail)


def score_writing(grammar_correct, typed, backspaces, target=None, grammar_total=None):
    """
    Writing & language: blends grammar with a copy-typing task.

    - Grammar is the share of grammar questions correct (weight 50%).
    - Typing is how closely the typed sentence matches the target, minus a
      small penalty for lots of corrections/backspaces (weight 50%).

    `target` is the sentence the student was asked to copy (now drawn from a
    pool) and `grammar_total` is how many grammar questions were asked; both
    fall back to the original fixed values.
    """
    target = target if target is not None else TYPING_SENTENCE
    grammar_total = grammar_total if grammar_total is not None else len(GRAMMAR_QUESTIONS)
    grammar = _percent(grammar_correct, grammar_total)

    accuracy = _similarity(target, typed)
    # Each backspace costs 2 points, capped at 20, so heavy correcting nudges
    # the typing score down without ever dominating it.
    penalty = min(20, backspaces * 2)

    # Run a real language check (spelling + basic grammar) on what was typed.
    # Each issue costs 5 points, capped at 15, so it refines the typing score
    # without ever dominating it. Degrades to zero issues if no checker is set
    # up (see writing_check), so this never breaks the flow.
    language = writing_check.analyze(typed)
    language_penalty = min(15, language["issues"] * 5)

    typing = max(0, accuracy - penalty - language_penalty)

    score = round(grammar * 0.5 + typing * 0.5)

    detail = [
        {"label": "Grammar accuracy", "value": f"{grammar_correct}/{grammar_total} ({grammar}%)"},
        {"label": "Copy-typing accuracy", "value": f"{accuracy}%"},
        {"label": "Corrections made", "value": str(backspaces)},
        {"label": "Language issues found", "value": str(language["issues"])},
    ]
    return _result(score, detail)


# ---------------------------------------------------------------------------
# Saving a whole screening
# ---------------------------------------------------------------------------

def save_session(student, results_by_domain):
    """
    Store a completed screening.

    `results_by_domain` maps a domain key to the dict returned by one of the
    scorers above, e.g.:

        {
            "math":    score_math(4),
            "reading": score_reading(2, 150),
            ...
        }

    Creates one ScreeningSession and one DomainResult per domain, marks the
    session complete, and returns it.
    """
    session = ScreeningSession.objects.create(student=student)

    for domain, result in results_by_domain.items():
        DomainResult.objects.create(
            session=session,
            domain=domain,
            score=result["score"],
            flagged=result["flagged"],
            detail=result["detail"],
        )

    session.completed_at = timezone.now()
    session.save()
    return session
