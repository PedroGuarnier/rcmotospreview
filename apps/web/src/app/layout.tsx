import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "RC Motos Digital", template: "%s · RC Motos" },
  description: "Sistema de gestão da RC Motos: estoque, vendas, comissões e painel.",
  robots: { index: false, follow: false }, // sistema interno
};

export const viewport: Viewport = {
  themeColor: "#0A0940",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className="h-full antialiased">
      <body className="min-h-full">{children}</body>
    </html>
  );
}
