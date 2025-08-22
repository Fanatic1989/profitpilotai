// frontend/src/components/Settings.jsx
import React, { useState, useEffect } from "react";

/**
 * Settings.jsx
 * Simple Settings UI for ProfitPilotAI.
 * - Manage API keys (stored client-side only for demo) -- Replace with secure vault in prod
 * - Toggle dry-run / live mode
 * - Set account size (demo)
 *
 * This component uses localStorage to persist basic settings for quick testing.
 */

const LS_KEY = "profitpilot_settings_v1";

export default function Settings() {
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [accountSize, setAccountSize] = useState(10000);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        setApiKey(parsed.apiKey || "");
        setApiSecret(parsed.apiSecret || "");
        setDryRun(parsed.dryRun !== undefined ? parsed.dryRun : true);
        setAccountSize(parsed.accountSize || 10000);
      }
    } catch (e) {
      console.warn("Failed to load settings", e);
    }
  }, []);

  function persist() {
    const payload = { apiKey, apiSecret, dryRun, accountSize };
    localStorage.setItem(LS_KEY, JSON.stringify(payload));
    alert("Settings saved locally (demo). In production store securely on backend.");
  }

  function clearSettings() {
    localStorage.removeItem(LS_KEY);
    setApiKey("");
    setApiSecret("");
    setDryRun(true);
    setAccountSize(10000);
    alert("Settings cleared.");
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h2 className="text-2xl font-semibold mb-4">App Settings</h2>

      <div className="mb-4">
        <label className="block mb-1">API Key (demo)</label>
        <input
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          className="w-full p-2 border rounded"
          placeholder="Enter API Key..."
        />
      </div>

      <div className="mb-4">
        <label className="block mb-1">API Secret (demo)</label>
        <input
          value={apiSecret}
          onChange={(e) => setApiSecret(e.target.value)}
          className="w-full p-2 border rounded"
          placeholder="Enter API Secret..."
          type="password"
        />
      </div>

      <div className="mb-4 flex items-center space-x-3">
        <label>Dry-run mode</label>
        <input
          type="checkbox"
          checked={dryRun}
          onChange={(e) => setDryRun(e.target.checked)}
        />
        <span className="text-sm text-gray-500">When checked, trades will be simulated only.</span>
      </div>

      <div className="mb-6">
        <label className="block mb-1">Account Size (USD)</label>
        <input
          type="number"
          value={accountSize}
          onChange={(e) => setAccountSize(Number(e.target.value))}
          className="w-full p-2 border rounded"
          min="0"
        />
      </div>

      <div className="flex gap-3">
        <button onClick={persist} className="px-4 py-2 rounded shadow bg-blue-600 text-white">
          Save Settings
        </button>
        <button onClick={clearSettings} className="px-4 py-2 rounded border">
          Clear
        </button>
      </div>

      <p className="mt-6 text-sm text-gray-500">
        Note: This demo keeps API credentials in localStorage for quick dev testing only.
        Never store production API secrets in localStorage — use a secure backend vault.
      </p>
    </div>
  );
}
