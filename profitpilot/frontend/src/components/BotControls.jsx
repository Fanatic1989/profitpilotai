import React from 'react'

export default function BotControls({ onStart, onPause, onStop, status }) {
  return (
    <div style={{ display:'flex', gap:12, alignItems:'center', marginTop: 8 }}>
      <button onClick={onStart}>Start</button>
      <button onClick={onPause}>Pause</button>
      <button onClick={onStop}>Stop</button>
      <span>Status: <strong>{status || 'inactive'}</strong></span>
    </div>
  )
}
