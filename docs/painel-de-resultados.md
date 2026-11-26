# Painel de resultados

Os resultados iniciais usam bilhetes por modalidade, sem alterar as regras de
geração ou o histórico particular dos usuários. São duas colunas no desktop e
uma coluna abaixo de 600 px. A Lotofácil usa cinco colunas de dezenas; Dia de
Sorte destaca separadamente o Mês da Sorte. Não há rotação automática.

## Responsabilidades

- `render.js`: valida quantidade, unicidade, limites das dezenas e metadados;
  monta os bilhetes com texto seguro, datas e ações acessíveis.
- `resultsBoard.js`: controla a recarga pública e a cópia, com retorno local
  anunciado por leitores de tela. Não lê nem altera jogos particulares.
- `main.js`: consulta `/latest_results` e `/data_status`. Recarregar apenas lê
  os dados disponíveis; não executa o atualizador administrativo.
- `drawDigest.js`: `openDigestEdition` abre e focaliza a edição correspondente,
  sem modificar a modalidade selecionada para geração.

## Estados e comunicação

Concurso, data do sorteio e data de consulta são informações distintas. Não
apresentar a consulta como confirmação oficial ou atualização em tempo real.
O registro do arquivo fica em um detalhe expansível. Divergência entre concurso
e status da base recebe aviso explícito. Respostas ausentes ou inválidas não
exibem dezenas inventadas; erros de rede permitem tentar novamente.

Copiar usa a API de clipboard do navegador, mediante clique, com concurso,
dezenas, mês quando aplicável e lembrete para conferir os canais oficiais da
CAIXA. Permissão recusada gera mensagem acessível, sem alterar o jogo.

## Verificação

`tests/browser_results.cjs` inicia uma prévia isolada em 5117. Verifica as cinco
modalidades, telas de 1440, 390 e 320 px, ambos os temas, texto ampliado, cópia
simulada (não modifica o clipboard real), abertura do boletim, divergência,
dezenas inválidas, falha de rede e nova tentativa. Capturas ficam em arquivos
ignorados de `tests/results-*.png`.

Ícones locais Lucide 0.468.0, sob a licença já presente no projeto; sem nova
biblioteca, imagem remota ou chamada externa para o efeito visual.
