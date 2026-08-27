from dataclasses import dataclass


@dataclass
class FileCoverage:
    file: str
    lines_found: int
    lines_hit: int
    line_hits: dict[int, int]


def parse_lcov(text: str) -> dict[str, FileCoverage]:
    # Multiple SF:<path> records for the same path are merged by summing per-line hit counts --
    # lines_found/lines_hit are then derived from the merged line_hits rather than trusting the
    # declared LF:/LH: totals, since summing those directly across duplicate records would
    # double-count lines that appear in both.
    merged: dict[str, dict[int, int]] = {}
    current_file: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("SF:"):
            current_file = line[len("SF:") :]
            merged.setdefault(current_file, {})
        elif line.startswith("DA:"):
            if current_file is None:
                continue
            line_no_str, hit_count_str = line[len("DA:") :].split(",", 1)
            line_no = int(line_no_str)
            hit_count = int(hit_count_str)
            line_hits = merged[current_file]
            line_hits[line_no] = line_hits.get(line_no, 0) + hit_count
        elif line == "end_of_record":
            current_file = None

    if not merged:
        raise ValueError("No SF: records found -- not a valid lcov report")

    result = {}
    for file, line_hits in merged.items():
        lines_found = len(line_hits)
        lines_hit = sum(1 for count in line_hits.values() if count > 0)
        result[file] = FileCoverage(
            file=file, lines_found=lines_found, lines_hit=lines_hit, line_hits=line_hits
        )
    return result
