import { useEffect, useState } from 'react'
import { Bot, CheckCircle, Clock, AlertCircle, Play, Loader2, Terminal } from 'lucide-react'
import { agentRunsApi, plannerApi, projectsApi } from '../lib/api'
import type { AgentRun, Project } from '../lib/api'

const agents = [
  { type: 'planner', name: 'Planner Agent', desc: 'Decomposes tasks into execution steps' },
  { type: 'repository', name: 'Repository Agent', desc: 'Understands code and architecture' },
  { type: 'knowledge', name: 'Knowledge Agent', desc: 'Retrieves relevant information' },
  { type: 'incident', name: 'Incident Agent', desc: 'Log analysis and root cause' },
  { type: 'documentation', name: 'Documentation Agent', desc: 'Generates README and API docs' },
  { type: 'code-review', name: 'Code Review Agent', desc: 'Reviews PRs and security' },
  { type: 'workflow', name: 'Workflow Engine', desc: 'Orchestrates multi-step workflows' },
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
  const [selectedProject, setSelectedProject] = useState('')
  const [taskInput, setTaskInput] = useState('')
  const [running, setRunning] = useState(false)

  async function load() {
    try {
      const [runsData, projData] = await Promise.all([
        agentRunsApi.list(),
        projectsApi.list(),
      ])
      setRuns(runsData)
      setProjects(projData)
    } catch { /* empty */ }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function handleRun(agentType: string) {
    if (!selectedProject) {
      alert('Select a project first')
      return
    }
    const task = taskInput || `Run ${agentType} analysis`
    setRunning(true)
    try {
      await plannerApi.planAndExecute(task, selectedProject)
      setTaskInput('')
      await load()
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to run agent')
    } finally {
      setRunning(false)
    }
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
        <div className="flex gap-4">
          <select
            value={selectedProject}
            onChange={e => setSelectedProject(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select project...</option>
            {projects.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <input
            type="text" value={taskInput}
            onChange={e => setTaskInput(e.target.value)}
            placeholder="Describe the task (optional)"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
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
              onClick={() => handleRun(a.type)}
              disabled={running || !selectedProject}
              className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5" /> {running ? 'Running...' : 'Run'}
            </button>
          </div>
        ))}
      </div>

      <div className="rounded-lg border border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">Recent Runs</h2>
        </div>
        {loading ? (
          <div className="px-6 py-8 text-center text-gray-400">Loading...</div>
        ) : runs.length === 0 ? (
          <div className="px-6 py-8 text-center text-gray-400">No runs yet</div>
        ) : (
          <div className="divide-y divide-gray-200">
            {runs.slice(0, 10).map(r => (
              <div key={r.id} className="px-6 py-4 flex items-center justify-between hover:bg-gray-50">
                <div className="flex items-center gap-4">
                  {statusIcon(r.status)}
                  <div>
                    <p className="text-sm font-medium text-gray-900">{r.agent_type}</p>
                    <p className="text-xs text-gray-500">{r.status}</p>
                  </div>
                </div>
                <span className="text-xs text-gray-400">
                  {new Date(r.created_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
