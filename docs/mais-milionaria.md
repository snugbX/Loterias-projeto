# +Milionária

## Aposta simples e integração

O app trabalha com seis dezenas diferentes de 1 a 50 e dois trevos diferentes
de 1 a 6. Os trevos são um conjunto separado: uma dezena pode ter o mesmo valor
de um trevo. A geração, a cópia e o histórico mantêm o formato de lista existente:
as seis primeiras posições são dezenas, seguidas pelos dois trevos inteiros.
Não foi criada tabela nem alterada a autenticação ou a propriedade dos jogos.

Consultas recebem `numbers` (seis inteiros) e `trevos` (dois inteiros). O campo
`month` não se aplica. O leitor validado mantém a tupla de quatro campos já
usada internamente: concurso, data, dezenas e extras. Para esta modalidade,
o quarto campo é uma tupla ordenada dos dois trevos, e não um Mês da Sorte.

## Fonte e atualização sem planilha

A listagem do As Loterias não é tratada como um histórico completo de trevos.
O importador usa a [fonte pública de resultados da CAIXA](https://servicebus2.caixa.gov.br/portaldeloterias/api/maismilionaria)
e consulta cada concurso faltante pelo endereço correspondente. Não requer
chave, login, scraping do navegador ou desativação da validação TLS.

```powershell
py src/update_lottery_data.py --lottery maismilionaria --no-publish
```

O atualizador geral também inclui a modalidade automaticamente, inclusive no
workflow do GitHub Actions já existente. O destino é
`mais_milionaria_resultados.csv`, dentro de `LOTTERY_DATA_DIR`. O CSV público
inicial acompanha o código, como as outras bases, para evitar uma importação
completa a cada rebuild gratuito. Sua ausência não autoriza inventar resultados.

- A primeira coleta busca todo o histórico; pode levar vários minutos.
- Cada ciclo consulta o último resultado e busca apenas os concursos faltantes.
- Um histórico já completo exige somente a consulta ao último resultado.
- Valida modalidade, concurso, data, seis dezenas e dois trevos distintos.
- Divergência com o último concurso local interrompe a atualização para revisão.
- Erros temporários têm até três tentativas, com espera crescente.
- Redirecionamentos para outros hosts ou para HTTP são recusados. Em respostas
  de limitação, o tempo `Retry-After` em segundos é respeitado; esperas acima de
  um minuto encerram a tentativa para uma verificação posterior.
- `.lottery-cache/maismilionaria/` guarda resultados públicos intermediários;
  é ignorado pelo Git e permite retomar uma coleta interrompida.
- Nenhum CSV parcial substitui a base. A substituição ocorre apenas ao completar
  o histórico validado, preservando o mecanismo existente de backup e troca atômica.
- `--force` reconsulta o histórico inteiro e ignora o cache. Não usar na rotina.
- Uma reconstrução forçada pode reparar cabeçalho, codificação ou linhas locais
  danificadas. O CSV antigo só é substituído depois de obter a base completa,
  com backup pelo atualizador. Concursos locais válidos mais recentes que a
  fonte continuam impedindo regressão, inclusive com `--force`.
- `--dry-run` preserva o CSV e a publicação; pode preencher o cache público.

Após atualizar a base, os relatórios públicos devem corresponder ao mesmo CSV:

```powershell
py src/build_statistical_reports.py
```

O GitHub Actions já executa essa etapa. A receita pública foi incrementada para
3: relatórios anteriores não são apresentados como atuais para a nova estrutura.

## Prêmios e probabilidades

As [regras da CAIXA](https://loterias.caixa.gov.br/Paginas/Mais-Milionaria.aspx)
definem dez faixas. Com quatro, cinco ou seis dezenas, há faixas para dois trevos
e para um ou nenhum. Com duas ou três dezenas, é necessário acertar ao menos
um trevo. Apenas acertar dois trevos, com zero ou uma dezena, não premia.

As probabilidades cruzam duas distribuições hipergeométricas independentes.
A chance do prêmio principal é `1 / (C(50,6) * C(6,2))`, ou 1 em 238.360.500.
As dez faixas são disjuntas. A consulta separa cobertura numérica (seis dezenas)
da cobertura da aposta completa (dezenas e trevos); mesmas dezenas com outro
par de trevos não são a mesma aposta completa.

O resumo da geração personalizada também distingue essas coberturas:
`numeric_jackpot_probability` mede as seis dezenas; `jackpot_probability` e
`jackpot_one_in` exigem seis dezenas e os dois trevos. Fixar o par não elimina
o fator de quinze do espaço de resultados. O resumo informa quantos pares
foram usados e se os trevos foram fixados ou selecionados aleatoriamente.

O filtro histórico forte continua sendo um filtro **numérico de quatro ou mais
acertos**. Ele não filtra trevos e pode permitir prêmios de duas ou três dezenas
com trevos. Isso fica explícito no catálogo e na ajuda. A alternativa por afinidade
altera somente dezenas e preserva os trevos informados, sem alegar vantagem.

## Radar, agenda e apresentação

- Radar de paridade das dezenas separado dos quinze pares de trevos.
- Referência de cada par: 1 em 15; de cada trevo individual: 1 em 3.
- Transições apenas entre concursos consecutivos; não conectam lacunas.
- Amostras pequenas sinalizadas, intervalos aproximados e teste cronológico.
- Trevos identificados no seletor, resultados, boletim, consulta, animação,
  cópia, geração personalizada, assistência e histórico privado.
- Conferência do histórico continua restrita a jogos marcados como efetivados.
- Datas da agenda vêm do cronograma mensal oficial, não de uma semana fixa.
- Sem dependência adicional ou nova variável obrigatória no deploy.

## Verificação

`tests/test_mais_milionaria.py` cobre as dez faixas, situações sem prêmio,
probabilidades exatas, validação, geração, comparações, conferência efetivada,
radar, importação incremental e retomada após falhas. As fixtures compartilhadas
foram ampliadas para incluir trevos em vez de contornar sua validação.

`tests/browser_mais_milionaria.cjs` usa contas descartáveis e uma prévia isolada
em 5119. Testa dados públicos reais, consulta, validação, comparação, radar,
geração real, Canvas não vazio, cópia simulada e histórico. Confere temas claro
e escuro em 1440, 390 e 320 px. Imagens de teste e caches não são publicados.
