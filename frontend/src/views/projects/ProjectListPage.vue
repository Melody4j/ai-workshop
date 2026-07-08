<script setup lang="ts">
import { onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { useRouter } from "vue-router"

import { disableProject, listProjects, type Project } from "../../api/projects"

const router = useRouter()
const projects = ref<Project[]>([])
const loading = ref(false)

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

async function archiveProject(id: number) {
  try {
    await disableProject(id)
    ElMessage.success("任务已停用。")
    await loadProjects()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : "任务停用失败。")
  }
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
      <el-button type="primary" @click="router.push('/projects/new')">新建任务</el-button>
    </div>

    <section class="card-grid">
      <el-card v-if="projects.length === 0" shadow="never" class="empty-panel">
        <el-empty description="当前还没有监控任务。" />
      </el-card>

      <el-card
        v-for="project in projects"
        :key="project.id"
        class="panel-card panel-card--compact"
        shadow="never"
        v-loading="loading"
      >
        <div class="page-header page-header--compact">
          <div>
            <p class="page-kicker">任务 #{{ project.id }}</p>
            <h3>{{ project.project_name }}</h3>
          </div>
          <el-tag :type="project.is_active ? 'info' : 'default'" effect="plain" round>
            {{ project.is_active ? "已启用" : "已停用" }}
          </el-tag>
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
          <el-button @click="router.push(`/projects/${project.id}/edit`)">编辑</el-button>
          <el-button text @click="router.push(`/monitoring?project=${project.id}`)">
            查看监控
          </el-button>
          <el-button
            text
            :disabled="!project.is_active"
            @click="archiveProject(project.id)"
          >
            停用任务
          </el-button>
        </div>
      </el-card>
    </section>
  </section>
</template>
