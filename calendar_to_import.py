#!/usr/bin/env python3
"""Convert a horizontal "calendar" call-schedule CSV into a normalized
pipe-delimited import file.

The source CSVs lay months out side-by-side. Each month block repeats the
same set of sub-columns, headed by a "Date" column:

    Date | Day | Shift Type | On Call | Vacation 1..N | Holiday

This script locates those blocks dynamically (by finding every column
where the header row reads "Date"), so it does not care how many months
or how many Vacation columns are present.
"""

from __future__ import annotations

import argparse
import csv
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

logger = logging.getLogger("calendar_to_import")

# Row (0-indexed) within the source CSV that holds the repeating sub-column
# headers ("Date", "Day", "Shift Type", "On Call", "Vacation N", "Holiday").
HEADER_ROW_INDEX = 2

# Known date formats seen in these schedules, tried in order.
DATE_FORMATS = ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d")


@dataclass
class MonthBlock:
    """Column indices for one month's worth of sub-columns."""

    date_col: int
    day_col: Optional[int] = None
    shift_type_col: Optional[int] = None
    on_call_col: Optional[int] = None
    holiday_col: Optional[int] = None
    vacation_cols: list[int] = field(default_factory=list)


@dataclass
class ScheduleRecord:
    """One raw parsed row from a month block, before normalization."""

    date: date
    resident: str
    holiday_raw: str
    vacationers: list[str]


@dataclass
class ImportRow:
    """One row of the final normalized output."""

    date: date
    resident: str
    holiday: bool
    vacationing_residents: list[str]
    or_day_residents: list[str] = field(default_factory=list)


def find_month_blocks(header_row: list[str]) -> list[MonthBlock]:
    """Locate each repeating month block in the header row.

    A block starts at a column containing "Date" and runs until the next
    "Date" column (or the end of the row). Sub-columns within the block
    are identified by name, so the number of Vacation columns can vary
    freely between files.
    """
    date_indices = [i for i, val in enumerate(header_row) if val.strip() == "Date"]
    if not date_indices:
        raise ValueError("No 'Date' columns found in header row; cannot detect month blocks.")

    blocks: list[MonthBlock] = []
    for i, start in enumerate(date_indices):
        end = date_indices[i + 1] if i + 1 < len(date_indices) else len(header_row)
        block = MonthBlock(date_col=start)
        for col in range(start, end):
            name = header_row[col].strip()
            if col == start:
                continue  # the Date column itself
            if name == "Day":
                block.day_col = col
            elif name == "Shift Type":
                block.shift_type_col = col
            elif name == "On Call":
                block.on_call_col = col
            elif name == "Holiday":
                block.holiday_col = col
            elif name.startswith("Vacation"):
                block.vacation_cols.append(col)
        blocks.append(block)

    logger.debug("Detected %d month block(s).", len(blocks))
    return blocks


def _parse_date(raw: str) -> Optional[date]:
    """Parse a date cell, trying known formats. Returns None if unparseable."""
    raw = raw.strip()
    if not raw or raw.upper() == "NA":
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_schedule(rows: list[list[str]], blocks: list[MonthBlock]) -> list[ScheduleRecord]:
    """Walk every data row and every month block, extracting raw records."""
    records: list[ScheduleRecord] = []

    for row_num, row in enumerate(rows, start=HEADER_ROW_INDEX + 2):
        if not any(cell.strip() for cell in row):
            continue  # blank/trailing row

        for block in blocks:
            try:
                if block.date_col >= len(row):
                    continue
                raw_date = row[block.date_col]
                parsed_date = _parse_date(raw_date)
                if parsed_date is None:
                    if raw_date.strip():
                        logger.warning(
                            "Row %d: skipping unparseable date %r in column %d",
                            row_num, raw_date, block.date_col,
                        )
                    continue

                resident = ""
                if block.on_call_col is not None and block.on_call_col < len(row):
                    resident = row[block.on_call_col].strip()

                holiday_raw = ""
                if block.holiday_col is not None and block.holiday_col < len(row):
                    holiday_raw = row[block.holiday_col].strip()

                vacationers = []
                for col in block.vacation_cols:
                    if col < len(row):
                        val = row[col].strip()
                        if val:
                            vacationers.append(val)

                records.append(ScheduleRecord(
                    date=parsed_date,
                    resident=resident,
                    holiday_raw=holiday_raw,
                    vacationers=vacationers,
                ))
            except (IndexError, ValueError) as exc:
                logger.warning("Row %d: skipping malformed record (%s)", row_num, exc)
                continue

    return records


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            result.append(v)
    return result


