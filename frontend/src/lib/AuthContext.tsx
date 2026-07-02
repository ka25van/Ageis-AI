import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { authApi, clearTokens, setTokens as storeTokens, isAuthenticated } from './api'
import type { UserInfo } from './api'

interface AuthState {
  user: UserInfo | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, full_name?: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchUser = useCallback(async () => {
    if (!isAuthenticated()) {
      setLoading(false)
      return
    }
    try {
      const u = await authApi.me()
      setUser(u)
    } catch {
      clearTokens()
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchUser() }, [fetchUser])

  const login = useCallback(async (email: string, password: string) => {
    const res = await authApi.login(email, password)
    storeTokens(res.access_token, res.refresh_token)
    setUser(res.user)
  }, [])

  const register = useCallback(async (email: string, password: string, full_name?: string) => {
    const res = await authApi.register(email, password, full_name)
    storeTokens(res.access_token, res.refresh_token)
    setUser(res.user)
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
