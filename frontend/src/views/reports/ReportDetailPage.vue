<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { useRoute, useRouter } from "vue-router"

import RatingForm from "../../components/reports/RatingForm.vue"
import { clearRating, createRating, getReport, updateRating, type ReportDetail } from "../../api/reports"

const route = useRoute()
const router = useRouter()
const report = ref<ReportDetail | null>(null)
const loading = ref(false)
const saving = ref(false)

const markdownPreview = computed(() => {
  if (!report.value) {
    return ""
  }

  return [
    `# 报告 ${report.value.id}`,
    "",
    "## 变化摘要",
    report.value.change_summary,
    "",
    "## 战略意图",
    report.value.strategic_intent,
    "",
    "## 行动建议",
    report.value.action_suggestion,
    "",
    "## 证据 Diff",
    report.value.evidence_diff,
  ].join("\n")
})

function downloadMarkdown() {
  if (!report.value) return

  const blob = new Blob([markdownPreview.value], { type: "text/markdown;charset=utf-8" })
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = `report-${report.value.id}.md`
  anchor.click()
  window.URL.revokeObjectURL(url)
}

function downloadPdfSummary() {
  if (!report.value) return

  const textContent = [
    `Report ${report.value.id}`,
    `Summary: ${report.value.change_summary}`,
    `Intent: ${report.value.strategic_intent}`,
    `Action: ${report.value.action_suggestion}`,
    `Evidence: ${report.value.evidence_diff}`,
  ].join("\n")

  const pdfContent = `%PDF-1.1
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length ${textContent.length + 40}>>stream
BT
/F1 12 Tf
72 720 Td
(${textContent.replace(/[()]/g, "")}) Tj
ET
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000060 00000 n 
0000000117 00000 n 
0000000243 00000 n 
0000000360 00000 n 
trailer<</Size 6/Root 1 0 R>>
startxref
430
%%EOF`

  const blob = new Blob([pdfContent], { type: "application/pdf" })
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = `report-${report.value.id}.pdf`
  anchor.click()
  window.URL.revokeObjectURL(url)
}

async function loadReport() {
  loading.value = true
  try {
    report.value = await getReport(Number(route.params.id))
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : "执行详情加载失败。")
    report.value = null
  } finally {
    loading.value = false
  }
}

async function saveRating(payload: { user_feedback: -1 | 1; user_comment: string }) {
  if (!report.value) return

  saving.value = true
  try {
    report.value =
      report.value.user_feedback === null
        ? await createRating(report.value.id, payload)
        : await updateRating(report.value.id, payload)
    ElMessage.success("评分已保存。")
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : "评分保存失败。")
  } finally {
    saving.value = false
  }
}

async function removeRating() {
  if (!report.value) return

  saving.value = true
  try {
    await clearRating(report.value.id)
    await loadReport()
    ElMessage.success("评分已清空。")
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : "评分清空失败。")
  } finally {
    saving.value = false
  }
}

onMounted(loadReport)
</script>

<template>
  <section class="page-stack">
    <div class="page-header">
      <div>
        <p class="page-kicker">任务监控</p>
        <h2>执行详情</h2>
      </div>
      <el-button text @click="router.push('/monitoring')">返回任务监控</el-button>
    </div>

    <template v-if="report">
      <el-card shadow="never">
        <div class="page-header">
          <div>
            <p class="page-kicker">{{ report.project.project_name }}</p>
            <h2>报告 #{{ report.id }}</h2>
          </div>
          <el-tag effect="plain" round>
            {{ report.job_status === "CHANGED" ? "重大变更" : report.job_status }}
          </el-tag>
        </div>

        <el-row :gutter="16">
          <el-col :xs="24" :xl="12">
            <el-card shadow="never" class="preview-card">
              <template #header>
                <div class="page-header page-header--compact">
                  <div>
                    <p class="page-kicker">Markdown</p>
                    <h3>MD 分析</h3>
                  </div>
                  <el-button @click="downloadMarkdown">下载 MD</el-button>
                </div>
              </template>
              <pre class="markdown-preview">{{ markdownPreview }}</pre>
            </el-card>
          </el-col>
          <el-col :xs="24" :xl="12">
            <el-card shadow="never" class="preview-card">
              <template #header>
                <div class="page-header page-header--compact">
                  <div>
                    <p class="page-kicker">PDF</p>
                    <h3>PDF 摘要</h3>
                  </div>
                  <el-button @click="downloadPdfSummary">下载 PDF</el-button>
                </div>
              </template>
              <div class="pdf-preview">
                <p>摘要已按 PDF 下载形式提供。</p>
                <p>变化摘要：{{ report.change_summary }}</p>
                <p>行动建议：{{ report.action_suggestion }}</p>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-descriptions :column="2" border class="detail-descriptions">
          <el-descriptions-item label="HTML 报告">
            {{ report.html_report_path || "-" }}
          </el-descriptions-item>
          <el-descriptions-item label="MD 报告">
            {{ report.md_table_path || "-" }}
          </el-descriptions-item>
          <el-descriptions-item label="发布时间">
            {{ new Date(report.published_at).toLocaleString() }}
          </el-descriptions-item>
          <el-descriptions-item label="反馈状态">
            {{ report.user_feedback ?? "未评分" }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <RatingForm
        :initial-feedback="report.user_feedback"
        :initial-comment="report.user_comment"
        :loading="saving"
        @save="saveRating"
        @clear="removeRating"
      />
    </template>

    <el-card v-else shadow="never" class="empty-panel">
      <el-empty :description="loading ? ' ' : '当前没有可展示的执行详情。'" />
    </el-card>
  </section>
</template>
