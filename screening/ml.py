"""
Predicted-risk model for the Disability Unit dashboard.

WHAT THIS IS
------------
A small, honest machine-learning *prototype*. It looks at a student's five
domain scores and predicts an overall support-risk level: "high", "medium",
or "low". The dashboard shows this next to each student so an officer can
triage at a glance, instead of only seeing a raw flag count (which cannot
tell a student who narrowly missed one domain from one who failed three
badly).

WHY IT IS HONEST ABOUT ITS LIMITS
---------------------------------
We do not have real, clinically-labelled screening data. So we CANNOT train
on ground truth. Instead this module:

  1. generates SYNTHETIC student profiles,
  2. labels each one with a documented, rule-based heuristic (`_heuristic_label`),
  3. adds a little random label noise so the model must generalise rather than
     memorise the rule exactly, and
  4. trains a RandomForest to reproduce that mapping.

Because the training labels come from our own rule, the model is essentially
learning to imitate that rule (with some smoothing). That is a deliberate,
documented limitation: the *pipeline* here — feature engineering, train/test
split, a real classifier, persistence, and inference wired into the app — is
exactly what a production system would use, and swapping the synthetic data
for real labelled outcomes later would need no code changes. It is a
demonstration of the ML workflow, not a clinically validated instrument.

SAFETY
------
Screening must never break because of ML. Every entry point degrades
gracefully: if scikit-learn is not installed, or the model file has not been
trained yet, `predict_risk` simply returns None and the dashboard shows "-".
"""

import os
import pickle

from django.conf import settings

from .content import DOMAIN_ORDER, PASS_THRESHOLD

# Where the trained model is saved. It is a build artefact (see .gitignore),
# regenerated with `python manage.py train_risk_model`, not committed.
MODEL_PATH = os.path.join(settings.BASE_DIR, "screening", "ml_model.pkl")

# The three risk levels, ordered least to most severe. Stored lowercase; the
# model predicts one of these strings.
RISK_LEVELS = ["low", "medium", "high"]

# The model's input is these features, ALWAYS in this order (the five domain
# scores in their fixed domain order, four engineered summary stats, then the
# median response time in seconds - a behavioural signal, see views.py).
FEATURE_NAMES = list(DOMAIN_ORDER) + ["mean", "min", "spread", "num_flagged", "response_s"]

# Used when a session has no captured timing (older sessions, or timing that
# was not recorded): a neutral "typical" median response, so the feature is
# never missing and old sessions still score.
NEUTRAL_RESPONSE_MS = 6000


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def _feature_vector(scores, response_ms=None):
    """
    Build the model's input row from a dict of {domain_key: score} and the
    student's median response time.

    Returns a fixed-length list: the five domain scores (in DOMAIN_ORDER),
    four engineered signals that describe the *shape* of the profile, and the
    median response time in seconds:

        mean         - overall level
        min          - the single weakest domain (a deep, isolated failure)
        spread        - standard deviation (uneven vs. flat profile)
        num_flagged  - how many domains fell below the pass threshold
        response_s   - median seconds per answer (slower can accompany some
                       difficulties); a neutral default is used if not captured
    """
    ordered = [scores.get(key, 0) for key in DOMAIN_ORDER]
    n = len(ordered)
    mean = sum(ordered) / n
    lowest = min(ordered)
    spread = (sum((s - mean) ** 2 for s in ordered) / n) ** 0.5
    num_flagged = sum(1 for s in ordered if s < PASS_THRESHOLD)
    response_s = (response_ms if response_ms else NEUTRAL_RESPONSE_MS) / 1000.0
    return ordered + [mean, lowest, spread, num_flagged, response_s]


def features_from_session(session):
    """Extract the feature vector from a completed ScreeningSession."""
    scores = {r.domain: r.score for r in session.domain_results.all()}
    return _feature_vector(scores, getattr(session, "median_response_ms", None))


# ---------------------------------------------------------------------------
# Synthetic training data + the labelling heuristic
# ---------------------------------------------------------------------------

def _heuristic_label(scores):
    """
    The documented rule used to label SYNTHETIC profiles. This is our
    stand-in for clinical ground truth (see the module docstring).

        HIGH   - three or more domains flagged, OR any domain badly failed
                 (below 30), OR a low overall mean (below 40).
        LOW    - nothing flagged, OR a strong overall mean (75+).
        MEDIUM - everything in between.
    """
    ordered = [scores.get(key, 0) for key in DOMAIN_ORDER]
    mean = sum(ordered) / len(ordered)
    lowest = min(ordered)
    num_flagged = sum(1 for s in ordered if s < PASS_THRESHOLD)

    if num_flagged >= 3 or lowest < 30 or mean < 40:
        return "high"
    if num_flagged == 0 or mean >= 75:
        return "low"
    return "medium"


