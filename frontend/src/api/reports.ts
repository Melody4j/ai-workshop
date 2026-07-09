import { deleteJson, getJson, patchJson, postJson } from "./client"
import type { Project } from "./projects"

export interface ReportSummary {
  id: number
  project: number
  project_name: string
  job_status: "CHANGED" | "NO_CHANGE" | "ERROR_CRAWL"
  change_summary: string
  user_feedback: number | null
  published_at: string
  html_report_path: string
  md_table_path: string
}

export interface ReportDetail {
  id: number
  project: Project
  job_status: "CHANGED" | "NO_CHANGE" | "ERROR_CRAWL"
  competitor_overview: string
  change_summary: string
  strategic_intent: string
  action_suggestion: string
  evidence_diff: string
  user_feedback: number | null
  user_comment: string
  html_report_path: string
  md_table_path: string
  published_at: string
  created_at: string
  updated_at: string
}

export interface ReportFilters {
  project?: string
  status?: string
  date_from?: string
  date_to?: string
}

export interface RatingPayload {
  user_feedback: -1 | 1
  user_comment: string
}

export function listReports(filters: ReportFilters = {}): Promise<ReportSummary[]> {
  const params = new URLSearchParams()

  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value)
    }
  })

  const query = params.toString()
  return getJson<ReportSummary[]>(`/api/reports${query ? `?${query}` : ""}`)
}

export function getReport(id: number): Promise<ReportDetail> {
  return getJson<ReportDetail>(`/api/reports/${id}`)
}

export function createRating(id: number, payload: RatingPayload): Promise<ReportDetail> {
  return postJson<ReportDetail>(`/api/reports/${id}/rating`, payload)
}

export function updateRating(
  id: number,
  payload: Partial<RatingPayload>,
): Promise<ReportDetail> {
  return patchJson<ReportDetail>(`/api/reports/${id}/rating`, payload)
}

export function clearRating(id: number): Promise<void> {
  return deleteJson(`/api/reports/${id}/rating`)
}

export function downloadReportMd(id: number): Promise<Blob> {
  return fetch(`/api/feeds/${id}/download_md`).then((res) => {
    if (!res.ok) throw new Error("MD 下载失败")
    return res.blob()
  })
}

export function getReportHtmlPreviewUrl(id: number): string {
  return `/api/feeds/${id}/preview_html`
}
