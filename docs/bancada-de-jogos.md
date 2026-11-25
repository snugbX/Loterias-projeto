# Bancada de Jogos

## Organização

A escolha de estratégia continua no seletor existente. Logo abaixo, a barra de
geração reúne modo ativo, quantidade e ação principal. Ela permanece visível ao
rolar ferramentas longas. O laboratório usa botões com ícones e rótulos curtos;
somente o painel da ferramenta ativa ocupa espaço.

Meu estilo, Consultar, Radar, Validação e Frequências são exibidos conforme o
acesso Premium. Histórico e Ajuda permanecem disponíveis para contas gratuitas
e visitantes. Controles administrativos mantêm as verificações já existentes.

## Compatibilidade

- `src/js/workbench.js` move os controles existentes para a bancada, preservando
  seus IDs, eventos e referências; não duplica quantidade nem botão de geração.
- Os painéis continuam sendo `details`, preservando carregamento sob demanda,
  estado dos formulários e as integrações de consulta, comparação e radar.
- Abrir um painel fecha os demais. Escape fecha o painel ativo e devolve o foco
  ao botão correspondente. As ferramentas possuem nomes visíveis e tooltips.
- Quando Meu estilo está aberto, a barra submete o formulário personalizado
  existente, com validação nativa e limite de lote do backend. Não converte um
  pedido personalizado em geração normal. As duas quantidades são sincronizadas.
- Durante a geração personalizada, a barra e as ferramentas ficam indisponíveis
  até a resposta, sem interromper a animação ou cancelar uma geração já iniciada.
- As cores vêm da modalidade selecionada; a organização e os recursos existentes
  específicos de cada loteria continuam sob responsabilidade de seus módulos.

## Ícones e Acessibilidade

Oito ícones oficiais Lucide 0.468.0 estão em `src/icons/lucide`, junto da licença.
São arquivos estáticos locais, com caminhos explicitamente permitidos no Flask;
não é necessário carregar biblioteca JavaScript, fonte de ícones ou CDN nova.
Referência: [Lucide Static](https://lucide.dev/guide/static).

Os ícones são decorativos para leitores de tela: os nomes dos botões vêm dos
rótulos e atributos acessíveis. Os controles têm foco visível, contraste adaptado
aos temas, áreas de toque de pelo menos 44 px e não dependem apenas de cor.
Movimento reduzido elimina as pequenas transições da prateleira.

## Verificação

`tests/browser_workbench.cjs` testa os ícones servidos, ausência de controles
duplicados, exclusividade dos painéis, geração personalizada real pela barra,
geração normal gratuita, quantidade sincronizada, barra visível em ferramentas
longas, teclado, permissões, quatro modalidades e temas em desktop e celular.
Os testes anteriores continuam cobrindo consultas, radar, histórico e animação.
