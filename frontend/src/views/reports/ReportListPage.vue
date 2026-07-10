<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue"
import { ElMessage } from "element-plus"
import { useRoute, useRouter } from "vue-router"

import { ApiError } from "../../api/client"
import { listProjects, type Project } from "../../api/projects"
import { listReports, type ReportSummary } from "../../api/reports"

const route = useRoute()
const router = useRouter()

const projects = ref<Project[]>([])
const reports = ref<ReportSummary[]>([])
const loading = ref(false)

const statusLabel = {
  CHANGED: "重大变更",
  NO_CHANGE: "无变更",
  ERROR_CRAWL: "执行失败",
} as const

function displaySummary(row: ReportSummary): string {
  if (row.change_summary) return row.change_summary
  if (row.job_status === "NO_CHANGE") return "规则归一化后内容无变化，系统已熔断。"
  if (row.job_status === "ERROR_CRAWL") return "采集或处理异常，请查看详情中的错误信息。"
  return "—"
}

function feedbackLabel(value: number | null): string {
  if (value === 1) return "有帮助"
  if (value === -1) return "没帮助"
  return "未评分"
}

const selectedProjectId = computed(() => String(route.query.project ?? ""))
const selectedProject = computed(
  () => projects.value.find((project) => String(project.id) === selectedProjectId.value) ?? null,
)

const changedCount = computed(() => reports.value.filter((row) => row.job_status === "CHANGED").length)
const noChangeCount = computed(
  () => reports.value.filter((row) => row.job_status === "NO_CHANGE").length,
)
const errorCount = computed(
  () => reports.value.filter((row) => row.job_status === "ERROR_CRAWL").length,
)

async function loadProjects() {
  projects.value = await listProjects()
}

async function loadReports() {
  loading.value = true
  try {
    reports.value = await listReports(
      selectedProjectId.value ? { project: selectedProjectId.value } : {},
    )
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : "任务执行记录加载失败，请稍后重试。")
    reports.value = []
  } finally {
    loading.value = false
  }
}

async function initialize() {
  loading.value = true
  try {
    await loadProjects()
    reports.value = await listReports(
      selectedProjectId.value ? { project: selectedProjectId.value } : {},
    )
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : "任务执行记录加载失败，请稍后重试。")
    projects.value = []
    reports.value = []
  } finally {
    loading.value = false
  }
}

onMounted(initialize)

watch(selectedProjectId, async (next, previous) => {
  if (next === previous) return
  await loadReports()
})
</script>

<template>
  <section class="page-stack">
    <section class="hero-slab hero-slab--compact">
      <div class="hero-slab__content">
        <p class="section-label">任务监控</p>
        <h1>任务监控</h1>
      </div>
      <div class="hero-slab__actions">
        <el-button v-if="selectedProjectId" @click="router.push('/monitoring')">返回全部列表</el-button>
        <el-button type="primary" :loading="loading" @click="loadReports">刷新记录</el-button>
      </div>
    </section>

    <el-alert
      v-if="selectedProject"
      :title="`当前仅查看任务：${selectedProject.project_name}`"
      type="info"
      :closable="false"
    />

    <section class="summary-strip">
      <div class="summary-pill">
        <span>总记录</span>
        <strong>{{ reports.length }}</strong>
      </div>
      <div class="summary-pill">
        <span>重大变更</span>
        <strong>{{ changedCount }}</strong>
      </div>
      <div class="summary-pill">
        <span>无变更</span>
        <strong>{{ noChangeCount }}</strong>
      </div>
      <div class="summary-pill">
        <span>执行失败</span>
        <strong>{{ errorCount }}</strong>
      </div>
    </section>

    <section class="report-collection" v-loading="loading">
      <section v-if="reports.length === 0" class="surface-panel surface-panel--empty">
        <el-empty description="当前没有可展示的任务执行记录。" />
      </section>

      <article v-for="row in reports" :key="row.id" class="report-card">
        <div class="report-card__head">
          <div class="title-block">
            <p class="section-label">{{ row.project_name }}</p>
            <h3>报告 #{{ row.id }}</h3>
            <p>{{ displaySummary(row) }}</p>
          </div>

          <span
            class="info-pill"
            :class="{
              'info-pill--accent': row.job_status === 'CHANGED',
              'info-pill--soft': row.job_status === 'NO_CHANGE',
              'info-pill--danger': row.job_status === 'ERROR_CRAWL',
            }"
          >
            {{ statusLabel[row.job_status] }}
          </span>
        </div>

        <div class="report-card__meta">
          <div class="meta-chip">
            <span>反馈</span>
            <strong>{{ feedbackLabel(row.user_feedback) }}</strong>
          </div>
          <div class="meta-chip">
            <span>执行时间</span>
            <strong>{{ new Date(row.published_at).toLocaleString() }}</strong>
          </div>
        </div>

        <div class="report-card__footer">
          <el-button type="primary" @click="router.push(`/monitoring/${row.id}`)">
            查看详情
          </el-button>
        </div>
      </article>
    </section>
  </section>
</template>

<style scoped>
.report-collection {
  display: grid;
  gap: 16px;
}

.report-card {
  display: grid;
  gap: 18px;
  padding: 22px;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-panel);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: var(--shadow-subtle);
}

.report-card__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.report-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.report-card__footer {
  display: flex;
  justify-content: flex-start;
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

@media (max-width: 640px) {
  .report-card__head,
  .report-card__footer {
    flex-direction: column;
    align-items: stretch;
  }

  .report-card__meta {
    flex-direction: column;
  }
}
</style>
