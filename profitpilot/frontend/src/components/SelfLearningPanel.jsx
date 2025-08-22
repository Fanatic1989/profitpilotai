// frontend/src/components/SelfLearningPanel.jsx
import React, { useState } from "react";

/**
 * SelfLearningPanel.jsx
 *
 * Basic UI to:
 * - send training batches to backend /train
 * - request a prediction from /predict
 *
 * Note: This demo expects your backend to be running on the same origin or CORS enabled.
 */

export default function SelfLearningPanel() {
  const [featuresText, setFeaturesText] = useState("0.1,0.2,0.3,0.4,0.5,0,0,0");
  const [label, setLabel] = useState("0.5");
  const [predictResult, setPredictResult] = useState(null);
  const [trainStatus, setTrainStatus] = useState(null);
  const [apiToken, setApiToken] = useState("");

  function parseFeatures(text) {
    return text.split(",").map((s) => parseFloat(s.trim())).filter((n)=>!Number.isNaN(n));
  }

  async function callPredict() {
    setPredictResult(null);
    const features = parseFeatures(featuresText);
    try {
      const resp = await fetch("/predict", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: apiToken ? `Bearer ${apiToken}` : ""
        },
        body: JSON.stringify({ features })
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || JSON.stringify(data));
      setPredictResult(data.score);
    } catch (e) {
      setPredictResult("Error: " + e.message);
    }
  }

  async function callTrain() {
    setTrainStatus("training...");
    const features = parseFeatures(featuresText);
    const y = [parseFloat(label)];
    try {
      const resp = await fetch("/train", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: apiToken ? `Bearer ${apiToken}` : ""
        },
        body: JSON.stringify({ X: [features], y })
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || JSON.stringify(data));
      setTrainStatus("Trained: " + (data.samples || 0) + " samples");
    } catch (e) {
      setTrainStatus("Error: " + e.message);
    }
  }

  return (
    <div className="p-6 bg-white shadow rounded">
      <h3 className="text-lg font-semibold mb-3">Self-Learning (demo)</h3>

      <div className="mb-3">
        <label className="block text-sm mb-1">API Token (optional)</label>
        <input value={apiToken} onChange={(e)=>setApiToken(e.target.value)} className="w-full p-2 border rounded" placeholder="Paste Bearer token to call protected endpoints"/>
      </div>

      <div className="mb-3">
        <label className="block text-sm mb-1">Feature vector (comma separated)</label>
        <input value={featuresText} onChange={(e)=>setFeaturesText(e.target.value)} className="w-full p-2 border rounded" />
        <div className="text-xs text-gray-500 mt-1">Ensure length matches model features (default 8)</div>
      </div>

      <div className="mb-3 flex gap-3">
        <div className="flex-1">
          <label className="block text-sm mb-1">Label / target (numeric)</label>
          <input value={label} onChange={(e)=>setLabel(e.target.value)} className="w-full p-2 border rounded" />
        </div>
        <div className="flex-shrink-0 self-end">
          <button onClick={callTrain} className="px-4 py-2 bg-blue-600 text-white rounded">Train</button>
        </div>
      </div>

      <div className="mb-3 flex gap-3">
        <button onClick={callPredict} className="px-4 py-2 border rounded">Predict</button>
        <div className="self-center text-sm">{predictResult !== null ? `Prediction: ${predictResult}` : ""}</div>
      </div>

      <div className="text-sm text-gray-500">{trainStatus}</div>
    </div>
  );
}
