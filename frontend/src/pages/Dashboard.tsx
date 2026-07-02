import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LayoutDashboard, GitBranch, Database, Bot, Activity, Server } from 'lucide-react'
import { projectsApi, repositoriesApi, agentRunsApi } from '../lib/api'
import type { Project, Repository, AgentRun } from '../lib/api'

export function Dashboard() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[]>([])
  const [repos, setRepos] = useState<Repository[]>([])
  const [runs, setRuns] = useState<AgentRun[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const [p, r, runsData] = await Promise.all([
          projectsApi.list(),
          repositoriesApi.list(),
          agentRunsApi.list(),
        ])
        setProjects(p)
        setRepos(r)
        setRuns(runsData)
      } catch {
        // not authenticated or empty
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const activeRuns = runs.filter(r => r.status === 'running' || r.status === 'in_progress')

  const stats = [
    { name: 'Projects', value: String(projects.length), icon: GitBranch, color: 'text-blue-600 bg-blue-100' },
    { name: 'Repositories', value: String(repos.length), icon: Database, color: 'text-green-600 bg-green-100' },
    { name: 'Agents', value: '7', icon: Bot, color: 'text-purple-600 bg-purple-100' },
    { name: 'Active Runs', value: String(activeRuns.length), icon: Activity, color: 'text-orange-600 bg-orange-100' },
  ]

  const recentItems = [
    ...runs.slice(0, 4).map(r => ({
      id: r.id,
      action: `Agent run: ${r.agent_type}`,
      target: r.input_data ? JSON.stringify(r.input_data).slice(0, 60) : '-',
      time: new Date(r.created_at).toLocaleDateString(),
      status: r.status,
    })),
    ...repos.slice(0, 2).map(r => ({
      id: r.id,
      action: `Repository: ${r.name}`,
      target: r.indexing_status === 'completed' ? 'Indexed' : `Status: ${r.indexing_status}`,
      time: new Date(r.created_at).toLocaleDateString(),
      status: r.indexing_status === 'completed' ? 'completed' : 'pending',
    })),
  ].slice(0, 5)

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-gray-500">Overview of your Aegis AI workspace</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.name} className="rounded-lg border border-gray-200 bg-white p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">{stat.name}</p>
                <p className="mt-1 text-3xl font-bold text-gray-900">
                  {loading ? '-' : stat.value}
                </p>
              </div>
              <div className={`p-3 rounded-lg ${stat.color}`}>
                <stat.icon className="h-6 w-6" aria-hidden="true" />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-lg border border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">Quick Actions</h2>
        </div>
        <div className="grid gap-4 p-6 sm:grid-cols-2 lg:grid-cols-4">
          <button
            onClick={() => navigate('/projects')}
            className="group flex flex-col items-center gap-3 rounded-lg border border-gray-200 p-6 hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <div className="p-3 rounded-lg bg-blue-100 text-blue-600 group-hover:bg-blue-200">
              <LayoutDashboard className="h-6 w-6" />
            </div>
            <span className="text-sm font-medium text-gray-700">New Project</span>
          </button>
          <button
            onClick={() => navigate('/repositories')}
            className="group flex flex-col items-center gap-3 rounded-lg border border-gray-200 p-6 hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <div className="p-3 rounded-lg bg-green-100 text-green-600 group-hover:bg-green-200">
              <GitBranch className="h-6 w-6" />
            </div>
            <span className="text-sm font-medium text-gray-700">Connect Repository</span>
          </button>
          <button
            onClick={() => navigate('/agents')}
            className="group flex flex-col items-center gap-3 rounded-lg border border-gray-200 p-6 hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <div className="p-3 rounded-lg bg-purple-100 text-purple-600 group-hover:bg-purple-200">
              <Bot className="h-6 w-6" />
            </div>
            <span className="text-sm font-medium text-gray-700">Run Agent</span>
          </button>
          <button className="group flex flex-col items-center gap-3 rounded-lg border border-gray-200 p-6 hover:border-blue-300 hover:bg-blue-50 transition-colors">
            <div className="p-3 rounded-lg bg-orange-100 text-orange-600 group-hover:bg-orange-200">
              <Server className="h-6 w-6" />
            </div>
            <span className="text-sm font-medium text-gray-700">Deploy</span>
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">Recent Activity</h2>
        </div>
        <div className="divide-y divide-gray-200">
          {loading ? (
            <div className="px-6 py-8 text-center text-gray-400">Loading...</div>
          ) : recentItems.length === 0 ? (
            <div className="px-6 py-8 text-center text-gray-400">No recent activity</div>
          ) : (
            recentItems.map((item) => (
              <div key={item.id} className="px-6 py-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`p-2 rounded-lg ${
                      item.status === 'completed' ? 'bg-green-100 text-green-600' :
                      item.status === 'in_progress' || item.status === 'running' ? 'bg-blue-100 text-blue-600' :
                      'bg-gray-100 text-gray-600'
                    }`}>
                      <Activity className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">{item.action}</p>
                      <p className="text-sm text-gray-500">{item.target}</p>
                    </div>
                  </div>
                  <span className="text-sm text-gray-400">{item.time}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
