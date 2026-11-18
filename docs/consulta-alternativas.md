# Destaques e alternativa na consulta Premium

A consulta destaca faixas simuladas no histórico, maior acerto numérico, perfil de
pares/ímpares e chance matemática da aposta simples. As tabelas detalhadas e os
avisos sobre a cobertura da base continuam disponíveis.

Cada jogo consultado recebe um perfil de referência a partir do radar da mesma
base de resultados usada na análise:

- Com pelo menos 30 transições após o perfil do último concurso, ordenamos os
  perfis pela frequência suavizada: `(ocorrências + 20 × probabilidade matemática)
  / (amostra + 20)`. O peso 20 é o mesmo da validação existente do radar.
- Com menos transições, usamos a distribuição matemática dos perfis. A interface
  identifica a amostra insuficiente, sem chamar essa referência de tendência.
- Empates são resolvidos pela referência matemática, menor quantidade de trocas
  e, por último, número de pares, tornando a sugestão reproduzível.
- A sugestão altera somente a quantidade de dezenas necessária para atingir a
  paridade de referência. Entre vizinhas disponíveis, prioriza menor distância,
  maior dezena original e vizinha superior. Isso é um critério de edição, não de
  probabilidade individual de um número.
- Se o jogo já segue o perfil, mantemos todas as dezenas e informamos que nenhuma
  troca é necessária. No Dia de Sorte, o mês escolhido é sempre preservado.
- O histórico da alternativa é simulado no mesmo conjunto de concursos do
  original. Isso não modifica a cobertura nem as probabilidades do conjunto
  consultado. A alternativa só entra na comparação quando o usuário a adiciona.

O usuário pode copiar a alternativa ou adicioná-la à consulta com “Comparar com
meu jogo”. O limite de dez jogos permanece. Se a alternativa já estiver na
consulta, a interface indica qual jogo é e evita adicioná-la outra vez.

O recurso não grava palpites, não consome a cota de geração, não altera o
histórico da conta e mantém a proteção Premium/admin, CSRF e respostas privadas
`no-store` da consulta existente. Atualizações da base refletem-se na consulta
seguinte, sem um novo agendamento.

Frequências de perfis não são a probabilidade de uma combinação específica. A
alternativa tem a mesma chance matemática individual da aposta original; não é
previsão nem evidência de vantagem sobre os próximos sorteios.

Testes: `python -m unittest discover -s tests -v` e
`node tests/browser_analysis.cjs` (contas e bancos temporários).
