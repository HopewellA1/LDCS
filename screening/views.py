import re
import statistics
import time
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from account.decorators import educator_required

from . import content, ml, question_bank, scoring
from .emails import send_survey_email
from .consent import CURRENT_CONSENT_VERSION, get_active_consent, has_valid_consent
from .decorators import consent_required
from .forms import ConsentForm, FollowUpQuestionFormSet, FollowUpTestForm
from .models import ConsentRecord, FollowUpTest, Referral, ScreeningSession


# ===========================================================================
# Consent lifecycle
# ===========================================================================

@login_required
def dashboard(request):
    # Officers get their own purpose-built dashboard, not the student one,
    # so send them straight there (this also covers the "Dashboard" nav link).
    profile = getattr(request.user, "profile", None)
    if profile is not None and profile.is_educator:
        return redirect("educator_dashboard")

    consent = get_active_consent(request.user)
    latest_session = request.user.screening_sessions.filter(
        completed_at__isnull=False
    ).first()
    # Practice tests an officer has assigned to this student (see follow-ups).
    practice_tests = request.user.follow_up_tests.filter(is_active=True)
    return render(
        request,
        "screening/dashboard.html",
        {
            "consent": consent,
            "latest_session": latest_session,
            "practice_tests": practice_tests,
            "threshold": content.PASS_THRESHOLD,
        },
    )


@login_required
def consent(request):
    # Where to send the student after they consent (only ever a local URL).
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = ""

    if has_valid_consent(request.user):
        return redirect(next_url or "dashboard")

    if request.method == "POST":
        form = ConsentForm(request.POST)
        if form.is_valid():
            ConsentRecord.objects.create(
                user=request.user, version=CURRENT_CONSENT_VERSION
            )
            messages.success(request, "Thank you. Your consent has been recorded.")
            return redirect(next_url or "dashboard")
    else:
        form = ConsentForm()

    return render(
        request,
        "screening/consent.html",
        {"form": form, "next": next_url, "version": CURRENT_CONSENT_VERSION},
    )


@login_required
@require_POST
def withdraw_consent(request):
    withdrawn = request.user.consent_records.filter(
        withdrawn_at__isnull=True
    ).update(withdrawn_at=timezone.now())
    if withdrawn:
        messages.info(
            request,
            "Your consent has been withdrawn. You will need to consent again before starting a screening.",
        )
    return redirect("dashboard")


# ===========================================================================
# Screening: shared progress helpers
#
# While a student is part-way through a screening, each finished domain's
# result is kept in the browser session under "screening_results". Nothing
# is written to the database until they finish the whole screening (see
# screening_finish). That way the database only ever holds complete attempts.
# ===========================================================================

def _get_results(request):
    """The in-progress results collected so far (a dict keyed by domain)."""
    return request.session.get("screening_results", {})


def _store_result(request, domain, result):
    """Record one domain's result and keep the session in sync."""
    results = _get_results(request)
    results[domain] = result
    request.session["screening_results"] = results
    request.session.modified = True


def _selected_index(request):
    """The option index the student picked, or None if nothing valid."""
    raw = request.POST.get("option")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


# --- Response-time capture (a behavioural signal for the risk model) ----------
# When a question is shown we stamp the time; when its answer arrives we record
# how long it took, clamped so a paused tab or an accidental double-tap cannot
# skew the result. The per-question times are summarised (median) when the
# screening is finished. This is invisible to the student - the screen is
# unchanged.

def _mark_shown(request, key):
    """Record that a question (identified by `key`) has just been shown."""
    request.session[f"shown_{key}"] = time.time()


def _record_time(request, key):
    """Record how long the student took to answer the question named by `key`."""
    shown = request.session.pop(f"shown_{key}", None)
    if shown is None:
        return
    ms = int((time.time() - shown) * 1000)
    ms = max(300, min(ms, 120000))  # 0.3s floor, 2 min ceiling
    times = request.session.get("response_times", [])
    times.append(ms)
    request.session["response_times"] = times
    request.session.modified = True


