<template>
  <div class="app-shell">
    <header class="app-header">
      <div>
        <p class="eyebrow">Competitive Intel Agent</p>
        <h1>Frontend Skeleton</h1>
      </div>
      <nav class="app-nav">
        <RouterLink to="/">Overview</RouterLink>
      </nav>
    </header>

    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
