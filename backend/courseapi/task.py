from celery import shared_task
from backend.settings import env
from django.conf import settings
import gspread


@shared_task()
def save_hw_to_gsheets(row, task, url):
    if row is None:
        return
    client = gspread.service_account(filename=settings.GSHEET_CREDS)
    print(env('SPREADSHEET'))
    wsheet = client.open(env('SPREADSHEET')).get_worksheet(0)
    col = int(env('FIRST_TASK_COL')) + (task - 1) * 2
    wsheet.update_cell(row, col, url)


@shared_task()
def save_mark_to_gsheets(row, task, mark):
    if row is None:
        return
    client = gspread.service_account(filename=settings.GSHEET_CREDS)
    print(env('SPREADSHEET'))
    wsheet = client.open(env('SPREADSHEET')).get_worksheet(0)
    col = int(env('FIRST_TASK_COL')) + (task - 1) * 2 + 1
    wsheet.update_cell(row, col, mark)
