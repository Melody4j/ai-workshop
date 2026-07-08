<script setup lang="ts">
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"

import { disableProject, listProjects, type Project } from "../../api/projects"

const router = useRouter()
const projects = ref<Project[]>([])
const loading = ref(false)
const error = ref("")

async function loadProjects() {
  loading.value = true
  error.value = ""
  try {
    projects.value = await listProjects()
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load projects."
  } finally {
    loading.value = false
  }
}

async function archiveProject(id: number) {
  await disableProject(id)
  await loadProjects()
}

onMounted(loadProjects)
</script>

<template>
  <section class="page-stack">
    <div class="page-header">
      <div>
        <p class="page-kicker">任务管理</p>
        <h2>任务管理</h2>
      </div>
      <button class="primary-button" @click="router.push('/projects/new')">新建任务</button>
    </div>

    <section class="card-grid">
      <article v-if="projects.length === 0" class="panel empty-panel">
        <p class="empty-state">当前还没有监控任务。</p>
      </article>

      <article v-for="project in projects" :key="project.id" class="panel panel--compact">
        <div class="page-header page-header--compact">
          <div>
            <p class="page-kicker">任务 #{{ project.id }}</p>
            <h3>{{ project.project_name }}</h3>
          </div>
          <span class="badge" :class="{ 'badge--muted': !project.is_active }">
            {{ project.is_active ? "已启用" : "已停用" }}
          </span>
        </div>

        <dl class="meta-grid">
          <div>
            <dt>Cron</dt>
            <dd>{{ project.cron }}</dd>
          </div>
          <div>
            <dt>竞品数量</dt>
            <dd>{{ project.competitor_urls.length }}</dd>
          </div>
        </dl>

        <div class="action-row action-row--end">
          <button class="secondary-button" @click="router.push(`/projects/${project.id}/edit`)">
            编辑
          </button>
          <button class="ghost-button" @click="router.push(`/monitoring?project=${project.id}`)">
            查看监控
          </button>
          <button
            class="ghost-button"
            :disabled="!project.is_active"
            @click="archiveProject(project.id)"
          >
            停用任务
          </button>
        </div>
      </article>
    </section>
  </section>
</template>
