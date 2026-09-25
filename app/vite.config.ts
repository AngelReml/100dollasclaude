import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The build goes into the Python package so Iván's PC never needs npm:
// the bridge serves it at http://127.0.0.1:20130/app/
export default defineConfig({
  base: "/app/",
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../src/webllm_agent/static/app",
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
  },
  server: { proxy: { "/api": "http://127.0.0.1:20130" } },
});
