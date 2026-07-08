<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { useRouter } from "vue-router"

import { ApiError } from "../../api/client"
import { listProjects, type Project } from "../../api/projects"
import { listReports, type ReportSummary } from "../../api/reports"

const router = useRouter()
const projects = ref<Project[]>([])
const reports = ref<ReportSummary[]>([])
const loading = ref(false)

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
  try {
    const [projectPayload, reportPayload] = await Promise.all([listProjects(), listReports()])
    projects.value = projectPayload
    reports.value = reportPayload
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : "仪表盘数据加载失败，请稍后重试。")
    projects.value = []
    reports.value = []
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
        <p class="page-kicker">仪表盘</p>
        <h2>监控仪表盘</h2>
      </div>
      <el-button :loading="loading" @click="loadCockpit">刷新数据</el-button>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :md="8">
        <el-card class="metric-card" shadow="never">
          <p class="stat-label">任务总数</p>
          <el-statistic :value="projects.length" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card class="metric-card" shadow="never">
          <p class="stat-label">过去 24 小时执行总次数</p>
          <el-statistic :value="last24HoursReports.length" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card class="metric-card" shadow="never">
          <p class="stat-label">过去 24 小时重大变更</p>
          <el-statistic
            :value="last24HoursReports.filter((report) => report.job_status === 'CHANGED').length"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <div class="page-header">
        <div>
          <p class="page-kicker">重大变更</p>
          <h3>最近有重大变更的任务执行</h3>
        </div>
      </div>

      <div v-if="changedReports.length === 0" class="empty-panel">
        <el-empty description="当前还没有可展示的重大变更记录。" />
      </div>

      <div v-else class="card-grid">
        <el-card
          v-for="report in changedReports"
          :key="report.id"
          class="panel-card is-clickable"
          shadow="hover"
          @click="router.push(`/monitoring/${report.id}`)"
        >
          <div class="change-card__top">
            <el-tag effect="plain" round type="info">重大变更</el-tag>
            <span>{{ new Date(report.published_at).toLocaleString() }}</span>
          </div>
          <strong>{{ report.project_name }}</strong>
          <p>{{ report.change_summary }}</p>
        </el-card>
      </div>
    </el-card>
  </section>
</template>
