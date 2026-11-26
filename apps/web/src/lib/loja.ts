/**
 * Dados da loja usados pelo site. Vêm de variáveis de ambiente (lidas a cada requisição),
 * para que telefone, endereço e horário sejam trocados sem mexer no código.
 * O que não estiver preenchido simplesmente não aparece no site — nada é inventado.
 */
export interface Loja {
  /** só dígitos, com DDD (ex.: 86999990000) */
  whatsapp: string | null;
  cidade: string | null;
  endereco: string | null;
  horario: string | null;
  /** sem @ */
  instagram: string | null;
  /** já formatado (00.000.000/0000-00); valor com dígito verificador errado é ignorado */
  cnpj: string | null;
  razaoSocial: string | null;
}

const texto = (valor: string | undefined) => valor?.trim() || null;

export function obterLoja(): Loja {
  return {
    whatsapp: texto(process.env.LOJA_WHATSAPP)?.replace(/\D/g, "") || null,
    cidade: texto(process.env.LOJA_CIDADE),
    endereco: texto(process.env.LOJA_ENDERECO),
    horario: texto(process.env.LOJA_HORARIO),
    instagram: texto(process.env.LOJA_INSTAGRAM)?.replace(/^@/, "") || null,
    cnpj: formatarCnpj(process.env.LOJA_CNPJ),
    razaoSocial: texto(process.env.LOJA_RAZAO_SOCIAL),
  };
}

/** Dígito verificador do CNPJ (módulo 11). Cada caractere vale o código dele menos 48: assim o
 * mesmo cálculo serve para o CNPJ só de números e para o alfanumérico (Receita, a partir de 2026). */
function digitoCnpj(base: string): number {
  let soma = 0;
  let peso = base.length - 7; // 5 para os 12 primeiros, 6 para os 13
  for (const caractere of base) {
    soma += (caractere.charCodeAt(0) - 48) * peso;
    peso = peso === 2 ? 9 : peso - 1;
  }
  const resto = soma % 11;
  return resto < 2 ? 0 : 11 - resto;
}

/** "12345678000195" ou "12.345.678/0001-95" → "12.345.678/0001-95"; inválido ou vazio → null. */
export function formatarCnpj(valor: string | undefined | null): string | null {
  const cnpj = (valor ?? "").toUpperCase().replace(/[\s./-]/g, "");
  if (!/^[0-9A-Z]{12}[0-9]{2}$/.test(cnpj) || /^(.)\1{13}$/.test(cnpj)) return null;
  const primeiro = digitoCnpj(cnpj.slice(0, 12));
  const segundo = digitoCnpj(cnpj.slice(0, 12) + primeiro);
  if (cnpj.slice(12) !== `${primeiro}${segundo}`) return null;
  return `${cnpj.slice(0, 2)}.${cnpj.slice(2, 5)}.${cnpj.slice(5, 8)}/${cnpj.slice(8, 12)}-${cnpj.slice(12)}`;
}

/** Link do WhatsApp com mensagem pronta. Sem número configurado, abre o WhatsApp para escolher o contato. */
export function linkWhats(numero: string | null, mensagem: string): string {
  const destino = numero ? `55${numero.replace(/^55/, "")}` : "";
  return `https://wa.me/${destino}?text=${encodeURIComponent(mensagem)}`;
}