def normalize_records(records: list[ScheduleRecord]) -> list[ImportRow]:
    """Convert raw schedule records into normalized import rows."""
    rows: list[ImportRow] = []
    for rec in records:
        holiday = rec.holiday_raw.strip().upper() == "Y"
        rows.append(ImportRow(
            date=rec.date,
            resident=rec.resident,
            holiday=holiday,
            vacationing_residents=_dedupe_preserve_order(rec.vacationers),
            or_day_residents=[],
        ))
    return rows


def fill_missing_dates(rows: list[ImportRow]) -> list[ImportRow]:
    """Fill any gap between the min and max dates with default rows.

    Existing entries take precedence over generated defaults.
    """
    if not rows:
        return rows

    by_date: dict[date, ImportRow] = {r.date: r for r in rows}
    min_date = min(by_date)
    max_date = max(by_date)

    filled: list[ImportRow] = []
    current = min_date
    while current <= max_date:
        if current in by_date:
            filled.append(by_date[current])
        else:
            filled.append(ImportRow(
                date=current,
                resident="",
                holiday=False,
                vacationing_residents=[],
                or_day_residents=[],
            ))
        current += timedelta(days=1)

    return filled


def write_import_file(rows: list[ImportRow], output_path: str) -> None:
    """Write rows to a pipe-delimited file, sorted by date ascending."""
    rows_sorted = sorted(rows, key=lambda r: r.date)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        f.write("Date|Resident|Holiday|VacationingResidents|ORDayResidents\n")
        for row in rows_sorted:
            vacationing = ", ".join(row.vacationing_residents)
            or_day = ", ".join(row.or_day_residents)
            f.write(
                f"{row.date.isoformat()}|{row.resident}|{row.holiday}|{vacationing}|{or_day}\n"
            )


def read_csv_rows(input_path: str) -> list[list[str]]:
    with open(input_path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a horizontal calendar-format call schedule CSV "
                     "into a normalized pipe-delimited import file."
    )
    parser.add_argument("input_csv", help="Path to the source calendar-format CSV.")
    parser.add_argument("output_txt", help="Path to write the pipe-delimited output file.")
    parser.add_argument(
        "--fill-missing-dates",
        dest="fill_missing_dates",
        action="store_true",
        default=True,
        help="Fill gaps in the date range with default rows (default: enabled).",
    )
    parser.add_argument(
        "--no-fill-missing-dates",
        dest="fill_missing_dates",
        action="store_false",
        help="Do not fill gaps in the date range.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    all_rows = read_csv_rows(args.input_csv)
    if len(all_rows) <= HEADER_ROW_INDEX:
        raise ValueError(f"Input file has fewer than {HEADER_ROW_INDEX + 1} rows; cannot find header.")

    header_row = all_rows[HEADER_ROW_INDEX]
    data_rows = all_rows[HEADER_ROW_INDEX + 1:]

    blocks = find_month_blocks(header_row)
    records = parse_schedule(data_rows, blocks)
    import_rows = normalize_records(records)

    if args.fill_missing_dates:
        import_rows = fill_missing_dates(import_rows)

    write_import_file(import_rows, args.output_txt)

    print(f"Processed {len(records)} schedule entries.")
    print(f"Generated {len(import_rows)} output rows.")
    print(f"Wrote output to {args.output_txt}.")


if __name__ == "__main__":
    main()
