# ResiCall

Generates fair on-call schedules for residents. You fill in your residents, dates, holidays, and vacations in a notebook, run it, and it hands back a schedule plus some charts showing how balanced it is.

No programming knowledge is required to use this — you're editing values in a form (a "cell" in the notebook), not writing code.

## What's in here

- `senior_call_scheduler.ipynb` — schedules senior residents (buddy call, holidays, rotation-aware).
- `junior_call_scheduler.ipynb` — schedules junior residents (AM/PM half-day rotation blocks).
- `calendar_to_import.py` — an optional helper script that converts an existing horizontal-calendar CSV export (months side by side) into a format the notebooks can import as a starting point. Most people won't need this unless they're importing a schedule from last cycle.

## Requirements

- **Python 3.10 or newer.** If you don't already have Python, get it from [python.org/downloads](https://www.python.org/downloads/) — on Windows, check the box that says "Add Python to PATH" during install. On Mac, you can also install it with `brew install python`.
- That's it. Everything else gets installed in the setup steps below.

## Setup (do this once)

1. **Download this repository** — click the green "Code" button on GitHub → "Download ZIP", then unzip it somewhere you'll remember (e.g. your Desktop). If you're comfortable with `git clone`, that works too.
2. **Open a terminal.**
   - Windows: search for "Command Prompt" or "PowerShell" in the Start menu.
   - Mac: open "Terminal" from Applications → Utilities.
3. **Navigate to the folder you unzipped.** For example:
   ```bash
   cd Desktop/resicall
   ```
4. **Install the required packages:**
   ```bash
   pip install -r requirements.txt
   ```
   This downloads the scheduling engine (OR-Tools) and a few supporting libraries. It can take a minute or two — that's normal.
