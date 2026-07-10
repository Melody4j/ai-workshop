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

const rawDiffItems = computed<DiffItem[]>(() => {
  if (!report.value?.raw_diff_text) return []
  return parseDiffLines(report.value.raw_diff_text)
})

const diffStats = computed(() => {
  const items = diffItems.value
  const additions = items.filter((i) => i.type === "add").length
  const deletions = items.filter((i) => i.type === "del").length
  const pairs = items.filter((i) => i.type === "pair").length
  return { added: additions + pairs, removed: deletions + pairs }
})

const rawDiffStats = computed(() => {
  const items = rawDiffItems.value
  const additions = items.filter((i) => i.type === "add").length
  const deletions = items.filter((i) => i.type === "del").length
  const pairs = items.filter((i) => i.type === "pair").length
  return { added: additions + pairs, removed: deletions + pairs }
})

const feedbackLabel = computed(() => {
  if (report.value?.user_feedback === 1) return "有帮助"
  if (report.value?.user_feedback === -1) return "没帮助"
  return "未评分"
})

onMounted(loadReport)
</script>

<template>
  <section class="page-stack">
    <section class="hero-slab hero-slab--compact">
      <div class="hero-slab__content">
        <p class="section-label">执行详情</p>
        <h1 v-if="report">{{ report.project.project_name }} / 报告 #{{ report.id }}</h1>
        <h1 v-else>执行详情</h1>
        <p>
          这一页优先服务分析阅读。先看状态和概览，再看正文、证据 diff 和反馈操作，不让重要信息散在多个层里。
        </p>
      </div>
      <div class="hero-slab__actions">
        <el-button @click="router.push('/monitoring')">返回任务监控</el-button>
        <el-button v-if="report" type="primary" @click="downloadMarkdown">下载 MD</el-button>
      </div>
    </section>

    <section v-if="report" class="detail-layout">
      <div class="detail-main">
        <section class="detail-overview">
          <div class="detail-overview__header">
            <div>
              <p class="section-label">报告概览</p>
              <h3>{{ statusLabel[report.job_status] }}</h3>
            </div>
            <span
              class="info-pill"
              :class="{
                'info-pill--accent': report.job_status === 'CHANGED',
                'info-pill--soft': report.job_status === 'NO_CHANGE',
                'info-pill--danger': report.job_status === 'ERROR_CRAWL',
              }"
            >
              {{ statusLabel[report.job_status] }}
            </span>
          </div>

          <div class="detail-overview__meta">
            <div class="meta-chip">
              <span>发布时间</span>
              <strong>{{ new Date(report.published_at).toLocaleString() }}</strong>
            </div>
            <div class="meta-chip">
              <span>反馈状态</span>
              <strong>{{ feedbackLabel }}</strong>
            </div>
          </div>
        </section>

        <template v-if="report.job_status === 'CHANGED'">
          <section class="detail-reading-grid">
            <article class="surface-panel">
              <div class="surface-panel__header">
                <div>
                  <p class="section-label">竞品概述</p>
                  <h3>先看整体背景</h3>
                </div>
              </div>
              <p class="detail-copy">{{ report.competitor_overview || "未提供竞品概述。" }}</p>
            </article>

            <article class="surface-panel">
              <div class="surface-panel__header">
                <div>
                  <p class="section-label">变化摘要</p>
                  <h3>本次变化发生了什么</h3>
                </div>
              </div>
              <p class="detail-copy">{{ report.change_summary || "未提供变化摘要。" }}</p>
            </article>

            <article class="surface-panel">
              <div class="surface-panel__header">
                <div>
                  <p class="section-label">战略意图</p>
                  <h3>系统对变化方向的判断</h3>
                </div>
              </div>
              <p class="detail-copy">{{ report.strategic_intent || "未提供战略意图。" }}</p>
            </article>

            <article class="surface-panel">
              <div class="surface-panel__header">
                <div>
                  <p class="section-label">行动建议</p>
                  <h3>下一步可以怎么跟进</h3>
                </div>
              </div>
              <p class="detail-copy">{{ report.action_suggestion || "未提供行动建议。" }}</p>
            </article>
          </section>

          <section class="surface-panel" v-if="report.evidence_diff">
            <div class="surface-panel__header">
              <div>
                <p class="section-label">关键证据</p>
                <h3>LLM 标注的证据摘要</h3>
              </div>
            </div>
            <p class="detail-copy detail-copy--mono">{{ report.evidence_diff }}</p>
          </section>

          <section class="surface-panel preview-panel">
            <div class="surface-panel__header">
              <div>
                <p class="section-label">HTML Report</p>
                <h3>完整报告预览</h3>
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
              </div>
            </div>
            <iframe
              :src="getReportHtmlPreviewUrl(report.id)"
              class="html-preview-frame"
              frameborder="0"
              scrolling="auto"
            />
          </section>
        </template>

        <template v-else-if="report.job_status === 'NO_CHANGE'">
          <section class="surface-panel">
            <div class="surface-panel__header">
              <div>
                <p class="section-label">熔断原因</p>
                <h3>为什么这次没有继续生成情报</h3>
              </div>
            </div>
            <el-alert type="warning" :closable="false" show-icon>
              <template #title>系统判断本次变化无分析价值，已熔断</template>
              <div class="detail-copy">{{ report.change_summary || "未提供原因。" }}</div>
            </el-alert>
          </section>

          <section v-if="rawDiffItems.length > 0" class="surface-panel">
            <div class="surface-panel__header">
              <div>
                <p class="section-label">原始证据</p>
                <h3>Firecrawl 原始 Markdown diff</h3>
              </div>
              <span class="diff-badge">+{{ rawDiffStats.added }} / -{{ rawDiffStats.removed }}</span>
            </div>
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
          </section>

          <section v-if="diffItems.length > 0" class="surface-panel">
            <div class="surface-panel__header">
              <div>
                <p class="section-label">规则归一化 diff</p>
                <h3>用于判断是否继续分析的稳定 diff</h3>
              </div>
              <span class="diff-badge">+{{ diffStats.added }} / -{{ diffStats.removed }}</span>
            </div>
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
          </section>

          <section
            v-if="rawDiffItems.length === 0 && diffItems.length === 0"
            class="surface-panel surface-panel--empty"
          >
            <el-empty description="无 diff 数据（首次爬取或无历史快照）" />
          </section>
        </template>

        <section v-else class="surface-panel">
          <div class="surface-panel__header">
            <div>
              <p class="section-label">执行异常</p>
              <h3>采集或处理过程中发生异常</h3>
            </div>
          </div>
          <el-alert type="error" :closable="false" show-icon>
            <template #title>错误信息</template>
            <div class="detail-copy detail-copy--mono">{{ report.change_summary || "未知错误" }}</div>
          </el-alert>
        </section>
      </div>

      <aside class="detail-side">
        <section class="surface-panel">
          <div class="surface-panel__header">
            <div>
              <p class="section-label">阅读指引</p>
              <h3>先看什么</h3>
            </div>
          </div>
          <ul class="detail-guide">
            <li>先确认状态和发布时间，判断是否需要立即跟进。</li>
            <li v-if="report.job_status === 'CHANGED'">再读变化摘要、战略意图和行动建议。</li>
            <li v-else-if="report.job_status === 'NO_CHANGE'">重点看熔断原因，以及原始 diff 是否有真实变化。</li>
            <li v-else>先处理错误信息，再决定是否需要重跑任务。</li>
          </ul>
        </section>

        <RatingForm
          :initial-feedback="report.user_feedback"
          :initial-comment="report.user_comment"
          :loading="saving"
          @save="saveRating"
          @clear="removeRating"
        />
      </aside>
    </section>

    <section v-else class="surface-panel surface-panel--empty">
      <el-empty :description="loading ? ' ' : '当前没有可展示的执行详情。'" />
    </section>
  </section>
