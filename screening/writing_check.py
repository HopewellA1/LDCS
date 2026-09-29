"""
Lightweight language check for the writing test.

It looks at what the student typed and returns a count of likely language
issues (misspellings and a few basic grammar slips), plus a couple of example
messages. That count feeds a small part of the writing score and is shown in
the results breakdown - a genuine, if simple, bit of NLP.

Backends, in order of preference:

  1. LanguageTool (via `language_tool_python`) - the strongest checker, but it
     needs Java installed. Only used when the USE_LANGUAGETOOL environment
     variable is set, so we never accidentally try to start Java or hit the
     network during a request.
  2. pyspellchecker - pure Python, offline, no Java. This is the default.
  3. Nothing installed - the check simply returns zero issues, so the writing
     test still works exactly as before.

Everything is wrapped so a checker problem can never break the screening flow.
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

# Built once and reused (loading the dictionary is a little expensive).
_SPELL = None
_SPELL_TRIED = False


def _basic_grammar_issues(text):
    """
    A few cheap, dependency-free grammar/style checks. Returns a list of short
    messages. These are deliberately simple - they catch obvious slips without
    pretending to be a full grammar engine.
    """
    messages = []
    stripped = text.strip()
    if not stripped:
        return messages

    # Sentence should start with a capital letter.
    if stripped[0].islower():
        messages.append("Sentence does not start with a capital letter.")
    # Sentence should end with . ! or ?
    if stripped[-1] not in ".!?":
        messages.append("Sentence is missing end punctuation.")
    # Doubled spaces.
    if "  " in text:
        messages.append("Contains double spaces.")
    # A word repeated back-to-back ("the the").
    if re.search(r"\b(\w+)\s+\1\b", text, flags=re.IGNORECASE):
        messages.append("Contains a repeated word.")
    # Space before punctuation ("word ,").
    if re.search(r"\s[,.!?;:]", text):
        messages.append("Space before a punctuation mark.")
    return messages


def _get_spell():
    """Load pyspellchecker once, or return None if it is not installed."""
    global _SPELL, _SPELL_TRIED
    if _SPELL_TRIED:
        return _SPELL
    _SPELL_TRIED = True
    try:
        from spellchecker import SpellChecker
        spell = SpellChecker()
        # Teach it the exact vocabulary of the copy-typing task. These are real
        # words (e.g. "assistive", "accommodations") that the default dictionary
        # does not always know; without this a perfectly correct copy would be
        # unfairly flagged. Only genuinely introduced typos then count.
        try:
            from . import question_bank
            known = re.findall(r"[A-Za-z']+", " ".join(question_bank.TYPING_SENTENCES))
            spell.word_frequency.load_words([w.lower() for w in known])
        except Exception:
            pass
        _SPELL = spell
    except Exception:
        _SPELL = None
    return _SPELL


def _check_languagetool(text):
    """Use LanguageTool if explicitly enabled and available. Java required."""
    import language_tool_python
    tool = language_tool_python.LanguageTool("en-US")
    try:
        matches = tool.check(text)
    finally:
        # Free the local server process where possible.
        close = getattr(tool, "close", None)
        if close:
            close()
    messages = [m.message for m in matches[:5]]
    return {"issues": len(matches), "messages": messages, "backend": "languagetool"}


def _check_pyspell(text):
    """Pure-Python spell check plus the basic grammar heuristics."""
    grammar = _basic_grammar_issues(text)
    spell = _get_spell()
    misspelled = []
    if spell is not None:
        words = re.findall(r"[A-Za-z']+", text)
        misspelled = sorted(spell.unknown(words))

    messages = grammar[:]
    if misspelled:
        shown = ", ".join(misspelled[:5])
        messages.append(f"Possible spelling issue: {shown}")

    backend = "pyspellchecker" if spell is not None else "heuristics-only"
    return {"issues": len(misspelled) + len(grammar), "messages": messages[:5],
            "backend": backend}


def analyze(text):
    """
    Analyse `text` and return {"issues": int, "messages": [str], "backend": str}.

    Never raises: on any failure it returns zero issues so the writing test is
    unaffected.
    """
    text = (text or "").strip()
    if not text:
        return {"issues": 0, "messages": [], "backend": "none"}
    try:
        if os.environ.get("USE_LANGUAGETOOL"):
            try:
                return _check_languagetool(text)
            except Exception:
                logger.warning("LanguageTool unavailable; falling back to pyspellchecker.")
        return _check_pyspell(text)
    except Exception:
        logger.exception("Writing check failed; treating as zero issues.")
        return {"issues": 0, "messages": [], "backend": "error"}
