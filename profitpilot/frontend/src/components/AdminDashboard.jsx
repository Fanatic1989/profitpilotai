import React, { useEffect, useState } from 'react'
import { admin } from '../lib/api'

export default function AdminDashboard() {
  const [users, setUsers] = useState([])
  const [form, setForm] = useState({ login_id:'', password:'', deriv_api_token:'', account_type:'basic' })
  const [editing, setEditing] = useState(null)
  const [updates, setUpdates] = useState({ password:'', preferred_strategy:'', is_active:true })

  const load = async () => setUsers(await admin.listUsers())
  useEffect(() => { load() }, [])

  const create = async (e) => {
    e.preventDefault()
    await admin.createUser(form)
    setForm({ login_id:'', password:'', deriv_api_token:'', account_type:'basic' })
    await load()
  }

  const saveUpdate = async (e) => {
    e.preventDefault()
    await admin.updateUser(editing, updates)
    setEditing(null)
    setUpdates({ password:'', preferred_strategy:'', is_active:true })
    await load()
  }

  return (
    <div>
      <h2>Admin Dashboard</h2>

      <section style={{ marginBottom: 24 }}>
        <h3>Create User</h3>
        <form onSubmit={create} style={{ display:'grid', gap:8, maxWidth: 420 }}>
          <input placeholder="login_id" value={form.login_id} onChange={e=>setForm({...form, login_id:e.target.value})} required />
          <input placeholder="password" value={form.password} onChange={e=>setForm({...form, password:e.target.value})} required />
          <input placeholder="deriv_api_token (optional)" value={form.deriv_api_token} onChange={e=>setForm({...form, deriv_api_token:e.target.value})} />
          <select value={form.account_type} onChange={e=>setForm({...form, account_type:e.target.value})}>
            <option value="basic">basic</option>
            <option value="demo">demo</option>
            <option value="real">real</option>
          </select>
          <button type="submit">Create</button>
        </form>
      </section>

      <section>
        <h3>Users</h3>
        <table border="1" cellPadding="6" style={{ borderCollapse:'collapse', minWidth: 600 }}>
          <thead>
            <tr><th>login_id</th><th>strategy</th><th>active</th><th>created</th><th>actions</th></tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id}>
                <td>{u.login_id}</td>
                <td>{u.preferred_strategy}</td>
                <td>{String(u.is_active)}</td>
                <td>{new Date(u.created_at).toLocaleString()}</td>
                <td>
                  <button onClick={() => { setEditing(u.login_id); setUpdates({ password:'', preferred_strategy:u.preferred_strategy || '', is_active:u.is_active }) }}>Edit</button>
                  <button onClick={async ()=>{ await admin.deleteUser(u.login_id); await load() }}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {editing && (
        <section style={{ marginTop: 24 }}>
          <h3>Edit: {editing}</h3>
          <form onSubmit={saveUpdate} style={{ display:'grid', gap:8, maxWidth: 420 }}>
            <input placeholder="new password (optional)" value={updates.password} onChange={e=>setUpdates({...updates, password:e.target.value})}/>
            <input placeholder="preferred_strategy" value={updates.preferred_strategy} onChange={e=>setUpdates({...updates, preferred_strategy:e.target.value})}/>
            <label style={{ display:'flex', gap:8, alignItems:'center' }}>
              <input type="checkbox" checked={updates.is_active} onChange={e=>setUpdates({...updates, is_active:e.target.checked})}/>
              Active
            </label>
            <button type="submit">Save</button>
            <button type="button" onClick={()=>setEditing(null)}>Cancel</button>
          </form>
        </section>
      )}
    </div>
  )
}
