<script setup lang="ts">
import { computed } from "vue"
import { useRoute } from "vue-router"

const route = useRoute()

const navigation = [
  {
    to: "/cockpit",
    label: "仪表盘",
    hint: "查看监控态势与关键入口",
    eyebrow: "Cockpit",
    title: "品牌化工作台",
    description: "把监控态势、关键变更和主要操作压到同一个高效首屏。",
  },
  {
    to: "/projects",
    label: "任务管理",
    hint: "配置监控任务与调度节奏",
    eyebrow: "Projects",
    title: "任务配置工作区",
    description: "围绕任务、竞品来源与调度参数组织出更清晰的操作路径。",
  },
  {
    to: "/monitoring",
    label: "任务监控",
    hint: "查看执行结果与情报报告",
    eyebrow: "Monitoring",
    title: "情报阅读工作区",
    description: "让状态、摘要、证据和反馈操作在一个阅读面里更稳定地协作。",
  },
] as const

const activeMenu = computed(() => {
  const path = route.path

  if (path.startsWith("/projects")) {
    return "/projects"
  }

  if (path.startsWith("/monitoring")) {
    return "/monitoring"
  }

  return "/cockpit"
})

const currentSection = computed(
  () => navigation.find((item) => item.to === activeMenu.value) ?? navigation[0],
)

const todayLabel = computed(() =>
  new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "short",
  }).format(new Date()),
)
</script>

<template>
  <div class="workspace-shell">
    <aside class="workspace-sidebar">
      <div class="shell-brand-card">
        <p class="shell-overline">Competitive Intel Agent</p>
        <h1>LinkFox Monitor</h1>
        <p class="shell-brand-card__body">
          在同一个控制台里完成任务配置、执行监控和情报阅读，保持工作台效率，也把品牌感拉起来。
        </p>
        <div class="shell-brand-card__chips">
          <span class="info-pill info-pill--accent">Frontend refresh</span>
          <span class="info-pill">{{ todayLabel }}</span>
        </div>
      </div>

      <nav class="shell-nav">
        <p class="shell-nav__label">Workspace</p>
        <RouterLink
          v-for="item in navigation"
          :key="item.to"
          :to="item.to"
          class="shell-nav__item"
          :class="{ 'is-active': activeMenu === item.to }"
        >
          <span class="shell-nav__title">{{ item.label }}</span>
          <span class="shell-nav__hint">{{ item.hint }}</span>
        </RouterLink>
      </nav>

      <section class="shell-side-note">
        <p class="shell-nav__label">Operating mode</p>
        <strong>Brand-led workspace</strong>
        <p>
          只重构 UI、布局和视觉层，不改现有业务能力、路由语义和数据契约。
        </p>
      </section>
    </aside>

    <section class="workspace-main">
      <header class="workspace-topbar">
        <div>
          <p class="workspace-topbar__eyebrow">{{ currentSection.eyebrow }}</p>
          <h2>{{ currentSection.title }}</h2>
          <p>{{ currentSection.description }}</p>
        </div>
        <div class="workspace-topbar__meta">
          <span class="topbar-chip">Vue Console</span>
          <span class="topbar-chip topbar-chip--soft">Element Plus</span>
        </div>
      </header>

      <main class="workspace-frame">
        <RouterView />
      </main>
    </section>
  </div>
</template>