@consent_required
def screening_home(request):
    """
    The screening menu: shows every domain, whether it's done, and a link to
    finish once all five are complete.
    """
    results = _get_results(request)
    domains = []
    for d in content.DOMAINS:
        done = d["key"] in results
        domains.append({
            "key": d["key"],
            "label": d["label"],
            "indicator": d["indicator"],
            "done": done,
            "score": results[d["key"]]["score"] if done else None,
            # Flagged when the score fell below the pass threshold - drives the
            # badge colour (orange) instead of the default "clear" green.
            "flagged": results[d["key"]]["flagged"] if done else False,
        })
    all_done = len(results) == len(content.DOMAINS)
    return render(
        request,
        "screening/screening_home.html",
        {"domains": domains, "all_done": all_done, "completed": len(results)},
    )


@consent_required
@require_POST
def screening_finish(request):
    """Persist the in-progress results as a ScreeningSession, then clear them."""
    results = _get_results(request)
    if len(results) != len(content.DOMAINS):
        messages.error(request, "Please complete all sections before finishing.")
        return redirect("screening_home")

    session = scoring.save_session(request.user, results)

    # Summarise how long the student took to answer (median across all
    # questions) - a behavioural signal the risk model uses. Set before the
    # prediction so the model can see it.
    times = request.session.pop("response_times", [])
    if times:
        session.median_response_ms = int(statistics.median(times))

    # Predict an overall risk level for the Disability Unit dashboard. This is
    # best-effort: if the model is not available it returns None and we simply
    # leave ml_risk blank - screening must never fail because of ML.
    risk = ml.predict_risk(session)
    if risk:
        session.ml_risk = risk

    session.save(update_fields=["median_response_ms", "ml_risk"])

    # Invite the student to the Disability Rights Unit survey (never blocks
    # the flow - see send_survey_email).
    if send_survey_email(request, request.user):
        messages.success(
            request,
            f"A survey invitation has been sent to {request.user.email}.",
        )
    request.session.pop("screening_results", None)
    request.session.modified = True
    return redirect("results")


# ===========================================================================
# Numeracy & executive function: plain multiple-choice tests
# ===========================================================================

MCQ_TESTS = {
    "math": {"title": "Numeracy test", "scorer": scoring.score_math},
    "scenario": {"title": "Executive-function test", "scorer": scoring.score_scenario},
}


@consent_required
def test_mcq(request, domain):
    if domain not in MCQ_TESTS:
        raise Http404("Unknown test")
    cfg = MCQ_TESTS[domain]
    state_key = f"state_{domain}"

    # On the first visit for this attempt, draw a fresh, option-shuffled subset
    # from the question pool and keep it in the session, so every later question
    # and the final score use the exact set the student was shown.
    state = request.session.get(state_key)
    if state is None:
        state = {"index": 0, "correct": 0, "questions": question_bank.draw_mcq(domain)}
        request.session[state_key] = state
        request.session.modified = True
    questions = state["questions"]

    if request.method == "POST":
        selected = _selected_index(request)
        if selected is None:
            messages.error(request, "Choose an answer first.")
            return redirect("test_mcq", domain=domain)
        _record_time(request, f"mcq_{domain}")
        if selected == questions[state["index"]]["answer"]:
            state["correct"] += 1
        state["index"] += 1
        request.session[state_key] = state
        request.session.modified = True

        if state["index"] >= len(questions):
            _store_result(request, domain,
                          cfg["scorer"](state["correct"], total=len(questions)))
            request.session.pop(state_key, None)
            request.session.modified = True
            return redirect("screening_home")
        return redirect("test_mcq", domain=domain)

    # GET: show the current question (or bail out if somehow past the end).
    if state["index"] >= len(questions):
        return redirect("screening_home")
    _mark_shown(request, f"mcq_{domain}")
    return render(request, "screening/question.html", {
        "title": cfg["title"],
        "q": questions[state["index"]],
        "index": state["index"],
        "total": len(questions),
        "action": reverse("test_mcq", args=[domain]),
    })


