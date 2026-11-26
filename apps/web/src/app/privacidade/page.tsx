import type { Metadata } from "next";
import { Moldura } from "@/components/site/Moldura";
import { Barras } from "@/components/site/pecas";
import { linkWhats, obterLoja } from "@/lib/loja";
import { ROBOTS_DEMONSTRACAO, carregarCatalogo, siteUrl } from "@/lib/vitrine";

// Os dados da loja vêm do ambiente (LOJA_*), lidos a cada visita.
export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const catalogo = await carregarCatalogo();
  const canonico = siteUrl();
  return {
    title: { absolute: "Privacidade — RC Motos" },
    description: "O que o site da RC Motos faz com os seus dados: sem cadastro, sem cookies de rastreamento.",
    robots: catalogo?.ilustrativo ? ROBOTS_DEMONSTRACAO : { index: true, follow: true },
    alternates: canonico ? { canonical: `${canonico}/privacidade` } : undefined,
  };
}

/**
 * Política de privacidade do site: só o que o sistema realmente faz. Se mudar o que o site
 * guarda (contagem, cookies, formulários), este texto muda junto.
 */
export default function Privacidade() {
  const loja = obterLoja();
  const linkLoja = linkWhats(loja.whatsapp, "Olá! Tenho uma dúvida sobre os meus dados (privacidade).");
  const empresa = [loja.razaoSocial, loja.cnpj && `CNPJ ${loja.cnpj}`].filter(Boolean).join(", ");
  const terceiros = [loja.endereco && "o endereço abre no Google Maps", loja.instagram && "o perfil abre no Instagram"]
    .filter(Boolean)
    .join(" e ");

  return (
    <Moldura loja={loja}>
      <article className="claro privacidade" aria-labelledby="titulo-privacidade">
        <p className="sobretitulo">
          <Barras /> Política de privacidade
        </p>
        <h1 id="titulo-privacidade" className="outdoor privacidade__titulo">
          Seus dados <em>no site.</em>
        </h1>
        <p className="privacidade__abre">
          Este é o site da RC Motos{empresa && ` (${empresa})`}. Ele mostra os veículos à venda e leva você até o
          WhatsApp da loja. Aqui está, sem rodeio, o que ele faz com os seus dados.
        </p>

        <section aria-labelledby="priv-nao">
          <h2 id="priv-nao">O que o site não faz</h2>
          <ul>
            <li>Não pede cadastro nem login. A área da equipe é só para quem trabalha na loja.</li>
            <li>
              Não usa cookies de rastreamento nem de publicidade, nem ferramentas de análise de outras empresas.
            </li>
            <li>Não tem formulário que grave o que você digita.</li>
          </ul>
        </section>

        <section aria-labelledby="priv-conta">
          <h2 id="priv-conta">O que o site conta</h2>
          <p>
            Quando alguém abre a página de um veículo, ou toca num botão de WhatsApp sobre um veículo (“Quero essa”,
            “Quero esse” ou o envio da proposta com o veículo escolhido), o site soma 1 num contador daquele veículo
            naquele dia. Só isso é guardado: o veículo, o dia e o total. Não guardamos endereço IP, navegador,
            aparelho nem nada que identifique quem visitou. A loja usa esses números para saber quais veículos
            estão sendo mais procurados.
          </p>
          <p>
            Para evitar abuso, o servidor limita quantas contagens e consultas de placa podem vir da mesma conexão
            por minuto. Para isso ele lembra o endereço da conexão por um minuto, só na memória, sem gravar.
          </p>
        </section>

        <section aria-labelledby="priv-placa">
          <h2 id="priv-placa">Consulta pela placa</h2>
          <p>
            A placa que você digita na consulta de procedência serve só para procurar o veículo entre os que estão
            à venda na loja e mostrar o laudo. Ela não é gravada.
          </p>
        </section>

        <section aria-labelledby="priv-terceiros">
          <h2 id="priv-terceiros">WhatsApp e outros serviços</h2>
          <p>
            Os botões de WhatsApp abrem o WhatsApp, um serviço da Meta, com uma mensagem pronta que você pode mudar
            antes de enviar. A conversa acontece lá, com as regras de privacidade do WhatsApp; o que você escrever
            chega à loja como qualquer mensagem.
            {terceiros && ` Da mesma forma, ${terceiros} — serviços de outras empresas, que só abrem se você tocar.`}
          </p>
        </section>

        <section aria-labelledby="priv-registros">
          <h2 id="priv-registros">Registros técnicos</h2>
          <p>
            Como em qualquer site, o servidor que hospeda o site pode manter registros técnicos de acesso (como
            endereço IP, data e hora) para funcionar e se proteger de ataques. Esses registros não entram no sistema
            da loja.
          </p>
        </section>

        <section aria-labelledby="priv-lgpd">
          <h2 id="priv-lgpd">Seus direitos (LGPD)</h2>
          <p>
            A Lei Geral de Proteção de Dados (Lei nº 13.709/2018) garante a você, entre outras coisas, saber se a
            loja tem dados seus, ter acesso a eles, corrigi-los e pedir a exclusão do que a loja não for obrigada a
            guardar. Se você comprou ou negociou com a loja, seus dados de cadastro e da compra ficam no sistema
            dela, para a venda, a documentação e as obrigações legais.
          </p>
          <p>Para qualquer pedido ou dúvida sobre os seus dados, fale com a loja pelo WhatsApp.</p>
          <a className="acao acao--tinta" href={linkLoja} target="_blank" rel="noopener">
            Falar com a loja
          </a>
        </section>

        <p className="dado privacidade__data">Atualizada em 26/11/2026</p>
      </article>
    </Moldura>
  );
}
