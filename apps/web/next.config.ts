import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Gera .next/standalone: imagem Docker pequena, sem node_modules inteiro.
  output: "standalone",
  // Fontes (.woff: o gerador de imagem não lê woff2) e logo das imagens de compartilhamento.
  outputFileTracingIncludes: {
    "/og/**": [
      "./node_modules/@fontsource/anton/files/anton-latin-400-normal.woff",
      "./node_modules/@fontsource/b612/files/b612-latin-700-normal.woff",
      "./public/logo.png",
    ],
  },
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