5. **Start Jupyter:**
   ```bash
   jupyter notebook
   ```
   This opens a browser tab showing the files in this folder. (If it doesn't open automatically, the terminal will print a `http://localhost:8888/...` link — copy/paste that into your browser.)

> **Using a virtual environment is optional.** If you already know what one is and prefer to use one, go ahead (`python -m venv venv` then activate it before step 4). If that sentence meant nothing to you, ignore it — the steps above work fine without it.

## Quick start

1. In the Jupyter browser tab, click `senior_call_scheduler.ipynb` (or `junior_call_scheduler.ipynb` — see below for which one you want).
2. Scroll to the section headed **"1) Schedule Parameters -- Adjust This"**. This is the one section you need to fill in — see "Configuration" below for what goes where.
3. From the menu, choose **Cell → Run All** (or **Run → Run All Cells**, depending on your Jupyter version).
4. Scroll down to the cell that prints `Solver status:`. You want it to say `FEASIBLE` or `OPTIMAL`. If it says `INFEASIBLE`, see "Troubleshooting" below.
5. Look for a new folder matching your `solution_name` (e.g. `senior_V1/`) inside the repository folder — that's where your schedule and charts land.

**Which notebook do I use?** `senior_call_scheduler.ipynb` if you're scheduling senior residents (it understands buddy call, holiday-only-for-seniors rules, and full-day rotations). `junior_call_scheduler.ipynb` if you're scheduling junior residents (it understands AM/PM half-day rotations instead). If you schedule both groups, you'll run both notebooks separately.

Both notebooks ship with a handful of placeholder residents (`ZZZ`, `YYY`, `XXX`, etc.) already filled in, so running one start-to-finish with zero edits will actually produce a working example schedule — useful for confirming your setup works before you touch anything.

## Configuration

**Sections you're expected to edit:**
- **"1) Schedule Parameters -- Adjust This"** — residents, dates, holidays, rotations, vacations, preferences, manual assignments. This is one long code cell; everything below in this README section lives inside it.
- **"2) Model Parameters -- Adjust This"**, *only if needed* — see "Model tuning" below.

**Everything else, leave alone.** The rest of the notebook (sections 3 onward: build model, solve, write results, plot diagnostics) reads whatever you put in the two sections above and doesn't need to be touched or understood to use the notebook. Just run it.

All hand-filled configuration lives in "1) Schedule Parameters -- Adjust This" (`# RESIDENTS` through `# MANUAL ASSIGNMENTS`).

**Residents**
```python
senior_residents = ["ZZZ", "XXX", "WWW"]       # senior-only, e.g. can take buddy call / holidays
less_senior_residents = ["YYY", "VVV"]         # junior-senior tier
residents = senior_residents + less_senior_residents
```
Use whatever short codes you want (initials, IDs, nicknames) — they're just dictionary keys and plot labels. Delete the placeholder entries and replace them with your actual roster. Keep the senior list at 2+ people if buddy call or holiday coverage needs to keep working while someone's on vacation — a lone senior resident can't cover a holiday week solo if the rules say seniors only.

**Date range**
```python
start_date = datetime(2026, 7, 5)
end_date   = datetime(2027, 7, 4)
```

**Holidays** — `datetime : shift_length` (12 or 24 hour override):
```python
holidays = {
    datetime(2026, 7, 4): 24,   # Independence Day
    ...
}
```

**Rotation blocks and per-resident rotations** — used to figure out who's even eligible on a given day:
```python
rotation_blocks = [
    {"block": 1, "start": datetime(2026, 6, 11).date(), "end": datetime(2026, 9, 10).date()},
    ...
]
resident_rotations = {
    "ZZZ": {1: "Rotation 1", 2: "Rotation 2", ...},
}
```

**Vacations**
```python
vacation_ranges = [
    {"res": "ZZZ", "start": "2026-12-29", "end": "2027-01-02"},
]
```
Flanking weekends and holidays get padded onto these automatically later in the notebook — you don't need to include them yourself.

**Preferences (soft — solver will try to honor, not guaranteed)**
```python
resident_preferences = {
    "ZZZ": {"avoid_ranges": [(date(2026, 8, 1), date(2026, 8, 7))]},
}
```

**Manual assignments (hard overrides for specific dates, e.g. a conference)**
```python
manual_assignments = {
    datetime(2026, 8, 10): "ZZZ",
}
```

**Model tuning ("2) Model Parameters -- Adjust This": `HARD CONSTRAINT PARAMETERS` / `SOFT CONSTRAINT WEIGHTS`)** — leave alone unless the solver keeps giving you a schedule you don't like or can't find a feasible one. The weights are commented with what each one controls.

## Importing a prior schedule

The "Optional: Import prior schedule as manual assignments" section (right after Schedule Parameters) looks for a file named exactly `import.txt` inside your output folder, and loads it automatically if it's there — no code to write.

1. Run the "1) Schedule Parameters" section first (this creates the `<solution_name>/` folder, e.g. `senior_V1/`).
2. Convert your prior schedule export into that format:
   ```bash
   python calendar_to_import.py prior_schedule.csv senior_V1/import.txt
   ```
3. Run the "Optional: Import prior schedule" section — it'll print the assignments it picked up. If `import.txt` isn't there, it just says so and moves on; nothing breaks either way.

This is useful for locking in dates that are already committed (e.g. the start of the new block overlapping with the tail of the old one).

## Output files

Written to `<solution_name>/` (e.g. `senior_V1/`):

| File | Contents |
|---|---|
| `*_shift_summary.txt` | Per-resident totals: shift counts, holiday counts, fairness stats. |
| `*_long_list_schedule.txt` | One row per day: assigned resident, holiday flag, who's on vacation, who's on an OR day. Pipe-delimited — same format `calendar_to_import.py` produces, so it can be re-imported next cycle. |
| `*_month_grid_calendar.txt` | Plain-text month-grid view of the schedule. |
| `*_month_grid_compact.csv` | Same, as CSV. |
| `*_vacation_grid.csv` | Month-grid view of who's on vacation when. |
| `*_scheduling_fairness.png` | Bar charts of shift/holiday distribution across residents — check this for obvious imbalance. |
| `*_month_grid_gantt.png` | Full-schedule Gantt chart, one row per resident. |

## Troubleshooting

**`pip install -r requirements.txt` fails, or errors out partway through.**
- Make sure you're running a recent Python (`python --version` should say 3.10+). Old Python versions can't install newer OR-Tools.
- Try `pip3` instead of `pip` if `pip` isn't recognized.
- On Windows, if you get a permissions error, try `pip install --user -r requirements.txt`.
- If one package fails (commonly `ortools` on an unusual OS/CPU combo), you can install the rest individually: `pip install pandas numpy matplotlib jupyter`, then retry `pip install ortools` on its own to see the actual error.

**A notebook cell errors with `ModuleNotFoundError` or "No module named X".**
- This means a package didn't install. Re-run `pip install -r requirements.txt` in the same terminal/environment you launched Jupyter from — it's easy to accidentally install packages into a different Python than the one Jupyter is using.
- The first cell in each notebook (`ensure_installed`) will try to auto-install a missing package the moment you run it — if it still fails, the error printed there tells you what to install manually.

**`Solver status:` comes back `INFEASIBLE`** (no valid schedule exists with what you gave it):
1. **Check for overlapping hard requirements first** — someone manually assigned to a date they're also marked on vacation for, or two `manual_assignments` conflicting with rotation eligibility.
2. **Check rotation coverage** — every day in `start_date`..`end_date` needs at least one eligible resident per the hard constraints (seniority, rotation, buddy-call window). A gap in `rotation_blocks` or `resident_rotations` will make a day unsolvable.
3. **Loosen a hard constraint** — `senior_cutoff_days`, `max_shift_deviation`, `max_12_buddy_shift_deviation`, `max_24_buddy_shift_deviation` in "2) Model Parameters" are the usual culprits. Try increasing the deviation allowances by 1 and re-run.
4. **Reduce vacation overlap** — if too many residents are on vacation on the same days, there may not be enough people left to cover. Check `*_vacation_grid.csv` from a previous run, or just eyeball `vacation_ranges`.
5. If it's still infeasible after that, cut the date range down (e.g. one rotation block at a time) to isolate which stretch is the problem.

**Solver comes back `FEASIBLE` but the schedule looks unbalanced or "off."** Not an error — the solver found *a* valid schedule but either hit the 30-second time limit (`solver.parameters.max_time_in_seconds`) before finding a better one, or a soft-constraint weight needs adjusting. Check `*_scheduling_fairness.png` first, then tune the weights in "2) Model Parameters" (increase the weight for whatever's unbalanced).

**The notebook seems stuck / is taking a long time to run.** The solver cell can genuinely take up to its time limit (30 seconds by default) especially on longer date ranges or more residents — that's expected, not frozen. If it's been stuck far longer than that on a different cell, check whether a `pip install` prompt is waiting for input in the terminal window behind your browser.

## Privacy

Real resident names/initials, vacation dates, and preferences are personal scheduling data — don't publish or commit them to a shared/public copy of this repository.

- Before sharing your copy of a notebook with anyone (or pushing it to GitHub), clear its outputs: in Jupyter, **Cell → All Output → Clear**, then save. Running the notebook prints and plots your real data *inside the file itself* — putting placeholder names back into "1) Schedule Parameters" afterward does **not** remove data that was already printed or charted while it had real names in it.
- Run `git status` before every commit and check what's actually staged, especially inside `senior_V1/` / `junior_V1/` (or whatever you set `solution_name` to) — that folder is where your real schedule and charts land, and `.gitignore` rules can drift out of sync with it over time.

## License

Licensed under **GPLv3**. Use it, modify it, run your own program's schedule with it — just keep any modified version you distribute open source too. See `LICENSE` for the full text.
