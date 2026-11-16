import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// `npm run dev` serves on :5173 and proxies the API to the FastAPI app on :8000 (python -m ferrero.web).
// `npm run build` writes into the Python package, where FastAPI serves it at /.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { outDir: "../src/ferrero/web/dist", emptyOutDir: true, chunkSizeWarningLimit: 900 },
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
});
