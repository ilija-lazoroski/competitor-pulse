import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the API runs on its own port; the dev server forwards /api to it, like nginx
// does in Docker, so the app always calls its own origin.
const apiUrl = process.env.CP_FRONTEND_API_URL ?? "http://localhost:8080";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": apiUrl },
  },
  test: {
    environment: "node",
    passWithNoTests: true,
  },
});
