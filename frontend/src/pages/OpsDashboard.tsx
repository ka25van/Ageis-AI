import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, BarChart3, Clock, Shield, Terminal, TrendingUp, Cpu, FileText } from 'lucide-react'
import { alertsApi } from '../lib/api'

interface DashboardData {
  total_runs: number
  completed: number
  failed: number
  running: number
  agent_counts: Record<string, number>
}

interface TracingEntry {
  id: string
  run_id: string
  step_type: string
  name: string
  status: string
  duration_ms: number
  created_at: string
}

interface AlertEntry {
  id: string
  text: string
  metadata: Record<string, unknown>
  similarity: number
}

export function OpsDashboard() {
  const [dash, setDash] = useState<DashboardData | null>(null)
  const [traces, setTraces] = useState<TracingEntry[]>([])
  const [alertStats, setAlertStats] = useState<{ total_alerts: number; firing: number; resolved: number } | null>(null)
  const [alerts, setAlerts] = useState<AlertEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const [dashRes, traceRes, alertRes, alertHistoryRes] = await Promise.all([
          fetch('/api/v1/observability/dashboard').then(r => r.json()),
          fetch('/api/v1/observability/tracing?limit=20').then(r => r.json()),
          alertsApi.stats(),
          alertsApi.history(20),
        ])
        setDash(dashRes)
        setTraces(traceRes.tracing || [])
        setAlertStats(alertRes)
        setAlerts((alertHistoryRes.alerts || []) as unknown as AlertEntry[])
      } catch {
        // not authenticated
      } finally {
        setLoading(false)
      }
    }
    load()
    const interval = setInterval(load, 15000)
    return () => clearInterval(interval)
  }, [])

  const successRate = dash && dash.total_runs > 0
    ? ((dash.completed / dash.total_runs) * 100).toFixed(1)
    : '—'

  const stats = [
    { name: 'Total Runs', value: String(dash?.total_runs ?? '-'), icon: Activity, color: 'text-blue-600 bg-blue-100' },
    { name: 'Success Rate', value: `${successRate}%`, icon: TrendingUp, color: 'text-green-600 bg-green-100' },
    { name: 'Failed', value: String(dash?.failed ?? '-'), icon: AlertTriangle, color: 'text-red-600 bg-red-100' },
    { name: 'Active Runs', value: String(dash?.running ?? '-'), icon: Clock, color: 'text-orange-600 bg-orange-100' },
    { name: 'Alerts (Firing)', value: String(alertStats?.firing ?? '-'), icon: AlertTriangle, color: 'text-amber-600 bg-amber-100' },
    { name: 'Total Alerts', value: String(alertStats?.total_alerts ?? '-'), icon: Shield, color: 'text-purple-600 bg-purple-100' },
  ]

  const failureRate = dash && dash.total_runs > 0
    ? ((dash.failed / dash.total_runs) * 100).toFixed(1)
    : '0'

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Ops Dashboard</h1>
        <p className="mt-1 text-gray-500">Agent run metrics, execution traces, and alert monitoring</p>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {stats.map((stat) => (
          <div key={stat.name} className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-gray-500">{stat.name}</p>
                <p className="mt-1 text-2xl font-bold text-gray-900">
                  {loading ? '-' : stat.value}
                </p>
              </div>
              <div className={`p-2.5 rounded-lg ${stat.color}`}>
                <stat.icon className="h-5 w-5" aria-hidden="true" />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Agent Run Breakdown */}
        <div className="rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">Agent Run Breakdown</h2>
          </div>
          <div className="p-6">
            {dash && dash.agent_counts && Object.keys(dash.agent_counts).length > 0 ? (
              <div className="space-y-4">
                {Object.entries(dash.agent_counts).map(([agent, count]) => {
                  const pct = dash.total_runs > 0 ? ((count / dash.total_runs) * 100) : 0
                  return (
                    <div key={agent}>
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span className="font-medium text-gray-700 capitalize">{agent}</span>
                        <span className="text-gray-500">{count} runs</span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="text-sm text-gray-400 text-center py-8">No agent runs yet</div>
            )}
          </div>
        </div>

        {/* Alert Status */}
        <div className="rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">Alert Status</h2>
          </div>
          <div className="p-6">
            {alertStats && alertStats.total_alerts > 0 ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-red-50 rounded-lg border border-red-100">
                  <div className="flex items-center gap-3">
                    <AlertTriangle className="h-5 w-5 text-red-500" />
                    <div>
                      <p className="text-sm font-medium text-red-700">Firing</p>
                      <p className="text-xs text-red-500">Active alerts requiring attention</p>
                    </div>
                  </div>
                  <span className="text-2xl font-bold text-red-600">{alertStats.firing}</span>
                </div>
                <div className="flex items-center justify-between p-4 bg-green-50 rounded-lg border border-green-200">
                  <div className="flex items-center gap-3">
                    <Shield className="h-5 w-5 text-green-500" />
                    <div>
                      <p className="text-sm font-medium text-green-700">Resolved</p>
                      <p className="text-xs text-green-500">Previously fired, now resolved</p>
                    </div>
                  </div>
                  <span className="text-2xl font-bold text-green-600">{alertStats.resolved}</span>
                </div>
                <div className="text-sm text-gray-500 text-center pt-2">
                  Failure rate: <span className="font-semibold text-gray-700">{failureRate}%</span>
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-400 text-center py-8">
                <Shield className="mx-auto h-8 w-8 mb-2 opacity-50" />
                No alerts received yet
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Alert Feed */}
      <div className="rounded-lg border border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Alert Feed</h2>
          <AlertTriangle className="h-5 w-5 text-gray-400" />
        </div>
        <div className="p-6">
          {loading ? (
            <div className="text-center text-gray-400 py-4">Loading...</div>
          ) : alerts.length === 0 ? (
            <div className="text-sm text-gray-400 text-center py-4">No alerts received</div>
          ) : (
            <div className="space-y-3 max-h-[400px] overflow-y-auto">
              {alerts.map((a) => {
                const meta = a.metadata
                const type = meta.type as string
                const severity = meta.severity as string
                const ts = meta.timestamp as string
                if (type === 'alert') {
                  return (
                    <div key={a.id} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg border border-gray-100">
                      <AlertTriangle className={`h-4 w-4 mt-0.5 ${meta.status === 'firing' ? 'text-red-500' : 'text-green-500'}`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-sm font-medium text-gray-900 truncate">{(meta.alert_names as string[])?.[0] || 'Alert'}</span>
                          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                            meta.status === 'firing' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                          }`}>{meta.status as string}</span>
                          <span className="text-xs text-gray-400 ml-auto">{ts ? new Date(ts).toLocaleTimeString() : ''}</span>
                        </div>
                        <p className="text-xs text-gray-500 line-clamp-2">{a.text}</p>
                      </div>
                    </div>
                  )
                }
                if (type === 'alert_analysis') {
                  const hasRemediation = meta.has_remediation as boolean
                  return (
                    <div key={a.id} className="flex items-start gap-3 p-3 bg-blue-50 rounded-lg border border-blue-100">
                      <Cpu className="h-4 w-4 mt-0.5 text-blue-500" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-sm font-medium text-blue-900 truncate">Analysis: {meta.alert_summary as string}</span>
                          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                            severity === 'critical' ? 'bg-red-100 text-red-700' :
                            severity === 'high' ? 'bg-orange-100 text-orange-700' :
                            severity === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                            'bg-green-100 text-green-700'
                          }`}>{severity}</span>
                          <span className="text-xs text-blue-400 ml-auto" title={`Confidence: ${((meta.confidence as number) * 100).toFixed(0)}%`}>
                            {((meta.confidence as number) * 100).toFixed(0)}%
                          </span>
                        </div>
                        <p className="text-xs text-gray-600">
                          <span className="font-medium">Root Cause:</span> {meta.root_cause as string}
                        </p>
                        <div className="flex items-center gap-3 mt-1">
                          {hasRemediation && (
                            <span className="text-xs text-green-600 flex items-center gap-1">
                              <FileText className="h-3 w-3" /> Remediation available
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                }
                return null
              })}
            </div>
          )}
        </div>
      </div>

      {/* Execution Traces */}
      <div className="rounded-lg border border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Recent Execution Traces</h2>
          <Terminal className="h-5 w-5 text-gray-400" />
        </div>
        <div className="overflow-x-auto">
          {loading ? (
            <div className="px-6 py-8 text-center text-gray-400">Loading...</div>
          ) : traces.length === 0 ? (
            <div className="px-6 py-8 text-center text-gray-400">No execution traces</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-6 py-3 font-medium text-gray-500">Step</th>
                  <th className="text-left px-6 py-3 font-medium text-gray-500">Type</th>
                  <th className="text-left px-6 py-3 font-medium text-gray-500">Status</th>
                  <th className="text-right px-6 py-3 font-medium text-gray-500">Duration</th>
                  <th className="text-right px-6 py-3 font-medium text-gray-500">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {traces.map((t) => (
                  <tr key={t.id} className="hover:bg-gray-50">
                    <td className="px-6 py-3 font-medium text-gray-900">{t.name}</td>
                    <td className="px-6 py-3">
                      <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                        {t.step_type}
                      </span>
                    </td>
                    <td className="px-6 py-3">
                      <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${
                        t.status === 'completed' ? 'bg-green-100 text-green-700' :
                        t.status === 'failed' ? 'bg-red-100 text-red-700' :
                        t.status === 'running' ? 'bg-blue-100 text-blue-700' :
                        'bg-gray-100 text-gray-600'
                      }`}>
                        {t.status}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-right text-gray-500">
                      {t.duration_ms ? `${(t.duration_ms / 1000).toFixed(1)}s` : '—'}
                    </td>
                    <td className="px-6 py-3 text-right text-gray-400">
                      {new Date(t.created_at).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Prometheus Link */}
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart3 className="h-5 w-5 text-gray-400" />
            <div>
              <h2 className="text-sm font-semibold text-gray-900">Prometheus Metrics</h2>
              <p className="text-xs text-gray-500">Raw Prometheus metrics endpoint for external scraping</p>
            </div>
          </div>
          <a
            href="/api/v1/observability/metrics"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:text-blue-700 hover:underline"
          >
            View Metrics →
          </a>
        </div>
      </div>
    </div>
  )
}