# ===========================================================================
# Reading fluency: timed passage, then comprehension questions
# ===========================================================================

@consent_required
def reading_test(request):
    phase = request.session.get("reading_phase", "ready")

    if phase == "ready":
        return render(request, "screening/reading_intro.html")

    if phase == "reading":
        return render(request, "screening/reading_passage.html",
                      {"passage": request.session.get("reading_passage",
                                                       content.READING_PASSAGE)})

    # phase == "questions"
    questions = request.session.get("reading_questions", content.READING_QUESTIONS)
    state = request.session.get("reading_state", {"index": 0, "correct": 0})
    if state["index"] >= len(questions):
        return redirect("screening_home")
    _mark_shown(request, "reading")
    return render(request, "screening/question.html", {
        "title": "Reading fluency - comprehension",
        "q": questions[state["index"]],
        "index": state["index"],
        "total": len(questions),
        "action": reverse("reading_answer"),
    })


@consent_required
@require_POST
def reading_start(request):
    """Draw a passage set for this attempt, start the timer, show the passage."""
    passage, questions = question_bank.draw_reading()
    request.session["reading_passage"] = passage
    request.session["reading_questions"] = questions
    request.session["reading_started_at"] = time.time()
    request.session["reading_phase"] = "reading"
    return redirect("reading_test")


@consent_required
@require_POST
def reading_finish(request):
    """Stop the timer, work out reading speed, and move to the questions."""
    started = request.session.get("reading_started_at", time.time())
    elapsed = max(3.0, time.time() - started)  # floor avoids silly-high speeds
    passage = request.session.get("reading_passage", content.READING_PASSAGE)
    words = len(passage.split())
    request.session["reading_wpm"] = round(words / elapsed * 60)
    request.session["reading_phase"] = "questions"
    request.session["reading_state"] = {"index": 0, "correct": 0}
    return redirect("reading_test")


@consent_required
@require_POST
def reading_answer(request):
    questions = request.session.get("reading_questions", content.READING_QUESTIONS)
    state = request.session.get("reading_state", {"index": 0, "correct": 0})
    selected = _selected_index(request)
    if selected is None:
        messages.error(request, "Choose an answer first.")
        return redirect("reading_test")
    _record_time(request, "reading")

    if selected == questions[state["index"]]["answer"]:
        state["correct"] += 1
    state["index"] += 1
    request.session["reading_state"] = state

    if state["index"] >= len(questions):
        wpm = request.session.get("reading_wpm", 0)
        _store_result(request, "reading",
                      scoring.score_reading(state["correct"], wpm, total=len(questions)))
        for key in ("reading_phase", "reading_started_at", "reading_wpm",
                    "reading_state", "reading_passage", "reading_questions"):
            request.session.pop(key, None)
        request.session.modified = True
        return redirect("screening_home")
    return redirect("reading_test")


# ===========================================================================
# Writing & language: grammar questions, then a copy-typing task
# ===========================================================================

@consent_required
def writing_test(request):
    # Draw this attempt's grammar questions and copy-typing sentence once, then
    # reuse them from the session for the rest of the test.
    if "writing_questions" not in request.session:
        request.session["writing_questions"] = question_bank.draw_mcq("grammar")
        request.session["writing_sentence"] = question_bank.random_typing_sentence()
        request.session.modified = True
    grammar_questions = request.session["writing_questions"]

    stage = request.session.get("writing_stage", "grammar")

    if stage == "grammar":
        index = request.session.get("writing_index", 0)
        if index >= len(grammar_questions):
            request.session["writing_stage"] = "typing"
            return redirect("writing_test")
        _mark_shown(request, "writing")
        return render(request, "screening/question.html", {
            "title": "Writing & language test",
            "q": grammar_questions[index],
            "index": index,
            "total": len(grammar_questions),
            "action": reverse("writing_grammar_answer"),
        })

    # stage == "typing"
    if "typing_started_at" not in request.session:
        request.session["typing_started_at"] = time.time()
    return render(request, "screening/writing_typing.html",
                  {"sentence": request.session["writing_sentence"]})