</template>

<style scoped>
.detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(300px, 0.9fr);
  gap: 18px;
}

.detail-main,
.detail-side,
.detail-reading-grid,
.detail-overview,
.detail-guide {
  display: grid;
  gap: 18px;
}

.detail-reading-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.detail-overview {
  padding: 22px;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-panel);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: var(--shadow-subtle);
}

.detail-overview__header,
.detail-overview__meta {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
  flex-wrap: wrap;
}

.detail-copy {
  margin: 0;
  color: var(--text-body);
  line-height: 1.75;
  white-space: pre-wrap;
}

.detail-copy--mono {
  font-family: "SF Mono", "Fira Code", "Consolas", monospace;
}

.preview-panel {
  gap: 18px;
}

.html-preview-frame {
  width: 100%;
  min-height: 720px;
  border: 0;
  border-radius: var(--radius-panel);
  background: #ffffff;
}

.detail-guide {
  margin: 0;
  padding-left: 18px;
  color: var(--text-body);
}

.detail-guide li {
  line-height: 1.7;
}

.diff-badge {
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--surface-muted);
  border: 1px solid var(--border-soft);
  color: var(--text-body);
  font-size: 0.88rem;
}

.diff-container {
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-panel);
  overflow: hidden;
  font-family: "SF Mono", "Fira Code", "Consolas", "Monaco", monospace;
  font-size: 13px;
  line-height: 1.65;
  background: #ffffff;
}

.diff-row-hunk {
  background: #e9f4ff;
  color: #2160b8;
  padding: 6px 12px;
  border-bottom: 1px solid var(--border-soft);
  font-size: 12px;
}

.diff-pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-bottom: 1px solid #e8edf3;
}

.diff-pair-side {
  padding: 4px 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.diff-pair-side.old {
  background: #fff0ef;
  border-right: 1px solid var(--border-soft);
}

.diff-pair-side.new {
  background: #eefbf7;
}

.diff-pair-side .prefix {
  font-weight: 700;
  margin-right: 6px;
}

.diff-pair-side.old .prefix {
  color: #d64b45;
}

.diff-pair-side.new .prefix {
  color: #179b72;
}

.diff-row {
  padding: 4px 12px;
  white-space: pre-wrap;
  word-break: break-word;
  border-bottom: 1px solid #e8edf3;
}

.diff-row .prefix {
  display: inline-block;
  width: 12px;
  margin-right: 6px;
  font-weight: 700;
}

.diff-row-add {
  background: #eefbf7;
}

.diff-row-add .prefix {
  color: #179b72;
}

.diff-row-del {
  background: #fff0ef;
}

.diff-row-del .prefix {
  color: #d64b45;
}

.diff-row-ctx {
  background: #f8fafc;
  color: #66768c;
}

.diff-row-ctx .prefix {
  color: transparent;
}

.info-pill--soft {
  background: rgba(53, 194, 190, 0.12);
  border-color: rgba(53, 194, 190, 0.22);
  color: #147b78;
}

.info-pill--danger {
  background: rgba(214, 75, 69, 0.12);
  border-color: rgba(214, 75, 69, 0.2);
  color: #bb3c37;
}

@media (max-width: 1120px) {
  .detail-layout {
    grid-template-columns: 1fr;
  }

  .detail-reading-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .detail-overview__header,
  .detail-overview__meta {
    flex-direction: column;
    align-items: stretch;
  }

  .diff-pair {
    grid-template-columns: 1fr;
  }

  .diff-pair-side.old {
    border-right: 0;
    border-bottom: 1px solid var(--border-soft);
  }
}
</style>
