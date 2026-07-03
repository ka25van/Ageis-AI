const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

interface RequestOptions {
  method?: string
  body?: unknown
  params?: Record<string, string | undefined>
}

async function getTokens() {
  const access = localStorage.getItem('access_token')
  const refresh = localStorage.getItem('refresh_token')
  return { access, refresh }
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem('access_token', access)
  localStorage.setItem('refresh_token', refresh)
}

export function clearTokens() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

export function isAuthenticated(): boolean {
  return !!localStorage.getItem('access_token')
}

async function refreshAccessToken(): Promise<string | null> {
  const { refresh } = await getTokens()
  if (!refresh) return null

  try {
    const res = await fetch(`${API_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
    if (!res.ok) {
      clearTokens()
      return null
    }
    const data = await res.json()
    setTokens(data.access_token, data.refresh_token)
    return data.access_token
  } catch {
    clearTokens()
    return null
  }
}

export async function api<T = unknown>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = 'GET', body, params } = options
  const { access } = await getTokens()

  let url = `${API_URL}${path}`
  if (params) {
    const searchParams = new URLSearchParams()
    for (const [key, val] of Object.entries(params)) {
      if (val !== undefined) searchParams.set(key, val)
    }
    const qs = searchParams.toString()
    if (qs) url += `?${qs}`
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (access) headers['Authorization'] = `Bearer ${access}`

  let res = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401 && access) {
    const newToken = await refreshAccessToken()
    if (newToken) {
      headers['Authorization'] = `Bearer ${newToken}`
      res = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      })
    }
  }

  if (res.status === 204) return undefined as T

  const text = await res.text()
  if (!text) return undefined as T

  try {
    return JSON.parse(text)
  } catch {
    throw new Error(`Invalid JSON response: ${text}`)
  }
}

// Auth
export const authApi = {
  login: (email: string, password: string) =>
    api<{ user: UserInfo; access_token: string; refresh_token: string }>('/auth/login', {
      method: 'POST',
      body: { email, password },
    }),
  register: (email: string, password: string, full_name?: string) =>
    api<{ user: UserInfo; access_token: string; refresh_token: string }>('/auth/register', {
      method: 'POST',
      body: { email, password, full_name },
    }),
  me: () => api<UserInfo>('/auth/me'),
  updateProfile: (full_name: string) =>
    api<UserInfo>('/auth/me', { method: 'PATCH', body: { full_name } }),
  changePassword: (current_password: string, new_password: string) =>
    api<{ message: string }>('/auth/change-password', { method: 'POST', body: { current_password, new_password } }),
  listApiKeys: () =>
    api<ApiKey[]>('/auth/api-keys'),
  createApiKey: (name: string) =>
    api<{ id: string; name: string; key: string; key_prefix: string; created_at: string }>('/auth/api-keys', { method: 'POST', body: { name } }),
  deleteApiKey: (id: string) =>
    api<void>(`/auth/api-keys/${id}`, { method: 'DELETE' }),
}

export interface ApiKey {
  id: string
  name: string
  key_prefix: string
  is_active: boolean
  created_at: string
  last_used_at: string | null
}

// Projects
export const projectsApi = {
  list: () => api<Project[]>('/projects'),
  get: (id: string) => api<Project>(`/projects/${id}`),
  create: (name: string, description?: string) =>
    api<Project>('/projects', { method: 'POST', body: { name, description } }),
  update: (id: string, data: { name?: string; description?: string; is_active?: boolean }) =>
    api<Project>(`/projects/${id}`, { method: 'PATCH', body: data }),
  delete: (id: string) =>
    api<void>(`/projects/${id}`, { method: 'DELETE' }),
}

// Repositories
export const repositoriesApi = {
  list: (project_id?: string) =>
    api<Repository[]>('/repositories', { params: { project_id } }),
  get: (id: string) => api<Repository>(`/repositories/${id}`),
  create: (data: { project_id: string; name: string; url: string; branch?: string; provider?: string; access_token?: string; is_private?: boolean }) =>
    api<Repository>('/repositories', { method: 'POST', body: data }),
  ingest: (id: string) =>
    api<{ message: string; repository_id: string }>(`/repositories/${id}/ingest`, { method: 'POST' }),
  delete: (id: string) =>
    api<void>(`/repositories/${id}`, { method: 'DELETE' }),
}

// Documents
export const documentsApi = {
  list: (project_id?: string) =>
    api<Document_[]>('/documents', { params: { project_id } }),
  getChunks: (id: string) =>
    api<Record<string, unknown>[]>(`/documents/${id}/chunks`),
}

// Planner Agent (decomposes tasks into execution steps)
export const plannerApi = {
  planAndExecute: (task: string, project_id: string) =>
    api<{ run_id: string }>('/planner/plan', { method: 'POST', body: { task, project_id } }),
  route: (message: string, project_id: string, repository_id?: string) =>
    api<RouteResponse>('/planner/route', {
      method: 'POST',
      body: { message, project_id, repository_id: repository_id || null },
    }),
  resume: (run_id: string) =>
    api<RouteResponse>(`/planner/resume/${run_id}`, { method: 'POST' }),
}

// Repository Agent (understands code, summarizes architecture, searches code)
export const repoAgentApi = {
  understand: (repository_id: string) =>
    api<Record<string, unknown>>(`/repo-agent/${repository_id}/understand`),
  summarize: (repository_id: string) =>
    api<Record<string, unknown>>(`/repo-agent/${repository_id}/summary`),
  search: (repository_id: string, query: string) =>
    api<Record<string, unknown>>(`/repo-agent/${repository_id}/search?query=${encodeURIComponent(query)}`),
}

// Knowledge Agent (retrieves and ranks information)
export const knowledgeAgentApi = {
  search: (query: string, project_id?: string, limit?: number) =>
    api<Record<string, unknown>>('/knowledge/search', {
      method: 'POST',
      body: { query, project_id: project_id || null, limit: limit || 10 },
    }),
}

// Incident Agent (analyzes errors and provides recommendations)
export const incidentAgentApi = {
  analyze: (repository_id: string) =>
    api<Record<string, unknown>>('/incidents/analyze', {
      method: 'POST',
      body: { repository_id },
    }),
}

// Documentation Agent (generates README and API docs)
export const docAgentApi = {
  generateReadme: (repository_id: string) =>
    api<Record<string, unknown>>('/docs/readme', {
      method: 'POST',
      body: { repository_id },
    }),
}

// Code Review Agent (reviews PRs and security)
export const codeReviewApi = {
  reviewPR: (repository_id: string) =>
    api<Record<string, unknown>>('/code-review/pr', {
      method: 'POST',
      body: { repository_id },
    }),
}

// Deploy Agent (analyzes deployment configs)
export const deployApi = {
  analyze: (repository_id: string) =>
    api<Record<string, unknown>>('/deploy/analyze', {
      method: 'POST',
      body: { repository_id },
    }),
}

// Approval Queue (Human-in-the-Loop)
export const approvalsApi = {
  listPending: () =>
    api<{ approvals: Record<string, unknown>[]; count: number }>('/approvals/pending'),
  approve: (id: string) =>
    api<{ status: string; id: string }>(`/approvals/${id}/approve`, { method: 'POST' }),
  reject: (id: string, reason?: string) =>
    api<{ status: string; id: string; reason?: string }>(`/approvals/${id}/reject`, {
      method: 'POST',
      body: { reason: reason || null },
    }),
}

// Memory System
export const memoryApi = {
  searchSemantic: (query: string, limit?: number, threshold?: number) =>
    api<{ results: Record<string, unknown>[]; count: number }>('/memory/search', {
      method: 'POST',
      body: { query, limit: limit || 5, threshold: threshold || 0.5 },
    }),
  getRunMemory: (run_id: string) =>
    api<Record<string, unknown>>(`/memory/runs/${run_id}/summary`),
  getConversation: (project_id: string) =>
    api<{ messages: { role: string; content: string; timestamp: string }[] }>(`/memory/conversation/${project_id}`),
  clearConversation: (project_id: string) =>
    api<{ status: string }>(`/memory/conversation/${project_id}`, { method: 'DELETE' }),
}

// Agent Runs
export const agentRunsApi = {
  list: (project_id?: string) =>
    api<AgentRun[]>('/workflows/runs', { params: { project_id } }),
}

// Types
export interface UserInfo {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  is_superuser: boolean
}

export interface Project {
  id: string
  name: string
  description: string | null
  owner_id: string
  is_active: boolean
  settings?: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Repository {
  id: string
  project_id: string
  name: string
  url: string
  branch: string
  provider: string
  is_private: boolean
  indexing_status: string
  last_indexed_at: string | null
  indexing_error: string | null
  created_at: string
  updated_at: string
}

export interface RepositoryFile {
  id: string
  path: string
  language: string | null
  size_bytes: number
  content_hash: string
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Document_ {
  id: string
  project_id: string
  title: string
  source_type: string
  source_url?: string | null
  source_path?: string | null
  metadata?: Record<string, unknown>
  created_at: string
  updated_at?: string
}

export interface RouteResponse {
  response: string
  execution_plan: { intent: string; required_agents: string[]; needs_approval: boolean; task_description: string }
  agents_used: string[]
  agent_details: Record<string, { confidence: number; recommendations: string[]; follow_up_actions: string[] }>
  needs_approval: boolean
  approval_id?: string
  run_id?: string
  planner_fallback: Record<string, unknown> | null
}

export interface AgentRun {
  id: string
  project_id: string
  agent_type: string
  status: string
  input_data: Record<string, unknown> | null
  output_data: Record<string, unknown> | null
  error: string | null
  created_at: string
  updated_at: string
}
