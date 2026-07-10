<script setup lang="ts">
import { computed, ref, watch } from "vue"

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

const isComplete = computed(
  () => props.initialFeedback !== null && props.initialComment.trim() !== "",
)

const hasFeedback = computed(() => feedback.value === 1 || feedback.value === -1)

watch(
  () => [props.initialFeedback, props.initialComment] as const,
  ([nextFeedback, nextComment]) => {
    feedback.value = nextFeedback
    comment.value = nextComment
  },
  { immediate: true },
)

function save() {
  if (!hasFeedback.value) return

  emit("save", {
    user_feedback: feedback.value as -1 | 1,
    user_comment: comment.value,
  })
}
</script>

<template>
  <section class="rating-surface">
    <div class="surface-panel__header">
      <div>
        <p class="section-label">反馈评分</p>
        <h3>告诉系统这条报告值不值得学</h3>
      </div>
      <el-button text :disabled="loading" @click="emit('clear')">清空评分</el-button>
    </div>

    <div class="rating-surface__body">
      <el-radio-group v-model="feedback" class="rating-grid" :disabled="isComplete">
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
            :disabled="isComplete"
          />
        </el-form-item>
      </el-form>
    </div>

    <div class="rating-surface__footer">
      <span v-if="isComplete" class="rating-surface__tip">已保存反馈，如需修改请先清空评分。</span>
      <el-button type="primary" :disabled="loading || isComplete || !hasFeedback" @click="save">
        保存评分
      </el-button>
    </div>
  </section>
</template>

<style scoped>
.rating-surface {
  display: grid;
  align-content: start;
  gap: 18px;
  padding: 22px;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-panel);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: var(--shadow-subtle);
}

.rating-surface__body {
  display: grid;
  gap: 18px;
}

.rating-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.rating-surface__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.rating-surface__tip {
  color: var(--text-muted);
  font-size: 0.92rem;
}

@media (max-width: 640px) {
  .rating-surface__footer {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
