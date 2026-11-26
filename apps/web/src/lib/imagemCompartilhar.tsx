/**
 * Imagens da prévia ao compartilhar um link do site (WhatsApp, Facebook, X), 1200×630, geradas
 * com `ImageResponse` (next/og): navy, amarelo, as barras de velocidade da logo e Anton nos títulos.
 * Só no servidor: lê as fontes e a logo do disco (incluídas no build por `outputFileTracingIncludes`).
 */
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";
import { anoVeiculo, precoVeiculo } from "@/components/site/anuncio";
import { numero } from "@/lib/formato";
import type { VeiculoPublico } from "@/lib/tipos";

export const TAMANHO = { width: 1200, height: 630 };

const NAVY = "#0A0940";
const AMARELO = "#ECD02F";
const NEVOA = "#B9BCE0";

let recursos: Promise<{ anton: Buffer; b612: Buffer; logo: string }> | null = null;

function carregarRecursos() {
  // Satori não lê woff2: as fontes do site vêm nos arquivos .woff dos mesmos pacotes.
  // Caminhos literais, para o build saber exatamente quais arquivos levar.
  recursos ??= Promise.all([
    readFile(join(process.cwd(), "node_modules/@fontsource/anton/files/anton-latin-400-normal.woff")),
    readFile(join(process.cwd(), "node_modules/@fontsource/b612/files/b612-latin-700-normal.woff")),
    readFile(join(process.cwd(), "public/logo.png")),
  ]).then(([anton, b612, logo]) => ({
    anton,
    b612,
    logo: `data:image/png;base64,${logo.toString("base64")}`,
  }));
  return recursos;
}

/** As três barras de velocidade do "R" da logo, cada uma mais curta que a de cima. */
function Barras({ escala = 1 }: { escala?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 * escala }}>
      {[260, 180, 100].map((largura) => (
        <div
          key={largura}
          style={{ width: largura * escala, height: 16 * escala, borderRadius: 99, background: AMARELO }}
        />
      ))}
    </div>
  );
}

async function desenhar(conteudo: React.ReactElement, cache: string): Promise<Response> {
  const { anton, b612 } = await carregarRecursos();
  return new ImageResponse(conteudo, {
    ...TAMANHO,
    fonts: [
      { name: "Anton", data: anton, weight: 400, style: "normal" },
      { name: "B612", data: b612, weight: 700, style: "normal" },
    ],
    headers: { "cache-control": cache },
  });
}

/** Página inicial: a logo, a marca e "Motos e carros seminovos · cidade". */
export async function imagemInicio(cidade: string | null): Promise<Response> {
  const { logo } = await carregarRecursos();
  const onde = cidade ?? "Piauí";
  return desenhar(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        gap: 56,
        padding: "0 80px",
        background: NAVY,
        color: "#fff",
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- desenho do ImageResponse, não é página */}
      <img src={logo} width={270} height={270} alt="" style={{ borderRadius: 999 }} />
      <div style={{ display: "flex", flexDirection: "column", gap: 28, flex: 1 }}>
        <Barras />
        <div style={{ display: "flex", fontFamily: "Anton", fontSize: 150, lineHeight: 1, color: AMARELO }}>
          RC MOTOS
        </div>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            rowGap: 8,
            fontFamily: "B612",
            fontSize: 30,
            letterSpacing: 2,
            textTransform: "uppercase",
            color: "#fff",
          }}
        >
          <span>Motos e carros seminovos</span>
          {/* o ponto anda junto com a cidade: se quebrar a linha, não sobra no fim */}
          <span style={{ display: "flex" }}>
            <span style={{ color: AMARELO, padding: "0 14px" }}>·</span>
            <span>{onde}</span>
          </span>
        </div>
      </div>
    </div>,
    "public, max-age=3600",
  );
}

/** Veículo sem foto: nome, ano, km e preço num pôster da marca. */
export async function imagemVeiculo(
  veiculo: VeiculoPublico,
  { cidade, ilustrativo }: { cidade: string | null; ilustrativo: boolean },
): Promise<Response> {
  const { logo } = await carregarRecursos();
  const ficha = [anoVeiculo(veiculo), veiculo.km !== null ? `${numero(veiculo.km)} km` : null, veiculo.cor]
    .filter(Boolean)
    .join("  ·  ");
  const letras = veiculo.modelo.length;
  const tamanhoModelo = letras <= 10 ? 150 : letras <= 16 ? 116 : letras <= 24 ? 88 : 68;
  return desenhar(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "56px 72px 60px",
        background: NAVY,
        color: "#fff",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
          {/* eslint-disable-next-line @next/next/no-img-element -- desenho do ImageResponse, não é página */}
          <img src={logo} width={92} height={92} alt="" style={{ borderRadius: 999 }} />
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", fontFamily: "Anton", fontSize: 48, lineHeight: 1, color: AMARELO }}>
              RC MOTOS
            </div>
            <div
              style={{
                display: "flex",
                marginTop: 8,
                fontFamily: "B612",
                fontSize: 20,
                letterSpacing: 2,
                textTransform: "uppercase",
                color: NEVOA,
              }}
            >
              {cidade ? `Seminovos · ${cidade}, PI` : "Motos e carros seminovos"}
            </div>
          </div>
        </div>
        <Barras escala={0.7} />
      </div>

      <div style={{ display: "flex", flexDirection: "column" }}>
        <div
          style={{
            display: "flex",
            fontFamily: "B612",
            fontSize: 34,
            letterSpacing: 3,
            textTransform: "uppercase",
            color: AMARELO,
          }}
        >
          {veiculo.marca}
        </div>
        <div
          style={{
            display: "flex",
            marginTop: 6,
            fontFamily: "Anton",
            fontSize: tamanhoModelo,
            lineHeight: 1.08,
            textTransform: "uppercase",
            color: "#fff",
          }}
        >
          {veiculo.modelo}
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 40 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {ficha && (
            <div
              style={{
                display: "flex",
                fontFamily: "B612",
                fontSize: 36,
                letterSpacing: 2,
                textTransform: "uppercase",
                color: "#fff",
              }}
            >
              {ficha}
            </div>
          )}
          {ilustrativo && (
            <div
              style={{
                display: "flex",
                fontFamily: "B612",
                fontSize: 22,
                letterSpacing: 2,
                textTransform: "uppercase",
                color: NEVOA,
              }}
            >
              Demonstração · dados ilustrativos
            </div>
          )}
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: 12,
            padding: "14px 30px 10px",
            borderRadius: 14,
            background: AMARELO,
            color: NAVY,
            fontFamily: "Anton",
          }}
        >
          <span style={{ fontSize: 44 }}>R$</span>
          <span style={{ fontSize: 96, lineHeight: 1 }}>{precoVeiculo(veiculo.preco)}</span>
        </div>
      </div>
    </div>,
    // o endereço da imagem leva a data da última mudança (?v=): mudou o anúncio, muda o endereço
    "public, max-age=86400",
  );
}
