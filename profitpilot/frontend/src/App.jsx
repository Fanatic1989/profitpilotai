// frontend/src/App.jsx
import React from "react";
import Settings from "./components/Settings";
import TradeLogs from "./components/TradeLogs";
import SelfLearningPanel from "./components/SelfLearningPanel";

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow p-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <h1 className="text-xl font-bold">ProfitPilotAI — Demo</h1>
          <div className="text-sm text-gray-500">Demo local mode</div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto py-8 space-y-8">
        <Settings />
        <SelfLearningPanel />
        <TradeLogs />
      </main>
    </div>
  );
}
