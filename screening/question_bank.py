"""
Larger question pools + a small helper for drawing a randomised, option-shuffled
subset each time a student takes a test.

Why this exists
---------------
The original screening used a handful of fixed questions with the correct
option always in the same position, so a repeat student could pattern-match
instead of answering. This module keeps the SAME on-screen format and the SAME
number of questions per attempt, but:

  * draws them from a bigger bank (variety between attempts), and
  * shuffles each question's options and recomputes the correct index at serve
    time (so there is no positional answer-key to memorise).

The banks below were AI-generated (with Claude) from the original questions and
then checked by hand. They are plain data - easy to read, extend, or replace.

`draw_mcq`, `draw_reading`, `random_memory_sequences` and `random_typing_sentence`
return ready-to-serve data; the views store that in the session for the duration
of one attempt and score against it, so the questions shown always match the
answer key used.
"""

import random


# How many questions to show per attempt, per domain. These match the original
# test lengths, so the screening feels exactly the same to the student.
DRAW_COUNTS = {
    "math": 5,
    "scenario": 4,
    "grammar": 3,   # the multiple-choice part of the writing test
    "reading": 3,   # comprehension questions after the passage
}


# ---------------------------------------------------------------------------
# Numeracy (dyscalculia-associated). Multiple choice; `answer` indexes options.
# ---------------------------------------------------------------------------
MATH_BANK = [
    {"q": "A lecture runs from 09:40 to 11:15. How long is it?", "options": ["1 hr 25 min", "1 hr 35 min", "1 hr 45 min", "2 hr 05 min"], "answer": 1},
    {"q": "What is 8 x 7 - 15 / 3?", "options": ["51", "56", "61", "46"], "answer": 0},
    {"q": "A textbook costs R240 after a 20% discount. What was the original price?", "options": ["R280", "R288", "R300", "R320"], "answer": 2},
    {"q": "Which fraction is largest?", "options": ["3/8", "5/12", "2/5", "7/16"], "answer": 3},
    {"q": "3 printers print 300 pages in 20 minutes. How long do 5 identical printers take to print 300 pages?", "options": ["8 min", "10 min", "12 min", "15 min"], "answer": 2},
    {"q": "A jacket costs R600. It is discounted 15%, then a further 10% off the new price. What is the final price?", "options": ["R450", "R459", "R465", "R477"], "answer": 1},
    {"q": "What is 3/4 of 2/3?", "options": ["1/2", "2/7", "5/12", "3/8"], "answer": 0},
    {"q": "A recipe for 4 people needs 300 g of flour. How much is needed for 10 people?", "options": ["600 g", "700 g", "750 g", "800 g"], "answer": 2},
    {"q": "Round 4,847 to the nearest hundred.", "options": ["4,800", "4,850", "4,900", "4,000"], "answer": 0},
    {"q": "A bus leaves every 12 minutes starting at 08:00. What time does the 5th bus leave?", "options": ["08:36", "08:44", "08:48", "09:00"], "answer": 2},
    {"q": "What is 15% of 240?", "options": ["24", "36", "40", "45"], "answer": 1},
    {"q": "A car travels 210 km in 3 hours. What is its average speed?", "options": ["60 km/h", "65 km/h", "70 km/h", "75 km/h"], "answer": 2},
    {"q": "Which value is equal to 0.6?", "options": ["3/5", "2/3", "5/8", "6/100"], "answer": 0},
    {"q": "You buy items for R37, R48 and R19. From R120, how much change do you get?", "options": ["R14", "R16", "R18", "R26"], "answer": 1},
    {"q": "A tank holds 50 litres and is 40% full. How many litres are in it?", "options": ["15", "20", "24", "30"], "answer": 1},
]

