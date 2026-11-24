# Apresentação Animada dos Jogos

## Direção de Design

Uma ilustração 2D de um globo mecânico apresenta as dezenas já recebidas do
servidor. O movimento marca a conclusão da geração; não representa um sorteio
oficial, um cálculo adicional, uma chance maior ou uma premiação.

As cores vêm de `lotteryColors`, sem duplicar a paleta. A quantidade de posições
acompanha cada modalidade; o Dia de Sorte tem uma posição separada para o mês.
Os resultados completos continuam sendo renderizados pelo componente existente.

## Pesquisa e Decisões

- [Material Design: Motion](https://m3.material.io/styles/motion): distingue
  movimento expressivo em momentos-chave de movimento funcional. Aplicação:
  revelação pontual, chegada suave das bolas e interface estável no restante.
- [NN/g: duração e características da animação](https://www.nngroup.com/articles/animation-duration/):
  animações devem comunicar feedback sem impor uma espera frustrante. Aplicação:
  cada entrada dura 280 ms. A apresentação tem mínimo visual de 5 segundos para
  um jogo ou 6,5 segundos para um lote, mais até 480 ms de transição final.
  É possível pular; esses tempos não se aplicam com movimento reduzido.
- [WCAG: animações por interação](https://www.w3.org/WAI/WCAG21/Understanding/animation-from-interactions):
  permitir desativar movimento não essencial. Aplicação: preferência local,
  respeito automático a `prefers-reduced-motion` e acesso imediato aos jogos.
- [WAI: diálogos modais](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/):
  contenção do foco e fechamento pelo teclado. Aplicação: Tab permanece no
  resultado, Escape fecha e os botões têm alvos de pelo menos 44 px.
- [MDN: requestAnimationFrame](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame):
  renderização sincronizada com o navegador. Aplicação: um único ciclo, cancelado
  ao pausar, concluir ou fechar; resolução limitada a duas vezes a dimensão lógica.
- [MDN: visibilitychange](https://developer.mozilla.org/en-US/docs/Web/API/Document/visibilitychange_event):
  suspender trabalho visual quando a página não está visível. Aplicação: não
  consumir quadros em segundo plano nem avançar a sequência enquanto oculta.
- [CAIXA: regras dos sorteios](https://loterias.caixa.gov.br/Paginas/regras-sorteios.aspx):
  o Dia de Sorte distingue dezenas e mês. Aplicação: oito posições na prévia,
  sendo sete dezenas e um selo de mês, sem apresentar o mês como oitava dezena.

Estas são decisões derivadas das referências, não evidência de aumento de
conversão ou preferência do público. Isso exige teste com usuários.

## Limites e Manutenção

### Preparação e Personagens

A preparação começa junto da requisição real, tanto no gerador normal quanto
no personalizado. O apresentador coloca bolas ilustrativas no globo enquanto o
servidor responde. Não existe percentual fictício nem atraso da requisição.
Fechar o painel não cancela uma geração que pode já ter sido salva no servidor;
o retorno daquela requisição não reabre uma apresentação dispensada.

Cada personagem usa um emblema e a paleta da modalidade. As associações abaixo
são escolhas de design, não emblemas oficiais da CAIXA nem promessa de sorte:

- Mega-Sena: trevo de quatro folhas. Referência cultural: [Pitt Rivers Museum,
  Oxford](https://web.prm.ox.ac.uk/amulets/index.php/four-leaf-clover-france/index.html).
- Lotofácil: joaninha. Referência de repertório: [University at Buffalo,
  boletim de março de 2024](https://www.buffalo.edu/content/dam/www/recreation/Recreation%20Newsletter%20-%20MAR%202024.pdf).
- Quina: ferradura. Referência de crenças populares: [acervo de folclore da
  University of Maine](https://library.umaine.edu/content/NAFOH/text/NA2445/NA2445_beliefs_luck.pdf).
- Dia de Sorte: gato da sorte, inspirado no maneki-neko. Referência: [SFO
  Museum](https://www.sfomuseum.org/exhibitions/maneki-neko-japans-beckoning-cat).

A saída da preparação preserva o painel e suaviza sua altura. Durante a
revelação, o personagem permanece visível ao lado do globo: ele deixa de
carregar bolas e acompanha as dezenas com um aceno suave. Na transição final,
a cena vira uma ilustração compacta e estática junto dos resultados, em vez de
sumir. A transição começa com uma dissolução de 160 ms e o resultado entra em 300 ms, com
acomodação de altura em 320 ms. Preferência por movimento reduzido elimina essas
transições; fechar ou iniciar outra apresentação cancela as anteriores.

### Implementação

- `src/js/drawExperience.js` concentra a apresentação. `MIN_PRESENTATION_MS`
  e `MIN_BATCH_PRESENTATION_MS` controlam os mínimos visuais; `MIX_MS` controla
  o trecho inicial. Não há biblioteca, fonte, imagem ou serviço remoto adicional.
- `FORMATS` define quantidade, universo visual e rótulo por loteria. Ao adicionar
  modalidade, atualizar a configuração e o teste de navegação correspondente.
- Os trajetos do globo são decorativos e determinísticos, não física nem geração
  de números. Somente valores retornados pelo servidor vão para a prévia final.
- A preferência guarda apenas `on`/`off` em `snugbx-draw-animation`; não guarda
  jogos, conta ou dados de pagamento.
- Pausar, pular e rever não chamam a API nem salvam novos jogos. Sem movimento
  permitido ou sem Canvas disponível, os jogos aparecem imediatamente.
- Lotes grandes não recebem animação individual de cada linha. O resumo de
  conclusão é anunciado por leitor de tela; o Canvas é decorativo e oculto dele.
- Lotes apresentam até `MAX_PREVIEW_GAMES` (3) jogos em sequência, com etapas
  visuais e aviso quando só parte do lote está na prévia. Todos os jogos aparecem
  numerados no resultado, inclusive ao ampliar a fonte. A duração não cresce
  proporcionalmente ao número de jogos.
- A integração compartilhada atende geração normal e geração personalizada,
  preservando permissões, limites, histórico e seleção de estratégia existentes.

## Verificação

`tests/browser_draw.cjs` usa contas temporárias e respostas conhecidas para
conferir identidade dos números, mês, quatro modalidades, temas, 320/390/1440 px,
Canvas não vazio e em movimento, pausa, repetição sem requisição, lote de 100
jogos, movimento reduzido, preferência, foco e falhas de geração. Os testes
existentes cobrem o backend e a integração real da geração personalizada.
