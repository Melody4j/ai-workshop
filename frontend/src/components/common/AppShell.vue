<script setup lang="ts">
import { computed } from "vue"
import { useRoute } from "vue-router"

const route = useRoute()

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
</script>

<template>
  <el-container class="workspace-shell">
    <el-aside class="workspace-sidebar" width="260px">
      <div class="sidebar-brand">
        <p class="sidebar-kicker">Competitive Intel Agent</p>
        <h1>监控控制台</h1>
      </div>

      <section class="sidebar-section">
        <p class="sidebar-section__title">仪表盘</p>
        <el-menu
          :default-active="activeMenu"
          router
          class="sidebar-menu"
          background-color="#000000"
          text-color="#ffffff"
          active-text-color="#ffffff"
        >
          <el-menu-item index="/cockpit">仪表盘</el-menu-item>
        </el-menu>
      </section>

      <section class="sidebar-section">
        <p class="sidebar-section__title">任务工作台</p>
        <el-menu
          :default-active="activeMenu"
          router
          class="sidebar-menu"
          background-color="#000000"
          text-color="#ffffff"
          active-text-color="#ffffff"
        >
          <el-menu-item index="/projects">任务管理</el-menu-item>
          <el-menu-item index="/monitoring">任务监控</el-menu-item>
        </el-menu>
      </section>
    </el-aside>

    <el-main class="workspace-main">
      <RouterView />
    </el-main>
  </el-container>
</template>
