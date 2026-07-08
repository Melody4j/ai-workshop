<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"

import { ApiError } from "../../api/client"
import { listProjects, type Project } from "../../api/projects"
import { listReports, type ReportSummary } from "../../api/reports"

const router = useRouter()
const projects = ref<Project[]>([])
const reports = ref<ReportSummary[]>([])
const loading = ref(false)
const error = ref("")

const last24HoursReports = computed(() => {
  const now = Date.now()
  const windowMs = 24 * 60 * 60 * 1000

  return reports.value.filter((report) => now - new Date(report.published_at).getTime() <= windowMs)
})

const changedReports = computed(() =>
  reports.value
    .filter((report) => report.job_status === "CHANGED")
    .sort(
      (left, right) =>
        new Date(right.published_at).getTime() - new Date(left.published_at).getTime(),
    ),
)

async function loadCockpit() {
  loading.value = true
  error.value = ""
  try {
    const [projectPayload, reportPayload] = await Promise.all([listProjects(), listReports()])
    projects.value = projectPayload
    reports.value = reportPayload
  } catch (err) {
    error.value =
      err instanceof ApiError ? err.message : "驾驶仓数据加载失败，请稍后重试。"
  } finally {
    loading.value = false
  }
}

onMounted(loadCockpit)
</script>

<template>
  <section class="page-stack">
    <div class="page-header">
      <div>
        <p class="page-kicker">驾驶舱</p>
        <h2>监控驾驶仓</h2>
      </div>
      <button class="secondary-button" @click="loadCockpit">刷新数据</button>
    </div>

    <section class="stats-grid">
      <article class="stat-card">
        <p class="stat-label">任务总数</p>
        <strong class="stat-value">{{ projects.length }}</strong>
      </article>

      <article class="stat-card">
        <p class="stat-label">过去 24 小时执行总次数</p>
        <strong class="stat-value">{{ last24HoursReports.length }}</strong>
      </article>

      <article class="stat-card">
        <p class="stat-label">过去 24 小时重大变更</p>
        <strong class="stat-value">
          {{ last24HoursReports.filter((report) => report.job_status === "CHANGED").length }}
        </strong>
      </article>
    </section>

    <section class="panel">
      <div class="page-header">
        <div>
          <p class="page-kicker">重大变更</p>
          <h3>最近有重大变更的任务执行</h3>
        </div>
      </div>

      <div v-if="changedReports.length === 0" class="empty-panel">
        <p class="empty-state">当前还没有可展示的重大变更记录。</p>
      </div>

      <div v-else class="card-grid">
        <button
          v-for="report in changedReports"
          :key="report.id"
          class="change-card"
          @click="router.push(`/monitoring/${report.id}`)"
        >
          <div class="change-card__top">
            <span class="change-card__status">重大变更</span>
            <span>{{ new Date(report.published_at).toLocaleString() }}</span>
          </div>
          <strong>{{ report.project_name }}</strong>
          <p>{{ report.change_summary }}</p>
        </button>
      </div>
    </section>
  </section>
</template>
