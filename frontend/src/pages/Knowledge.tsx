import { useEffect, useState } from 'react'
import { FileText, Search, BookOpen } from 'lucide-react'
import { documentsApi } from '../lib/api'
import type { Document_ } from '../lib/api'

export function Knowledge() {
  const [docs, setDocs] = useState<Document_[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  async function load() {
    try {
      const data = await documentsApi.list()
      setDocs(data)
    } catch { /* empty */ }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const filtered = docs.filter(d =>
    d.title.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Knowledge Base</h1>
        <p className="text-gray-500">Indexed documents and knowledge</p>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          type="text" value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search documents..."
          className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">Loading...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-400 border rounded-lg">
          <BookOpen className="mx-auto h-12 w-12 mb-3 text-gray-300" />
          <p className="text-lg font-medium text-gray-500">
            {search ? 'No documents match your search' : 'No documents indexed'}
          </p>
          <p className="text-sm mt-1">
            {search ? 'Try a different search term' : 'Upload documents or connect repositories to build knowledge'}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(d => (
            <div key={d.id} className="rounded-lg border border-gray-200 bg-white p-4 flex items-center gap-4 hover:shadow-sm transition-shadow">
              <div className="p-2 rounded-lg bg-purple-100 text-purple-600">
                <FileText className="h-5 w-5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{d.title}</p>
                <p className="text-xs text-gray-500">{d.source_type}</p>
              </div>
              <span className="text-xs text-gray-400">
                {new Date(d.created_at).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
