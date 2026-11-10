import { SITUACAO, data, dataHora, moeda } from "@/lib/formato";
import type { Evento, Situacao } from "@/lib/tipos";

const ENTIDADE: Record<string, string> = {
  veiculo: "veículo",
  custo: "custo",
  foto: "foto",
  cliente: "cliente",
  venda: "venda",
  comissao: "comissão",
  aporte: "aporte",
  laudo: "laudo de procedência",
  usuario: "usuário",
  sessao: "",
};

const CAMPO: Record<string, string> = {
  tipo: "tipo",
  marca: "marca",
  modelo: "modelo",
  ano_fabricacao: "ano de fabricação",
  ano_modelo: "ano do modelo",
  cor: "cor",
  km: "km",
  placa: "placa",
  chassi: "chassi",
  renavam: "RENAVAM",
  valor_compra: "valor de compra",
  data_compra: "data da compra",
  preco_venda: "preço de venda",
  situacao: "situação",
  observacoes: "observações",
  descricao: "descrição",
  valor: "valor",
  data: "data",
  nome: "nome",
  email: "e-mail",
  telefone: "telefone",
  cpf_cnpj: "CPF/CNPJ",
  endereco: "endereço",
  perfil: "perfil",
  ativo: "ativo",
  acesso_aportes: "acesso aos aportes",
  comissao_regra: "regra de comissão",
  comissao_valor: "valor da regra de comissão",
  senha: "senha",
  status: "status",
  lucro: "lucro",
  total_custos: "total de custos",
  forma: "forma de pagamento",
  data_venda: "data da venda",
  entrada: "entrada",
  numero_parcelas: "nº de parcelas",
  valor_parcela: "valor da parcela",
  primeiro_vencimento: "1º vencimento",
  banco: "banco",
  motivo_cancelamento: "motivo do cancelamento",
  paga_em: "paga em",
  ordem: "ordem",
  semaforo: "sinal",
  ilustrativo: "ilustrativo",
};

const DINHEIRO = new Set([
  "valor", "valor_compra", "preco_venda", "lucro", "total_custos", "entrada", "valor_parcela",
]);
const OCULTOS = new Set([
  "veiculo_id", "cliente_id", "vendedor_id", "venda_id", "registrada_por_id", "registrado_por_id",
  "cancelada_por_id", "cancelada_em", "consultado_por_id", "provedor", "arquivo", "miniatura", "regra", "regra_valor", "ordem",
]);

const VALOR: Record<string, string> = {
  moto: "moto",
  carro: "carro",
  manutencao: "manutenção",
  documentacao: "documentação",
  debito: "débito pago",
  outro: "outro",
  a_vista: "à vista",
  financiado_banco: "financiado (banco)",
  parcelado_loja: "parcelado na loja",
  ativa: "ativa",
  cancelada: "cancelada",
  pendente: "pendente",
  paga: "paga",
  percentual_lucro: "% do lucro",
  percentual_venda: "% da venda",
  valor_fixo: "valor fixo",
};

function valorLegivel(campo: string, valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") return "vazio";
  if (typeof valor === "boolean") return valor ? "sim" : "não";
  if (DINHEIRO.has(campo)) return moeda(String(valor));
  if (campo === "situacao") return SITUACAO[valor as Situacao] ?? String(valor);
  if (typeof valor === "string" && /^\d{4}-\d{2}-\d{2}T/.test(valor)) return dataHora(valor);
  if (typeof valor === "string" && /^\d{4}-\d{2}-\d{2}$/.test(valor)) return data(valor);
  return VALOR[String(valor)] ?? String(valor);
}

function frase(e: Evento): string {
  if (e.entidade === "sessao") return e.resumo ?? e.acao;
  if (e.entidade === "foto") return e.acao === "excluiu" ? "removeu uma foto" : "adicionou uma foto";
  const alvo = [ENTIDADE[e.entidade] ?? e.entidade, e.resumo].filter(Boolean).join(" ");
  return `${e.acao} ${alvo}`;
}

function detalhes(e: Evento): string[] {
  if (!e.alteracoes) return [];
  return Object.entries(e.alteracoes)
    .filter(([campo]) => !OCULTOS.has(campo))
    .map(([campo, valor]) => {
      const nome = CAMPO[campo] ?? campo;
      if (e.acao === "alterou" && valor && typeof valor === "object") {
        const { de, para } = valor as { de: unknown; para: unknown };
        return `${nome}: ${valorLegivel(campo, de)} → ${valorLegivel(campo, para)}`;
      }
      return `${nome}: ${valorLegivel(campo, valor)}`;
    });
}

/** Linha do tempo do audit log: quem, quando, o quê. */
export function ListaEventos({ eventos }: { eventos: Evento[] }) {
  return (
    <ol className="divide-y divide-borda">
      {eventos.map((e) => {
        const linhas = detalhes(e);
        return (
          <li key={e.id} className="py-3 text-sm">
            <p>
              <b>{e.usuario_nome ?? "Sistema"}</b> {frase(e)}
            </p>
            {linhas.length > 0 && (
              <p className="mt-0.5 text-[13px] leading-relaxed text-suave">{linhas.join(" · ")}</p>
            )}
            <time className="mt-0.5 block text-xs text-suave">{dataHora(e.criado_em)}</time>
          </li>
        );
      })}
    </ol>
  );
}
