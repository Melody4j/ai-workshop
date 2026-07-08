<template>
  <div class="workspace-shell">
    <aside class="workspace-sidebar">
      <div class="sidebar-brand">
        <p class="sidebar-kicker">Competitive Intel Agent</p>
        <h1>监控控制台</h1>
      </div>

      <section class="sidebar-section">
        <p class="sidebar-section__title">驾驶仓</p>
        <RouterLink to="/cockpit" class="sidebar-link">驾驶仓</RouterLink>
      </section>

      <section class="sidebar-section">
        <p class="sidebar-section__title">任务工作台</p>
        <RouterLink to="/projects" class="sidebar-link">任务管理</RouterLink>
        <RouterLink to="/monitoring" class="sidebar-link">任务监控</RouterLink>
      </section>
    </aside>

    <main class="workspace-main">
      <RouterView />
    </main>
  </div>
</template>
