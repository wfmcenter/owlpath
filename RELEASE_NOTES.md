# Release notes — 2026-11-06

## Deliverables

- A new **program-independent Python engine** (`engine.py`) driven by catalog JSON records.
- A new **program-independent Streamlit app** (`app.py`), synthetic academic and interest profile input, three strategies, provisional advisor review, exports, optional grounded AI Q&A.
- Three program definitions: **Computer Science BA**, **Computer Science BS**, and **Psychology BA** (2026–27).
- Shared normalized catalog: **145 distinct course IDs** and **88 course prerequisite-rule objects**. Psychology course selections include its two 2-course foundations, 3 advanced courses, additional elective, science options and 90-prior-credit capstone condition.
- Two contrasting Psychology students and two contrasting CS students, plus blocked math-readiness case.
- **20 passing automated tests**, including headless Streamlit control-flow, academic capstone sequencing, multi-select rules, interest differentiation, invalid-data and dynamic new-program tests.
- Offline report JSON and Markdown advising briefs and a **static HTML browser preview** from actual planner output.

## What was verified

1. Python syntax compilation and 20 automated tests passed.
2. Program discovery without changes to code was tested with a newly added test program JSON.
3. Selected Psychology capstone is not scheduled until *at least 90 modeled credits were earned in previous terms*.
4. Clinical-oriented and neuroscience-oriented students with the same academic record receive distinct Psychology pathways.
5. AI- and cybersecurity-oriented CS students receive distinct electives.
6. Unverified math placement in a newly starting Psychology student leads to BLOCKED results.
7. Source-limited prerequisites remain unavailable rather than guessed as satisfied.
8. Static report HTML rendered in a Chromium browser; warnings appear visibly.

## What was **not** verified

- **Native Streamlit graphical browser session**: Streamlit was not installed in the execution environment; test harness simulates widget choices and checks control flow. User must run a local Streamlit smoke test after installing requirements.
- **Live OpenAI API call**: optional integration was not run with real credentials.
- **Real university data integration**, catalog exceptions, verified current TUJ class schedule, course enrollment sections, GPA/transfer equivalence, institutional permissions. No official degree audit.
- Psychology advanced 3413/3418 prerequisite details and CJ 3408 credits were not completely verified; such options are retained but blocked from automatic selection.
- GenEd and free elective positions are explicitly **provisional credit slots**, not actual Temple course registrations.

The word **modeled pass** means the constraints represented in this prototype passed. It does not mean graduation or official advising approval.
