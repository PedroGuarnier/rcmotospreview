import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Gera .next/standalone: imagem Docker pequena, sem node_modules inteiro.
  output: "standalone",
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
