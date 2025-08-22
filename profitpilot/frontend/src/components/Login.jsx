import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { auth } from '../lib/api'

export default function Login() {
  const [login_id, setLoginId] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await auth.login(login_id, password)
      navigate('/dashboard')
    } catch (err) {
      setError(err?.response?.data?.detail || 'Login failed')
    }
  }

  return (
    <div style={{ maxWidth: 420 }}>
      <h2>Login</h2>
      {error && <p style={{ color:'red' }}>{error}</p>}
      <form onSubmit={submit} style={{ display:'grid', gap:12 }}>
        <label>Login ID
          <input value={login_id} onChange={e => setLoginId(e.target.value)} required />
        </label>
        <label>Password
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} required />
        </label>
        <button type="submit">Sign in</button>
      </form>
    </div>
  )
}
