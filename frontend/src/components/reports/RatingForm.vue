<script setup lang="ts">
import { ref, watch } from "vue"

const props = defineProps<{
  initialFeedback: number | null
  initialComment: string
  loading?: boolean
}>()

const emit = defineEmits<{
  save: [payload: { user_feedback: -1 | 1; user_comment: string }]
  clear: []
}>()

const feedback = ref<number | null>(null)
const comment = ref("")

watch(
  () => [props.initialFeedback, props.initialComment] as const,
  ([nextFeedback, nextComment]) => {
    feedback.value = nextFeedback
    comment.value = nextComment
  },
  { immediate: true },
)

function save() {
  if (feedback.value !== -1 && feedback.value !== 1) {
    return
  }

  emit("save", {
    user_feedback: feedback.value,
    user_comment: comment.value,
  })
}
</script>

<template>
  <el-card shadow="never">
    <div class="page-header">
      <div>
        <p class="page-kicker">反馈评分</p>
        <h3>评分与评语</h3>
      </div>
      <el-button text :disabled="loading" @click="emit('clear')">
        清空评分
      </el-button>
    </div>

    <el-radio-group v-model="feedback" class="rating-options">
      <el-radio-button :label="1">有帮助</el-radio-button>
      <el-radio-button :label="-1">没帮助</el-radio-button>
    </el-radio-group>

    <el-form label-position="top">
      <el-form-item label="评语">
        <el-input
          v-model="comment"
          type="textarea"
          :rows="4"
          placeholder="这条报告为什么有帮助或没帮助？"
        />
      </el-form-item>
    </el-form>

    <div class="action-row">
      <el-button type="primary" :disabled="loading" @click="save">保存评分</el-button>
    </div>
  </el-card>
</template>
