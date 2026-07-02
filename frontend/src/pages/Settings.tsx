import { useState, useEffect } from 'react'
import { User, Shield, Key, Copy, Check, Eye, EyeOff, Plus, Trash2 } from 'lucide-react'
import { useAuth } from '../lib/AuthContext'
import { authApi } from '../lib/api'
import type { ApiKey } from '../lib/api'

type Section = 'profile' | 'security' | 'api-keys' | null

export function Settings() {
  const { user } = useAuth()
  const [activeSection, setActiveSection] = useState<Section>(null)
  const [fullName, setFullName] = useState(user?.full_name || '')
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  // Password
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [changingPw, setChangingPw] = useState(false)

  // API Keys
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([])
  const [loadingKeys, setLoadingKeys] = useState(false)
  const [keyName, setKeyName] = useState('')
  const [createdKey, setCreatedKey] = useState<string | null>(null)
  const [creatingKey, setCreatingKey] = useState(false)

  useEffect(() => { setFullName(user?.full_name || '') }, [user])

  async function handleSaveProfile() {
    setSaving(true)
    setMsg('')
    try {
      await authApi.updateProfile(fullName)
      setMsg('Profile updated')
    } catch { setMsg('Failed to update profile') }
    finally { setSaving(false) }
  }

  async function handleChangePassword() {
    if (!currentPw || !newPw) return
    setChangingPw(true)
    setMsg('')
    try {
      await authApi.changePassword(currentPw, newPw)
      setMsg('Password changed')
      setCurrentPw('')
      setNewPw('')
    } catch { setMsg('Failed to change password') }
    finally { setChangingPw(false) }
  }

  async function loadKeys() {
    setLoadingKeys(true)
    try {
      const keys = await authApi.listApiKeys()
      setApiKeys(keys)
    } catch { /* empty */ }
    finally { setLoadingKeys(false) }
  }

  useEffect(() => {
    if (activeSection === 'api-keys') loadKeys()
  }, [activeSection])

  async function handleCreateKey() {
    if (!keyName) return
    setCreatingKey(true)
    setCreatedKey(null)
    try {
      const res = await authApi.createApiKey(keyName)
      setCreatedKey(res.key)
      setKeyName('')
      await loadKeys()
    } catch { setMsg('Failed to create key') }
    finally { setCreatingKey(false) }
  }

  async function handleDeleteKey(id: string) {
    if (!confirm('Delete this API key?')) return
    try {
      await authApi.deleteApiKey(id)
      await loadKeys()
    } catch { setMsg('Failed to delete key') }
  }

  const sections = [
    { id: 'profile' as const, name: 'Profile', icon: User, desc: 'Manage your personal information' },
    { id: 'security' as const, name: 'Security', icon: Shield, desc: 'Password and authentication settings' },
    { id: 'api-keys' as const, name: 'API Keys', icon: Key, desc: 'Manage API access tokens' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500">Manage your workspace settings</p>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <div className="flex items-center gap-4">
          <div className="h-16 w-16 rounded-full bg-blue-100 flex items-center justify-center">
            <span className="text-2xl font-bold text-blue-600">
              {(user?.full_name || user?.email || '?')[0].toUpperCase()}
            </span>
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900">{user?.full_name || 'User'}</h2>
            <p className="text-sm text-gray-500">{user?.email}</p>
          </div>
        </div>
      </div>

      {msg && (
        <div className="p-3 text-sm text-green-700 bg-green-50 rounded-lg border border-green-200">{msg}</div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        {sections.map(s => (
          <button
            key={s.id}
            onClick={() => setActiveSection(activeSection === s.id ? null : s.id)}
            className={`rounded-lg border p-5 text-left hover:shadow-sm transition-shadow ${
              activeSection === s.id ? 'border-blue-300 bg-blue-50' : 'border-gray-200 bg-white'
            }`}
          >
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${activeSection === s.id ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-600'}`}>
                <s.icon className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">{s.name}</h3>
                <p className="text-sm text-gray-500">{s.desc}</p>
              </div>
            </div>
          </button>
        ))}
      </div>

      {activeSection === 'profile' && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 space-y-4">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <User className="h-4 w-4" /> Edit Profile
          </h3>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Full name</label>
            <input type="text" value={fullName} onChange={e => setFullName(e.target.value)}
              className="w-full max-w-md px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input type="email" value={user?.email || ''} disabled
              className="w-full max-w-md px-3 py-2 border border-gray-300 rounded-md text-sm bg-gray-50 text-gray-500 cursor-not-allowed" />
          </div>
          <button onClick={handleSaveProfile} disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      )}

      {activeSection === 'security' && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 space-y-4">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <Shield className="h-4 w-4" /> Change Password
          </h3>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Current password</label>
            <div className="relative max-w-md">
              <input type={showPw ? 'text' : 'password'} value={currentPw}
                onChange={e => setCurrentPw(e.target.value)}
                className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <button onClick={() => setShowPw(!showPw)} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">New password</label>
            <input type={showPw ? 'text' : 'password'} value={newPw}
              onChange={e => setNewPw(e.target.value)}
              className="w-full max-w-md px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <button onClick={handleChangePassword} disabled={!currentPw || !newPw || changingPw}
            className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {changingPw ? 'Changing...' : 'Change Password'}
          </button>
        </div>
      )}

      {activeSection === 'api-keys' && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 space-y-4">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <Key className="h-4 w-4" /> API Keys
          </h3>

          {createdKey && (
            <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg space-y-2">
              <p className="text-sm font-medium text-yellow-800">Key created — copy it now, it won't be shown again:</p>
              <div className="flex gap-2">
                <code className="flex-1 px-3 py-2 bg-white border border-yellow-300 rounded text-sm font-mono break-all">{createdKey}</code>
                <button onClick={() => { navigator.clipboard.writeText(createdKey); setMsg('Copied!') }}
                  className="p-2 text-gray-500 hover:text-gray-700">
                  <Copy className="h-4 w-4" />
                </button>
              </div>
              <button onClick={() => setCreatedKey(null)}
                className="text-sm text-yellow-700 hover:underline">
                <Check className="h-3.5 w-3.5 inline mr-1" />Done
              </button>
            </div>
          )}

          <div className="flex gap-3 max-w-md">
            <input type="text" value={keyName} onChange={e => setKeyName(e.target.value)}
              placeholder="Key name (e.g. CI/CD)"
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            <button onClick={handleCreateKey} disabled={!keyName || creatingKey}
              className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
              <Plus className="h-4 w-4" /> Create
            </button>
          </div>

          {loadingKeys ? (
            <div className="text-sm text-gray-400">Loading...</div>
          ) : apiKeys.length === 0 ? (
            <div className="text-sm text-gray-400">No API keys yet</div>
          ) : (
            <div className="space-y-2">
              {apiKeys.map(k => (
                <div key={k.id} className="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{k.name}</p>
                    <p className="text-xs text-gray-500 font-mono">{k.key_prefix}...</p>
                  </div>
                  <button onClick={() => handleDeleteKey(k.id)}
                    className="p-1.5 text-gray-400 hover:text-red-600 rounded">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
