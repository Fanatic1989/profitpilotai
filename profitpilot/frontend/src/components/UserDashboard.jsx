import React, { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { userApi } from '../lib/api'
import BotControls from '../components/BotControls'
import PairMultiSelect from '../components/PairMultiSelect'

export default function UserDashboard() {
  const { user } = useAuth()
  const [pairs, setPairs] = useState([])
  const [selected, setSelected] = useState([])
  const [strategy, setStrategy] = useState('scalping')
  const [tradingType, setTradingType] = useState('forex')
  const [mode, setMode] = useState('demo')
  const [derivToken, setDerivToken] = useState('')
  const [status, setStatus] = useState('inactive')

  useEffect(() => {
    userApi.getPairs().then(setPairs)
  }, [])

  // WebSocket live status
  useEffect(() => {
    if (!user?.login_id) return
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${proto}://${location.host.replace(':5173', ':8000')}/ws/${user.login_id}`
    const ws = new WebSocket(url)
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'status') setStatus(msg.status)
      } catch {}
    }
    return () => ws.close()
  }, [user?.login_id])

  const save = async () => {
    await userApi.saveSettings({
      deriv_api_token: derivToken,
      account_mode: mode,
      strategy,
      trading_type: tradingType,
      selected_pairs: selected
    })
    alert('Settings saved')
  }

  return (
    <div>
      <h2>User Dashboard</h2>
      <section style={{ display:'grid', gap:12, maxWidth: 520 }}>
        <label>Deriv API Token
          <input value={derivToken} onChange={e => setDerivToken(e.target.value)} placeholder="Paste your Deriv token"/>
        </label>

        <label>Account Mode
          <select value={mode} onChange={e => setMode(e.target.value)}>
            <option value="demo">Demo</option>
            <option value="real">Real</option>
          </select>
        </label>

        <label>Strategy
          <select value={strategy} onChange={e => setStrategy(e.target.value)}>
            <option value="scalping">Scalping</option>
            <option value="day trading">Day Trading</option>
            <option value="swing trading">Swing Trading</option>
          </select>
        </label>

        <label>Trading Type
          <select value={tradingType} onChange={e => setTradingType(e.target.value)}>
            <option value="forex">Forex</option>
            <option value="binary">Binary Options</option>
          </select>
        </label>

        <div>
          <div style={{ marginBottom: 6 }}>Select Pairs</div>
          <PairMultiSelect pairs={pairs} selected={selected} setSelected={setSelected}/>
        </div>

        <div style={{ display:'flex', gap:8 }}>
          <button onClick={save}>Save Settings</button>
        </div>
      </section>

      <BotControls
        status={status}
        onStart={async () => { const r = await userApi.botStart(); setStatus(r.status) }}
        onPause={async () => { const r = await userApi.botPause(); setStatus(r.status) }}
        onStop={async () => { const r = await userApi.botStop(); setStatus(r.status) }}
      />
    </div>
  )
}
