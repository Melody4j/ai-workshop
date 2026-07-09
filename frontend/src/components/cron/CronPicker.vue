<script setup lang="ts">
import { reactive, ref, computed, watch } from "vue"
import {
  cron2form,
  cron2label,
  cronObj2cron,
  defaultCronForm,
  form2cronObj,
  getNextRuns,
  toBackendCron,
  type CronForm,
} from "./cron-utils"

const props = defineProps<{
  expression: string
}>()

const emit = defineEmits<{
  fill: [expression: string]
  hide: []
}>()

const form = reactive<CronForm>(defaultCronForm())
const activeTab = ref("second")

watch(
  () => props.expression,
  (val) => {
    const formData = cron2form(val)
    if (formData) {
      Object.assign(form, formData)
    }
  },
  { immediate: true },
)

const cronText = computed(() => cronObj2cron(form2cronObj(form)))
const cronLang = computed(() => cron2label(cronText.value))
const nextRuns = computed(() => getNextRuns(toBackendCron(cronText.value), 5))

// 日/周互斥：选日 → 周自动设"不指定"，选周 → 日自动设"不指定"
watch(
  () => form.day.type,
  (newVal) => {
    if (newVal !== -1 && form.week.type !== -1) {
      form.week.type = -1
    }
  },
)

watch(
  () => form.week.type,
  (newVal) => {
    if (newVal !== -1 && form.day.type !== -1) {
      form.day.type = -1
    }
  },
)

const weekOptions = [
  { value: 1, label: "周日" },
  { value: 2, label: "周一" },
  { value: 3, label: "周二" },
  { value: 4, label: "周三" },
  { value: 5, label: "周四" },
  { value: 6, label: "周五" },
  { value: 7, label: "周六" },
]

function confirm() {
  emit("fill", cronText.value)
}

function cancel() {
  emit("hide")
}
</script>

