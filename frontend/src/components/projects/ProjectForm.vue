<script setup lang="ts">
import { computed, reactive, watch } from "vue"

import type { ProjectPayload } from "../../api/projects"

const props = defineProps<{
  initialValue: ProjectPayload
  loading?: boolean
  submitLabel?: string
}>()

const emit = defineEmits<{
  submit: [payload: ProjectPayload]
  cancel: []
}>()

const form = reactive<ProjectPayload>({
  project_name: "",
  competitor_urls: [],
  self_product_doc: "",
  cron: "0 9 * * *",
  feishu_webhook: "",
  is_active: true,
})

watch(
  () => props.initialValue,
  (value) => {
    form.project_name = value.project_name
    form.competitor_urls = value.competitor_urls.map((item) => ({ ...item }))
    form.self_product_doc = value.self_product_doc
    form.cron = value.cron
    form.feishu_webhook = value.feishu_webhook
    form.is_active = value.is_active
  },
  { immediate: true, deep: true },
)

const canSubmit = computed(
  () =>
    form.project_name.trim().length > 0 &&
    form.competitor_urls.every((item) => item.title.trim() && item.url.trim()),
)

function addCompetitor() {
  form.competitor_urls.push({ title: "", url: "" })
}

function removeCompetitor(index: number) {
  if (form.competitor_urls.length === 1) {
    return
  }

  form.competitor_urls.splice(index, 1)
}

function onSubmit() {
  emit("submit", {
    project_name: form.project_name.trim(),
    competitor_urls: form.competitor_urls.map((item) => ({
      title: item.title.trim(),
      url: item.url.trim(),
    })),
    self_product_doc: form.self_product_doc,
    cron: form.cron.trim(),
    feishu_webhook: form.feishu_webhook.trim(),
    is_active: form.is_active,
  })
}
</script>

<template>
  <section class="panel">
    <div class="page-header">
      <div>
        <p class="page-kicker">任务配置</p>
        <h2>监控任务配置</h2>
      </div>
      <button type="button" class="secondary-button" @click="emit('cancel')">返回</button>
    </div>

    <form class="form-grid" @submit.prevent="onSubmit">
      <label class="field">
        <span>项目名称</span>
        <input v-model="form.project_name" type="text" placeholder="AI IDE Monitor" />
      </label>

      <label class="field field--wide">
        <span>自有产品锚定文档</span>
        <textarea
          v-model="form.self_product_doc"
          rows="5"
          placeholder="请输入自有产品定位、差异化能力与重点关注方向。"
        />
      </label>

      <div class="field field--wide">
        <div class="field-header">
          <span>竞品列表</span>
          <button type="button" class="secondary-button" @click="addCompetitor">新增一行</button>
        </div>

        <div class="list-stack">
          <div
            v-for="(competitor, index) in form.competitor_urls"
            :key="index"
            class="competitor-row"
          >
            <input v-model="competitor.title" type="text" placeholder="Lovable" />
            <input v-model="competitor.url" type="url" placeholder="https://lovable.dev" />
            <button type="button" class="ghost-button" @click="removeCompetitor(index)">
              删除
            </button>
          </div>
        </div>
      </div>

      <label class="field">
        <span>Cron</span>
        <input v-model="form.cron" type="text" placeholder="0 9 * * *" />
      </label>

      <label class="field">
        <span>Feishu Webhook</span>
        <input
          v-model="form.feishu_webhook"
          type="url"
          placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
        />
      </label>

      <label class="checkbox-row">
        <input v-model="form.is_active" type="checkbox" />
        <span>启用任务</span>
      </label>

      <div class="action-row">
        <button type="submit" class="primary-button" :disabled="!canSubmit || loading">
          {{ submitLabel ?? "保存任务" }}
        </button>
      </div>
    </form>
  </section>
</template>