# ---------------------------------------------------------------------------
# Executive function ("scenario"). Judgement / planning multiple choice.
# ---------------------------------------------------------------------------
SCENARIO_BANK = [
    {"q": "You have three assignments due in the same week and feel overwhelmed. What is the best first step?", "options": ["Start with whichever is due first, without planning further", "Break each assignment into smaller tasks and schedule them across the week", "Wait until you feel less stressed before starting any of them", "Ask a friend to do one of the assignments for you"], "answer": 1},
    {"q": "Halfway through a test you realise you misread the instructions and wasted ten minutes. What should you do?", "options": ["Panic and rush through the rest without re-reading anything", "Re-read the instructions carefully, then re-plan your remaining time", "Leave the test and tell the invigilator you misread it", "Ignore the mistake and keep working exactly as before"], "answer": 1},
    {"q": "A group project teammate has not submitted their section and the deadline is tomorrow. What is the most constructive response?", "options": ["Message them, ask for a status update, and offer to help finish it", "Say nothing and let the group mark suffer", "Report them to the lecturer without contacting them first", "Redo their entire section yourself without telling anyone"], "answer": 0},
    {"q": "You are given a long list of unordered instructions for a lab task. What helps most before starting?", "options": ["Start the first instruction you notice", "Number the steps in the order they need to happen, then begin", "Try to memorise the whole list before touching any equipment", "Ask someone else to complete the task for you"], "answer": 1},
    {"q": "You keep forgetting deadlines. What is the most reliable fix?", "options": ["Try harder to remember them", "Put every deadline in one calendar with reminders", "Write them on scattered sticky notes", "Ask classmates to remind you each time"], "answer": 1},
    {"q": "You have two hours to study four topics. What is the best approach?", "options": ["Study whichever topic feels easiest until you are bored", "Allocate time to each topic and set a timer for each", "Spend the whole two hours on the first topic", "Read all your notes once with no plan"], "answer": 1},
    {"q": "Halfway through a big task you realise it will not be finished in time. What is the best move?", "options": ["Keep going in order and hope for the best", "Identify the most important part and prioritise finishing that", "Stop and start something else", "Do the easiest parts first regardless of importance"], "answer": 1},
    {"q": "You are easily distracted by your phone while studying. What is the most effective step?", "options": ["Keep it next to you but promise not to check it", "Put it in another room, on silent and out of reach", "Reply to messages quickly so they stop", "Study with the phone screen facing up"], "answer": 1},
    {"q": "A group project has unclear roles. What is the best first step?", "options": ["Wait for someone else to take charge", "Agree who does what, and by when", "Everyone works on everything at once", "Split the mark and work separately without talking"], "answer": 1},
    {"q": "You tend to start assignments the night before and rush. What is the best change?", "options": ["Keep doing it, but drink more coffee", "Break the work across several days with small daily goals", "Ask for an extension every time", "Only start early on assignments you enjoy"], "answer": 1},
    {"q": "The instructions for a task change midway through. What is the best response?", "options": ["Carry on with the original plan anyway", "Pause, note what changed, and adjust the plan", "Start the whole task again from scratch", "Wait until the deadline and explain the confusion"], "answer": 1},
    {"q": "You have many small tasks and one big deadline. How should you decide the order?", "options": ["Do the quickest tasks first regardless of importance", "Rank tasks by importance and deadline, then do the highest-priority first", "Do them in the order you remember them", "Leave the big deadline until everything else is done"], "answer": 1},
]

