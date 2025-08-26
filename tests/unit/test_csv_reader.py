import pytest
from showads_connector.csv_reader import iter_csv_rows

def _write(tmp_path, name, text):
    p = tmp_path / name  # build file path (tmp_path is a pytest fixture: a fresh temporary directory)
    p.write_text(text, encoding="utf-8", newline="\n")  # creates the file and writes text into it
    return p

def test_missing_header_raises(tmp_path):
    p = _write(tmp_path, "no_header.csv", "")   # creates an empty CSV file (no header row)
    with pytest.raises(ValueError, match="CSV has no header"):  # asserts the block raises a ValueError and match the error msg (re.search)
        next(iter_csv_rows(str(p))) # next() forces the first iteration of the generator

def test_duplicate_headers_after_trim_raises(tmp_path):
    # Duplicate "Name" (second one has spaces that get trimmed)
    p = _write(tmp_path, "dupe.csv", "Name,  Age , Cookie,  Name \nJohn,35,u,12\n")
    with pytest.raises(ValueError, match="Duplicate headers"):
        list(iter_csv_rows(str(p)))

def test_trims_and_ignores_unknowns(tmp_path):
    # Headers and values get trimmed; unknown "Notes" is ignored
    p = _write(
        tmp_path,
        "trim_unknown.csv",
        "  Name  , Age , Cookie , Banner_id , Notes \n John Doe , 35 , u , 7 , hello \n",
    )
    (line_no, row), = list(iter_csv_rows(str(p)))
    assert line_no == 2
    assert row == {"Name": "John Doe", "Age": "35", "Cookie": "u", "Banner_id": "7"}
    assert "Notes" not in row

def test_skips_blank_lines_and_line_numbers(tmp_path):
    # Blank line between header and data is skipped
    p = _write(
        tmp_path,
        "blank.csv",
        "Name,Age,Cookie,Banner_id\n\nJane,22,u2,9\n",
    )
    rows = list(iter_csv_rows(str(p)))
    assert len(rows) == 1
    line_no, row = rows[0]
    assert line_no == 2  # DictReader skipped the blank line
    assert row == {"Name": "Jane", "Age": "22", "Cookie": "u2", "Banner_id": "9"}
