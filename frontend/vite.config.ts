import { defineConfig, loadEnv } from "vite";
import solid from "vite-plugin-solid";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath, URL } from "node:url";

export default defineConfig(({ mode }) => {
  // URL del backend configurable via VITE_API_URL (env var o fichero .env).
  // Por defecto apunta al backend local en desarrollo.
  const env = loadEnv(mode, process.cwd(), "");
  const apiUrl = (
    env.VITE_API_URL ||
    process.env.VITE_API_URL ||
    "http://localhost:8000"
  ).replace(/\/+$/, "");
  const wsUrl = apiUrl.replace(/^http/, "ws");

  return {
    plugins: [tailwindcss(), solid()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    server: {
      host: "0.0.0.0",
      port: 5173,
      proxy: {
        "/api": apiUrl,
        "/ws": {
          target: wsUrl,
          ws: true,
        },
        "/health": apiUrl,
      },
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
      target: "es2020",
      rollupOptions: {
        output: {
          manualChunks: undefined,
        },
      },
    },
  };
});
