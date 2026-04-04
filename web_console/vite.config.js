import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  base: "/static/",
  build: {
    outDir: path.resolve(__dirname, "../web_ui/static"),
    emptyOutDir: true,
  },
});
