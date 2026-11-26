# Seletor de loterias: faixa de volantes

## Proposta visual

Uma faixa horizontal de pequenos volantes mantém a seleção compacta quando
novas modalidades são incluídas. Há navegação por toque, barra de rolagem e
setas explícitas, sem movimento automático. Cada volante mostra o nome e a
descrição real da aposta simples, com a cor da modalidade e um marcador de
seleção que não depende apenas da cor. Os antigos exemplos de dezenas foram
removidos: não eram resultados ou apostas geradas.

A apresentação usa apenas HTML, CSS e ícones Lucide já locais. Não adiciona
imagens remotas, dependências ou consultas para buscar/filterar modalidades.

## Referências estudadas

- [Material Design / Android: carousels](https://developer.android.com/develop/ui/compose/components/carousel):
  inspiração para uma faixa horizontal com itens de tamanho consistente e um
  trecho do próximo item visível. Não foi importado código Android nem usado
  o redimensionamento/parallax dos exemplos de mídia.
- [Carbon: search patterns](https://www.carbondesignsystem.com/building-blocks/core/patterns/search):
  busca local com retorno imediato e contagem, sem mudar a seleção ao filtrar.
- [W3C APG: radio group](https://www.w3.org/WAI/ARIA/apg/patterns/radio/):
  seleção única, `aria-checked`, um ponto de entrada no foco e navegação por
  setas. Home/End continuam como atalhos adicionais já existentes no app.

São referências de comportamento e composição, não uma cópia integral desses
sistemas. A identidade de cores, os volantes e a linguagem pertencem ao app.

## Manutenção

`lotteryPicker.js` monta o seletor nativo e os botões a partir de `lotteryDetails`
em `dom.js`, preservando IDs e eventos usados pelo restante do app. Uma nova
modalidade já integrada ao sistema não exige outro bloco de HTML do seletor:
o nome e a descrição entram no catálogo de apresentação; o tema segue os
mesmos cadastros de cores e estilos das modalidades atuais.

`main.js` continua responsável por trocar a modalidade e sincronizar geração,
consulta, radar, assistência e histórico. O módulo visual não altera acesso,
limites de conta nem regras de geração. A rolagem pelas setas apenas explora
opções; não muda a loteria selecionada.

## Busca e acessibilidade

- Busca por nome ou descrição, sem diferenciar acentos, espaços e pontuação.
- Nenhum resultado é escolhido automaticamente pela busca.
- A seleção atual permanece no resumo mesmo se for ocultada pelo filtro.
- Filtrar sem encontrar opções anuncia o estado e oferece limpar a busca.
- As setas do teclado percorrem somente as modalidades visíveis.
- O volante selecionado é trazido horizontalmente à vista, sem rolar a página
  verticalmente. Movimento reduzido usa rolagem imediata.
- Fonte ampliada pode aumentar a altura dos itens, sem cortar conteúdo.
- Nenhum dado de busca ou de seleção é salvo em contas, banco ou armazenamento.

`tests/browser_lottery_picker.cjs` usa uma prévia isolada em 5120 e contas
descartáveis. Cobre cinco modalidades, 1440/768/390/320 px, dois temas, seleção,
busca sem acentos, estado vazio, foco, teclado, rolagem sem selecionar e texto
no tamanho máximo. Capturas geradas são ignoradas pelo Git.