@consent_required
@require_POST
def writing_grammar_answer(request):
    grammar_questions = request.session.get("writing_questions", content.GRAMMAR_QUESTIONS)
    index = request.session.get("writing_index", 0)
    correct = request.session.get("writing_correct", 0)
    selected = _selected_index(request)
    if selected is None:
        messages.error(request, "Choose an answer first.")
        return redirect("writing_test")
    _record_time(request, "writing")

    if selected == grammar_questions[index]["answer"]:
        correct += 1
    index += 1
    request.session["writing_index"] = index
    request.session["writing_correct"] = correct
    if index >= len(grammar_questions):
        request.session["writing_stage"] = "typing"
    return redirect("writing_test")


@consent_required
@require_POST
def writing_typing_submit(request):
    typed = request.POST.get("typed", "").strip()
    if not typed:
        messages.error(request, "Type the sentence shown above.")
        return redirect("writing_test")
    try:
        backspaces = int(request.POST.get("backspaces", 0) or 0)
    except ValueError:
        backspaces = 0

    grammar_correct = request.session.get("writing_correct", 0)
    grammar_questions = request.session.get("writing_questions", content.GRAMMAR_QUESTIONS)
    sentence = request.session.get("writing_sentence", content.TYPING_SENTENCE)
    _store_result(request, "writing",
                  scoring.score_writing(grammar_correct, typed, backspaces,
                                        target=sentence,
                                        grammar_total=len(grammar_questions)))
    for key in ("writing_stage", "writing_index", "writing_correct",
                "typing_started_at", "writing_questions", "writing_sentence"):
        request.session.pop(key, None)
    request.session.modified = True
    return redirect("screening_home")


# ===========================================================================
# Working memory: digit-span recall
# ===========================================================================

@consent_required
def memory_test(request):
    # Fresh random digit sequences per attempt (same lengths as before).
    sequences = request.session.get("memory_sequences")
    if sequences is None:
        sequences = question_bank.random_memory_sequences()
        request.session["memory_sequences"] = sequences
        request.session.modified = True

    round_index = request.session.get("memory_round", 0)
    if round_index >= len(sequences):
        return redirect("screening_home")
    _mark_shown(request, "memory")
    return render(request, "screening/memory.html", {
        "sequence": sequences[round_index],
        "round_index": round_index,
        "total": len(sequences),
    })


@consent_required
@require_POST
def memory_answer(request):
    sequences = request.session.get("memory_sequences", content.MEMORY_SEQUENCES)
    round_index = request.session.get("memory_round", 0)
    correct = request.session.get("memory_correct", 0)
    longest = request.session.get("memory_longest", 0)
    sequence = sequences[round_index]

    # Ignore spaces so "4 9 2" and "492" both count.
    typed = re.sub(r"\s+", "", request.POST.get("answer", ""))
    if not typed:
        messages.error(request, "Type the sequence you saw.")
        return redirect("memory_test")
    _record_time(request, "memory")

    if typed == "".join(sequence):
        correct += 1
        longest = max(longest, len(sequence))
    round_index += 1
    request.session["memory_round"] = round_index
    request.session["memory_correct"] = correct
    request.session["memory_longest"] = longest

    if round_index >= len(sequences):
        _store_result(request, "memory",
                      scoring.score_memory(correct, longest, total=len(sequences)))
        for key in ("memory_round", "memory_correct", "memory_longest",
                    "memory_sequences"):
            request.session.pop(key, None)
        request.session.modified = True
        return redirect("screening_home")
    return redirect("memory_test")