# Synthetic median response times (ms) by true risk level: higher-risk profiles
# tend to answer more slowly. These are invented for the prototype's training
# data (we have no real timing), so timing is a useful-but-imperfect signal, not
# ground truth - documented alongside the synthetic labels.
_RESPONSE_MS_BY_LABEL = {"low": 4500, "medium": 7000, "high": 10000}


def _synthetic_response_ms(label, rng):
    """A plausible median response time (ms) for a synthetic profile."""
    ms = rng.gauss(_RESPONSE_MS_BY_LABEL[label], 2000)
    return int(max(1000, min(20000, ms)))


def generate_synthetic(n=600, noise=0.05, seed=42):
    """
    Build `n` synthetic (features, label) pairs.

    Each domain score is drawn from a spread-out distribution so the whole
    0-100 range is covered. About `noise` (5%) of the labels are deliberately
    flipped to a different level, so the model has to generalise from the
    overall pattern instead of memorising the heuristic perfectly.

    Uses the standard library `random` (seeded) so training is reproducible
    and needs no extra dependency to generate the data itself.
    """
    import random

    rng = random.Random(seed)
    features, labels = [], []
    for _ in range(n):
        # Give each synthetic student an overall ability level spread evenly
        # across the whole range, then vary each domain around it. This covers
        # strong, mixed, and weak profiles in roughly equal numbers, so all
        # three risk levels are well represented in training.
        base = rng.uniform(20, 95)
        scores = {
            key: max(0, min(100, round(rng.gauss(base, 14))))
            for key in DOMAIN_ORDER
        }
        label = _heuristic_label(scores)
        # Timing is drawn from the TRUE state (before label noise), so it stays
        # a real - if imperfect - signal once the label is flipped.
        response_ms = _synthetic_response_ms(label, rng)
        if rng.random() < noise:
            label = rng.choice([lv for lv in RISK_LEVELS if lv != label])
        features.append(_feature_vector(scores, response_ms))
        labels.append(label)
    return features, labels


# ---------------------------------------------------------------------------
# Train / persist / load / predict
# ---------------------------------------------------------------------------

def train(n=600, noise=0.05, seed=42):
    """
    Train the RandomForest on freshly generated synthetic data.

    Returns (model, metrics) where `metrics` is a plain dict the management
    command prints so a reviewer can see how the model did:
    train/test accuracy, the label set, a confusion matrix, and which
    features mattered most.

    scikit-learn is imported here (not at module top) so the rest of the app
    keeps working even if it is not installed.
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, confusion_matrix
    from sklearn.model_selection import train_test_split

    features, labels = generate_synthetic(n=n, noise=noise, seed=seed)
    x_train, x_test, y_train, y_test = train_test_split(
        features, labels, test_size=0.25, random_state=seed, stratify=labels
    )

    model = RandomForestClassifier(
        n_estimators=120, max_depth=8, random_state=seed
    )
    model.fit(x_train, y_train)

    present = sorted(set(labels))
    test_preds = model.predict(x_test)
    metrics = {
        "n": n,
        "noise": noise,
        "train_accuracy": round(accuracy_score(y_train, model.predict(x_train)), 3),
        "test_accuracy": round(accuracy_score(y_test, test_preds), 3),
        "labels": present,
        "confusion": confusion_matrix(y_test, test_preds, labels=present).tolist(),
        "importances": sorted(
            zip(FEATURE_NAMES, [round(v, 3) for v in model.feature_importances_]),
            key=lambda pair: pair[1],
            reverse=True,
        ),
    }
    return model, metrics


def save_model(model):
    """Persist the trained model to MODEL_PATH."""
    with open(MODEL_PATH, "wb") as handle:
        pickle.dump(model, handle)


def load_model():
    """
    Load the trained model, or return None if it cannot be loaded for any
    reason (never trained, file deleted, scikit-learn not installed). Callers
    treat None as "no prediction available".
    """
    try:
        with open(MODEL_PATH, "rb") as handle:
            return pickle.load(handle)
    except Exception:
        # FileNotFoundError (not trained yet), ModuleNotFoundError (sklearn
        # missing), or a corrupt/incompatible pickle all mean the same thing
        # to callers: no model to predict with.
        return None


def predict_risk(session, model=None):
    """
    Predict "low" | "medium" | "high" for one completed ScreeningSession.

    Returns None if no model is available or prediction fails, so the caller
    (screening completion, dashboard backfill) never breaks because of ML.
    Pass `model` to reuse a single loaded model across many sessions.
    """
    if model is None:
        model = load_model()
    if model is None:
        return None
    try:
        return str(model.predict([features_from_session(session)])[0])
    except Exception:
        return None
