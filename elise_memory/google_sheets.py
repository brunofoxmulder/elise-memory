"""Read-only Google Sheets source adapter for canonical compilation."""

from dataclasses import dataclass

from google.oauth2 import service_account
from googleapiclient.discovery import build

SHEETS_READONLY = "https://www.googleapis.com/auth/spreadsheets.readonly"


@dataclass(frozen=True)
class SheetRange:
    spreadsheet_id: str
    sheet_name: str
    a1_range: str


class GoogleSheetsReader:
    """Minimal Sheets v4 reader. It exposes no write operation."""

    def __init__(self, credentials_file: str) -> None:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_file, scopes=[SHEETS_READONLY]
        )
        self._service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

    def values(self, source: SheetRange) -> list[list[str]]:
        range_name = f"'{source.sheet_name.replace(chr(39), chr(39)*2)}'!{source.a1_range}"
        result = (
            self._service.spreadsheets()
            .values()
            .get(
                spreadsheetId=source.spreadsheet_id,
                range=range_name,
                valueRenderOption="FORMATTED_VALUE",
            )
            .execute()
        )
        return result.get("values", [])
