<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
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
import { parseDiffLines, type DiffItem } from "../../utils/diff-parser"

const route = useRoute()
const router = useRouter()
const report = ref<ReportDetail | null>(null)
const loading = ref(false)
const saving = ref(false)

const statusLabel = {
  CHANGED: "重大变更",
  NO_CHANGE: "无变更",
  ERROR_CRAWL: "执行失败",
} as const

const statusTagType = {
  CHANGED: "success" as const,
  NO_CHANGE: "info" as const,
  ERROR_CRAWL: "danger" as const,
}

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

const diffItems = computed<DiffItem[]>(() => {
  if (!report.value?.diff_text) return []
  return parseDiffLines(report.value.diff_text)
})

const diffStats = computed(() => {
  const items = diffItems.value
  const additions = items.filter((i) => i.type === "add").length
  const deletions = items.filter((i) => i.type === "del").length
  const pairs = items.filter((i) => i.type === "pair").length
  const ctx = items.filter((i) => i.type === "ctx").length
  return { added: additions + pairs, removed: deletions + pairs, ctx }
})

const rawDiffItems = computed<DiffItem[]>(() => {
  if (!report.value?.raw_diff_text) return []
  return parseDiffLines(report.value.raw_diff_text)
})

const rawDiffStats = computed(() => {
  const items = rawDiffItems.value
  const additions = items.filter((i) => i.type === "add").length
  const deletions = items.filter((i) => i.type === "del").length
  const pairs = items.filter((i) => i.type === "pair").length
  const ctx = items.filter((i) => i.type === "ctx").length
  return { added: additions + pairs, removed: deletions + pairs, ctx }
})

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
      <!-- 基本信息 -->
      <el-card shadow="never">
        <div class="page-header">
          <div>
            <p class="page-kicker">{{ report.project.project_name }}</p>
            <h2>报告 #{{ report.id }}</h2>
          </div>
          <el-tag :type="statusTagType[report.job_status]" effect="plain" round>
            {{ statusLabel[report.job_status] }}
          </el-tag>
        </div>

        <el-descriptions :column="2" border class="detail-descriptions">
          <el-descriptions-item label="发布时间">
            {{ new Date(report.published_at).toLocaleString() }}
          </el-descriptions-item>
          <el-descriptions-item label="反馈状态">
            {{ report.user_feedback ?? "未评分" }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- CHANGED: 完整 HTML 报告预览 -->
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

      <!-- NO_CHANGE: LLM 判断原因 + diff 对比 -->
      <template v-if="report.job_status === 'NO_CHANGE'">
        <el-card shadow="never">
          <template #header>
            <div class="page-header page-header--compact">
              <div>
                <p class="page-kicker">LLM 判断</p>
                <h3>判断为无意义变化的原因</h3>
              </div>
            </div>
          </template>
          <el-alert
            type="warning"
            :closable="false"
            show-icon
            class="no-change-alert"
          >
            <template #title>系统判断本次变化无分析价值，已熔断</template>
            <div class="no-change-reason">{{ report.change_summary || "未提供原因" }}</div>
          </el-alert>
        </el-card>

        <!-- Firecrawl 降噪前 diff（原始采集内容变化） -->
        <el-card v-if="rawDiffItems.length > 0" shadow="never">
          <template #header>
            <div class="page-header page-header--compact">
              <div>
                <p class="page-kicker">Firecrawl 采集原文</p>
                <h3>降噪前内容差异（原始变化）</h3>
              </div>
              <span class="diff-stats">
                <span class="added">+{{ rawDiffStats.added }}</span>
                <span class="removed">-{{ rawDiffStats.removed }}</span>
                <span class="ctx-count">{{ rawDiffStats.ctx }} context</span>
              </span>
            </div>
          </template>
          <div class="diff-container">
            <template v-for="(item, idx) in rawDiffItems" :key="'raw-' + idx">
              <div v-if="item.type === 'hunk'" class="diff-row-hunk">{{ item.content }}</div>
              <div v-else-if="item.type === 'pair'" class="diff-pair">
                <div class="diff-pair-side old"><span class="prefix">-</span>{{ item.old }}</div>
                <div class="diff-pair-side new"><span class="prefix">+</span>{{ item.new }}</div>
              </div>
              <div v-else-if="item.type === 'add'" class="diff-row diff-row-add"><span class="prefix">+</span>{{ item.content }}</div>
              <div v-else-if="item.type === 'del'" class="diff-row diff-row-del"><span class="prefix">-</span>{{ item.content }}</div>
              <div v-else-if="item.type === 'ctx'" class="diff-row diff-row-ctx"><span class="prefix">&nbsp;</span>{{ item.content }}</div>
            </template>
          </div>
        </el-card>

        <!-- LLM 降噪后 diff（被熔断的 diff） -->
        <el-card v-if="diffItems.length > 0" shadow="never">
          <template #header>
            <div class="page-header page-header--compact">
              <div>
                <p class="page-kicker">LLM 降噪后</p>
                <h3>降噪后内容差异（被判定为无意义）</h3>
              </div>
              <span class="diff-stats">
                <span class="added">+{{ diffStats.added }}</span>
                <span class="removed">-{{ diffStats.removed }}</span>
                <span class="ctx-count">{{ diffStats.ctx }} context</span>
              </span>
            </div>
          </template>
          <div class="diff-container">
            <template v-for="(item, idx) in diffItems" :key="'llm-' + idx">
              <div v-if="item.type === 'hunk'" class="diff-row-hunk">{{ item.content }}</div>
              <div v-else-if="item.type === 'pair'" class="diff-pair">
                <div class="diff-pair-side old"><span class="prefix">-</span>{{ item.old }}</div>
                <div class="diff-pair-side new"><span class="prefix">+</span>{{ item.new }}</div>
              </div>
              <div v-else-if="item.type === 'add'" class="diff-row diff-row-add"><span class="prefix">+</span>{{ item.content }}</div>
              <div v-else-if="item.type === 'del'" class="diff-row diff-row-del"><span class="prefix">-</span>{{ item.content }}</div>
              <div v-else-if="item.type === 'ctx'" class="diff-row diff-row-ctx"><span class="prefix">&nbsp;</span>{{ item.content }}</div>
            </template>
          </div>
        </el-card>

        <!-- 无任何 diff 数据 -->
        <el-card v-if="rawDiffItems.length === 0 && diffItems.length === 0" shadow="never">
          <el-empty description="无 diff 数据（首次爬取或无历史快照）" />
        </el-card>
      </template>

      <!-- ERROR_CRAWL: 错误信息 -->
      <el-card v-if="report.job_status === 'ERROR_CRAWL'" shadow="never">
        <template #header>
          <div class="page-header page-header--compact">
            <div>
              <p class="page-kicker">执行异常</p>
              <h3>错误信息</h3>
            </div>
          </div>
        </template>
        <el-alert type="error" :closable="false" show-icon>
          <template #title>采集或处理过程中发生异常</template>
          <div class="error-message">{{ report.change_summary || "未知错误" }}</div>
        </el-alert>
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

.no-change-alert {
  margin-bottom: 0;
}

.no-change-reason {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.error-message {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  font-family: "SF Mono", "Fira Code", "Consolas", monospace;
}

/* Diff 统计 */
.diff-stats {
  font-size: 12px;
  font-weight: 400;
}
.diff-stats .added { color: #1a7f37; margin-right: 8px; }
.diff-stats .removed { color: #d1242f; margin-right: 8px; }
.diff-stats .ctx-count { color: #8c959f; }

/* Diff 容器 */
.diff-container {
  border: 1px solid #d0d7de;
  border-radius: 6px;
  overflow: hidden;
  font-family: "SF Mono", "Fira Code", "Consolas", "Monaco", monospace;
  font-size: 13px;
  line-height: 1.6;
}

/* Hunk 头 */
.diff-row-hunk {
  background: #ddf4ff;
  color: #0969da;
  padding: 4px 12px;
  border-top: 1px solid #d0d7de;
  border-bottom: 1px solid #d0d7de;
  font-size: 12px;
}

/* 配对行 */
.diff-pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-bottom: 1px solid #e1e4e8;
}
.diff-pair-side {
  padding: 2px 10px 2px 12px;
  white-space: pre-wrap;
  word-break: break-word;
}
.diff-pair-side.old {
  background: #ffebe9;
  border-right: 1px solid #d0d7de;
}
.diff-pair-side.new {
  background: #dafbe1;
}
.diff-pair-side .prefix {
  font-weight: 700;
  margin-right: 6px;
}
.diff-pair-side.old .prefix { color: #d1242f; }
.diff-pair-side.new .prefix { color: #1a7f37; }

/* 单行 diff */
.diff-row {
  padding: 2px 10px 2px 12px;
  white-space: pre-wrap;
  word-break: break-word;
  border-bottom: 1px solid #e1e4e8;
}
.diff-row .prefix {
  font-weight: 700;
  margin-right: 6px;
  display: inline-block;
  width: 12px;
}
.diff-row-add {
  background: #dafbe1;
}
.diff-row-add .prefix { color: #1a7f37; }
.diff-row-del {
  background: #ffebe9;
}
.diff-row-del .prefix { color: #d1242f; }
.diff-row-ctx {
  background: #f6f8fa;
  color: #57606a;
}
.diff-row-ctx .prefix { color: transparent; }
</style>
