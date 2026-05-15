from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread
import pandas as pd
import set_sy

#============== Shopify ==========================
SHOPIFY_ACCESS_TOKEN=set_sy.get_token()
HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    "Content-Type": "application/json"
}

#============== Google ==========================
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file(
    "credentials/dialy-report-automation-e20c53e67542.json",
    scopes=scope
)

service = build("sheets", "v4", credentials=creds)
sheet = service.spreadsheets()
gc = gspread.authorize(creds)
_SPREADSHEET_CACHE = {}
_WORKSHEET_CACHE = {}
_VALUES_CACHE = {}
_EXCEL_CACHE = {}

def _get_spreadsheet(sheet_id):
    spreadsheet = _SPREADSHEET_CACHE.get(sheet_id)
    if spreadsheet is None:
        spreadsheet = gc.open_by_key(sheet_id)
        _SPREADSHEET_CACHE[sheet_id] = spreadsheet
    return spreadsheet

def _get_worksheet(sheet_id, worksheet_name=None, worksheet_index=None):
    if worksheet_name is None and worksheet_index is None:
        raise ValueError("Either worksheet_name or worksheet_index must be provided")

    worksheet_key = worksheet_name if worksheet_name is not None else f"__index__{worksheet_index}"
    cache_key = (sheet_id, worksheet_key)
    worksheet = _WORKSHEET_CACHE.get(cache_key)
    if worksheet is None:
        spreadsheet = _get_spreadsheet(sheet_id)
        if worksheet_name is not None:
            worksheet = spreadsheet.worksheet(worksheet_name)
        else:
            worksheet = spreadsheet.get_worksheet(worksheet_index)
        _WORKSHEET_CACHE[cache_key] = worksheet
    return worksheet

def _get_sheet_values(
    sheet_id,
    worksheet_name=None,
    worksheet_index=None,
    range_name=None,
    use_all_values=False,
):
    cache_key = (sheet_id, worksheet_name, worksheet_index, range_name, use_all_values)
    values = _VALUES_CACHE.get(cache_key)
    if values is not None:
        return values

    worksheet = _get_worksheet(
        sheet_id=sheet_id,
        worksheet_name=worksheet_name,
        worksheet_index=worksheet_index,
    )
    if use_all_values:
        values = worksheet.get_all_values()
    else:
        values = worksheet.get(range_name)
    _VALUES_CACHE[cache_key] = values
    return values

def _read_excel_cached(path, header):
    cache_key = (path, header)
    dataframe = _EXCEL_CACHE.get(cache_key)
    if dataframe is None:
        dataframe = pd.read_excel(path, header=header)
        _EXCEL_CACHE[cache_key] = dataframe
    return dataframe

#============== 