# ===========================================================================
# Student results
# ===========================================================================

@consent_required
def results(request):
    """Show the student their most recent completed screening."""
    session = request.user.screening_sessions.filter(
        completed_at__isnull=False
    ).first()
    if session is None:
        messages.info(request, "You haven't completed a screening yet.")
        return redirect("screening_home")

    # Split results into flagged / strong, and attach the follow-up exercises
    # for each flagged domain.
    flagged, strong = [], []
    for r in session.domain_results.all():
        if r.flagged:
            r.exercise = content.EXERCISES.get(r.domain)
            flagged.append(r)
        else:
            strong.append(r)

    return render(request, "screening/results.html", {
        "session": session,
        "flagged": flagged,
        "strong": strong,
        "threshold": content.PASS_THRESHOLD,
    })


# ===========================================================================
# Educator dashboard
# ===========================================================================

def _parse_date(value):
    """Parse a yyyy-mm-dd string from the date filter, or return None."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@educator_required
def educator_dashboard(request):
    """
    The Disability Unit dashboard: summary tiles with sparklines, a set of
    Chart.js charts (flags by domain, flagged/referred donuts, distribution,
    flags by faculty), and a searchable/filterable roster. Everything can be
    narrowed to a date range.
    """
    # --- Date-range filter (applies to when a screening was completed) ---
    date_from = _parse_date(request.GET.get("from"))
    date_to = _parse_date(request.GET.get("to"))

    sessions_qs = ScreeningSession.objects.filter(completed_at__isnull=False)
    if date_from:
        sessions_qs = sessions_qs.filter(completed_at__date__gte=date_from)
    if date_to:
        sessions_qs = sessions_qs.filter(completed_at__date__lte=date_to)

    sessions = (
        sessions_qs
        .select_related("student", "student__profile", "student__referral")
        .prefetch_related("domain_results")
    )

    # Each student's most recent completed screening in the range (newest
    # first, so the first one we see per student is their latest).
    latest_by_student = {}
    for s in sessions:
        latest_by_student.setdefault(s.student_id, s)

    # --- Walk each student's latest screening once, aggregating as we go ---
    week_ago = timezone.now() - timedelta(days=7)
    domain_flags = {d["key"]: 0 for d in content.DOMAINS}
    flag_distribution = {n: 0 for n in range(len(content.DOMAINS) + 1)}  # 0..5 flags
    faculty_stats = {}   # faculty label -> {"screened", "flagged"}
    monthly = {}         # "yyyy-mm" -> {"screened", "flagged"}
    rows = []
    students_flagged = 0
    students_referred = 0
    screened_this_week = 0
    high_risk = 0  # students whose latest screening the model rated "high"

    for session in latest_by_student.values():
        student = session.student
        flagged_domains = [r.domain for r in session.domain_results.all() if r.flagged]
        n_flags = len(flagged_domains)
        is_flagged = n_flags > 0

        for key in flagged_domains:
            if key in domain_flags:
                domain_flags[key] += 1
        flag_distribution[n_flags] = flag_distribution.get(n_flags, 0) + 1

        profile = getattr(student, "profile", None)
        faculty_label = (
            profile.get_faculty_display() if profile and profile.faculty else "Not specified"
        )
        fac = faculty_stats.setdefault(faculty_label, {"screened": 0, "flagged": 0})
        fac["screened"] += 1
        if is_flagged:
            fac["flagged"] += 1
            students_flagged += 1

        referral = getattr(student, "referral", None)
        is_referred = bool(referral and referral.referred)
        if is_referred:
            students_referred += 1
        if session.completed_at and session.completed_at >= week_ago:
            screened_this_week += 1
        if session.completed_at:
            bucket = monthly.setdefault(
                session.completed_at.strftime("%Y-%m"), {"screened": 0, "flagged": 0}
            )
            bucket["screened"] += 1
            if is_flagged:
                bucket["flagged"] += 1

        if session.ml_risk == "high":
            high_risk += 1

        rows.append({
            "student": student,
            "student_number": profile.student_number if profile else "",
            "faculty": faculty_label,
            "session": session,
            "flagged_count": n_flags,
            "completed_at": session.completed_at,
            "referred": is_referred,
            "risk": session.ml_risk,  # "", "low", "medium" or "high"
            "risk_label": session.get_ml_risk_display() if session.ml_risk else "",
        })

    total = len(rows)
    kpis = {
        "screened": total,
        "flagged": students_flagged,
        "this_week": screened_this_week,
        "awaiting": total - students_referred,  # screened but not yet referred
        "high_risk": high_risk,  # from the ML model (0 until it has scored)
    }

    # --- Chart datasets (handed to Chart.js as JSON in the template) ---
    months = sorted(monthly.keys())
    charts = {
        "domain": {
            "labels": [d["label"] for d in content.DOMAINS],
            "data": [domain_flags[d["key"]] for d in content.DOMAINS],
        },
        "flagged": {
            "labels": ["Flagged", "Clear"],
            "data": [students_flagged, total - students_flagged],
        },
        "referred": {
            "labels": ["Referred", "Not referred"],
            "data": [students_referred, total - students_referred],
        },
        "distribution": {
            "labels": [str(n) for n in sorted(flag_distribution)],
            "data": [flag_distribution[n] for n in sorted(flag_distribution)],
        },
        "faculty": {
            "labels": list(faculty_stats.keys()),
            "data": [v["flagged"] for v in faculty_stats.values()],
        },
        "trend": {
            "labels": months,
            "screened": [monthly[m]["screened"] for m in months],
            "flagged": [monthly[m]["flagged"] for m in months],
        },
    }

    # --- Presentation-ready values for the CSS/SVG charts in the template ---
    # (The dashboard draws its own bars and donut rings from these, so no
    # charting library is needed.)
    def _bars(key):
        """Each item plus its share of the biggest bar (for the CSS width)."""
        labels, data = charts[key]["labels"], charts[key]["data"]
        biggest = max(data) if data else 0
        return [
            {"label": label, "value": value,
             "pct": round(value / biggest * 100) if biggest else 0}
            for label, value in zip(labels, data)
        ]

    def _ring_offset(part, whole, circumference=440):
        """SVG stroke-dashoffset so the ring shows the `part`/`whole` share."""
        return round(circumference * (whole - part) / whole, 1) if whole else circumference

    donuts = {
        "flagged": {"count": students_flagged, "other": total - students_flagged,
                    "offset": _ring_offset(students_flagged, total)},
        "referred": {"count": students_referred, "other": total - students_referred,
                     "offset": _ring_offset(students_referred, total)},
    }
    domain_bars = _bars("domain")
    distribution_bars = _bars("distribution")
    faculty_bars = _bars("faculty")

    # --- Roster search / filter / sort (the tiles and charts above are over
    # all students in range; only this list responds to these controls) ---
    query = request.GET.get("q", "").strip()
    active_filter = request.GET.get("filter", "all")
    sort = request.GET.get("sort", "flags")

    if query:
        q = query.lower()
        rows = [
            r for r in rows
            if q in r["student"].get_username().lower()
            or q in (r["student_number"] or "").lower()
        ]
    if active_filter == "flagged":
        rows = [r for r in rows if r["flagged_count"] > 0]
    elif active_filter == "high_risk":
        rows = [r for r in rows if r["risk"] == "high"]
    elif active_filter == "referred":
        rows = [r for r in rows if r["referred"]]
    elif active_filter == "not_referred":
        rows = [r for r in rows if not r["referred"]]

    if sort == "recent":
        rows.sort(key=lambda r: r["completed_at"], reverse=True)
    else:  # "flags"
        rows.sort(key=lambda r: r["flagged_count"], reverse=True)

    return render(request, "screening/educator_dashboard.html", {
        "rows": rows,
        "kpis": kpis,
        "donuts": donuts,
        "domain_bars": domain_bars,
        "distribution_bars": distribution_bars,
        "faculty_bars": faculty_bars,
        "total_domains": len(content.DOMAINS),
        "query": query,
        "active_filter": active_filter,
        "sort": sort,
        "date_from": request.GET.get("from", ""),
        "date_to": request.GET.get("to", ""),
    })


@educator_required
def educator_student(request, student_id):
    """One student's most recent screening, plus the referral control."""
    # A student may have screened more than once, so take the latest
    # completed session (newest-first via the model's ordering).
    session = (
        ScreeningSession.objects
        .select_related("student", "student__profile")
        .filter(student_id=student_id, completed_at__isnull=False)
        .first()
    )
    if session is None:
        raise Http404("No completed screening for this student")
    student = session.student

    # The officer toggles the referral from this page.
    if request.method == "POST":
        referral, _ = Referral.objects.get_or_create(student=student)
        referral.referred = "referred" in request.POST
        referral.note = request.POST.get("note", "").strip()
        referral.updated_by = request.user
        referral.save()
        messages.success(request, "Referral status updated.")
        return redirect("educator_student", student_id=student_id)

    profile = getattr(student, "profile", None)
    results = list(session.domain_results.all())
    # Domains this student fell below the threshold on - offered as one-click
    # targets when the officer creates a follow-up practice test.
    weak_domains = [
        {"key": r.domain, "label": r.label}
        for r in results if r.flagged
    ]
    return render(request, "screening/educator_student.html", {
        "student": student,
        "student_number": profile.student_number if profile else "",
        "session": session,
        "results": results,
        "threshold": content.PASS_THRESHOLD,
        "referral": getattr(student, "referral", None),
        "weak_domains": weak_domains,
        "follow_up_tests": student.follow_up_tests.all(),
    })


