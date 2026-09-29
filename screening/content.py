"""
All the fixed screening content: the five domains, their questions, and
the follow-up exercises. This is plain data (no database, no logic) so it
is easy to read, change, and review on its own.

Ported from the original Flask prototype.
"""

# The score (percentage) below which a domain is "flagged" as a possible
# area of difficulty. One place to change it.
PASS_THRESHOLD = 60


# ---------------------------------------------------------------------------
# The five domains. `key` is stored in the database; `label` and `indicator`
# are shown to people. This list is the single source of truth for what
# domains exist and what order they run in.
# ---------------------------------------------------------------------------
DOMAINS = [
    {"key": "math", "label": "Numeracy", "indicator": "Dyscalculia-associated patterns"},
    {"key": "reading", "label": "Reading fluency", "indicator": "Dyslexia-associated patterns"},
    {"key": "writing", "label": "Writing & language", "indicator": "Dysgraphia-associated patterns"},
    {"key": "memory", "label": "Working memory", "indicator": "Working-memory / attention-associated patterns"},
    {"key": "scenario", "label": "Executive function", "indicator": "Executive-function-associated patterns"},
]

# Handy lookups derived from the list above.
DOMAIN_CHOICES = [(d["key"], d["label"]) for d in DOMAINS]
DOMAIN_LOOKUP = {d["key"]: d for d in DOMAINS}
DOMAIN_ORDER = [d["key"] for d in DOMAINS]


# ---------------------------------------------------------------------------
# Numeracy: multiple-choice. `answer` is the index of the correct option.
# ---------------------------------------------------------------------------
MATH_QUESTIONS = [
    {"q": "A lecture runs from 09:40 to 11:15. How long is it?", "options": ["1 hr 25 min", "1 hr 35 min", "1 hr 45 min", "2 hr 05 min"], "answer": 1},
    {"q": "What is 8 × 7 − 15 ÷ 3?", "options": ["51", "56", "61", "46"], "answer": 0},
    {"q": "A textbook costs R240 after a 20% discount. What was the original price?", "options": ["R280", "R288", "R300", "R320"], "answer": 2},
    {"q": "Which fraction is largest?", "options": ["3/8", "5/12", "2/5", "7/16"], "answer": 3},
    {"q": "If 3 printers print 300 pages in 20 minutes, how long do 5 identical printers take to print 300 pages?", "options": ["8 min", "10 min", "12 min", "15 min"], "answer": 1},
]

# ---------------------------------------------------------------------------
# Executive function ("scenario"): multiple-choice reasoning.
# ---------------------------------------------------------------------------
SCENARIO_QUESTIONS = [
    {"q": "You have three assignments due in the same week and feel overwhelmed just thinking about them. What's the best first step?", "options": ["Start with whichever one is due first, without planning further", "Break each assignment into smaller tasks and schedule them across the week", "Wait until you feel less stressed before starting any of them", "Ask a friend to do one of the assignments for you"], "answer": 1},
    {"q": "You realise halfway through a test that you've misread the instructions and wasted ten minutes. What should you do?", "options": ["Panic and rush through the rest without re-reading anything", "Re-read the instructions carefully, then re-plan your remaining time", "Leave the test and explain to the invigilator you misread it", "Ignore the mistake and keep working exactly as before"], "answer": 1},
    {"q": "A group project teammate has not submitted their section and the deadline is tomorrow. What's the most constructive response?", "options": ["Message them directly, ask for a status update, and offer to help finish it", "Say nothing and let the group mark suffer", "Report them to the lecturer immediately without contacting them first", "Redo their entire section yourself without telling anyone"], "answer": 0},
    {"q": "You're given a long list of unordered instructions for a lab task. What helps most before starting?", "options": ["Start the first instruction you notice", "Number the steps in the order they need to happen, then begin", "Try to memorise the whole list before touching any equipment", "Ask someone else to complete the task for you"], "answer": 1},
]

# ---------------------------------------------------------------------------
# Writing & language: grammar multiple-choice, then a copy-typing task.
# ---------------------------------------------------------------------------
GRAMMAR_QUESTIONS = [
    {"q": "Choose the correct sentence.", "options": ["Neither of the tutors were available.", "Neither of the tutors was available.", "Neither of the tutors is being available.", "Neither of the tutors being available."], "answer": 1},
    {"q": "Choose the correct sentence.", "options": ["Its important to submit your assignment on time.", "It's important to submit your assignment on time.", "Its' important to submit your assignment on time.", "It important to submit your assignment on time."], "answer": 1},
    {"q": "Which word correctly completes: 'The results were better ___ we expected.'", "options": ["then", "than", "that", "wherein"], "answer": 1},
]

