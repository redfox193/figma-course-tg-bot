from .models import Statistic, Member, Homework
from django.db.models import F
from backend.settings import env
from django.conf import settings
import gspread


def updateStatisticCheck(username, task_id, prev_mark, mark):
    statistic = Member.objects.get(username=username).statistic
    prev_passed = max(statistic.passed, 0)
    if not prev_mark:
        statistic.passed = prev_passed + 1
        statistic.sum = F('sum') + mark
    else:
        statistic.sum = F('sum') - prev_mark + mark

    if task_id == int(env('PROJECT_ID')):
        statistic.project = mark
    statistic.save()