# ---------------------------------------------------------------------------
# Writing & language: grammar multiple choice (the typing task is separate).
# ---------------------------------------------------------------------------
GRAMMAR_BANK = [
    {"q": "Choose the correct sentence.", "options": ["Neither of the tutors were available.", "Neither of the tutors was available.", "Neither of the tutors is being available.", "Neither of the tutors being available."], "answer": 1},
    {"q": "Choose the correct sentence.", "options": ["Its important to submit your assignment on time.", "It's important to submit your assignment on time.", "Its' important to submit your assignment on time.", "It important to submit your assignment on time."], "answer": 1},
    {"q": "Which word correctly completes: 'The results were better ___ we expected.'", "options": ["then", "than", "that", "wherein"], "answer": 1},
    {"q": "Choose the correctly punctuated sentence.", "options": ["The lecture, was interesting and useful.", "The lecture was interesting and useful.", "The lecture was interesting, and useful", "the lecture was interesting and useful"], "answer": 1},
    {"q": "Which word correctly completes: '___ going to submit their reports tomorrow.'", "options": ["Their", "There", "They're", "Theyre"], "answer": 2},
    {"q": "Which word correctly completes: 'The new policy will ___ every student.'", "options": ["affect", "effect", "affects", "effects"], "answer": 0},
    {"q": "Choose the correct sentence.", "options": ["The list of requirements are on the website.", "The list of requirements is on the website.", "The list of requirements were on the website.", "The list of requirements be on the website."], "answer": 1},
    {"q": "Choose the sentence with the correct possessive.", "options": ["The students results were posted online.", "The student's results were posted online.", "The students' results was posted online.", "The students result were posted online."], "answer": 1},
    {"q": "Which is a correctly joined sentence (no comma splice)?", "options": ["I studied hard, I still felt nervous.", "I studied hard, but I still felt nervous.", "I studied hard I still felt nervous.", "I studied hard, however I still felt nervous"], "answer": 1},
    {"q": "Which word correctly completes: '___ submitting the assignment late again.'", "options": ["Your", "You're", "Youre", "Yours"], "answer": 1},
    {"q": "Which word correctly completes: 'There are ___ students in the class this year.'", "options": ["less", "fewer", "lesser", "little"], "answer": 1},
    {"q": "Choose the correct sentence.", "options": ["The lecturer gave the notes to John and I.", "The lecturer gave the notes to John and me.", "The lecturer gave the notes to John and myself.", "The lecturer gave the notes to I and John."], "answer": 1},
    {"q": "Which word correctly completes: 'By next week I ___ finished the project.'", "options": ["will have", "will has", "have had", "will be have"], "answer": 0},
    {"q": "Which word correctly completes: 'The tutor ___ helped me was very patient.'", "options": ["which", "who", "whom", "what"], "answer": 1},
    {"q": "Which word correctly completes: 'Try not to ___ your student card.'", "options": ["loose", "lose", "loosen", "loses"], "answer": 1},
]

# ---------------------------------------------------------------------------
# Reading fluency: a timed passage, then comprehension questions. One whole set
# (passage + its questions) is drawn per attempt.
# ---------------------------------------------------------------------------
READING_BANK = [
    {
        "passage": (
            "The Disability Unit at the university offers assistive technology, extended time in "
            "assessments, and note-taking support to registered students. Applications open at the "
            "start of each semester and require a supporting report from a registered practitioner. "
            "Students are encouraged to apply early, since assessment of applications can take up to "
            "three weeks and support cannot be backdated once a semester's tests have begun."
        ),
        "questions": [
            {"q": "What three forms of support does the passage mention?", "options": ["Tutoring, funding, transport", "Assistive technology, extended time, note-taking support", "Counselling, housing, meals", "Library access, printing, Wi-Fi"], "answer": 1},
            {"q": "What must accompany an application?", "options": ["A letter from a lecturer", "A supporting report from a registered practitioner", "A copy of the timetable", "A bank statement"], "answer": 1},
            {"q": "What happens if a student applies after tests have started?", "options": ["Support is backdated automatically", "Support cannot be backdated", "The application is rejected outright", "The student is fast-tracked"], "answer": 1},
        ],
    },
    {
        "passage": (
            "The campus library extended its hours during the examination period, staying open until "
            "midnight on weekdays. Group study rooms can be booked online for up to two hours at a "
            "time, and a valid student card is needed to enter after 18:00. Food is not allowed in "
            "the silent study area, but a cafe on the ground floor remains open until 22:00."
        ),
        "questions": [
            {"q": "Until what time does the library stay open on weekdays during exams?", "options": ["20:00", "22:00", "Midnight", "01:00"], "answer": 2},
            {"q": "How long can a group study room be booked at one time?", "options": ["One hour", "Two hours", "Three hours", "The whole day"], "answer": 1},
            {"q": "What is needed to enter after 18:00?", "options": ["A booking receipt", "A valid student card", "A staff escort", "Nothing"], "answer": 1},
        ],
    },
    {
        "passage": (
            "A student society organised a coding workshop for beginners on Saturday morning. Places "
            "were limited to thirty, and registration closed once the list was full. Attendees were "
            "asked to bring their own laptops, though a few loan machines were available on request. "
            "The society said a follow-up session would be scheduled if there was enough interest."
        ),
        "questions": [
            {"q": "How many places were available at the workshop?", "options": ["Twenty", "Thirty", "Forty", "Unlimited"], "answer": 1},
            {"q": "What were attendees asked to bring?", "options": ["Their own laptops", "A textbook", "A registration fee", "A packed lunch"], "answer": 0},
            {"q": "What determines whether a follow-up session happens?", "options": ["The weather", "Whether there is enough interest", "Approval from the library", "The number of loan laptops"], "answer": 1},
        ],
    },
    {
        "passage": (
            "The university introduced a shuttle service between the two main campuses to reduce "
            "travel time for students with back-to-back classes. The shuttle runs every twenty minutes "
            "from 07:00 to 18:00 and is free with a student card. During the first month, students were "
            "asked to give feedback through an online form so the timetable could be improved."
        ),
        "questions": [
            {"q": "Why was the shuttle service introduced?", "options": ["To raise money for the university", "To reduce travel time between campuses", "To replace the library bus", "To give tours to visitors"], "answer": 1},
            {"q": "How often does the shuttle run?", "options": ["Every ten minutes", "Every twenty minutes", "Every hour", "Twice a day"], "answer": 1},
            {"q": "How were students asked to give feedback?", "options": ["By calling the office", "Through an online form", "At a public meeting", "By email to the driver"], "answer": 1},
        ],
    },
]

