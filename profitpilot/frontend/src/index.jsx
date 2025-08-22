// frontend/src/index.jsx
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css"; // make sure you have this file; Vite + Tailwind setup expected

const container = document.getElementById("root");
const root = createRoot(container);
root.render(<App />);
