import { useEffect, useState } from 'react'
import { CheckCircle, XCircle, Clock, Loader2 } from 'lucide-react'
import { approvalsApi, plannerApi } from '../lib/api'

interface ApprovalItem {
  id: string
  run_id: string
  action_type: string
  action_data: Record<string, unknown>
  status: string
  created_at: string
}

export function ApprovalQueue() {
  const [approvals, setApprovals] = useState<ApprovalItem[]>([])
  const [loading, setLoading] = useState(true)
  const [actionId, setActionId] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [rejectingId, setRejectingId] = useState<string | null>(null)
  const [execResult, setExecResult] = useState<{ run_id: string; response: string } | null>(null)

  async function load() {
    try {
      const data = await approvalsApi.listPending()
      setApprovals(data.approvals as unknown as ApprovalItem[])
    } catch { /* empty */ }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  async function handleApprove(item: ApprovalItem) {
    setActionId(item.id)
    setExecResult(null)
    try {
      await approvalsApi.approve(item.id)
      // Execute the approved action
      const result = await plannerApi.resume(item.run_id)
      setExecResult({ run_id: item.run_id, response: result.response })
      await load()
    } catch { /* empty */ }
    finally { setActionId(null) }
  }

  async function handleReject(id: string) {
    setActionId(id)
    try {
      await approvalsApi.reject(id, rejectReason || undefined)
      setRejectingId(null)
      setRejectReason('')
      await load()
    } catch { /* empty */ }
    finally { setActionId(null) }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Approval Queue</h1>
        <p className="text-gray-500">Review and approve agent actions before execution</p>
      </div>

      {loading ? (
        <div className="text-center text-gray-400 py-12">Loading...</div>
      ) : approvals.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-12 text-center">
          <CheckCircle className="h-12 w-12 text-green-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-1">All Clear</h3>
          <p className="text-sm text-gray-500">No pending approvals required</p>
        </div>
      ) : (
        <div className="space-y-3">
          {approvals.map(a => (
            <div key={a.id} className="rounded-lg border border-gray-200 bg-white p-5">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <Clock className="h-5 w-5 text-amber-500" />
                  <div>
                    <p className="font-medium text-gray-900">{a.action_type}</p>
                    <p className="text-xs text-gray-400">Requested {new Date(a.created_at).toLocaleString()}</p>
                  </div>
                </div>
                <span className="px-2 py-1 text-xs font-medium bg-amber-100 text-amber-700 rounded-full">Pending</span>
              </div>
              {a.action_data && Object.keys(a.action_data).length > 0 && (
                <div className="mb-4 bg-gray-50 rounded p-3 max-h-48 overflow-auto">
                  <pre className="text-xs text-gray-600 whitespace-pre-wrap">{JSON.stringify(a.action_data, null, 2)}</pre>
                </div>
              )}
              <div className="flex items-center gap-3">
                <button
                  onClick={() => handleApprove(a)}
                  disabled={actionId === a.id}
                  className="flex items-center gap-1.5 px-4 py-2 bg-green-600 text-white text-sm rounded-md hover:bg-green-700 disabled:opacity-50"
                >
                  {actionId === a.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle className="h-4 w-4" />}
                  Approve & Execute
                </button>
                <button
                  onClick={() => setRejectingId(rejectingId === a.id ? null : a.id)}
                  className="flex items-center gap-1.5 px-4 py-2 bg-red-100 text-red-700 text-sm rounded-md hover:bg-red-200"
                >
                  <XCircle className="h-4 w-4" />
                  Reject
                </button>
              </div>
              {rejectingId === a.id && (
                <div className="mt-3 flex items-center gap-2">
                  <input
                    type="text"
                    value={rejectReason}
                    onChange={e => setRejectReason(e.target.value)}
                    placeholder="Reason for rejection (optional)"
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm"
                  />
                  <button
                    onClick={() => handleReject(a.id)}
                    disabled={actionId === a.id}
                    className="px-3 py-2 bg-red-600 text-white text-sm rounded-md hover:bg-red-700 disabled:opacity-50"
                  >
                    Confirm
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {execResult && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-5">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="h-5 w-5 text-green-600" />
            <h3 className="font-medium text-green-800">Action Executed</h3>
          </div>
          <p className="text-sm text-gray-700 whitespace-pre-wrap">{execResult.response.slice(0, 2000)}</p>
          <p className="text-xs text-gray-400 mt-2">Run ID: {execResult.run_id}</p>
        </div>
      )}
    </div>
  )
}
