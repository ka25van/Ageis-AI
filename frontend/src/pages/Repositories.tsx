import { useEffect, useState } from 'react'
import { GitBranch, Plus, RefreshCw, Globe, Lock, CheckCircle, Clock, AlertCircle, MoreVertical, Trash2 } from 'lucide-react'
import { repositoriesApi, projectsApi } from '../lib/api'
import type { Repository, Project } from '../lib/api'

export function Repositories() {
  const [repos, setRepos] = useState<Repository[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [projectId, setProjectId] = useState('')
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [branch, setBranch] = useState('main')
  const [saving, setSaving] = useState(false)
  const [openMenu, setOpenMenu] = useState<string | null>(null)

  async function load() {
    try {
      const [r, p] = await Promise.all([
        repositoriesApi.list(),
        projectsApi.list(),
      ])
      setRepos(r)
      setProjects(p)
    } catch { /* empty */ }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function handleSave() {
    if (!projectId) return
    setSaving(true)
    try {
      await repositoriesApi.create({ project_id: projectId, name, url, branch })
      setName('')
      setUrl('')
      setBranch('main')
      setProjectId('')
      setShowForm(false)
      await load()
    } finally { setSaving(false) }
  }

  async function handleIngest(id: string) {
    await repositoriesApi.ingest(id)
    await load()
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this repository?')) return
    await repositoriesApi.delete(id)
    setOpenMenu(null)
    await load()
  }

  const statusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'in_progress': return <Clock className="h-4 w-4 text-blue-500" />
      case 'failed': return <AlertCircle className="h-4 w-4 text-red-500" />
      default: return <Clock className="h-4 w-4 text-gray-400" />
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Repositories</h1>
          <p className="text-gray-500">Connect and index your code repositories</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" /> Add Repository
        </button>
      </div>

      {showForm && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 space-y-4">
          <h3 className="font-semibold text-gray-900">Connect Repository</h3>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Project</label>
            <select
              value={projectId}
              onChange={e => setProjectId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a project...</option>
              {projects.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Git URL</label>
            <input type="url" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://github.com/user/repo"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Branch</label>
            <input type="text" value={branch} onChange={e => setBranch(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div className="flex gap-3">
            <button onClick={handleSave} disabled={!name || !url || !projectId || saving}
              className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
              {saving ? 'Connecting...' : 'Connect'}
            </button>
            <button onClick={() => setShowForm(false)}
              className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50">
              Cancel
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-400">Loading...</div>
      ) : repos.length === 0 ? (
        <div className="text-center py-12 text-gray-400 border rounded-lg">
          <GitBranch className="mx-auto h-12 w-12 mb-3 text-gray-300" />
          <p className="text-lg font-medium text-gray-500">No repositories connected</p>
          <p className="text-sm mt-1">Connect a repository to start indexing</p>
        </div>
      ) : (
        <div className="space-y-3">
          {repos.map(r => (
            <div key={r.id} className="rounded-lg border border-gray-200 bg-white p-5 flex items-center justify-between hover:shadow-sm transition-shadow">
              <div className="flex items-center gap-4">
                <div className="p-2 rounded-lg bg-green-100 text-green-600">
                  <GitBranch className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-gray-900">{r.name}</h3>
                    {r.is_private ? <Lock className="h-3.5 w-3.5 text-gray-400" /> : <Globe className="h-3.5 w-3.5 text-gray-400" />}
                  </div>
                  <p className="text-sm text-gray-500">{r.url}</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1.5 text-sm">
                  {statusIcon(r.indexing_status)}
                  <span className="text-gray-500 capitalize">{r.indexing_status}</span>
                </div>
                <button onClick={() => handleIngest(r.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded-md text-sm text-gray-600 hover:bg-gray-50">
                  <RefreshCw className="h-3.5 w-3.5" /> Index
                </button>
                <div className="relative">
                  <button
                    onClick={() => setOpenMenu(openMenu === r.id ? null : r.id)}
                    className="p-1 rounded text-gray-400 hover:text-gray-600"
                  >
                    <MoreVertical className="h-4 w-4" />
                  </button>
                  {openMenu === r.id && (
                    <>
                      <div className="fixed inset-0 z-10" onClick={() => setOpenMenu(null)} />
                      <div className="absolute right-0 top-8 z-20 bg-white border rounded-lg shadow-lg py-1 min-w-[120px]">
                        <button onClick={() => handleDelete(r.id)}
                          className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-600 hover:bg-red-50">
                          <Trash2 className="h-3.5 w-3.5" /> Delete
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
