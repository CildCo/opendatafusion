import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version || "dev"),
  },
  base: "/ui/",
  build: {
    outDir: "../impl/odf/static",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (id.includes("echarts")) return "vendor-echarts";
          if (id.includes("@vue-flow")) return "vendor-vueflow";
          if (id.includes("codemirror")) return "vendor-codemirror";
          if (id.includes("element-plus")) return "vendor-element";
          if (id.includes("vue-router") || id.includes("/vue/")
              || id.includes("@vue/")) {
            return "vendor-vue";
          }
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
