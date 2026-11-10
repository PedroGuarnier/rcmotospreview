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
}

const texto = (valor: string | undefined) => valor?.trim() || null;

export function obterLoja(): Loja {
  return {
    whatsapp: texto(process.env.LOJA_WHATSAPP)?.replace(/\D/g, "") || null,
    cidade: texto(process.env.LOJA_CIDADE),
    endereco: texto(process.env.LOJA_ENDERECO),
    horario: texto(process.env.LOJA_HORARIO),
    instagram: texto(process.env.LOJA_INSTAGRAM)?.replace(/^@/, "") || null,
  };
}

/** Link do WhatsApp com mensagem pronta. Sem número configurado, abre o WhatsApp para escolher o contato. */
export function linkWhats(numero: string | null, mensagem: string): string {
  const destino = numero ? `55${numero.replace(/^55/, "")}` : "";
  return `https://wa.me/${destino}?text=${encodeURIComponent(mensagem)}`;
}
