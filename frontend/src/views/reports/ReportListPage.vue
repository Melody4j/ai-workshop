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
const selectedProjectId = computed(() => String(route.query.project ?? ""))
const selectedProject = computed(() =>
  projects.value.find((project) => String(project.id) === selectedProjectId.value) ?? null,
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
  if (next === previous) {
    return
  }

  await loadReports()
})
</script>

<template>
  <section class="page-stack">
    <div class="page-header">
      <div>
        <p class="page-kicker">任务监控</p>
        <h2>任务执行情况</h2>
      </div>
      <div class="monitoring-toolbar">
        <el-button v-if="selectedProjectId" text @click="router.push('/monitoring')">
          返回全部列表
        </el-button>
        <el-button :loading="loading" @click="loadReports">刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="selectedProject"
      :title="`当前仅查看任务：${selectedProject.project_name}`"
      type="info"
      :closable="false"
    />

    <el-card shadow="never">
      <el-empty v-if="reports.length === 0" description="当前没有可展示的任务执行记录。" />

      <el-table v-else :data="reports" class="monitoring-table" table-layout="auto">
        <el-table-column label="任务" min-width="180">
          <template #default="{ row }">
            <div>
              <p class="page-kicker">{{ row.project_name }}</p>
              <strong>#{{ row.id }}</strong>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="执行情况" min-width="120">
          <template #default="{ row }">
            <el-tag effect="plain" round>{{ statusLabel[row.job_status] }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="变化摘要" min-width="320" prop="change_summary" />

        <el-table-column label="评分" min-width="120">
          <template #default="{ row }">
            {{ row.user_feedback ?? "未评分" }}
          </template>
        </el-table-column>

        <el-table-column label="执行时间" min-width="180">
          <template #default="{ row }">
            {{ new Date(row.published_at).toLocaleString() }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.job_status === 'CHANGED'"
              type="primary"
              link
              @click="router.push(`/monitoring/${row.id}`)"
            >
              查看详情
            </el-button>
            <span v-else class="table-placeholder">-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>
