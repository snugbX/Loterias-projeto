# Caderno dos Sorteios

O boletim apresenta cinco páginas editoriais, uma por modalidade, com o último
concurso disponível em cada uma. A paginação não representa um arquivo de
concursos antigos: seus números são apenas as posições das modalidades.

## Design e Navegação

- Cabeçalho de caderno, identificação do concurso e cor própria de cada loteria.
- Dezenas sorteadas, retrato de paridade, soma, repetição em relação ao concurso
  anterior, duplas consecutivas e distribuição numérica por faixa.
- A Lotofácil organiza suas 15 dezenas em três linhas; o Dia de Sorte apresenta
  o mês em uma faixa própria. Nenhuma dessas informações representa previsão.
- Abas com nomes das modalidades e controles anterior/próxima. A troca dura
  240 ms e só ocorre por ação do usuário, sem avanço automático ou temporizador.
- As páginas compartilham a mesma célula de CSS Grid, reservando o espaço da
  maior edição. As inativas têm `hidden`, `visibility:hidden`, `inert` e
  `aria-hidden`, sem deixar conteúdo ou controles ocultos no foco/leitor de tela.
- Setas, Home e End navegam pelas abas. A paginação inferior leva o foco e a
  leitura à nova página. Movimento reduzido desativa a transição e a rolagem suave.

Referências: [WAI: carrosséis acessíveis](https://www.w3.org/WAI/tutorials/carousels/),
[WAI: controles e interação](https://www.w3.org/WAI/tutorials/carousels/controls/)
e [BBC GEL: padrões de navegação](https://bbc.github.io/gel/).
A composição editorial é própria do projeto, sem copiar identidade de terceiros.

## Dados e Manutenção

`src/js/drawDigest.js` continua consumindo somente `/draw_digest`. Não muda o
cálculo dos boletins, não adiciona chamadas de estatística pesada e não interfere
nas funções Premium ou no histórico privado. Somente abrir/atualizar o painel
ou a atualização já existente dos resultados solicita os dados; paginar é local.

O backend existente valida a correspondência do relatório com os CSVs atuais.
Boletins pendentes, malformados ou com contagens inconsistentes viram uma página
de atualização, sem reutilizar números antigos como atuais. A interface também
confere quantidade/universo das dezenas, paridade, soma, repetidas, consecutivas,
faixas e cobertura antes de apresentar uma edição como atual.

Comparação indisponível com o concurso anterior não é exibida como zero
repetições. Mês ausente é indicado explicitamente. O leitor pode abrir a origem
e a cobertura da base em “Sobre estes dados” e consultar a modalidade na CAIXA.

A seleção de modalidade permanece ao atualizar. Requisições antigas são
canceladas e não sobrescrevem as novas; fechar o caderno cancela requisição e
animação. Quatro ícones Lucide 0.468.0 foram adicionados à coleção local, mantendo
a licença e a lista explícita de arquivos servidos, sem nova biblioteca ou CDN.

## Testes

`tests/browser_digest.cjs` usa servidor e contas temporários, além de boletins
conhecidos para validar dados, cinco modalidades, mês, trevos, navegação e foco,
transição, altura estável, temas, 320/390/1440 px, ampliação de fonte, movimento
reduzido, dados pendentes/inconsistentes, falha e recuperação, seleção preservada
e acesso como visitante. Os testes existentes continuam cobrindo o relatório
público real e as demais funções do app.