# ===========================================================================
# Follow-up practice tests: officer-side CRUD
#
# An officer builds a small multiple-choice test for one student, aimed at a
# domain they struggled with. These four views are the Create, Read, Update
# and Delete operations; the student can take the test later.
# ===========================================================================

@educator_required
def followup_list(request):
    """Read: every follow-up test, optionally filtered to one student."""
    tests = FollowUpTest.objects.select_related("student", "created_by").all()
    student_filter = request.GET.get("student", "")
    if student_filter:
        tests = tests.filter(student_id=student_filter)
    return render(request, "screening/followup_list.html", {
        "tests": tests,
        "student_filter": student_filter,
    })


@educator_required
def followup_create(request, student_id):
    """Create a follow-up test for a student (domain can be pre-filled)."""
    student = get_object_or_404(get_user_model(), pk=student_id)

    if request.method == "POST":
        form = FollowUpTestForm(request.POST)
        formset = FollowUpQuestionFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            test = form.save(commit=False)
            test.student = student
            test.created_by = request.user
            test.save()
            formset.instance = test
            formset.save()
            messages.success(request, "Follow-up test created.")
            return redirect("followup_list")
    else:
        initial = {}
        domain = request.GET.get("domain")
        if domain in content.DOMAIN_LOOKUP:
            initial["domain"] = domain
            initial["title"] = f"{content.DOMAIN_LOOKUP[domain]['label']} practice"
        form = FollowUpTestForm(initial=initial)
        formset = FollowUpQuestionFormSet()

    return render(request, "screening/followup_form.html", {
        "form": form,
        "formset": formset,
        "student": student,
        "mode": "create",
    })


