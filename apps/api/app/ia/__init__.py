"""IA do assistente: perguntas sobre vendas, estoque e financeiro (modelo + ferramentas).

- `ferramentas`: consultas ao banco, só leitura, com o recorte do perfil de quem pergunta.
- `provedores`: adaptadores do Groq (padrão, formato OpenAI via httpx) e da Anthropic (SDK).
- `agente`: o laço de tool use, igual para os dois, com limites e tratamento de erro.
- `atendimento`: decide quem responde cada mensagem do assistente (motor de regras ou IA).
"""
