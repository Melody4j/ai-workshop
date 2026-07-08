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
  <section class="panel">
    <div class="page-header">
      <div>
        <p class="page-kicker">反馈评分</p>
        <h3>评分与评语</h3>
      </div>
      <button type="button" class="ghost-button" :disabled="loading" @click="emit('clear')">
        清空评分
      </button>
    </div>

    <div class="rating-options">
      <button
        type="button"
        class="secondary-button"
        :class="{ active: feedback === 1 }"
        @click="feedback = 1"
      >
        有帮助
      </button>
      <button
        type="button"
        class="secondary-button"
        :class="{ active: feedback === -1 }"
        @click="feedback = -1"
      >
        没帮助
      </button>
    </div>

    <label class="field field--wide">
      <span>评语</span>
      <textarea v-model="comment" rows="4" placeholder="这条报告为什么有帮助或没帮助？" />
    </label>

    <div class="action-row">
      <button type="button" class="primary-button" :disabled="loading" @click="save">
        保存评分
      </button>
    </div>
  </section>
</template>
