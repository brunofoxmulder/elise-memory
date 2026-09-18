from elise_memory.google_sheets import SHEETS_READONLY, SheetRange


def test_scope_is_strictly_read_only():
    assert SHEETS_READONLY.endswith("/spreadsheets.readonly")
    assert SHEETS_READONLY != "https://www.googleapis.com/auth/spreadsheets"


def test_sheet_range_is_explicit():
    s=SheetRange("book","Référentiel métier","A1:P1000")
    assert s.spreadsheet_id=="book"
    assert s.sheet_name=="Référentiel métier"
