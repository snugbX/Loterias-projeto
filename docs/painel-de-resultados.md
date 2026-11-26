# Painel de resultados

Os resultados iniciais usam bilhetes por modalidade, sem alterar as regras de
geração ou o histórico particular dos usuários. São duas colunas no desktop e
uma coluna abaixo de 600 px. A Lotofácil usa cinco colunas de dezenas; Dia de
Sorte destaca separadamente o Mês da Sorte. Não há rotação automática.

## Paginação

O painel exibe dois bilhetes por página no desktop e um em telas de até 600 px.
Setas e um seletor nativo permitem navegar sem novas consultas à API. A quantidade
de páginas é calculada a partir dos bilhetes renderizados, sem limite fixo de
modalidades. A recarga preserva a página e a mudança de faixa de tela mantém a
primeira loteria visível sempre que possível. Se a lista encolher, a página é
ajustada para o novo limite.

Os bilhetes fora da página usam `hidden` e `inert`, portanto não ficam na ordem
de foco ou na leitura por tecnologias assistivas. Há anúncio do intervalo
visível, teclas direcionais nos botões, controles de 44 px e transição curta
de opacidade que respeita movimento reduzido. Não existe avanço automático.
Uma altura mínima evita saltos comuns entre bilhetes sem impedir a expansão
do texto ou dos detalhes da base.

A navegação numerada exibe uma janela de até três páginas, com pequenas faixas
nas cores das loterias presentes em cada uma. A página atual usa contraste e
`aria-current`, não apenas cor. O seletor nativo continua disponível para ir a
qualquer página sem criar uma faixa de navegação interminável. Atualizações
preservam também o foco nos botões numerados.

O evento local `results:rendered`, emitido por `render.js` ao terminar a montagem,
permite que `resultsBoard.js` reaplique a página sem acoplar o renderizador aos
controles. O estado da página existe apenas em memória, não em contas ou banco.

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
