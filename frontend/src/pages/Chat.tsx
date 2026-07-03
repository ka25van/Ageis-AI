import { useState, useRef, useEffect } from 'react'
import { MessageSquare, Send, Bot, User, ChevronDown, ChevronRight, Loader2 } from 'lucide-react'
import { useAuth } from '../lib/AuthContext'
import { plannerApi, projectsApi, memoryApi, RouteResponse } from '../lib/api'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  agent_details?: RouteResponse['agent_details']
  agents_used?: string[]
}

export function Chat() {
  const { user } = useAuth()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [expandedDetails, setExpandedDetails] = useState<Set<number>>(new Set())
  const [projects, setProjects] = useState<{ id: string; name: string }[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    projectsApi.list().then((list) => {
      setProjects(list)
      if (list.length > 0 && !selectedProjectId) {
        setSelectedProjectId(list[0].id)
      }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedProjectId) return
    memoryApi.getConversation(selectedProjectId).then((data) => {
      if (data.messages && data.messages.length > 0) {
        const loaded: ChatMessage[] = data.messages.map((m) => ({
          role: m.role as 'user' | 'assistant',
          content: m.content,
        }))
        setMessages(loaded)
      }
    }).catch(() => {})
  }, [selectedProjectId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim() || loading || !selectedProjectId) return

    const userMessage: ChatMessage = { role: 'user', content: input }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const data = await plannerApi.route(input.trim(), selectedProjectId)

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.response,
          agent_details: data.agent_details,
          agents_used: data.agents_used,
        },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${err instanceof Error ? err.message : 'Request failed'}` },
      ])
    } finally {
      setLoading(false)
    }
  }

  function toggleDetails(index: number) {
    setExpandedDetails((prev) => {
      const next = new Set(prev)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  if (!user) return null

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Chat</h1>
          <p className="text-sm text-gray-500">Ask anything about your projects</p>
        </div>
        <select
          value={selectedProjectId}
          onChange={(e) => setSelectedProjectId(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Select a project...</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-20">
            <MessageSquare className="h-12 w-12 mx-auto mb-4" />
            <p className="text-lg">Ask me anything</p>
            <p className="text-sm">Try: "Explain the project architecture" or "Find security issues"</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-xl px-4 py-3 ${msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-white border border-gray-200'}`}>
              <div className="flex items-center gap-2 mb-1">
                {msg.role === 'user' ? (
                  <User className="h-4 w-4" />
                ) : (
                  <Bot className="h-4 w-4 text-blue-600" />
                )}
                <span className="text-xs font-medium opacity-70">
                  {msg.role === 'user' ? 'You' : 'Aegis AI'}
                </span>
              </div>
              <div className="text-sm whitespace-pre-wrap">{msg.content}</div>

              {msg.agents_used && msg.agents_used.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-200">
                  <button
                    onClick={() => toggleDetails(i)}
                    className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
                  >
                    {expandedDetails.has(i) ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                    Agents used: {msg.agents_used.join(', ')}
                  </button>
                  {expandedDetails.has(i) && msg.agent_details && (
                    <div className="mt-2 space-y-2">
                      {Object.entries(msg.agent_details).map(([name, details]) => (
                        <div key={name} className="text-xs bg-gray-50 rounded p-2">
                          <div className="font-medium text-gray-700">{name}</div>
                          <div className="text-gray-500">Confidence: {(details.confidence * 100).toFixed(0)}%</div>
                          {details.recommendations.length > 0 && (
                            <div className="mt-1 text-gray-500">
                              Recommendations: {details.recommendations.join(', ')}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-xl px-4 py-3">
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                <span className="text-sm text-gray-500">Thinking...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={selectedProjectId ? 'Ask about your project...' : 'Select a project first'}
          disabled={loading || !selectedProjectId}
          className="flex-1 rounded-xl border border-gray-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading || !input.trim() || !selectedProjectId}
          className="rounded-xl bg-blue-600 px-4 py-3 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          <Send className="h-5 w-5" />
        </button>
      </form>
    </div>
  )
}
