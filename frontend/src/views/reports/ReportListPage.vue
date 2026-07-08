<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import { ApiError } from "../../api/client"
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
const selectedProjectId = computed(() => String(route.query.project ?? ""))
const selectedProject = computed(() =>
  projects.value.find((project) => String(project.id) === selectedProjectId.value) ?? null,
)

async function loadProjects() {
  projects.value = await listProjects()
}

async function loadReports() {
  loading.value = true
  error.value = ""
  try {
    reports.value = await listReports(
      selectedProjectId.value ? { project: selectedProjectId.value } : {},
    )
  } catch (err) {
    error.value =
      err instanceof ApiError ? err.message : "任务执行记录加载失败，请稍后重试。"
  } finally {
    loading.value = false
  }
}

async function initialize() {
  loading.value = true
  error.value = ""
  try {
    await loadProjects()
    reports.value = await listReports(
      selectedProjectId.value ? { project: selectedProjectId.value } : {},
    )
  } catch (err) {
    error.value =
      err instanceof ApiError ? err.message : "任务执行记录加载失败，请稍后重试。"
  } finally {
    loading.value = false
  }
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
      <div class="action-row">
        <button v-if="selectedProjectId" class="ghost-button" @click="router.push('/monitoring')">
          返回全部列表
        </button>
        <button class="secondary-button" @click="loadReports">刷新</button>
      </div>
    </div>

    <section v-if="selectedProject" class="panel panel--compact">
      <div class="page-header page-header--compact">
        <div>
          <p class="page-kicker">当前任务</p>
          <h3>{{ selectedProject.project_name }}</h3>
        </div>
        <span class="badge">仅查看该任务执行记录</span>
      </div>
    </section>

    <section class="monitoring-list">
      <article v-if="reports.length === 0" class="panel empty-panel">
        <p class="empty-state">当前没有可展示的任务执行记录。</p>
      </article>

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
