# OwlPath Universal — TUJ Academic Planning Demonstration

**2026-11-06 prototype, data-driven rebuild.** Computer Science BA, Computer Science BS and Psychology BA are discovered at startup from independent program data files. The same Python engine and Streamlit interface are used for every program.

This is **not an official degree audit, graduation guarantee, TUJ course schedule, or institutional advisor approval**. Sample records are synthetic. College, language, GPA, GenEd, university exceptions and future campus offerings need independent advisor verification.

## Install and run

**Windows PowerShell** (from the unzipped `OwlPath_Universal` directory):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

**Mac Terminal** (from the unzipped `OwlPath_Universal` directory):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Use **Python 3.10 or newer**. Open <http://localhost:8501>. The app works without an LLM API key. For optional AI questions, set the key in the same terminal before starting Streamlit:

```bash
export OPENAI_API_KEY="your-key"  # Mac/Linux
# $env:OPENAI_API_KEY = "your-key" # Windows PowerShell
```

Do not commit API keys. ChatGPT subscription and API billing are separate. Do not test with identifiable real student records.

## Test without Streamlit

```bash
python -m unittest discover -s tests -v
python run_demo.py --profile psy_neuro
python run_demo.py --profile psy_clinical
python run_demo.py --profile cs_ai
python run_demo.py --profile cs_cyber
python run_demo.py --profile psy_math_blocked
```

Generated JSON and Markdown advising briefs appear under `outputs/`.

## Architecture: academic facts are data, not code

```
OwlPath_Universal/
  engine.py                        # Major-independent academic rules and planner
  app.py                           # Major-independent Streamlit UI
  demo.py                          # Profile input and exports
  ai.py                            # Optional grounded AI explanation
  run_demo.py                      # Offline scenarios
  catalog/
    courses.json                   # Course ID, title, credits, source, interests
    prerequisites.json             # AND/OR prerequisite expression trees
    interest_labels.json           # UI interest vocabulary
    profile_flags.json             # UI documented eligibility flags
    sources.json                   # Source provenance/limitations
    templates/
      CST_2026.json                # CST GenEd slots/waivers
      CLA_2026.json                # CLA GenEd slots (including GS x 2)
    programs/
      CS_BA_2026.json
      CS_BS_2026.json
      PSY_BA_2026.json
  samples/                         # Synthetic students, no real student information
  tools/new_major.py               # Generates draft program file
  tests/                            # Academic and headless UI tests
```

At startup `Catalog()` loads **all** `catalog/programs/*.json`. Adding a valid program requires no new `if major == ...` branches in `engine.py`, `demo.py`, `app.py`, or `ai.py`. There is a regression test that copies an existing program as a fourth program, reloads the catalog and generates its plan without changing runtime code.

## How to add a new major

1. Consult the **current official Bulletin year** and TUJ program page, noting variant/concentration, college rules, and the campus. Don't confuse a current program with an older TUJ page.
2. Add **new distinct course records** to `catalog/courses.json`: `id`, `title`, numeric `credits`, `subject`, `level`, `school`, official `source`, `metadata_verified` and topical `tags` (0–3). Existing courses are shared, never duplicated by major.
3. Add course prerequisite expressions to `catalog/prerequisites.json`. See below. If a prerequisite is not fully known, represent it as an **unverified flag** and exclude it from automatic selection; do not assume it is satisfied.
4. Reuse a GenEd template or add a new `catalog/templates/<TEMPLATE>.json` with the slot list (the engine discovers templates automatically).
5. Create a new major definition with `python tools/new_major.py --id SOC_BA_2026 --major Sociology --degree BA --template CLA_2026`. The file appears in `drafts/`. Edit it and **only move it into `catalog/programs` once it has correct groups**.
6. Put academic requirements into the new program's JSON `groups`, `other_slots`, and `checks`. Add tags to `catalog/interest_labels.json` for new interests.
7. Test the catalog, build two contrasting synthetic profiles, verify course sequencing and the new program's capstone/upper-level rules. Restart Streamlit. The degree is now listed in the dropdown.

### Program requirement group examples

One required course:

```json
{"id":"INTRO","label":"Introduction","type":"choose","count":1,"section":"major","choices":[["SUBJ1001"]]}
```

Choose two distinct electives:

```json
{"id":"FOUNDATION","label":"Foundation electives","type":"choose","count":2,"section":"major", "choices":[["SUBJ2001"],["SUBJ2002"],["SUBJ2003"]]}
```