<template>
  <div class="cron-picker">
    <el-tabs v-model="activeTab" type="card" class="cron-tabs">
      <!-- 秒 -->
      <el-tab-pane label="秒" name="second">
        <el-radio-group v-model="form.second.type">
          <div class="cron-line"><el-radio :value="0">每秒</el-radio></div>
          <div class="cron-line">
            <el-radio :value="1">从第</el-radio>
            <el-input-number v-model="form.second.from" :min="0" :max="58" size="small" controls-position="right" />
            <span>秒到第</span>
            <el-input-number v-model="form.second.to" :min="0" :max="59" size="small" controls-position="right" />
            <span>秒</span>
          </div>
          <div class="cron-line">
            <el-radio :value="2">从第</el-radio>
            <el-input-number v-model="form.second.start" :min="0" :max="58" size="small" controls-position="right" />
            <span>秒开始，每隔</span>
            <el-input-number v-model="form.second.step" :min="1" :max="59" size="small" controls-position="right" />
            <span>秒执行一次</span>
          </div>
          <div class="cron-line">
            <el-radio :value="3">指定</el-radio>
            <el-select
              v-model="form.second.list"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="选择秒"
              size="small"
              class="cron-select"
            >
              <el-option v-for="n in 60" :key="n - 1" :value="n - 1" :label="String(n - 1)" />
            </el-select>
            <span>分别执行一次</span>
          </div>
        </el-radio-group>
      </el-tab-pane>

      <!-- 分钟 -->
      <el-tab-pane label="分钟" name="minute">
        <el-radio-group v-model="form.minute.type">
          <div class="cron-line"><el-radio :value="0">每分钟</el-radio></div>
          <div class="cron-line">
            <el-radio :value="1">从第</el-radio>
            <el-input-number v-model="form.minute.from" :min="0" :max="58" size="small" controls-position="right" />
            <span>分钟到第</span>
            <el-input-number v-model="form.minute.to" :min="0" :max="59" size="small" controls-position="right" />
            <span>分钟</span>
          </div>
          <div class="cron-line">
            <el-radio :value="2">从第</el-radio>
            <el-input-number v-model="form.minute.start" :min="0" :max="58" size="small" controls-position="right" />
            <span>分钟开始，每隔</span>
            <el-input-number v-model="form.minute.step" :min="1" :max="59" size="small" controls-position="right" />
            <span>分钟执行一次</span>
          </div>
          <div class="cron-line">
            <el-radio :value="3">指定</el-radio>
            <el-select
              v-model="form.minute.list"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="选择分钟"
              size="small"
              class="cron-select"
            >
              <el-option v-for="n in 60" :key="n - 1" :value="n - 1" :label="String(n - 1)" />
            </el-select>
            <span>分别执行一次</span>
          </div>
        </el-radio-group>
      </el-tab-pane>

      <!-- 小时 -->
      <el-tab-pane label="小时" name="hour">
        <el-radio-group v-model="form.hour.type">
          <div class="cron-line"><el-radio :value="0">每小时</el-radio></div>
          <div class="cron-line">
            <el-radio :value="1">从第</el-radio>
            <el-input-number v-model="form.hour.from" :min="0" :max="22" size="small" controls-position="right" />
            <span>小时到第</span>
            <el-input-number v-model="form.hour.to" :min="0" :max="23" size="small" controls-position="right" />
            <span>小时</span>
          </div>
          <div class="cron-line">
            <el-radio :value="2">从第</el-radio>
            <el-input-number v-model="form.hour.start" :min="0" :max="22" size="small" controls-position="right" />
            <span>小时开始，每隔</span>
            <el-input-number v-model="form.hour.step" :min="1" :max="23" size="small" controls-position="right" />
            <span>小时执行一次</span>
          </div>
          <div class="cron-line">
            <el-radio :value="3">指定</el-radio>
            <el-select
              v-model="form.hour.list"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="选择小时"
              size="small"
              class="cron-select"
            >
              <el-option v-for="n in 24" :key="n - 1" :value="n - 1" :label="String(n - 1)" />
            </el-select>
            <span>分别执行一次</span>
          </div>
        </el-radio-group>
      </el-tab-pane>

      <!-- 日 -->
      <el-tab-pane label="日" name="day">
        <el-radio-group v-model="form.day.type">
          <div class="cron-line"><el-radio :value="-1">不指定</el-radio></div>
          <div class="cron-line"><el-radio :value="0">每天</el-radio></div>
          <div class="cron-line">
            <el-radio :value="1">从第</el-radio>
            <el-input-number v-model="form.day.from" :min="1" :max="30" size="small" controls-position="right" />
            <span>天到第</span>
            <el-input-number v-model="form.day.to" :min="1" :max="31" size="small" controls-position="right" />
            <span>天</span>
          </div>
          <div class="cron-line">
            <el-radio :value="2">从第</el-radio>
            <el-input-number v-model="form.day.start" :min="1" :max="30" size="small" controls-position="right" />
            <span>天开始，每隔</span>
            <el-input-number v-model="form.day.step" :min="1" :max="31" size="small" controls-position="right" />
            <span>天执行一次</span>
          </div>
          <div class="cron-line">
            <el-radio :value="3">指定</el-radio>
            <el-select
              v-model="form.day.list"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="选择日期"
              size="small"
              class="cron-select"
            >
              <el-option v-for="n in 31" :key="n" :value="n" :label="`${n}日`" />
            </el-select>
            <span>分别执行一次</span>
          </div>
        </el-radio-group>
      </el-tab-pane>

      <!-- 月 -->
      <el-tab-pane label="月" name="month">
        <el-radio-group v-model="form.month.type">
          <div class="cron-line"><el-radio :value="0">每月</el-radio></div>
          <div class="cron-line">
            <el-radio :value="1">从第</el-radio>
            <el-input-number v-model="form.month.from" :min="1" :max="11" size="small" controls-position="right" />
            <span>个月到第</span>
            <el-input-number v-model="form.month.to" :min="1" :max="12" size="small" controls-position="right" />
            <span>个月</span>
          </div>
          <div class="cron-line">
            <el-radio :value="2">从第</el-radio>
            <el-input-number v-model="form.month.start" :min="1" :max="11" size="small" controls-position="right" />
            <span>个月开始，每隔</span>
            <el-input-number v-model="form.month.step" :min="1" :max="12" size="small" controls-position="right" />
            <span>个月执行一次</span>
          </div>
          <div class="cron-line">
            <el-radio :value="3">指定</el-radio>
            <el-select
              v-model="form.month.list"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="选择月份"
              size="small"
              class="cron-select"
            >
              <el-option v-for="n in 12" :key="n" :value="n" :label="`${n}月`" />
            </el-select>
            <span>分别执行一次</span>
          </div>
        </el-radio-group>
      </el-tab-pane>

      <!-- 周 -->
      <el-tab-pane label="周" name="week">
        <el-radio-group v-model="form.week.type">
          <div class="cron-line"><el-radio :value="-1">不指定</el-radio></div>
          <div class="cron-line"><el-radio :value="0">每周</el-radio></div>
          <div class="cron-line">
            <el-radio :value="1">从</el-radio>
            <el-select v-model="form.week.from" size="small" class="cron-week-select">
              <el-option v-for="opt in weekOptions" :key="opt.value" :value="opt.value" :label="opt.label" />
            </el-select>
            <span>到</span>
            <el-select v-model="form.week.to" size="small" class="cron-week-select">
              <el-option v-for="opt in weekOptions" :key="opt.value" :value="opt.value" :label="opt.label" />
            </el-select>
          </div>
          <div class="cron-line">
            <el-radio :value="2">指定</el-radio>
            <el-select
              v-model="form.week.list"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="选择星期"
              size="small"
              class="cron-select"
            >
              <el-option v-for="opt in weekOptions" :key="opt.value" :value="opt.value" :label="opt.label" />
            </el-select>
            <span>分别执行一次</span>
          </div>
        </el-radio-group>
      </el-tab-pane>
    </el-tabs>

    <!-- 表达式 + 自然语言 -->
    <div class="cron-preview">
      <div class="cron-preview__row">
        <span class="cron-preview__label">Cron 表达式</span>
        <el-input :model-value="cronText" readonly size="small" />
      </div>
      <div class="cron-preview__row">
        <span class="cron-preview__label">自然语言表达</span>
        <el-input :model-value="cronLang" type="textarea" :autosize="{ minRows: 1, maxRows: 3 }" readonly size="small" />
      </div>
    </div>

    <!-- 接下来 5 次运行时间 -->
    <div class="cron-next-runs" v-if="nextRuns.length">
      <p class="cron-next-runs__title">接下来 5 次运行时间</p>
      <ul class="cron-next-runs__list">
        <li v-for="(run, index) in nextRuns" :key="index">{{ index + 1 }}. {{ run }}</li>
      </ul>
    </div>

    <!-- 操作按钮 -->
    <div class="cron-actions">
      <el-button @click="cancel">取消</el-button>
      <el-button type="primary" @click="confirm">应用</el-button>
    </div>
  </div>
</template>
