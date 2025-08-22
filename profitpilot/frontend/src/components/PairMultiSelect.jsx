import React from 'react'

export default function PairMultiSelect({ pairs, selected, setSelected }) {
  const toggle = (symbol) => {
    setSelected(prev => prev.includes(symbol) ? prev.filter(s => s !== symbol) : [...prev, symbol])
  }
  return (
    <div style={{ border:'1px solid #ddd', padding: 8, borderRadius: 6, maxHeight: 180, overflowY:'auto' }}>
      {pairs.map(p => (
        <label key={p.symbol} style={{ display:'flex', gap:8, alignItems:'center' }}>
          <input
            type="checkbox"
            checked={selected.includes(p.symbol)}
            onChange={() => toggle(p.symbol)}
          />
          <span>{p.display_name} <small style={{opacity:.6}}>({p.symbol})</small></span>
        </label>
      ))}
    </div>
  )
}
