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
  paridade de referência. A escolha agora usa afinidade histórica, não distância
  entre números. Para cada possível troca, avalia as dezenas novas contra as
  originais que seriam mantidas. Prioriza associação positiva com a maioria
  dessas dezenas, depois maximiza a menor proporção de associações positivas
  entre as novas dezenas e a média dos logaritmos dos índices de afinidade. Empates usam
  a menor dezena nova e a menor original; números menores não são mais prováveis.
- A busca é incremental: reavalia todas as novas dezenas após cada troca, mas
  não garante o melhor conjunto global entre todas as combinações possíveis.
- Cada nova dezena precisa ter afinidade positiva com mais da metade das
  dezenas mantidas ao final. Se o perfil exigir substituir todas as dezenas,
  usa o jogo original como referência e informa essa diferença na tela.
- Se a busca não encontrar maioria positiva com suporte mínimo, nenhuma
  alternativa é apresentada como sinérgica. O jogo original é mantido com aviso
  de que ele não foi adaptado ao perfil. Não há retorno ao critério de vizinhança.
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

## Afinidade Entre Dezenas

O índice usa todos os concursos válidos da mesma base da consulta. Para um par
de dezenas A e B:

```text
N = concursos válidos
k = dezenas sorteadas por concurso
U = tamanho do universo de dezenas
esperado = aparições(A) × aparições(B) / N × (k - 1) × U / (k × (U - 1))
afinidade = (coocorrências(A,B) + 5) / (esperado + 5)
```

O ajuste de população finita considera o sorteio sem reposição: sob marginais
uniformes, a referência de um par em sorteio justo fica em 1, não abaixo de 1.
As frequências marginais observadas ajustam a popularidade individual; o
acréscimo de cinco coocorrências suaviza oscilações de poucos registros.

Só pares com pelo menos três coocorrências e pelo menos 30 aparições de cada
dezena participam como evidência. Pares abaixo do suporte ficam neutros, não
positivos. Índice acima de 1 é chamado de associação positiva descritiva.
Esses limiares são escolhas operacionais, não critérios de significância.

A tela informa quantas e quais dezenas mantidas se associam a cada nova dezena.
Isso representa associações de pares separadas: não significa que todo o grupo
tenha saído junto, nem que a hipótese de independência foi rejeitada. A busca
avalia muitos pares sem correção de múltiplas comparações. Nenhum resultado é
apresentado como previsão ou aumento de chance de uma aposta específica.

O índice armazena somente resultados públicos, tem cache limitado a quatro
bases e é invalidado quando o conteúdo validado muda. É construído uma vez por
base, não uma vez por jogo do lote. Não exige tarefa agendada adicional.

Testes: `python -m unittest discover -s tests -v` e
`node tests/browser_analysis.cjs` (contas e bancos temporários).