@educator_required
def followup_edit(request, pk):
    """Update an existing follow-up test and its questions."""
    test = get_object_or_404(FollowUpTest, pk=pk)

    if request.method == "POST":
        form = FollowUpTestForm(request.POST, instance=test)
        formset = FollowUpQuestionFormSet(request.POST, instance=test)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Follow-up test updated.")
            return redirect("followup_list")
    else:
        form = FollowUpTestForm(instance=test)
        formset = FollowUpQuestionFormSet(instance=test)

    return render(request, "screening/followup_form.html", {
        "form": form,
        "formset": formset,
        "student": test.student,
        "mode": "edit",
        "test": test,
    })


@educator_required
@require_POST
def followup_delete(request, pk):
    """Delete a follow-up test (its questions cascade)."""
    test = get_object_or_404(FollowUpTest, pk=pk)
    test.delete()
    messages.success(request, "Follow-up test deleted.")
    return redirect("followup_list")


# ===========================================================================
# Follow-up practice tests: student side (take a test, clear a flag on a pass)
# ===========================================================================

def _clear_domain_flag(student, domain, score):
    """
    A student passed a follow-up test, so clear that domain's flag on their
    latest screening. Because every dashboard reads DomainResult.flagged, this
    one change makes the flag count drop everywhere. The score is bumped to
    reflect the improvement and a note records how it changed.
    """
    session = (
        ScreeningSession.objects
        .filter(student=student, completed_at__isnull=False)
        .first()
    )
    if session is None:
        return
    result = session.domain_results.filter(domain=domain).first()
    if result is None or not result.flagged:
        return
    result.flagged = False
    result.score = max(result.score, score)
    result.detail = list(result.detail) + [
        {"label": "Improved via follow-up practice", "value": f"{score}%"}
    ]
    result.save(update_fields=["flagged", "score", "detail"])


