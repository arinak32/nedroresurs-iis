import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, token, type User } from './api'

interface AuthState { user: User | null; loading: boolean; login: (l: string, p: string) => Promise<void>; logout: () => void }
const Ctx = createContext<AuthState>(null!)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(!!token.get())

  useEffect(() => {
    if (!token.get()) return
    api.get<User>('/api/auth/me').then(setUser).catch(() => token.clear()).finally(() => setLoading(false))
  }, [])

  const login = async (l: string, p: string) => {
    const r = await api.login(l, p)
    token.set(r.access_token)
    setUser(await api.get<User>('/api/auth/me'))
  }
  const logout = () => { token.clear(); setUser(null) }
  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)
