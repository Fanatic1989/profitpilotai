import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/trade": "http://localhost:8000",
      "/train": "http://localhost:8000",
      "/predict": "http://localhost:8000",
      "/orders": "http://localhost:8000",
      "/portfolio": "http://localhost:8000",
      "/strategies": "http://localhost:8000"
    }
  }
});
