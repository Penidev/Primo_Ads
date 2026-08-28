import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    // Keep the runner away from build output and dependencies, which contain
    // their own test files and would otherwise be collected.
    exclude: ["node_modules/**", ".next/**", "e2e/**"],
  },
  resolve: {
    // Mirrors the `@/*` path alias from tsconfig.json.
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