# ---------------------------------------------------------------------------
# Copy-typing sentences (writing test). One is drawn per attempt.
# ---------------------------------------------------------------------------
TYPING_SENTENCES = [
    "Students who register early receive extended time and assistive technology support.",
    "The library extends its opening hours during the examination period each semester.",
    "Please remember to bring your student card and a fully charged laptop to the workshop.",
    "Applications for support must include a report from a registered practitioner.",
    "The shuttle between campuses runs every twenty minutes and is free with a student card.",
    "Breaking a large assignment into smaller steps makes it far easier to manage.",
    "Reasonable accommodations help create a more inclusive learning environment for everyone.",
    "Reading each question carefully before answering can prevent simple avoidable mistakes.",
]


# ---------------------------------------------------------------------------
# Drawing helpers. All take an optional `rng` so a test can be made repeatable.
# ---------------------------------------------------------------------------

def _shuffle_options(item, rng):
    """
    Return a copy of a multiple-choice item with its options shuffled and the
    `answer` index updated to wherever the correct option landed. This removes
    any fixed answer position, so the correct choice is never predictable.
    """
    options = list(item["options"])
    correct_text = options[item["answer"]]
    rng.shuffle(options)
    return {
        "q": item["q"],
        "options": options,
        "answer": options.index(correct_text),
    }


def draw_mcq(domain, rng=None):
    """Draw DRAW_COUNTS[domain] questions for an MCQ domain, options shuffled."""
    rng = rng or random
    bank = {"math": MATH_BANK, "scenario": SCENARIO_BANK, "grammar": GRAMMAR_BANK}[domain]
    count = min(DRAW_COUNTS[domain], len(bank))
    picked = rng.sample(bank, count)
    return [_shuffle_options(item, rng) for item in picked]


def draw_reading(rng=None):
    """Pick one reading set; return (passage, shuffled comprehension questions)."""
    rng = rng or random
    chosen = rng.choice(READING_BANK)
    questions = [_shuffle_options(q, rng) for q in chosen["questions"]]
    return chosen["passage"], questions


def random_memory_sequences(rng=None):
    """
    Build fresh digit sequences of lengths 3, 4, 5 and 6 (same lengths as the
    original test, so scoring is unchanged) with random digits each attempt.
    """
    rng = rng or random
    return [[str(rng.randint(0, 9)) for _ in range(length)] for length in (3, 4, 5, 6)]


def random_typing_sentence(rng=None):
    """Pick one copy-typing sentence for the writing test."""
    return (rng or random).choice(TYPING_SENTENCES)
