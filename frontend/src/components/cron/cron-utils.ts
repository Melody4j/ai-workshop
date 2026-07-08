import cronstrue from "cronstrue"
import "cronstrue/locales/zh_CN"

export type Unit = "second" | "minute" | "hour" | "day" | "month" | "week"

export interface FieldForm {
  type: number
  from: number
  to: number
  start: number
  step: number
  list: (string | number)[]
}

export interface CronForm {
  second: FieldForm
  minute: FieldForm
  hour: FieldForm
  day: FieldForm
  month: FieldForm
  week: FieldForm
}

export function defaultCronForm(): CronForm {
  return {
    second: { type: 0, from: 0, to: 1, start: 0, step: 1, list: [] },
    minute: { type: 0, from: 0, to: 1, start: 0, step: 1, list: [] },
    hour: { type: 0, from: 0, to: 1, start: 0, step: 1, list: [] },
    day: { type: -1, from: 1, to: 2, start: 1, step: 1, list: [] },
    month: { type: 0, from: 1, to: 2, start: 1, step: 1, list: [] },
    week: { type: -1, from: 1, to: 2, start: 1, step: 1, list: [] },
  }
}

/**
 * 表单状态 → cron 对象
 */
export function form2cronObj(form: CronForm): Record<Unit, string> {
  const obj: Record<Unit, string> = {
    second: "*",
    minute: "*",
    hour: "*",
    day: "*",
    month: "*",
    week: "?",
  }

  const { second, minute, hour, day, month, week } = form

  switch (second.type) {
    case 0: obj.second = "*"; break
    case 1: obj.second = `${second.from}-${second.to}`; break
    case 2: obj.second = `${second.start}/${second.step}`; break
    case 3: obj.second = second.list.length ? second.list.join(",") : "*"; break
  }

  switch (minute.type) {
    case 0: obj.minute = "*"; break
    case 1: obj.minute = `${minute.from}-${minute.to}`; break
    case 2: obj.minute = `${minute.start}/${minute.step}`; break
    case 3: obj.minute = minute.list.length ? minute.list.join(",") : "*"; break
  }

  switch (hour.type) {
    case 0: obj.hour = "*"; break
    case 1: obj.hour = `${hour.from}-${hour.to}`; break
    case 2: obj.hour = `${hour.start}/${hour.step}`; break
    case 3: obj.hour = hour.list.length ? hour.list.join(",") : "*"; break
  }

  switch (day.type) {
    case -1: obj.day = "?"; break
    case 0: obj.day = "*"; break
    case 1: obj.day = `${day.from}-${day.to}`; break
    case 2: obj.day = `${day.start}/${day.step}`; break
    case 3: obj.day = day.list.length ? day.list.join(",") : "*"; break
  }

  switch (month.type) {
    case 0: obj.month = "*"; break
    case 1: obj.month = `${month.from}-${month.to}`; break
    case 2: obj.month = `${month.start}/${month.step}`; break
    case 3: obj.month = month.list.length ? month.list.join(",") : "*"; break
  }

  switch (week.type) {
    case -1: obj.week = "?"; break
    case 0: obj.week = "*"; break
    case 1: obj.week = `${week.from}-${week.to}`; break
    case 2: obj.week = week.list.length ? week.list.join(",") : "*"; break
  }

  return obj
}

/**
 * cron 对象 → cron 字符串（6 段 Quartz）
 */
export function cronObj2cron(obj: Record<Unit, string>): string {
  return [obj.second, obj.minute, obj.hour, obj.day, obj.month, obj.week].join(" ")
}

/**
 * cron 字符串 → 表单状态（反解）
 */
export function cron2form(cron: string): CronForm | null {
  const parts = (cron || "").trim().split(/\s+/)
  if (parts.length < 6) return null

  const form = defaultCronForm()
  const keys: Unit[] = ["second", "minute", "hour", "day", "month", "week"]
  const config: Record<string, string> = {}
  keys.forEach((k, i) => { config[k] = parts[i] })

  function parseField(value: string, field: FieldForm, hasUnspecified: boolean) {
    if (hasUnspecified && value === "?") {
      field.type = -1
      return
    }
    if (value === "*" || value === "?") {
      field.type = 0
      return
    }
    const rangeMatch = value.match(/^(\d+)-(\d+)$/)
    if (rangeMatch) {
      field.type = 1
      field.from = parseInt(rangeMatch[1])
      field.to = parseInt(rangeMatch[2])
      return
    }
    const stepMatch = value.match(/^(\d+)\/(\d+)$/)
    if (stepMatch) {
      field.type = 2
      field.start = parseInt(stepMatch[1])
      field.step = parseInt(stepMatch[2])
      return
    }
    const stepAllMatch = value.match(/^\*\/(\d+)$/)
    if (stepAllMatch) {
      field.type = 2
      field.start = 0
      field.step = parseInt(stepAllMatch[1])
      return
    }
    if (value.includes(",")) {
      field.type = 3
      field.list = value.split(",")
      return
    }
    const num = parseInt(value)
    if (!isNaN(num)) {
      field.type = 3
      field.list = [num]
      return
    }
  }

  parseField(config.second, form.second, false)
  parseField(config.minute, form.minute, false)
  parseField(config.hour, form.hour, false)
  parseField(config.day, form.day, true)
  parseField(config.month, form.month, false)
  parseField(config.week, form.week, true)

  return form
}

