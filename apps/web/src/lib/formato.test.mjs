// Roda com: npm test  (Node lê o TypeScript direto, sem compilar)
import assert from "node:assert/strict";
import { test } from "node:test";
import { data, valorParaApi, valorParaCampo } from "./formato.ts";

test("dinheiro digitado do jeito brasileiro: ponto é milhar, vírgula é centavo", () => {
  const casos = {
    "14.900": "14900.00", // já gravou R$ 14,90 por engano: nunca mais
    "1.500": "1500.00",
    "1.500.000": "1500000.00",
    "14.900,50": "14900.50",
    "1500,5": "1500.50",
    "1,5": "1.50",
    "R$ 2.000,00": "2000.00",
    "14900": "14900.00",
    "14900.5": "14900.50",
    "9.90": "9.90",
    "1,500.00": "1500.00",
    "0": "0.00",
  };
  for (const [digitado, esperado] of Object.entries(casos)) {
    assert.equal(valorParaApi(digitado), esperado, `"${digitado}"`);
  }
});

test("o que não dá para entender volta nulo, em vez de virar um número errado", () => {
  for (const digitado of ["", "   ", "abc", "1,2,3", "1.2.3", "12,34,56", ",50", "R$"]) {
    assert.equal(valorParaApi(digitado), null, `"${digitado}"`);
  }
});

test("o campo mostra de volta exatamente o que vai ser gravado", () => {
  for (const digitado of ["14.900", "1500,5", "2.000,00", "9.90"]) {
    const gravado = valorParaApi(digitado);
    assert.equal(valorParaApi(valorParaCampo(gravado)), gravado, `"${digitado}"`);
  }
});

test("data de um instante usa o dia no Piauí, não em UTC", () => {
  assert.equal(data("2026-11-24T00:30:00Z"), "23/11/2026"); // 21h30 do dia 23 em Teresina
  assert.equal(data("2026-11-24T03:00:00Z"), "24/11/2026");
  assert.equal(data("2026-11-10"), "10/11/2026"); // data pura não muda
  assert.equal(data(null), "—");
});