def _finish_followup(request, test, questions, state):
    """Score a completed attempt, store it, and clear the flag if passed."""
    total = len(questions)
    score = round(state["correct"] / total * 100) if total else 0
    passed = score >= content.PASS_THRESHOLD

    test.last_score = score
    test.passed = passed
    test.completed_at = timezone.now()
    test.save(update_fields=["last_score", "passed", "completed_at"])

    request.session.pop(f"futest_{test.pk}", None)
    request.session.modified = True

    if passed:
        _clear_domain_flag(request.user, test.domain, score)
        messages.success(
            request,
            f"Great work - you scored {score}% and cleared the "
            f"{test.domain_label} flag.",
        )
    else:
        messages.info(
            request,
            f"You scored {score}%. Keep practising - {content.PASS_THRESHOLD}% "
            f"is needed to clear the {test.domain_label} flag.",
        )
    return redirect("dashboard")


@login_required
def followup_take(request, pk):
    """A student works through one of their assigned follow-up tests."""
    test = get_object_or_404(FollowUpTest, pk=pk, student=request.user, is_active=True)
    questions = list(test.questions.all())
    if not questions:
        messages.info(request, "This practice test has no questions yet.")
        return redirect("dashboard")

    state_key = f"futest_{pk}"
    state = request.session.get(state_key, {"index": 0, "correct": 0})

    if request.method == "POST":
        selected = _selected_index(request)
        if selected is None:
            messages.error(request, "Choose an answer first.")
            return redirect("followup_take", pk=pk)
        _, correct_index = questions[state["index"]].display_options()
        if selected == correct_index:
            state["correct"] += 1
        state["index"] += 1
        request.session[state_key] = state
        request.session.modified = True
        if state["index"] >= len(questions):
            return _finish_followup(request, test, questions, state)
        return redirect("followup_take", pk=pk)

    if state["index"] >= len(questions):
        return redirect("dashboard")
    options, _ = questions[state["index"]].display_options()
    return render(request, "screening/question.html", {
        "title": f"Practice: {test.title}",
        "q": {"q": questions[state["index"]].prompt, "options": options},
        "index": state["index"],
        "total": len(questions),
        "action": reverse("followup_take", args=[pk]),
    })
