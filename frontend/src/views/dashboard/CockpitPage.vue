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

const featuredChanges = computed(() => changedReports.value.slice(0, 4))
const activeProjectCount = computed(() => projects.value.filter((project) => project.is_active).length)
const dormantProjectCount = computed(() => projects.value.filter((project) => !project.is_active).length)

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
    <section class="hero-slab">
      <div class="hero-slab__content">
        <p class="section-label">监控总览</p>
        <h1>把任务态势、关键变更和主要操作压到同一个首屏里。</h1>
        <p>
          这个仪表盘仍然是工作台，不是营销首页。它负责先把今天值得处理的事情讲清楚，再把你送到任务配置和报告阅读入口。
        </p>
      </div>
      <div class="hero-slab__actions">
        <el-button type="primary" @click="router.push('/projects')">进入任务管理</el-button>
        <el-button @click="router.push('/monitoring')">查看任务监控</el-button>
        <el-button text :loading="loading" @click="loadCockpit">刷新数据</el-button>
      </div>
    </section>

    <section class="stats-grid">
      <article class="metric-panel">
        <p class="metric-panel__label">任务总数</p>
        <strong class="metric-panel__value">{{ projects.length }}</strong>
        <span class="metric-panel__note">当前已配置的监控任务</span>
      </article>
      <article class="metric-panel">
        <p class="metric-panel__label">24h 执行次数</p>
        <strong class="metric-panel__value">{{ last24HoursReports.length }}</strong>
        <span class="metric-panel__note">最近一天所有执行记录</span>
      </article>
      <article class="metric-panel">
        <p class="metric-panel__label">重大变更</p>
        <strong class="metric-panel__value">{{ changedReports.length }}</strong>
        <span class="metric-panel__note">需要优先查看的变化任务</span>
      </article>
      <article class="metric-panel metric-panel--soft">
        <p class="metric-panel__label">启用 / 停用</p>
        <strong class="metric-panel__value">{{ activeProjectCount }} / {{ dormantProjectCount }}</strong>
        <span class="metric-panel__note">保持调度状态一眼可见</span>
      </article>
    </section>

    <section class="surface-panel">
      <div class="surface-panel__header">
        <div>
          <p class="section-label">快速入口</p>
          <h3>继续今天的主要工作流</h3>
        </div>
        <span class="surface-panel__meta">首屏即可达</span>
      </div>

      <div class="action-tile-grid">
        <button class="action-tile" type="button" @click="router.push('/projects')">
          <span class="action-tile__label">任务管理</span>
          <strong>配置监控任务</strong>
          <p>查看任务清单、调度节奏和下一次运行时间。</p>
        </button>
        <button class="action-tile" type="button" @click="router.push('/monitoring')">
          <span class="action-tile__label">任务监控</span>
          <strong>阅读情报结果</strong>
          <p>集中查看执行状态、变化摘要和报告详情。</p>
        </button>
      </div>
    </section>

    <section class="surface-panel">
      <div class="surface-panel__header">
        <div>
          <p class="section-label">最近重大变更</p>
          <h3>优先处理这些变化任务</h3>
        </div>
        <span class="surface-panel__meta">{{ changedReports.length }} 条可读记录</span>
      </div>

      <div v-if="featuredChanges.length === 0" class="surface-panel__empty">
        <el-empty description="当前还没有可展示的重大变更记录。" />
      </div>

      <div v-else class="change-feed">
        <button
          v-for="report in featuredChanges"
          :key="report.id"
          type="button"
          class="change-feed__item"
          @click="router.push(`/monitoring/${report.id}`)"
        >
          <div class="change-feed__row">
            <span class="info-pill info-pill--accent">重大变更</span>
            <time>{{ new Date(report.published_at).toLocaleString() }}</time>
          </div>
          <strong>{{ report.project_name }}</strong>
          <p>{{ report.change_summary }}</p>
        </button>
      </div>
    </section>
  </section>
</template>
