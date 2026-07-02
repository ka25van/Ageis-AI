import { useEffect, useState } from 'react'
import { Bot, CheckCircle, Clock, AlertCircle, Play, Loader2, Terminal, ChevronDown, ChevronUp, RotateCw } from 'lucide-react'
import {
  agentRunsApi, projectsApi, repositoriesApi,
  plannerApi, repoAgentApi, knowledgeAgentApi,
  incidentAgentApi, docAgentApi, codeReviewApi, deployApi,
} from '../lib/api'
import type { AgentRun, Project, Repository } from '../lib/api'

interface AgentDef {
  type: string
  name: string
  desc: string
  needsRepo: boolean
  needsProject: boolean
}

const agents: AgentDef[] = [
  { type: 'planner', name: 'Planner Agent', desc: 'Decomposes tasks into execution steps', needsRepo: false, needsProject: true },
  { type: 'repository', name: 'Repository Agent', desc: 'Understands code and architecture', needsRepo: true, needsProject: false },
  { type: 'knowledge', name: 'Knowledge Agent', desc: 'Retrieves relevant information via semantic search', needsRepo: false, needsProject: true },
  { type: 'incident', name: 'Incident Agent', desc: 'Analyzes logs, finds root causes, gives recommendations', needsRepo: true, needsProject: false },
  { type: 'documentation', name: 'Documentation Agent', desc: 'Generates README and API architecture docs', needsRepo: true, needsProject: false },
  { type: 'code-review', name: 'Code Review Agent', desc: 'Reviews PRs, security, and best practices', needsRepo: true, needsProject: false },
  { type: 'deploy', name: 'Deploy Agent', desc: 'Analyzes deployment configs and infrastructure', needsRepo: true, needsProject: false },
]

const statusIcon = (status: string) => {
  switch (status) {
    case 'completed': return <CheckCircle className="h-4 w-4 text-green-500" />
    case 'running': case 'in_progress': return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
    case 'failed': return <AlertCircle className="h-4 w-4 text-red-500" />
    default: return <Clock className="h-4 w-4 text-gray-400" />
  }
}

