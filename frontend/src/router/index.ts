import { createRouter, createWebHistory } from "vue-router"

import CockpitPage from "../views/dashboard/CockpitPage.vue"
import ProjectFormPage from "../views/projects/ProjectFormPage.vue"
import ProjectListPage from "../views/projects/ProjectListPage.vue"
import ReportDetailPage from "../views/reports/ReportDetailPage.vue"
import ReportListPage from "../views/reports/ReportListPage.vue"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/cockpit",
    },
    {
      path: "/cockpit",
      name: "cockpit",
      component: CockpitPage,
    },
    {
      path: "/projects",
      name: "project-list",
      component: ProjectListPage,
    },
    {
      path: "/projects/new",
      name: "project-create",
      component: ProjectFormPage,
    },
    {
      path: "/projects/:id/edit",
      name: "project-edit",
      component: ProjectFormPage,
      props: true,
    },
    {
      path: "/monitoring",
      name: "monitoring-list",
      component: ReportListPage,
    },
    {
      path: "/monitoring/:id",
      name: "monitoring-detail",
      component: ReportDetailPage,
      props: true,
    },
    {
      path: "/reports",
      redirect: "/monitoring",
    },
    {
      path: "/reports/:id",
      redirect: (to) => `/monitoring/${to.params.id}`,
    },
  ],
})

export default router
