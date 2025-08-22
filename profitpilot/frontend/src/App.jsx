import React from 'react'
import { Routes, Route, Link, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import UserDashboard from './pages/UserDashboard'
import AdminDashboard from './pages/AdminDashboard'
import ProtectedRoute from './components/ProtectedRoute'
import { useAuth } from './context/AuthContext'

export default function App() {
  const { user, logout } = useAuth()
  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: 16 }}>
      <nav style={{ display:'flex', gap:12, marginBottom: 16 }}>
        <Link to="/">Home</Link>
        {!user && <Link to="/login">Login</Link>}
        {user && <Link to="/dashboard">Dashboard</Link>}
        {user && <Link to="/admin">Admin</Link>}
        {user && <button onClick={logout}>Logout</button>}
      </nav>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={!user ? <Login/> : <Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<ProtectedRoute><UserDashboard/></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute><AdminDashboard/></ProtectedRoute>} />
        <Route path="*" element={<h3>Not found</h3>} />
      </Routes>
    </div>
  )
}

function Home(){
  return (
    <div>
      <h1>ProfitPilotAI</h1>
      <p>Full-stack trading assistant. Login to continue.</p>
    </div>
  )
}
