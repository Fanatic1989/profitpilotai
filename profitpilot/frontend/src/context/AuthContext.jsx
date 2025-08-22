import React, { createContext, useContext, useEffect, useState } from 'react'
import { auth } from '../lib/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const logout = () => { auth.logout(); setUser(null) }

  useEffect(() => {
    const token = localStorage.getItem('pp_token')
    if (!token) { setLoading(false); return }
    auth.me().then(u => setUser(u)).catch(() => logout()).finally(() => setLoading(false))
  }, [])

  const value = { user, setUser, logout, loading }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
