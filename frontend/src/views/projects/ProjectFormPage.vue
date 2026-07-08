<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import ProjectForm from "../../components/projects/ProjectForm.vue"
import {
  createProject,
  getProject,
  updateProject,
  type ProjectPayload,
} from "../../api/projects"

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const error = ref("")

const emptyProject: ProjectPayload = {
  project_name: "",
  competitor_urls: [{ title: "", url: "" }],
  self_product_doc: "",
  cron: "0 9 * * *",
  feishu_webhook: "",
  is_active: true,
}

const formValue = ref<ProjectPayload>({ ...emptyProject })
const projectId = computed(() => Number(route.params.id))
const isEdit = computed(() => Number.isFinite(projectId.value))

async function loadProject() {
  if (!isEdit.value) {
    formValue.value = { ...emptyProject, competitor_urls: [{ title: "", url: "" }] }
    return
  }

  loading.value = true
  error.value = ""
  try {
    const project = await getProject(projectId.value)
    formValue.value = {
      project_name: project.project_name,
      competitor_urls: project.competitor_urls.length
        ? project.competitor_urls
        : [{ title: "", url: "" }],
      self_product_doc: project.self_product_doc,
      cron: project.cron,
      feishu_webhook: project.feishu_webhook,
      is_active: project.is_active,
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load project."
  } finally {
    loading.value = false
  }
}

async function submit(payload: ProjectPayload) {
  loading.value = true
  error.value = ""
  try {
    if (isEdit.value) {
      await updateProject(projectId.value, payload)
    } else {
      await createProject(payload)
    }
    await router.push("/projects")
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to save project."
  } finally {
    loading.value = false
  }
}

onMounted(loadProject)
</script>

<template>
  <section class="page-stack">
    <div class="page-header">
      <div>
        <p class="page-kicker">任务管理</p>
        <h2>{{ isEdit ? "编辑任务" : "新增任务" }}</h2>
      </div>
    </div>

    <p v-if="error" class="error-text">{{ error }}</p>
    <ProjectForm
      :initial-value="formValue"
      :loading="loading"
      :submit-label="isEdit ? '保存修改' : '创建任务'"
      @submit="submit"
      @cancel="router.push('/projects')"
    />
  </section>
</template>
