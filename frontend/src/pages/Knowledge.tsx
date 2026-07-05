import { useEffect, useState } from 'react'
import { FileText, Search, BookOpen, Database, GitBranch, ChevronDown, ChevronUp, Loader2, Brain } from 'lucide-react'
import { documentsApi, repositoriesApi, projectsApi, knowledgeAgentApi, memoryApi } from '../lib/api'
import type { Document_, Repository, Project } from '../lib/api'

export function Knowledge() {
  const [docs, setDocs] = useState<Document_[]>([])
  const [repos, setRepos] = useState<Repository[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [searchResult, setSearchResult] = useState<Record<string, unknown> | null>(null)
  const [searching, setSearching] = useState(false)
  const [selectedProject, setSelectedProject] = useState('')
  const [expandedDoc, setExpandedDoc] = useState<string | null>(null)
  const [expandedRepo, setExpandedRepo] = useState<string | null>(null)
  const [docChunks, setDocChunks] = useState<Record<string, Record<string, unknown>[]>>({})
  const [repoDocs, setRepoDocs] = useState<Record<string, Record<string, unknown>[]>>({})
  const [loadingChunks, setLoadingChunks] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'docs' | 'memory'>('docs')
  const [memSearch, setMemSearch] = useState('')
  const [memResults, setMemResults] = useState<Record<string, unknown>[] | null>(null)
  const [memSearching, setMemSearching] = useState(false)

  async function load() {
    try {
      const [d, r, p] = await Promise.all([
        documentsApi.list(),
        repositoriesApi.list(),
        projectsApi.list(),
      ])
      setDocs(d)
      setRepos(r)
      setProjects(p)
    } catch { /* empty */ }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function handleSearch() {
    if (!search.trim()) return
    setSearching(true)
    setSearchResult(null)
    try {
      const res = await knowledgeAgentApi.search(search, selectedProject || undefined)
      setSearchResult(res)
    } catch (err: unknown) {
      setSearchResult({ error: err instanceof Error ? err.message : 'Search failed' })
    } finally { setSearching(false) }
  }

  async function toggleDoc(id: string) {
    if (expandedDoc === id) { setExpandedDoc(null); return }
    setExpandedDoc(id)
    setExpandedRepo(null)
    if (!docChunks[id]) {
      setLoadingChunks(id)
      try {
        const chunks = await documentsApi.getChunks(id)
        setDocChunks(prev => ({ ...prev, [id]: chunks }))
      } catch { /* */ }
      finally { setLoadingChunks(null) }
    }
  }

  async function toggleRepo(id: string) {
    if (expandedRepo === id) { setExpandedRepo(null); return }
    setExpandedRepo(id)
    setExpandedDoc(null)
    if (!repoDocs[id]) {
      setLoadingChunks(id)
      try {
        const allDocs = await documentsApi.list()
        const match = allDocs.find((d: Document_) => d.source_type === 'repository' && d.title.includes(repos.find(r => r.id === id)?.name || ''))
        if (match) {
          const chunks = await documentsApi.getChunks(match.id)
          setRepoDocs(prev => ({ ...prev, [id]: chunks }))
        } else {
          setRepoDocs(prev => ({ ...prev, [id]: [] }))
        }
      } catch { /* */ }
      finally { setLoadingChunks(null) }
    }
  }

  const indexedRepos = repos.filter(r => r.indexing_status === 'completed')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Knowledge Base</h1>
        <p className="text-gray-500">Search across indexed repositories and documents</p>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-5 space-y-4">
        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
          <Search className="h-4 w-4" /> Semantic Search
        </h3>
        <div className="flex gap-3">
          <select value={selectedProject} onChange={e => setSelectedProject(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">All projects</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <input type="text" value={search} onChange={e => setSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="Search across knowledge (e.g. 'authentication flow', 'error handling')"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          <button onClick={handleSearch} disabled={searching || !search.trim()}
            className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {searching ? 'Searching...' : 'Search'}
          </button>
        </div>
      </div>

      {searchResult && (
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900">Search Results</h3>
            <button onClick={() => setSearchResult(null)} className="text-sm text-gray-400 hover:text-gray-600">Clear</button>
          </div>
          {searchResult.error ? (
            <div className="text-sm text-red-600 bg-red-50 rounded p-4">
              {String(searchResult.error)}
              {String(searchResult.error).includes('Ollama') && (
                <p className="text-xs mt-2">Make sure Ollama is running with `nomic-embed-text` loaded: <code className="bg-red-100 px-1 rounded">ollama pull nomic-embed-text</code></p>
              )}
            </div>
          ) : (
            <div>
              {(() => {
                const count = typeof searchResult.count === 'number' ? searchResult.count : 0
                const results = Array.isArray(searchResult.results) ? (searchResult.results as Record<string, unknown>[]) : []
                const total = count || results.length
                return (
                  <>
                    <p className="text-xs text-gray-500 mb-3">{total} results found</p>
                    {results.length > 0 ? (
                      <div className="space-y-3 max-h-96 overflow-auto">
                        {results.slice(0, 20).map((r, i) => {
                          const title = typeof r.document_title === 'string' ? r.document_title : `Result ${i + 1}`
                          const src = typeof r.source_type === 'string' ? r.source_type : ''
                          const sim = typeof r.similarity === 'number' ? r.similarity : 0
                          const content = typeof r.content === 'string' ? r.content : ''
                          return (
                            <div key={i} className="border border-gray-200 rounded-lg p-4 hover:border-blue-200 transition-colors">
                              <div className="flex items-center justify-between mb-2">
                                <p className="text-sm font-medium text-gray-900">{title}</p>
                                <span className="text-xs text-gray-400">{src} {sim ? `· ${(sim * 100).toFixed(0)}% match` : null}</span>
                              </div>
                              <pre className="text-sm text-gray-600 whitespace-pre-wrap line-clamp-6">{content}</pre>
                            </div>
                          )
                        })}
                      </div>
                    ) : (
                      <div className="text-sm text-gray-500">No results found. Try a different query or index a repository first.</div>
                    )}
                  </>
                )
              })()}
            </div>
          )}
        </div>
      )}

      <div className="border-b border-gray-200 mb-4">
        <div className="flex gap-4">
          <button onClick={() => setActiveTab('docs')}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors ${activeTab === 'docs' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            <FileText className="h-4 w-4 inline mr-1" /> Documents
          </button>
          <button onClick={() => setActiveTab('memory')}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors ${activeTab === 'memory' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            <Brain className="h-4 w-4 inline mr-1" /> Agent Memory
          </button>
        </div>
      </div>

      {activeTab === 'memory' ? (
        <div className="space-y-4">
          <div className="rounded-lg border border-gray-200 bg-white p-5 space-y-4">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <Brain className="h-4 w-4" /> Semantic Memory Search
            </h3>
            <p className="text-xs text-gray-500">Search past agent results and knowledge stored in semantic memory</p>
            <div className="flex gap-3">
              <input type="text" value={memSearch} onChange={e => setMemSearch(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && (async () => {
                  if (!memSearch.trim()) return
                  setMemSearching(true)
                  try {
                    const res = await memoryApi.searchSemantic(memSearch, 10, 0.3)
                    setMemResults(res.results)
                  } catch { setMemResults([]) }
                  finally { setMemSearching(false) }
                })()}
                placeholder="Search agent memory (e.g. 'deployment analysis', 'code review')"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <button onClick={async () => {
                if (!memSearch.trim()) return
                setMemSearching(true)
                try {
                  const res = await memoryApi.searchSemantic(memSearch, 10, 0.3)
                  setMemResults(res.results)
                } catch { setMemResults([]) }
                finally { setMemSearching(false) }
              }} disabled={memSearching || !memSearch.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-purple-600 text-white rounded-md text-sm font-medium hover:bg-purple-700 disabled:opacity-50">
                {memSearching ? 'Searching...' : 'Search Memory'}
              </button>
            </div>
          </div>
          {memResults !== null && (
            <div className="rounded-lg border border-gray-200 bg-white p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-900">Memory Results ({memResults.length})</h3>
                <button onClick={() => setMemResults(null)} className="text-sm text-gray-400 hover:text-gray-600">Clear</button>
              </div>
              {memResults.length === 0 ? (
                <div className="text-sm text-gray-500">No matching memory entries found.</div>
              ) : (
                <div className="space-y-3 max-h-96 overflow-auto">
                  {memResults.map((r, i) => (
                    <div key={i} className="border border-gray-200 rounded-lg p-4 hover:border-purple-200 transition-colors">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-purple-600">{String((r.metadata as Record<string, unknown>)?.type || 'memory')}</span>
                        <span className="text-xs text-gray-400">{typeof r.similarity === 'number' ? `${(r.similarity * 100).toFixed(0)}% match` : ''}</span>
                      </div>
                      <pre className="text-sm text-gray-700 whitespace-pre-wrap line-clamp-6">{String(r.text || '')}</pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <GitBranch className="h-4 w-4" /> Indexed Repositories
            </h2>
          </div>
          {loading ? (
            <div className="px-6 py-8 text-center text-gray-400">Loading...</div>
          ) : indexedRepos.length === 0 ? (
            <div className="px-6 py-8 text-center text-gray-400">
              <Database className="mx-auto h-8 w-8 mb-2 text-gray-300" />
              <p>No indexed repositories</p>
              <p className="text-xs mt-1">Connect and index a repository from the Repositories page</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {indexedRepos.map(r => (
                <div key={r.id}>
                  <div className="px-6 py-4 flex items-center justify-between hover:bg-gray-50 cursor-pointer" onClick={() => toggleRepo(r.id)}>
                    <div>
                      <p className="text-sm font-medium text-gray-900">{r.name}</p>
                      <p className="text-xs text-gray-500">{r.branch} &middot; {r.provider}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {loadingChunks === r.id ? <Loader2 className="h-4 w-4 animate-spin text-gray-400" /> : null}
                      {expandedRepo === r.id ? <ChevronUp className="h-4 w-4 text-gray-400" /> : <ChevronDown className="h-4 w-4 text-gray-400" />}
                    </div>
                  </div>
                  {expandedRepo === r.id && (
                    <div className="px-6 pb-4">
                      {repoDocs[r.id] === undefined ? (
                        <p className="text-xs text-gray-400">Loading...</p>
                      ) : repoDocs[r.id].length === 0 ? (
                        <p className="text-xs text-gray-400">No content chunks found</p>
                      ) : (
                        <div className="space-y-2 max-h-80 overflow-auto">
                          {repoDocs[r.id].slice(0, 50).map((chunk, i) => (
                            <div key={i} className="text-xs bg-gray-50 rounded p-3 border border-gray-100">
                              <p className="text-gray-400 mb-1">Chunk {i + 1}</p>
                              <pre className="text-gray-700 whitespace-pre-wrap">{typeof chunk.content === 'string' ? chunk.content.slice(0, 500) : JSON.stringify(chunk)}</pre>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <FileText className="h-4 w-4" /> Documents
            </h2>
          </div>
          {loading ? (
            <div className="px-6 py-8 text-center text-gray-400">Loading...</div>
          ) : docs.length === 0 ? (
            <div className="px-6 py-8 text-center text-gray-400">
              <BookOpen className="mx-auto h-8 w-8 mb-2 text-gray-300" />
              <p>No documents uploaded</p>
              <p className="text-xs mt-1">Upload documents via the API or ingestion pipeline</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {docs.map(d => (
                <div key={d.id}>
                  <div className="px-6 py-4 flex items-center justify-between hover:bg-gray-50 cursor-pointer" onClick={() => toggleDoc(d.id)}>
                    <div>
                      <p className="text-sm font-medium text-gray-900">{d.title}</p>
                      <p className="text-xs text-gray-500">{d.source_type}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-400">{new Date(d.created_at).toLocaleDateString()}</span>
                      {loadingChunks === d.id ? <Loader2 className="h-4 w-4 animate-spin text-gray-400" /> : null}
                      {expandedDoc === d.id ? <ChevronUp className="h-4 w-4 text-gray-400" /> : <ChevronDown className="h-4 w-4 text-gray-400" />}
                    </div>
                  </div>
                  {expandedDoc === d.id && (
                    <div className="px-6 pb-4">
                      {docChunks[d.id] === undefined ? (
                        <p className="text-xs text-gray-400">Loading...</p>
                      ) : docChunks[d.id].length === 0 ? (
                        <p className="text-xs text-gray-400">No chunks found</p>
                      ) : (
                        <div className="space-y-2 max-h-80 overflow-auto">
                          {docChunks[d.id].slice(0, 50).map((chunk, i) => (
                            <div key={i} className="text-xs bg-gray-50 rounded p-3 border border-gray-100">
                              <p className="text-gray-400 mb-1">Chunk {i + 1}</p>
                              <pre className="text-gray-700 whitespace-pre-wrap">{typeof chunk.content === 'string' ? chunk.content.slice(0, 500) : JSON.stringify(chunk)}</pre>
                            </div>
                          ))}
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
      )}
    </div>
  )
}
