<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { useRouter } from "vue-router"

import { executeProject, listProjects, toggleProjectActive, type Project } from "../../api/projects"
import { cron2label, getNextRuns, toQuartzCron } from "../../components/cron/cron-utils"

const router = useRouter()
const projects = ref<Project[]>([])
const loading = ref(false)
const executingId = ref<number | null>(null)
const togglingId = ref<number | null>(null)

const projectNextRuns = computed(() => {
  const map: Record<number, string[]> = {}
  for (const project of projects.value) {
    if (project.is_active) {
      map[project.id] = getNextRuns(project.cron, 5)
    } else {
      map[project.id] = []
    }
  }
  return map
})

const projectCronLabels = computed(() => {
  const map: Record<number, string> = {}
  for (const project of projects.value) {
    map[project.id] = cron2label(toQuartzCron(project.cron))
  }
  return map
})

const activeProjectCount = computed(() => projects.value.filter((project) => project.is_active).length)
const competitorCount = computed(() =>
  projects.value.reduce((total, project) => total + project.competitor_urls.length, 0),
)

function projectSourcePreview(project: Project) {
  return project.competitor_urls
    .slice(0, 3)
    .map((item) => item.title || item.url)
    .filter(Boolean)
    .join(" / ")
}

async function loadProjects() {
  loading.value = true
  try {
    projects.value = await listProjects()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : "任务列表加载失败。")
    projects.value = []
  } finally {
    loading.value = false
  }
}

async function toggleProjectActiveHandler(project: Project) {
  togglingId.value = project.id
  const newActive = !project.is_active
  try {
    await toggleProjectActive(project.id, newActive)
    ElMessage.success(newActive ? "任务已启用。" : "任务已停用。")
    await loadProjects()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : "操作失败。")
  } finally {
    togglingId.value = null
  }
}

async function executeProjectNow(id: number) {
  executingId.value = id
  try {
    await executeProject(id)
    ElMessage.success("任务已开始执行，请稍后在监控页面查看结果。")
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : "任务执行失败。")
  } finally {
    executingId.value = null
  }
}

onMounted(loadProjects)
</script>

<template>
  <section class="page-stack">
    <section class="hero-slab hero-slab--compact">
      <div class="hero-slab__content">
        <p class="section-label">任务管理</p>
        <h1>让任务状态、调度语义和核心操作都保持在同一层级里。</h1>
        <p>
          这一页优先服务高频查看和快速操作。信息分层更清楚，但不牺牲启停、立即执行和跳转监控的效率。
        </p>
      </div>
      <div class="hero-slab__actions">
        <el-button type="primary" @click="router.push('/projects/new')">新建任务</el-button>
        <el-button text :loading="loading" @click="loadProjects">刷新列表</el-button>
      </div>
    </section>

    <section class="summary-strip">
      <div class="summary-pill">
        <span>任务总数</span>
        <strong>{{ projects.length }}</strong>
      </div>
      <div class="summary-pill">
        <span>启用中</span>
        <strong>{{ activeProjectCount }}</strong>
      </div>
      <div class="summary-pill">
        <span>竞品来源</span>
        <strong>{{ competitorCount }}</strong>
      </div>
    </section>

    <section class="project-collection" v-loading="loading">
      <section v-if="projects.length === 0" class="surface-panel surface-panel--empty">
        <el-empty description="当前还没有监控任务。" />
      </section>

      <article v-for="project in projects" :key="project.id" class="project-card">
        <div class="project-card__head">
          <div class="title-block">
            <p class="section-label">任务 #{{ project.id }}</p>
            <h3>{{ project.project_name }}</h3>
            <p>{{ projectSourcePreview(project) || "暂未补充竞品来源说明。" }}</p>
          </div>

          <div class="project-card__state">
            <span class="info-pill" :class="{ 'info-pill--accent': project.is_active }">
              {{ project.is_active ? "启用中" : "已停用" }}
            </span>
            <el-switch
              :model-value="project.is_active"
              :loading="togglingId === project.id"
              active-text="启用"
              inactive-text="停用"
              inline-prompt
              @change="toggleProjectActiveHandler(project)"
            />
          </div>
        </div>

        <div class="project-card__meta">
          <div class="meta-chip">
            <span>Cron</span>
            <strong>{{ project.cron }}</strong>
          </div>
          <div class="meta-chip">
            <span>调度语义</span>
            <strong>{{ projectCronLabels[project.id] }}</strong>
          </div>
          <div class="meta-chip">
            <span>竞品数量</span>
            <strong>{{ project.competitor_urls.length }}</strong>
          </div>
        </div>

        <div
          v-if="project.is_active && projectNextRuns[project.id]?.length"
          class="project-card__schedule"
        >
          <div class="section-heading section-heading--inline">
            <div>
              <p class="section-label">接下来 5 次运行</p>
              <h4>调度窗口</h4>
            </div>
          </div>
          <ul class="run-list">
            <li v-for="(run, index) in projectNextRuns[project.id]" :key="index">{{ run }}</li>
          </ul>
        </div>

        <div v-else class="project-card__schedule project-card__schedule--muted">
          <p>当前任务未启用，因此不会自动调度执行。</p>
        </div>

        <div class="project-card__footer">
          <el-button
            type="primary"
            :loading="executingId === project.id"
            @click="executeProjectNow(project.id)"
          >
            立即执行
          </el-button>
          <el-button @click="router.push(`/projects/${project.id}/edit`)">编辑</el-button>
          <el-button text @click="router.push(`/monitoring?project=${project.id}`)">
            查看监控
          </el-button>
        </div>
      </article>
    </section>
  </section>
</template>
