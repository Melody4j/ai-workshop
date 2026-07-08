<script setup lang="ts">
import type { UploadFile } from "element-plus"
import { computed, reactive, ref, watch } from "vue"

import CronPicker from "../cron/CronPicker.vue"
import { cron2label, toBackendCron, toQuartzCron } from "../cron/cron-utils"

import type {
  CompetitorContextInput,
  CompetitorInput,
  ProjectPayload,
} from "../../api/projects"
interface CompetitorFormRow {
  title: string
  url: string
  crawl_hint: string
  supplement_doc_name: string
  supplement_doc_content: string
}

const props = defineProps<{
  initialValue: ProjectPayload
  loading?: boolean
  submitLabel?: string
}>()

const emit = defineEmits<{
  submit: [payload: ProjectPayload]
  cancel: []
}>()

const form = reactive({
  project_name: "",
  self_product_doc: "",
  self_product_doc_name: "",
  cron: "* * * * *",
  feishu_webhook: "",
  is_active: true,
})
const cronDialogVisible = ref(false)
const cronPickerExpression = ref("0 * * * * ?")
const uploadError = ref("")
const competitors = ref<CompetitorFormRow[]>([])

function createEmptyCompetitor(): CompetitorFormRow {
  return {
    title: "",
    url: "",
    crawl_hint: "",
    supplement_doc_name: "",
    supplement_doc_content: "",
  }
}

function mergeCompetitors(
  competitorUrls: CompetitorInput[],
  competitorContexts: CompetitorContextInput[],
): CompetitorFormRow[] {
  const normalizedUrls = competitorUrls.length ? competitorUrls : [createEmptyCompetitor()]

  return normalizedUrls.map((item, index) => {
    const matchedContext = competitorContexts[index]

    return {
      title: item.title ?? matchedContext?.title ?? "",
      url: item.url ?? matchedContext?.url ?? "",
      crawl_hint: item.crawl_hint ?? "",
      supplement_doc_name: matchedContext?.supplement_doc_name ?? "",
      supplement_doc_content: matchedContext?.supplement_doc_content ?? "",
    }
  })
}

watch(
  () => props.initialValue,
  (value) => {
    form.project_name = value.project_name
    form.self_product_doc = value.self_product_doc
    form.self_product_doc_name = value.self_product_doc_name
    form.cron = value.cron
    form.feishu_webhook = value.feishu_webhook
    form.is_active = value.is_active
    competitors.value = mergeCompetitors(value.competitor_urls, value.competitor_contexts)
  },
  { immediate: true, deep: true },
)

const canSubmit = computed(
  () =>
    form.project_name.trim().length > 0 &&
    form.cron.trim().length > 0 &&
    competitors.value.every((item) => item.title.trim() && item.url.trim()),
)

const cronSemantic = computed(() => cron2label(toQuartzCron(form.cron)))

function addCompetitor() {
  competitors.value.push(createEmptyCompetitor())
}

function removeCompetitor(index: number) {
  if (competitors.value.length === 1) {
    return
  }

  competitors.value.splice(index, 1)
}

async function readTextFile(file: File): Promise<string> {
  return file.text()
}

async function onSelfProductFileChange(file: UploadFile) {
  const rawFile = file.raw

  if (!rawFile) {
    return
  }

  uploadError.value = ""

  try {
    form.self_product_doc = await readTextFile(rawFile)
    form.self_product_doc_name = rawFile.name
  } catch {
    uploadError.value = "自有产品文档读取失败。"
  }
}

async function onCompetitorFileChange(index: number, file: UploadFile) {
  const rawFile = file.raw

  if (!rawFile) {
    return
  }

  uploadError.value = ""

  try {
    competitors.value[index].supplement_doc_content = await readTextFile(rawFile)
    competitors.value[index].supplement_doc_name = rawFile.name
  } catch {
    uploadError.value = "竞品补充文档读取失败。"
  }
}

function clearSelfProductFile() {
  form.self_product_doc_name = ""
  form.self_product_doc = ""
}

function clearCompetitorFile(index: number) {
  competitors.value[index].supplement_doc_name = ""
  competitors.value[index].supplement_doc_content = ""
}

function openCronDialog() {
  cronPickerExpression.value = toQuartzCron(form.cron)
  cronDialogVisible.value = true
}

function closeCronDialog() {
  cronDialogVisible.value = false
}

function fillCronExpression(expression: string) {
  form.cron = toBackendCron(expression)
  cronDialogVisible.value = false
}

function normalizeManualCronValue() {
  form.cron = toBackendCron(form.cron)
}

function onSubmit() {
  const competitorUrls: CompetitorInput[] = competitors.value.map((item) => ({
    title: item.title.trim(),
    url: item.url.trim(),
    crawl_hint: item.crawl_hint.trim(),
  }))
  const competitorContexts: CompetitorContextInput[] = competitors.value.map((item) => ({
    title: item.title.trim(),
    url: item.url.trim(),
    supplement_doc_name: item.supplement_doc_name.trim(),
    supplement_doc_content: item.supplement_doc_content.trim(),
  }))

  emit("submit", {
    project_name: form.project_name.trim(),
    competitor_urls: competitorUrls,
    self_product_doc: form.self_product_doc,
    self_product_doc_name: form.self_product_doc_name.trim(),
    competitor_contexts: competitorContexts,
    cron: toBackendCron(form.cron),
    feishu_webhook: form.feishu_webhook.trim(),
    is_active: form.is_active,
  })
}
</script>