A choice between **bundled** lecture + lab and a single course:

```json
{"id":"SCIENCE","label":"Science","type":"choose","count":1,"section":"major", "choices":[["BIOL1001"],["CHEM1021","CHEM1023"]]}
```

Select a credit range with arbitrary generic limits:

```json
{"id":"ELECTIVES","label":"Major electives","type":"credits","min_credits":15,"max_credits":16,
 "choices":[["SUBJ3300"],["SUBJ3400"],["SUBJ3500"]],
 "limits":[{"choices":["SUBJ3300","SUBJ3400"],"max_courses":1}],"section":"major"}
```

To conservatively keep bundle elements in successive terms, use `"bundle_order":"separate_terms"` on a group. This **modeling convention** is not automatically an official university prerequisite.

### Prerequisites: generic expression grammar

Everything is described with recursive JSON conditions using `all`, `any`, `course`, `flag`, `subject_level`, `min_prior_credits`:

```json
{
 "PSY4696": {
   "all": [
     {"any":[{"course":"PSY3096"},{"course":"PSY2196"}]},
     {"min_prior_credits":90}
   ],
   "verified":true,
   "source":"https://bulletin.temple.edu/courses/psy/"
 }
}
```

`min_prior_credits` is tested against **credits at the start of the term**, not credits simultaneously scheduled that semester. For `subject_level`, e.g. at least one completed PSY 2000-level course, use `{"subject_level":{"subject":"PSY","min_level":2000,"max_level":2999}}`. Eligibility flags are explicit **synthetic declarations** for things like math placement and honors permission; the planner does not invent these approvals.

### Other academic verification checks

Program files support `major_credits`, `courses_complete`, `credits_scope`, `residency`, `slot_or_flag` and `manual`. College-wide school/level credits, residency and GPA remain flagged for **advisor review** when unverified metadata or placeholders make a certified result impossible.

## What is verified and what is not

- **Modeled deterministic checks:** prerequisite course ordering; `choose N` distinct-course groups; bundle selections; program-specific required courses; approved elective credit ranges; capstone **90-prior-credit** rule for Psychology; overall simulated credits; generic GenEd slots; student interest ranking; warning / blocked outcomes.
- **Not verified:** exact TUJ Tokyo/Kyoto offerings, registration conflicts, catalog exceptions, actual transfer equivalencies, institutional GPA, verified future university residency, language placement details, complete live GenEd course equivalence. Credit placeholders **are not actual courses**.
- Courses with missing credit/prerequisite metadata are retained for reference but excluded from automatic option selection. The Psychology advanced catalog is represented, but course offerings at TUJ and some source-specific prerequisites must be checked by an advisor.
- The LLM, when configured, receives only the **selected provisional plan, interests, career interests and validation notices**, not names, student IDs or grades. It never changes a course plan.

## Sources and provenance

Primary public sources (catalog year **2026–27**):

- [Psychology BA](https://bulletin.temple.edu/undergraduate/liberal-arts/psychology-ba/) — degree requirements including DCS (choose 2), BCS (choose 2), advanced (choose 3), additional elective, science option, methods course and senior capstone.
- [Psychology courses](https://bulletin.temple.edu/courses/psy/) — course titles, credits and course-specific prerequisites.
- [TUJ Psychology](https://www.tuj.ac.jp/ug/academics/academic-requirements/major-minor-requirements/psychology) — Japan-campus cross-check; current Bulletin takes precedence when catalog years differ.
- [Computer Science BA](https://bulletin.temple.edu/undergraduate/science-technology/computer-science-ba/) and [Computer Science BS](https://bulletin.temple.edu/undergraduate/science-technology/computer-science-bs/) — migrated from the earlier tested CS CSV dataset.
- [CIS course catalog](https://bulletin.temple.edu/courses/cis/) — baseline Computer Science prerequisites.

**How data was extracted:** Public course/degree text was read from official pages, and manually structured into one normalized courses table, generic prerequisite trees, common GenEd templates, and individual program JSON definitions. A one-time migration from the earlier CS CSV data was used for CS BA/BS. These program-specific facts are *not embedded* in the running Python code.

**Limitations:** A data-driven engine can support programs expressible by the current supported constraint grammar without code edits. A university program with a novel constraint (e.g., institutional double-count exceptions or GPA-driven access decisions) needs an explicit new generic rule type and validation tests; such requirements must not be silently treated as satisfied.
