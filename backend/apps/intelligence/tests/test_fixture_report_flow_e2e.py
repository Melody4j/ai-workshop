"""基于本地测试夹具的真实报告链路 E2E。

本测试类用于手工验证以下完整链路：
1. 将本地 HTML 夹具上传到公共 Blob URL
2. 由 Firecrawl 真实抓取夹具页面
3. 以 baseline 夹具作为上一条快照，触发 diff / judge / generate_intel / report

默认跳过。仅在显式设置 RUN_FIXTURE_REPORT_E2E=1 时执行，
避免日常测试误触发真实 Firecrawl / LLM / Blob 调用。
"""

import os
import uuid
from datetime import timedelta
from pathlib import Path
from unittest import SkipTest
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, tag
from django.utils import timezone

from apps.intelligence.models import DataSnapshot, IntelligenceFeed, MonitorProject
from apps.intelligence.services import blob_storage, crawler_service, file_storage, scheduler_service

RUN_FLAG = "RUN_FIXTURE_REPORT_E2E"
FIXTURE_ROOT = Path("/Users/melody/Downloads/测试包")
PRODUCT_DOC_PATH = Path("/Users/melody/Documents/LinkFox AI 介绍文档.md")


@tag("e2e", "network", "firecrawl", "llm", "manual")
class FixtureReportFlowE2ETest(TestCase):
    """使用真实 Firecrawl + 真实 LLM 验证测试夹具报告链路。"""

    positive_cases = [
        {
            "case_id": "Z-Pricing-1",
            "rel_path": "cases/Z-Pricing-1.html",
            "expected_diff_fragments": ["$39/月", "$29/月"],
        },
        {
            "case_id": "Z-Feature-1",
            "rel_path": "cases/Z-Feature-1.html",
            "expected_diff_fragments": ["AI 视频广告"],
        },
    ]
    negative_cases = [
        {
            "case_id": "Z-Noise-2",
            "rel_path": "cases/Z-Noise-2.html",
        },
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        if os.environ.get(RUN_FLAG) != "1":
            raise SkipTest(f"仅手工执行：请设置 {RUN_FLAG}=1 后再运行。")

        missing = []
        if not settings.FIRECRAWL_API_KEY:
            missing.append("FIRECRAWL_API_KEY")
        if not settings.LLM_API_KEY:
            missing.append("LLM_API_KEY")
        if not settings.BLOB_READ_WRITE_TOKEN:
            missing.append("BLOB_READ_WRITE_TOKEN")
        if missing:
            raise SkipTest(f"缺少真实集成测试所需环境变量：{', '.join(missing)}")

        if not FIXTURE_ROOT.exists():
            raise SkipTest(f"测试夹具目录不存在：{FIXTURE_ROOT}")
        if not PRODUCT_DOC_PATH.exists():
            raise SkipTest(f"自家产品文档不存在：{PRODUCT_DOC_PATH}")

        cls.product_doc_content = PRODUCT_DOC_PATH.read_text(encoding="utf-8").strip()
        if not cls.product_doc_content:
            raise SkipTest(f"自家产品文档为空：{PRODUCT_DOC_PATH}")

        cls.run_id = uuid.uuid4().hex
        cls.baseline_fixture_path = FIXTURE_ROOT / "index.html"
        cls.baseline_public_url = cls._upload_fixture_html(
            "baseline.html",
            cls.baseline_fixture_path.read_text(encoding="utf-8"),
        )
        cls.baseline_raw_html, cls.baseline_md = crawler_service.fetch_and_clean(cls.baseline_public_url)

        if not cls.baseline_raw_html or not cls.baseline_md:
            raise SkipTest("Firecrawl 无法抓取 baseline 夹具，跳过本组 E2E。")

    @classmethod
    def _upload_fixture_html(cls, filename: str, html_content: str) -> str:
        """将夹具 HTML 上传为可被 Firecrawl 访问的公共 Blob URL。"""
        pathname = f"tests/firecrawl-fixtures/{cls.run_id}/{filename}"
        return blob_storage.upload(pathname, html_content, content_type="text/html")

    def setUp(self):
        self.mock_push = patch(
            "apps.intelligence.services.scheduler_service.feishu_service.push_intelligence"
        ).start()
        self.mock_push.return_value = "skipped-in-e2e-test"

    def tearDown(self):
        patch.stopall()

    def _upload_case_fixture(self, rel_path: str) -> str:
        fixture_path = FIXTURE_ROOT / rel_path
        html_content = fixture_path.read_text(encoding="utf-8")
        return self.__class__._upload_fixture_html(fixture_path.name, html_content)

    def _create_project_for_case(self, case_url: str, case_id: str) -> MonitorProject:
        return MonitorProject.objects.create(
            project_name=f"Fixture E2E - {case_id}",
            competitor_urls=[{"url": case_url, "title": case_id}],
            cron="*/5 * * * *",
            is_active=True,
            self_product_doc=self.__class__.product_doc_content,
            self_product_doc_name=PRODUCT_DOC_PATH.name,
        )

    def _seed_prev_snapshot_from_baseline(
        self,
        project: MonitorProject,
        logical_url: str,
        title: str,
    ) -> DataSnapshot:
        """用 baseline 夹具预置上一条快照。

        baseline 是通过另一个公共 URL 被 Firecrawl 抓取的，因此需要将 source URL
        相关标记重写为当前 case URL，避免 diff 只因 source 行不同而失真。
        """
        fetch_time = timezone.now() - timedelta(hours=1)
        baseline_raw_html = self.__class__.baseline_raw_html.replace(
            self.__class__.baseline_public_url,
            logical_url,
        )
        baseline_md = self.__class__.baseline_md.replace(
            self.__class__.baseline_public_url,
            logical_url,
        )

        raw_html_path = file_storage.save_raw_html(project.id, logical_url, baseline_raw_html, fetch_time)
        raw_md_path = file_storage.save_clean_md(project.id, logical_url, baseline_md, fetch_time)
        clean_md_path = file_storage.save_llm_clean_md(project.id, logical_url, baseline_md, fetch_time)

        return DataSnapshot.objects.create(
            project=project,
            source_url=logical_url,
            source_title=title,
            raw_html_path=raw_html_path,
            clean_md_path=clean_md_path,
            raw_md_path=raw_md_path,
            fetch_time=fetch_time,
        )

    def _run_case_once(self, case_id: str, rel_path: str) -> tuple[MonitorProject, IntelligenceFeed]:
        case_url = self._upload_case_fixture(rel_path)
        project = self._create_project_for_case(case_url, case_id)
        self._seed_prev_snapshot_from_baseline(project, case_url, case_id)

        scheduler_service.run_scan_for_project(project.id)

        feed = IntelligenceFeed.objects.filter(project=project).first()
        self.assertIsNotNone(feed, "run_scan_for_project() 应至少产出 1 条 IntelligenceFeed")
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 2)
        return project, feed

    def _assert_changed_report_generated(self, feed: IntelligenceFeed):
        self.assertEqual(feed.job_status, IntelligenceFeed.JobStatus.CHANGED)
        self.assertTrue(feed.competitor_overview)
        self.assertTrue(feed.change_summary)
        self.assertTrue(feed.strategic_intent)
        self.assertTrue(feed.action_suggestion)
        self.assertTrue(feed.evidence_diff)
        self.assertTrue(feed.diff_text)
        self.assertTrue(feed.raw_diff_text)
        self.assertTrue(feed.html_report_path)
        self.assertTrue(feed.md_table_path)

        html_report = blob_storage.read_content(feed.html_report_path)
        md_report = blob_storage.read_content(feed.md_table_path)
        self.assertIn(feed.change_summary, html_report)
        self.assertIn(feed.change_summary, md_report)

    def test_positive_fixture_cases_generate_changed_reports(self):
        """定价/功能类夹具通过真实 Firecrawl + LLM 产出 CHANGED 报告。"""
        for case in self.positive_cases:
            with self.subTest(case_id=case["case_id"]):
                _, feed = self._run_case_once(case["case_id"], case["rel_path"])
                self._assert_changed_report_generated(feed)
                for fragment in case["expected_diff_fragments"]:
                    self.assertIn(fragment, feed.diff_text)

    def test_noise_fixture_case_is_circuit_broken(self):
        """纯排版噪音夹具不应生成 CHANGED 报告。"""
        for case in self.negative_cases:
            with self.subTest(case_id=case["case_id"]):
                _, feed = self._run_case_once(case["case_id"], case["rel_path"])
                self.assertEqual(feed.job_status, IntelligenceFeed.JobStatus.NO_CHANGE)
                self.assertIn("无变化", feed.change_summary)
                self.assertEqual(feed.html_report_path, "")
                self.assertEqual(feed.md_table_path, "")
                self.assertEqual(self.mock_push.call_count, 0)