# The student is asked to type this sentence exactly (tests accuracy and how
# many corrections they make).
TYPING_SENTENCE = "Students who register early receive extended time and assistive technology support."

# ---------------------------------------------------------------------------
# Reading fluency: a timed passage, then comprehension multiple-choice.
# ---------------------------------------------------------------------------
READING_PASSAGE = (
    "The Disability Unit at the university offers assistive technology, extended time in "
    "assessments, and note-taking support to registered students. Applications open at the "
    "start of each semester and require a supporting report from a registered practitioner. "
    "Students are encouraged to apply early, since assessment of applications can take up to "
    "three weeks and support cannot be backdated once a semester's tests have begun."
)

READING_QUESTIONS = [
    {"q": "What three forms of support does the passage mention?", "options": ["Tutoring, funding, transport", "Assistive technology, extended time, note-taking support", "Counselling, housing, meals", "Library access, printing, Wi-Fi"], "answer": 1},
    {"q": "What must accompany an application?", "options": ["A letter from a lecturer", "A supporting report from a registered practitioner", "A copy of the timetable", "A bank statement"], "answer": 1},
    {"q": "What happens if a student applies after tests have started?", "options": ["Support is backdated automatically", "Support cannot be backdated", "The application is rejected outright", "The student is fast-tracked"], "answer": 1},
]

# ---------------------------------------------------------------------------
# Working memory: digit-span. Each sequence is shown briefly, then hidden,
# and the student types it back. They get progressively longer.
# ---------------------------------------------------------------------------
MEMORY_SEQUENCES = [
    ["4", "9", "2"],
    ["7", "1", "8", "5"],
    ["3", "6", "9", "2", "4"],
    ["8", "5", "1", "7", "3", "6"],
]


# ---------------------------------------------------------------------------
# Follow-up exercises shown for each flagged domain on the results page.
# ---------------------------------------------------------------------------
EXERCISES = {
    "math": {
        "summary": "Responses showed patterns often linked to difficulty with number sense, multi-step calculation, or working with fractions and percentages under time pressure - patterns associated with dyscalculia.",
        "drills": [
            "Practise breaking multi-step problems into separate labelled steps before calculating anything.",
            "Use a number line or grid paper to keep place value visually organised.",
            "Convert percentages and fractions to a common form (e.g. all decimals) before comparing them.",
            "Estimate an answer before calculating, then check your result against the estimate.",
        ],
    },
    "reading": {
        "summary": "Responses showed patterns often linked to difficulty with reading speed, word decoding, or holding written detail in mind - patterns associated with dyslexia.",
        "drills": [
            "Read in short chunks and summarise each paragraph in one sentence before moving on.",
            "Use a finger or ruler to track your place line by line and reduce visual skipping.",
            "Try text-to-speech tools alongside reading to reinforce comprehension.",
            "After reading, write down three facts from memory before checking the text again.",
        ],
    },
    "writing": {
        "summary": "Responses showed patterns often linked to sentence structure, punctuation, or motor consistency while writing - patterns associated with dysgraphia.",
        "drills": [
            "Read sentences aloud - errors in agreement and structure are often easier to hear than see.",
            "Keep a personal list of your five most repeated errors and check new writing against it.",
            "Practise copying short passages exactly, then compare for dropped or altered words.",
            "Use grammar-checking tools as a learning aid - read why each suggestion was made, not just apply it.",
        ],
    },
    "memory": {
        "summary": "Responses showed patterns often linked to difficulty holding and manipulating information in working memory, sometimes associated with attention difficulties.",
        "drills": [
            "Chunk information into groups of 3–4 items rather than trying to hold long unbroken sequences.",
            "Say sequences aloud while writing them down - verbal and written rehearsal reinforce each other.",
            "Use external memory aids consistently: checklists, planners, and sticky notes for multi-step tasks.",
            "Practise the 'link method' - attach new information to something you already know well.",
        ],
    },
    "scenario": {
        "summary": "Responses showed patterns often linked to difficulty with planning, prioritising, or adapting a plan once it changes - associated with executive-function difficulty.",
        "drills": [
            "Before starting any task, write a short plan with three steps in order - even a rough one.",
            "When a plan breaks, pause and ask 'what changed?' before deciding what to do next.",
            "Practise the 'two-minute pause' - before reacting to a problem, take two minutes to think through options.",
            "Use a weekly planner that separates urgent tasks from important-but-not-urgent ones.",
        ],
    },
}
