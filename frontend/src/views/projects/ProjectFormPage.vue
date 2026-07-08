<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
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

const emptyProject: ProjectPayload = {
  project_name: "",
  competitor_urls: [{ title: "", url: "" }],
  self_product_doc: "",
  self_product_doc_name: "",
  competitor_contexts: [
    { title: "", url: "", supplement_doc_name: "", supplement_doc_content: "" },
  ],
  cron: "0 9 * * *",
  feishu_webhook: "",
  is_active: true,
}

const formValue = ref<ProjectPayload>({ ...emptyProject })
const projectId = computed(() => Number(route.params.id))
const isEdit = computed(() => Number.isFinite(projectId.value))

async function loadProject() {
  if (!isEdit.value) {
    formValue.value = {
      ...emptyProject,
      competitor_urls: [{ title: "", url: "" }],
      competitor_contexts: [
        { title: "", url: "", supplement_doc_name: "", supplement_doc_content: "" },
      ],
    }
    return
  }

  loading.value = true
  try {
    const project = await getProject(projectId.value)
    formValue.value = {
      project_name: project.project_name,
      competitor_urls: project.competitor_urls.length
        ? project.competitor_urls
        : [{ title: "", url: "" }],
      self_product_doc: project.self_product_doc,
      self_product_doc_name: project.self_product_doc_name,
      competitor_contexts: project.competitor_contexts.length
        ? project.competitor_contexts
        : [
            {
              title: "",
              url: "",
              supplement_doc_name: "",
              supplement_doc_content: "",
            },
          ],
      cron: project.cron,
      feishu_webhook: project.feishu_webhook,
      is_active: project.is_active,
    }
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : "任务加载失败。")
  } finally {
    loading.value = false
  }
}

async function submit(payload: ProjectPayload) {
  loading.value = true
  try {
    if (isEdit.value) {
      await updateProject(projectId.value, payload)
    } else {
      await createProject(payload)
    }
    ElMessage.success(isEdit.value ? "任务已更新。" : "任务已创建。")
    await router.push("/projects")
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : "任务保存失败。")
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

    <ProjectForm
      :initial-value="formValue"
      :loading="loading"
      :submit-label="isEdit ? '保存修改' : '创建任务'"
      @submit="submit"
      @cancel="router.push('/projects')"
    />
  </section>
</template>
