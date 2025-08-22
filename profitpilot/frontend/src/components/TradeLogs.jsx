// frontend/src/components/TradeLogs.jsx
import React, { useEffect, useState } from "react";

/**
 * TradeLogs.jsx
 * Shows a simple list of orders stored in browser localStorage / or fetched from backend.
 * This demo will use localStorage and provide buttons to fetch sample logs.
 *
 * Replace the fetchLocalOrders function to call your backend (e.g., /api/orders).
 */

const LS_ORDERS_KEY = "profitpilot_orders_v1";

function sampleOrder() {
  return {
    order_id: `sim-${Math.random().toString(36).slice(2, 10)}`,
    symbol: "BTCUSD",
    action: Math.random() > 0.5 ? "buy" : "sell",
    usd_size: Math.round(Math.random() * 500 + 10),
    status: "filled",
    filled_at: Date.now() - Math.round(Math.random() * 1000 * 60 * 60)
  };
}

export default function TradeLogs() {
  const [orders, setOrders] = useState([]);

  useEffect(() => {
    loadLocal();
  }, []);

  function loadLocal() {
    try {
      const raw = localStorage.getItem(LS_ORDERS_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      setOrders(parsed);
    } catch (e) {
      setOrders([]);
    }
  }

  function addSample() {
    const arr = JSON.parse(localStorage.getItem(LS_ORDERS_KEY) || "[]");
    arr.unshift(sampleOrder());
    localStorage.setItem(LS_ORDERS_KEY, JSON.stringify(arr.slice(0, 200)));
    loadLocal();
  }

  function clearLogs() {
    localStorage.removeItem(LS_ORDERS_KEY);
    loadLocal();
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-xl font-semibold">Trade Logs</h3>
        <div className="flex gap-2">
          <button onClick={addSample} className="px-3 py-1 rounded bg-green-600 text-white">Add Sample</button>
          <button onClick={clearLogs} className="px-3 py-1 rounded border">Clear</button>
        </div>
      </div>

      <div className="bg-white shadow rounded">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b">
              <th className="p-3">Order ID</th>
              <th className="p-3">Symbol</th>
              <th className="p-3">Action</th>
              <th className="p-3">USD Size</th>
              <th className="p-3">Status</th>
              <th className="p-3">Time</th>
            </tr>
          </thead>
          <tbody>
            {orders.length === 0 ? (
              <tr>
                <td colSpan="6" className="p-4 text-center text-gray-500">No orders yet — add a sample to test.</td>
              </tr>
            ) : (
              orders.map((o) => (
                <tr key={o.order_id} className="border-b hover:bg-gray-50">
                  <td className="p-3 font-mono text-sm">{o.order_id}</td>
                  <td className="p-3">{o.symbol}</td>
                  <td className="p-3">{o.action}</td>
                  <td className="p-3">{o.usd_size}</td>
                  <td className="p-3">{o.status}</td>
                  <td className="p-3">{new Date(o.filled_at).toLocaleString()}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
