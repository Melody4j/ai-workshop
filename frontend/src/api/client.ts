export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE"

async function request<T>(url: string, method: HttpMethod, body?: unknown): Promise<T> {
  const response = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new ApiError(message || `Request failed: ${response.status}`, response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export function getJson<T>(url: string): Promise<T> {
  return request<T>(url, "GET")
}

export function postJson<T>(url: string, body: unknown): Promise<T> {
  return request<T>(url, "POST", body)
}

export function patchJson<T>(url: string, body: unknown): Promise<T> {
  return request<T>(url, "PATCH", body)
}

export function deleteJson(url: string): Promise<void> {
  return request<void>(url, "DELETE")
}