export function Agents() {
  const [runs, setRuns] = useState<AgentRun[]>([])
  const [loading, setLoading] = useState(true)
  const [projects, setProjects] = useState<Project[]>([])
  const [repos, setRepos] = useState<Repository[]>([])
  const [selectedProject, setSelectedProject] = useState('')
  const [selectedRepo, setSelectedRepo] = useState('')
  const [taskInput, setTaskInput] = useState('')
  const [runningType, setRunningType] = useState<string | null>(null)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [expandedRun, setExpandedRun] = useState<string | null>(null)

  async function load() {
    try {
      const [runsData, projData, repoData] = await Promise.all([
        agentRunsApi.list(),
        projectsApi.list(),
        repositoriesApi.list(),
      ])
      setRuns(runsData)
      setProjects(projData)
      setRepos(repoData)
    } catch { /* empty */ }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function handleRun(agent: AgentDef) {
    if (agent.needsProject && !selectedProject) {
      alert('Select a project first')
      return
    }
    if (agent.needsRepo && !selectedRepo) {
      alert('Select a repository first (index it from the Repositories page)')
      return
    }

    setRunningType(agent.type)
    setResult(null)
    try {
      let res: Record<string, unknown>

      switch (agent.type) {
        case 'planner': {
          const task = taskInput || 'Analyze the project and suggest improvements'
          const r = await plannerApi.planAndExecute(task, selectedProject)
          res = r as Record<string, unknown>
          break
        }
        case 'repository':
          res = await repoAgentApi.understand(selectedRepo)
          break
        case 'knowledge': {
          const query = taskInput || 'What is this project about?'
          res = await knowledgeAgentApi.search(query, selectedProject || undefined)
          break
        }
        case 'incident':
          res = await incidentAgentApi.analyze(selectedRepo)
          break
        case 'documentation':
          res = await docAgentApi.generateReadme(selectedRepo)
          break
        case 'code-review':
          res = await codeReviewApi.reviewPR(selectedRepo)
          break
        case 'deploy':
          res = await deployApi.analyze(selectedRepo)
          break
        default:
          res = { error: 'Unknown agent type' }
      }

      setResult(res)
      setTaskInput('')
      await load()
    } catch (err: unknown) {
      setResult({ error: err instanceof Error ? err.message : 'Failed to run agent' })
    } finally {
      setRunningType(null)
    }
  }

  function formatAgentResult(res: Record<string, unknown>) {
    const r = res as any
    const sections: JSX.Element[] = []
    if (typeof r.plan === 'string') sections.push(<div key="plan"><p className="text-xs font-medium text-gray-500 mb-1">Plan</p><pre className="text-sm bg-gray-50 rounded p-3 overflow-auto max-h-60 whitespace-pre-wrap">{r.plan}</pre></div>)
    if (typeof r.summary === 'string') sections.push(<div key="summary"><p className="text-xs font-medium text-gray-500 mb-1">Summary</p><pre className="text-sm bg-gray-50 rounded p-3 overflow-auto max-h-60 whitespace-pre-wrap">{r.summary}</pre></div>)
    if (typeof r.content === 'string') sections.push(<div key="content"><p className="text-xs font-medium text-gray-500 mb-1">Content</p><pre className="text-sm bg-gray-50 rounded p-3 overflow-auto max-h-60 whitespace-pre-wrap">{r.content}</pre></div>)
    if (typeof r.description === 'string') sections.push(<div key="desc"><p className="text-xs font-medium text-gray-500 mb-1">Description</p><pre className="text-sm bg-gray-50 rounded p-3 overflow-auto max-h-60 whitespace-pre-wrap">{r.description}</pre></div>)
    if (typeof r.analysis === 'string') sections.push(<div key="analysis"><p className="text-xs font-medium text-gray-500 mb-1">Analysis</p><pre className="text-sm bg-gray-50 rounded p-3 overflow-auto max-h-60 whitespace-pre-wrap">{r.analysis}</pre></div>)
    if (Array.isArray(r.results)) {
      const items = r.results.slice(0, 20).map((item: any, i: number) => {
        const sim = typeof item.similarity === 'number' ? item.similarity : 0
        const c = typeof item.content === 'string' ? item.content : JSON.stringify(item)
        return <div key={i} className="text-sm bg-gray-50 rounded p-3"><p className="text-xs text-gray-400 mb-1">#{i + 1}{sim ? ` similarity: ${sim.toFixed(3)}` : ''}</p><pre className="whitespace-pre-wrap text-gray-700">{c}</pre></div>
      })
      sections.push(<div key="results"><p className="text-xs font-medium text-gray-500 mb-1">Results ({r.results.length})</p><div className="space-y-2 max-h-80 overflow-auto">{items}</div></div>)
    }
    if (Array.isArray(r.recommendations)) {
      const items = r.recommendations.map((rec: any, i: number) => <li key={i} className="text-sm text-gray-700">{String(rec)}</li>)
      sections.push(<div key="recs"><p className="text-xs font-medium text-gray-500 mb-1">Recommendations</p><ul className="list-disc list-inside space-y-1">{items}</ul></div>)
    }
    if (Array.isArray(r.issues)) {
      const items = r.issues.map((issue: any, i: number) => {
        const sev = typeof issue.severity === 'string' ? issue.severity : 'Issue'
        const file = typeof issue.file === 'string' ? issue.file : ''
        const msg = typeof issue.message === 'string' ? issue.message : ''
        return <div key={i} className="text-sm bg-red-50 rounded p-3 border border-red-100"><p className="font-medium text-red-700">{sev} {file ? <span className="font-mono text-xs">in {file}</span> : null}</p><p className="text-red-600 text-xs mt-1">{msg || JSON.stringify(issue)}</p></div>
      })
      sections.push(<div key="issues"><p className="text-xs font-medium text-gray-500 mb-1">Issues Found</p><div className="space-y-2">{items}</div></div>)
    }
    if (sections.length === 0) {
      return <pre className="text-sm text-gray-700 bg-gray-50 rounded p-4 overflow-auto max-h-96 whitespace-pre-wrap">{JSON.stringify(res, null, 2)}</pre>
    }
    return <>{sections}</>
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Agents</h1>
        <p className="text-gray-500">AI engineering agents and their run history</p>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-5 space-y-4">
        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
          <Terminal className="h-4 w-4" /> Run Agent
        </h3>
        <div className="flex flex-wrap gap-4">
          <select value={selectedProject} onChange={e => setSelectedProject(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">Select project...</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <select value={selectedRepo} onChange={e => setSelectedRepo(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">Select repository...</option>
            {repos.filter(r => r.indexing_status === 'completed').map(r => (
              <option key={r.id} value={r.id}>{r.name}</option>
            ))}
          </select>
          <input type="text" value={taskInput} onChange={e => setTaskInput(e.target.value)}
            placeholder="Task description (optional)"
            className="flex-1 min-w-[200px] px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <p className="text-xs text-gray-400">
          Planner and Knowledge need a project. Repository, Incident, Documentation, and Code Review need an indexed repository.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {agents.map(a => (
          <div key={a.type} className="rounded-lg border border-gray-200 bg-white p-5 hover:shadow-sm transition-shadow">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 rounded-lg bg-purple-100 text-purple-600">
                <Bot className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">{a.name}</h3>
              </div>
            </div>
            <p className="text-sm text-gray-500 mb-4">{a.desc}</p>
            <button
              onClick={() => handleRun(a)}
              disabled={runningType !== null}
              className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium disabled:opacity-50"
            >
              {runningType === a.type
                ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Running...</>
                : <><Play className="h-3.5 w-3.5" /> Run</>
              }
            </button>
          </div>
        ))}
      </div>

      {result && (
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900">Result</h3>
            <button onClick={() => setResult(null)} className="text-sm text-gray-400 hover:text-gray-600">Clear</button>
          </div>
          {result.error ? (
            <div className="text-sm text-red-600 bg-red-50 rounded p-4">{String(result.error)}</div>
          ) : (
            <div className="space-y-2">{formatAgentResult(result)}</div>
          )}
        </div>
      )}

      <div className="rounded-lg border border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Recent Runs</h2>
          <button onClick={load} className="text-gray-400 hover:text-gray-600">
            <RotateCw className="h-4 w-4" />
          </button>
        </div>
        {loading ? (
          <div className="px-6 py-8 text-center text-gray-400">Loading...</div>
        ) : runs.length === 0 ? (
          <div className="px-6 py-8 text-center text-gray-400">No runs yet</div>
        ) : (
          <div className="divide-y divide-gray-200">
            {runs.slice(0, 10).map(r => (
              <div key={r.id}>
                <div
                  className="px-6 py-4 flex items-center justify-between hover:bg-gray-50 cursor-pointer"
                  onClick={() => setExpandedRun(expandedRun === r.id ? null : r.id)}
                >
                  <div className="flex items-center gap-4">
                    {statusIcon(r.status)}
                    <div>
                      <p className="text-sm font-medium text-gray-900">{r.agent_type}</p>
                      <p className="text-xs text-gray-500">{r.status}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400">{new Date(r.created_at).toLocaleString()}</span>
                    {expandedRun === r.id ? <ChevronUp className="h-4 w-4 text-gray-400" /> : <ChevronDown className="h-4 w-4 text-gray-400" />}
                  </div>
                </div>
                {expandedRun === r.id && (
                  <div className="px-6 pb-4">
                    {r.input_data && (
                      <div className="mb-2">
                        <p className="text-xs font-medium text-gray-500 mb-1">Input</p>
                        <pre className="text-xs bg-gray-50 rounded p-3 overflow-auto max-h-40 whitespace-pre-wrap">{JSON.stringify(r.input_data, null, 2)}</pre>
                      </div>
                    )}
                    {r.output_data && (
                      <div className="mb-2">
                        <p className="text-xs font-medium text-gray-500 mb-1">Output</p>
                        <pre className="text-xs bg-gray-50 rounded p-3 overflow-auto max-h-40 whitespace-pre-wrap">{JSON.stringify(r.output_data, null, 2)}</pre>
                      </div>
                    )}
                    {r.error && (
                      <div>
                        <p className="text-xs font-medium text-red-500 mb-1">Error</p>
                        <pre className="text-xs text-red-600 bg-red-50 rounded p-3">{r.error}</pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
