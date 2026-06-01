"""Coaching methodology constants (docs/DESIGN.md §10).

Frameworks encoded into prompts: GROW, OKR/SMART, Motivational Interviewing,
behavioral design (Atomic/Tiny Habits), Immunity to Change. Style adapts to
the user's preferences (challenger vs supporter; direct vs socratic).
"""

FRAMEWORKS = [
    "GROW",
    "OKR",
    "SMART",
    "MotivationalInterviewing",
    "BehavioralDesign",
    "ImmunityToChange",
]

# Hard boundaries: NOT therapy/medical/legal/financial advice. See app/safety/.
