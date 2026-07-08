declare module "*.vue" {
  import type { DefineComponent } from "vue"

  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>
  export default component
}

declare module "vue3-cron-plus-picker" {
  import type { DefineComponent, Plugin } from "vue"

  export const Vue3CronPlusPicker: DefineComponent<
    {
      expression?: string
      hideComponent?: string
    },
    Record<string, never>,
    unknown
  >

  const plugin: Plugin
  export default plugin
}
