<script setup lang="ts">
import { onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { useRoute, useRouter } from "vue-router"

import RatingForm from "../../components/reports/RatingForm.vue"
import {
  clearRating,
  createRating,
  downloadReportMd,
  getReport,
  getReportHtmlPreviewUrl,
  updateRating,
  type ReportDetail,
} from "../../api/reports"

const route = useRoute()
const router = useRouter()
const report = ref<ReportDetail | null>(null)
const loading = ref(false)
const saving = ref(false)

async function downloadMarkdown() {
  if (!report.value) return

  try {
    const blob = await downloadReportMd(report.value.id)
    const url = window.URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `report-${report.value.id}.md`
    anchor.click()
    window.URL.revokeObjectURL(url)
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : "MD 下载失败。")
  }
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

        <el-card v-if="report.job_status === 'CHANGED'" shadow="never" class="preview-card">
          <template #header>
            <div class="page-header page-header--compact">
              <div>
                <p class="page-kicker">HTML Report</p>
                <h3>报告预览</h3>
              </div>
              <div class="action-row">
                <el-button
                  tag="a"
                  :href="`/view/html/${report.id}`"
                  target="_blank"
                  rel="noopener"
                >
                  在新窗口打开
                </el-button>
                <el-button @click="downloadMarkdown">下载 MD</el-button>
              </div>
            </div>
          </template>
          <iframe
            :src="getReportHtmlPreviewUrl(report.id)"
            class="html-preview-frame"
            frameborder="0"
            scrolling="auto"
          />
        </el-card>

        <el-descriptions :column="2" border class="detail-descriptions">
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

<style scoped>
.html-preview-frame {
  width: 100%;
  height: 600px;
  border: none;
  border-radius: 4px;
}
</style>