<template>
  <el-card shadow="never">
    <div class="page-header">
      <div>
        <p class="page-kicker">任务配置</p>
        <h2>监控任务配置</h2>
      </div>
      <el-button @click="emit('cancel')">返回</el-button>
    </div>

    <el-form label-position="top" class="form-grid" @submit.prevent="onSubmit">
      <el-form-item label="项目名称">
        <el-input v-model="form.project_name" placeholder="AI IDE Monitor" />
      </el-form-item>

      <el-form-item label="自有产品锚定文档" class="field--wide">
        <div class="field-block">
          <div class="field-header">
            <span>支持上传文本文件自动填充</span>
            <el-upload
              :auto-upload="false"
              :show-file-list="false"
              accept=".txt,.md,.markdown,.json"
              :on-change="onSelfProductFileChange"
            >
              <el-button>上传文件</el-button>
            </el-upload>
          </div>

          <div class="upload-card">
            <div>
              <p class="upload-card__title">已上传文件</p>
              <strong>{{ form.self_product_doc_name || "未上传文件" }}</strong>
            </div>
            <el-button v-if="form.self_product_doc_name" text @click="clearSelfProductFile">
              清除文件
            </el-button>
          </div>

          <el-input
            v-model="form.self_product_doc"
            type="textarea"
            :rows="6"
            placeholder="请输入自有产品定位、差异化能力与重点关注方向。"
          />
        </div>
      </el-form-item>

      <el-form-item label="竞品列表" class="field--wide">
        <div class="field-block">
          <div class="field-header">
            <span>为每个竞品补充来源名称、URL 与补充说明</span>
            <el-button @click="addCompetitor">新增一行</el-button>
          </div>

          <div class="list-stack">
            <el-card
              v-for="(competitor, index) in competitors"
              :key="index"
              class="panel-card competitor-card"
              shadow="never"
            >
              <template #header>
                <div class="competitor-card__header">
                  <strong>竞品 {{ index + 1 }}</strong>
                  <el-button text @click="removeCompetitor(index)">删除</el-button>
                </div>
              </template>

              <div class="competitor-row competitor-row--stacked">
                <el-input v-model="competitor.title" placeholder="Lovable" />
                <el-input v-model="competitor.url" placeholder="https://lovable.dev" />
              </div>

              <div class="competitor-hint">
                <el-input
                  v-model="competitor.crawl_hint"
                  placeholder='采集提示词（可选）：如"爬取定价页、功能列表页"'
                  :rows="2"
                  type="textarea"
                />
              </div>

              <div class="field-block">
                <div class="field-header">
                  <span>竞品补充文档</span>
                  <el-upload
                    :auto-upload="false"
                    :show-file-list="false"
                    accept=".txt,.md,.markdown,.json"
                    :on-change="(file) => onCompetitorFileChange(index, file)"
                  >
                    <el-button>上传文件</el-button>
                  </el-upload>
                </div>

                <div class="upload-card">
                  <div>
                    <p class="upload-card__title">已上传文件</p>
                    <strong>{{ competitor.supplement_doc_name || "未上传文件" }}</strong>
                  </div>
                  <el-button
                    v-if="competitor.supplement_doc_name"
                    text
                    @click="clearCompetitorFile(index)"
                  >
                    清除文件
                  </el-button>
                </div>

                <el-input
                  v-model="competitor.supplement_doc_content"
                  type="textarea"
                  :rows="4"
                  placeholder="请输入竞品补充说明，或通过上传文件自动填充。"
                />
              </div>
            </el-card>
          </div>
        </div>
      </el-form-item>

      <el-form-item label="Cron 表达式" class="field--wide">
        <div class="cron-card">
          <el-input
            v-model="form.cron"
            placeholder="请输入标准 5 段 cron 表达式"
            @blur="normalizeManualCronValue"
          >
            <template #append>
              <el-button @click="openCronDialog">配置表达式</el-button>
            </template>
          </el-input>
          <div class="cron-semantic">
            <span class="cron-semantic__label">语义</span>
            <strong class="cron-semantic__text">{{ cronSemantic }}</strong>
          </div>
          <div class="cron-value">
            <span>当前保存值（5 段 crontab）</span>
            <strong>{{ form.cron }}</strong>
          </div>
        </div>
      </el-form-item>

      <el-form-item label="Feishu Webhook">
        <el-input
          v-model="form.feishu_webhook"
          placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
        />
      </el-form-item>

      <el-form-item label="任务状态">
        <el-switch
          v-model="form.is_active"
          inline-prompt
          active-text="启用"
          inactive-text="停用"
        />
      </el-form-item>

      <el-alert
        v-if="uploadError"
        :title="uploadError"
        type="error"
        :closable="false"
        class="field--wide"
      />

      <div class="action-row">
        <el-button type="primary" :disabled="!canSubmit || loading" @click="onSubmit">
          {{ submitLabel ?? "保存任务" }}
        </el-button>
      </div>
    </el-form>

    <el-dialog v-model="cronDialogVisible" title="配置 Cron 表达式" width="960px">
      <CronPicker
        :expression="cronPickerExpression"
        @fill="fillCronExpression"
        @hide="closeCronDialog"
      />
    </el-dialog>
  </el-card>
</template>
