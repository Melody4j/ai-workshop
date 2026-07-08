from datetime import datetime
from django.test import SimpleTestCase

from apps.intelligence.services.cron_matcher import get_next_run


class CronMatcherTest(SimpleTestCase):
    def test_every_5_minutes(self):
        result = get_next_run("*/5 * * * *", datetime(2026, 7, 8, 14, 3))
        self.assertEqual(result, datetime(2026, 7, 8, 14, 5))

    def test_daily_9am_same_day_before(self):
        result = get_next_run("0 9 * * *", datetime(2026, 7, 8, 8, 30))
        self.assertEqual(result, datetime(2026, 7, 8, 9, 0))

    def test_daily_9am_same_day_after(self):
        result = get_next_run("0 9 * * *", datetime(2026, 7, 8, 9, 2))
        self.assertEqual(result, datetime(2026, 7, 9, 9, 0))

    def test_every_30min(self):
        result = get_next_run("*/30 * * * *", datetime(2026, 7, 8, 14, 17))
        self.assertEqual(result, datetime(2026, 7, 8, 14, 30))

    def test_weekly_monday_9am(self):
        # 2026-07-07 是周二，下周一 7/13
        result = get_next_run("0 9 * * 1", datetime(2026, 7, 7, 9, 3))
        self.assertEqual(result, datetime(2026, 7, 13, 9, 0))

    def test_non_5_multiple_minute(self):
        # 非 5 倍数分钟也能计算
        result = get_next_run("3 9 * * *", datetime(2026, 7, 8, 9, 0))
        self.assertEqual(result, datetime(2026, 7, 8, 9, 3))
