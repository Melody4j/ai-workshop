export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE"
const REQUEST_TIMEOUT_MS = 30000

async function request<T>(url: string, method: HttpMethod, body?: unknown): Promise<T> {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  let response: Response

  try {
    response = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("请求超时，请确认后端服务已经启动。", 408)
    }

    throw new ApiError("无法连接后端服务，请先启动 Django API。", 503)
  } finally {
    window.clearTimeout(timeoutId)
  }

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
