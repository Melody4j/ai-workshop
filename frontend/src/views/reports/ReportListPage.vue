<script setup lang="ts">
import { onMounted, reactive, ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import { listProjects, type Project } from "../../api/projects"
import { listReports, type ReportSummary } from "../../api/reports"

const route = useRoute()
const router = useRouter()

const projects = ref<Project[]>([])
const reports = ref<ReportSummary[]>([])
const loading = ref(false)
const error = ref("")
const statusLabel = {
  CHANGED: "重大变更",
  NO_CHANGE: "无变更",
  ERROR_CRAWL: "执行失败",
} as const
const filters = reactive({
  project: String(route.query.project ?? ""),
  status: "",
  date_from: "",
  date_to: "",
})

async function loadProjects() {
  projects.value = await listProjects()
}

async function loadReports() {
  loading.value = true
  error.value = ""
  try {
    reports.value = await listReports(filters)
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load reports."
  } finally {
    loading.value = false
  }
}

async function initialize() {
  await loadProjects()
  await loadReports()
}

onMounted(initialize)
</script>

<template>
  <section class="page-stack">
    <div class="page-header">
      <div>
        <p class="page-kicker">任务监控</p>
        <h2>任务执行情况</h2>
      </div>
      <button class="secondary-button" @click="loadReports">刷新</button>
    </div>

    <section class="panel filters-grid">
      <label class="field">
        <span>项目</span>
        <select v-model="filters.project">
          <option value="">全部</option>
          <option v-for="project in projects" :key="project.id" :value="String(project.id)">
            {{ project.project_name }}
          </option>
        </select>
      </label>

      <label class="field">
        <span>状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option value="CHANGED">重大变更</option>
          <option value="NO_CHANGE">无变更</option>
          <option value="ERROR_CRAWL">执行失败</option>
        </select>
      </label>

      <label class="field">
        <span>开始日期</span>
        <input v-model="filters.date_from" type="date" />
      </label>

      <label class="field">
        <span>结束日期</span>
        <input v-model="filters.date_to" type="date" />
      </label>

      <div class="action-row">
        <button class="primary-button" @click="loadReports">应用筛选</button>
      </div>
    </section>

    <p v-if="error" class="error-text">{{ error }}</p>
    <p v-else-if="loading">正在加载任务执行记录...</p>

    <section v-else class="monitoring-list">
      <article v-for="report in reports" :key="report.id" class="monitoring-row">
        <div class="monitoring-row__action">
          <button
            v-if="report.job_status === 'CHANGED'"
            class="primary-button"
            @click="router.push(`/monitoring/${report.id}`)"
          >
            查看详情
          </button>
        </div>

        <div class="monitoring-row__content">
          <div>
            <p class="page-kicker">{{ report.project_name }}</p>
            <h3>#{{ report.id }} {{ statusLabel[report.job_status] }}</h3>
            <p>{{ report.change_summary }}</p>
          </div>

          <div class="monitoring-row__meta">
            <span class="badge">{{ statusLabel[report.job_status] }}</span>
            <span>评分：{{ report.user_feedback ?? "未评分" }}</span>
            <span>{{ new Date(report.published_at).toLocaleString() }}</span>
          </div>
        </div>
      </article>
    </section>
  </section>
</template>