/**
 * cron 字符串 → 中文自然语言
 */
export function cron2label(cron: string): string {
  if (!cron) return "暂无调度"
  const parts = cron.trim().split(/\s+/)
  if (parts.length < 6) return "无效的 cron 表达式"

  try {
    return cronstrue.toString(cron, {
      locale: "zh_CN",
      verbose: true,
      dayOfWeekStartIndexZero: false,
    })
  } catch {
    return "无法解析的 cron 表达式"
  }
}

// === 后端兼容：6 段 Quartz ↔ 5 段 crontab ===

/**
 * 6 段 Quartz → 5 段 crontab（后端 croniter 用）
 * 剥离秒字段，? → *，周 Quartz 1-7 → crontab 0-6
 */
export function toBackendCron(quartzCron: string): string {
  const parts = quartzCron.trim().split(/\s+/)
  if (parts.length < 6) return quartzCron.trim()

  const [, minute, hour, day, month, week] = parts
  const normalizedDay = day === "?" ? "*" : day
  const normalizedWeek = convertWeekQuartzToCrontab(week === "?" ? "*" : week)

  return `${minute} ${hour} ${normalizedDay} ${month} ${normalizedWeek}`
}

/**
 * 5 段 crontab → 6 段 Quartz（picker 用）
 * 补 0 秒，day/week 其一设 ?，周 crontab 0-6 → Quartz 1-7
 */
export function toQuartzCron(crontabCron: string): string {
  const parts = crontabCron.trim().split(/\s+/)
  if (parts.length === 6 || parts.length === 7) return crontabCron.trim()
  if (parts.length !== 5) return "0 * * * * ?"

  const [minute, hour, day, month, week] = parts
  const quartzWeek = convertWeekCrontabToQuartz(week)

  let quartzDay = day
  let normalizedWeek = quartzWeek

  if (quartzDay !== "*" && quartzDay !== "?") {
    normalizedWeek = "?"
  } else if (normalizedWeek !== "*" && normalizedWeek !== "?") {
    quartzDay = "?"
  } else {
    normalizedWeek = "?"
  }

  return `0 ${minute} ${hour} ${quartzDay} ${month} ${normalizedWeek}`
}

function convertWeekQuartzToCrontab(week: string): string {
  if (week === "*" || week === "?") return "*"
  if (week.includes(",")) {
    return week.split(",").map(convertSingleWeekQuartzToCrontab).join(",")
  }
  if (week.includes("-") && !week.includes("/")) {
    const [a, b] = week.split("-")
    return `${convertSingleWeekQuartzToCrontab(a)}-${convertSingleWeekQuartzToCrontab(b)}`
  }
  if (week.includes("/")) {
    const [base, step] = week.split("/")
    if (base === "*") return week
    return `${convertSingleWeekQuartzToCrontab(base)}/${step}`
  }
  return convertSingleWeekQuartzToCrontab(week)
}

function convertSingleWeekQuartzToCrontab(val: string): string {
  const n = parseInt(val)
  if (isNaN(n)) return val
  return String(n - 1)
}

function convertWeekCrontabToQuartz(week: string): string {
  if (week === "*" || week === "?") return "*"
  if (week.includes(",")) {
    return week.split(",").map(convertSingleWeekCrontabToQuartz).join(",")
  }
  if (week.includes("-") && !week.includes("/")) {
    const [a, b] = week.split("-")
    return `${convertSingleWeekCrontabToQuartz(a)}-${convertSingleWeekCrontabToQuartz(b)}`
  }
  if (week.includes("/")) {
    const [base, step] = week.split("/")
    if (base === "*") return week
    return `${convertSingleWeekCrontabToQuartz(base)}/${step}`
  }
  return convertSingleWeekCrontabToQuartz(week)
}

function convertSingleWeekCrontabToQuartz(val: string): string {
  const n = parseInt(val)
  if (isNaN(n)) return val
  return String(n + 1)
}
