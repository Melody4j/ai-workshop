<script setup lang="ts">
import { computed } from "vue"
import { useRoute } from "vue-router"

const route = useRoute()

const navigation = [
  {
    to: "/cockpit",
    label: "仪表盘",
    eyebrow: "Cockpit",
    title: "竞品分析工作台",
    description: "",
  },
  {
    to: "/projects",
    label: "任务管理",
    eyebrow: "Projects",
    title: "任务配置工作区",
    description: "",
  },
  {
    to: "/monitoring",
    label: "任务监控",
    eyebrow: "Monitoring",
    title: "情报阅读工作区",
    description: "",
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
        <h1>Monitor</h1>
        <div class="shell-brand-card__chips">
          <span class="info-pill">{{ todayLabel }}</span>
        </div>
      </div>

      <nav class="shell-nav">
        <RouterLink
          v-for="item in navigation"
          :key="item.to"
          :to="item.to"
          class="shell-nav__item"
          :class="{ 'is-active': activeMenu === item.to }"
        >
          <span class="shell-nav__title">{{ item.label }}</span>
        </RouterLink>
      </nav>
    </aside>

    <section class="workspace-main">
      <header class="workspace-topbar">
        <div>
          <p class="workspace-topbar__eyebrow">{{ currentSection.eyebrow }}</p>
          <h2>{{ currentSection.title }}</h2>
        </div>
      </header>

      <main class="workspace-frame">
        <RouterView />
      </main>
    </section>
  </div>
</template>
