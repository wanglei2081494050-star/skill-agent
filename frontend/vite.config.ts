import { defineConfig } from "vite";

const API = process.env.API_ORIGIN ?? "http://127.0.0.1:8787";

export default defineConfig({
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: API, changeOrigin: true },
      "/health": { target: API, changeOrigin: true },
    },
  },
});
