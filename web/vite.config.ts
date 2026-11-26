import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // In development the page comes from Vite and the socket from the Python server.
  server: { proxy: { "/ws": { target: "ws://localhost:8000", ws: true } } },
});
