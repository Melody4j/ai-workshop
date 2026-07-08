import { deleteJson, getJson, patchJson, postJson } from "./client"

export interface CompetitorInput {
  title: string
  url: string
  crawl_hint?: string
}

export interface CompetitorContextInput {
  title: string
  url: string
  supplement_doc_name: string
  supplement_doc_content: string
}

export interface ProjectPayload {
  project_name: string
  competitor_urls: CompetitorInput[]
  self_product_doc: string
  self_product_doc_name: string
  competitor_contexts: CompetitorContextInput[]
  cron: string
  feishu_webhook: string
  is_active: boolean
}

export interface Project extends ProjectPayload {
  id: number
  refined_rules: string
  created_at: string
  updated_at: string
}

export function listProjects(): Promise<Project[]> {
  return getJson<Project[]>("/api/projects")
}

export function getProject(id: number): Promise<Project> {
  return getJson<Project>(`/api/projects/${id}`)
}

export function createProject(payload: ProjectPayload): Promise<Project> {
  return postJson<Project>("/api/projects", payload)
}

export function updateProject(id: number, payload: Partial<ProjectPayload>): Promise<Project> {
  return patchJson<Project>(`/api/projects/${id}`, payload)
}

export function disableProject(id: number): Promise<void> {
  return deleteJson(`/api/projects/${id}`)
}
