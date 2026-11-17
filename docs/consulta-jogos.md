# Consulta e comparacao de jogos Premium

O painel "Consultar e comparar jogos" aceita de 1 a 10 apostas simples da mesma
loteria. O usuario adiciona/remove campos e, no Dia de Sorte, escolhe um mes para
cada jogo. Mudar a loteria ou a conta limpa os palpites e resultados da consulta.
Editar um jogo invalida o resultado anterior e cancela uma requisicao pendente.

## Comparacao

- Resumo por jogo com dezenas, mes, concursos premiaveis, maior acerto numerico,
  pares/impares e frequencia condicional do perfil no radar.
- Identificacao de apostas repetidas, inclusive com dezenas em outra ordem.
- Dezenas em comum e porcentagem de sobreposicao entre cada par de jogos.
- Concursos em que pelo menos um jogo teria faixa de premio, sem contar um
  mesmo concurso mais de uma vez e sem limitar o resumo aos 30 exemplos recentes.
- Cobertura do premio principal numerico por combinacoes distintas.
- Meses diferentes cobertos no Dia de Sorte, calculados separadamente.
- Detalhes individuais recolhidos para nao repetir informacoes na tela toda.

O destaque de frequencia historica nao e uma classificacao de melhores apostas.
Todas as apostas simples individuais tem a mesma chance matematica em sorteios
justos. O perfil de pares/impares reune muitas combinacoes: sua frequencia nao e
a chance de uma combinacao especifica ganhar.

Se ha u combinacoes numericas diferentes de k dezenas em universo N, a chance de
ao menos uma acertar todos os numeros no mesmo concurso e `u / C(N,k)`. Apostas
com as mesmas dezenas nao ampliam essa cobertura, mesmo com meses diferentes.
Para m meses distintos do Dia de Sorte, a cobertura do mes e `m/12`.
Essas duas chances nao sao somadas. Nao calculamos a chance coletiva de qualquer
faixa menor somando probabilidades individuais, pois os eventos se sobrepoem.

## Atualizacao e privacidade

Uma unica leitura validada da base atende todo o lote. O radar e construido a
partir dessa mesma versao dos concursos. Cada nova consulta acompanha o CSV
atualizado pelo fluxo existente, sem precisar reiniciar o app. Uma consulta ja
exibida e um retrato da base informada; nao e reenviada automaticamente em segundo
plano. Uma nova consulta recebe os dados atuais.

Palpites desta consulta nao sao salvos em historico, banco, navegador ou enviados
a fontes externas. A resposta usa Cache-Control: no-store. A rota exige acesso
Premium/admin e token CSRF; limita a 10 jogos e valida todos antes de ler a base.
Historico de premios e simulacao pelas regras atuais, nao comprovante de aposta
ou de premio recebido. Bases incompletas sao sinalizadas.

API: `POST /analyze_games/<lottery_type>` com JSON:

```json
{"games":[{"numbers":[1,2,3,4,5,6]},{"numbers":[10,20,30,40,50,60]}]}
```

Para Dia de Sorte cada objeto inclui `month` inteiro de 1 a 12. A antiga rota
`POST /analyze_game/<lottery_type>` permanece compativel para consulta individual.

Testes: `python -m unittest discover -s tests -v` e `node tests/browser_analysis.cjs`.
