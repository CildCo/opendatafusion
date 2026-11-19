import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  base: "/ui/",
  build: {
    outDir: "../impl/odf/static",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-vue": ["vue", "vue-router"],
          "vendor-element": ["element-plus", "@element-plus/icons-vue"],
          "vendor-echarts": ["echarts"],
          "vendor-vueflow": [
            "@vue-flow/core", "@vue-flow/background",
            "@vue-flow/controls", "@vue-flow/minimap",
          ],
          "vendor-codemirror": ["codemirror", "@codemirror/lang-sql"],
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:18080",
    },
  },
});
