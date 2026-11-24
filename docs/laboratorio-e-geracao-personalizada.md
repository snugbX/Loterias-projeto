# Laboratório, Premissas e Boletins

Implementação em três etapas, precedidas por releitura dos módulos envolvidos e
execução incremental dos testes existentes. As quatro modalidades continuam
usando `LOTTERY_CONFIGS`, o leitor de concursos validados e as permissões já
existentes. Nenhuma dependência adicional foi incluída.

## Catálogo de Estratégias

`strategy_catalog.py` centraliza rótulos, descrições, disponibilidade por
modalidade e comandos de configuração. `GET /strategy_catalog/<modalidade>`
exige entrada no app e não consulta histórico nem modelos. O frontend monta
os 11 modos executáveis a partir desse cadastro, inclusive Pares/ímpares e
Filtro histórico forte usados separadamente. Não mantém uma segunda lista de
incompatibilidades em JavaScript ou botões duplicados manualmente no HTML.

Aleatório uniforme e Minhas regras/diversificação são comandos distintos para
abrir o painel próprio com o método correto. Não são enviados à antiga rota
de geração, que possui outra validação e limite de quantidade. Permanecem
Premium/admin. Os comandos têm semântica de botão; os modos executáveis têm
semântica de rádio, com navegação por setas e foco controlado.

Para acrescentar um modo, implemente a geração e disponibilidade no módulo de
loterias, registre seu ID em `GENERATION_MODES` e sua apresentação em
`MODE_PRESENTATION`. Os testes verificam a correspondência exata; modos sem
implementação não podem cair silenciosamente no gerador normal. Estatísticas
históricas e laboratório só devem ser ampliados com definições matemáticas
próprias, sem inventar porcentagens para ferramentas de configuração.

## 1. Validação da Sinergia e do Radar

`statistical_audit.py` trabalha exclusivamente com resultados públicos validados.
Para todos os pares da modalidade, calcula a cauda binomial unilateral de
coocorrências sob sorteios uniformes independentes. A probabilidade de um par
em um sorteio de k dezenas entre U é `k*(k-1)/(U*(U-1))`.

Todos os pares, não apenas os encontrados na sugestão, entram na correção de
falsas descobertas Benjamini–Yekutieli. O nível de 5% refere-se ao controle da
taxa esperada de falsas descobertas, não à chance de cada par estar correto.
Esse teste usa referência uniforme: não é teste de associação condicionado às
frequências marginais usadas no índice descritivo de afinidade. Não valida a
capacidade de prever jogos ou a integridade física dos sorteios.

O teste global compara o maior excesso entre pares com 199 históricos de mesmo
tamanho, simulados com dezenas sem reposição em cada concurso e independência
entre concursos. Usa `Generator.multivariate_hypergeometric` do NumPy com uma
unidade por dezena; amostrar uma matriz inteira sem reposição seria incorreto.
O valor p utiliza `(extremos+1)/(simulações+1)` e nunca é zero. Sua resolução
mínima é mostrada. Uma semente pública fixa torna a simulação reproduzível;
ela nunca é usada para gerar jogos particulares dos usuários.

A estabilidade entre duas metades do histórico continua sendo descritiva,
com o suporte mínimo e a afinidade suavizada já existentes. Nenhum par é
chamado de preditivo. Na consulta, a afinidade anterior é preservada como
descrição e a auditoria separada informa quantos pares passaram no teste e
quantos foram positivos nas duas metades.

O Laboratório compara os perfis estáticos viáveis de cada modalidade com a
referência combinatória exata e a faixa central de contagens nos históricos
simulados. Usa as mesmas definições de paridade, faixas, datas e números altos
do gerador, verificadas por teste de equivalência. Os valores p binomiais
bilaterais recebem correção BY em uma família separada dos pares. Não são
taxas de prêmios de apostas geradas, backtest de rentabilidade ou validação de
filtros dependentes da própria base (como Quentes/frios e filtro histórico).

O radar mantém o teste congelado 70/30 e adiciona três janelas posteriores de
20%, com treino expansivo inicial de 40%, 60% e 80%. O modelo permanece
congelado durante cada janela, as janelas de teste não se sobrepõem e saltos
de concurso são excluídos. Aplica-se à paridade e aos meses do Dia de Sorte.
O Brier usa as distribuições completas; a acurácia escolhe o perfil de maior
probabilidade, com desempate determinístico. Uma referência uniforme de meses
possui empate entre os 12 meses, não um mês comprovadamente superior.

O painel Premium “Confiabilidade das análises” apresenta os resultados e os
intervalos sem aparecer. Intervalos ausentes por falta de concursos não são
inventados. A cauda geométrica `(1-k/U)^intervalo` descreve uma ausência sob
independência; não aumenta a chance de a dezena sair em seguida.

## 2. Monte Seu Estilo e Diversificação

`constrained_generation.py` valida entradas estritas (inclusive rejeita booleanos
onde se espera inteiro), intervalos, duplicatas, interseção entre fixas/excluídas,
paridade viável, limites de soma, capacidade combinatória e limites básicos de
sobreposição. As regras são adaptadas às quatro modalidades.

Dois modos distintos:

- **Aleatório uniforme:** `secrets.SystemRandom.sample`, sem reposição dentro do
  jogo, com rejeição de jogos numéricos repetidos no lote. Não aceita filtros.
- **Minhas regras:** `scipy.optimize.milp`/HiGHS, com variáveis binárias e objetivo
  aleatório. Respeita fixas, exclusões, paridade, soma e sobreposição entre cada
  par de jogos do lote. Não é amostragem uniforme entre soluções viáveis nem
  busca de dezenas com chance maior.

O lote tem no máximo 20 jogos, busca total limitada a oito segundos e chamadas
ao solver limitadas a 0,4 segundo. Há um semáforo por processo para impedir fila
de otimizações simultâneas no mesmo worker. Soluções do solver são verificadas
novamente antes de serem usadas. Não se relaxam as regras silenciosamente.

A busca é incremental e pode ficar sem uma continuação mesmo quando outro lote
global seria possível. A mensagem distingue essa situação de uma prova de
inviabilidade global. Erro ou timeout descarta todo o lote; não salva jogos
parciais nem registra uso. Em sucesso, mantém o fluxo existente de salvamento
privado por proprietário e de registro de uso; essas duas operações mantêm as
fronteiras transacionais já existentes no projeto.

No Dia de Sorte, o mês pode ser fixo ou escolhido uniformemente por jogo.
A cobertura de meses do lote usa meses distintos, não a quantidade de apostas;
a chance numérica do prêmio principal não é ampliada por repetir o mesmo jogo
com outro mês. A cobertura matemática pressupõe o lote no mesmo concurso e
não representa expectativa de lucro. Lotes de até dez jogos podem ser enviados
diretamente à consulta existente; os demais continuam disponíveis no histórico.

Rotas: `GET /generation_rules/<modalidade>` e
`POST /generate_constrained/<modalidade>`. Ambas exigem Premium/admin; a segunda
também exige CSRF. O limite de tamanho de requisição e os controles de conta
existentes permanecem. Respostas privadas usam `Cache-Control: no-store`.

## 3. Boletim e Execução Offline

`build_draw_digest.py` produz somente fatos: concurso, data, paridade, soma,
faixas numéricas, pares consecutivos, repetição do concurso imediatamente
anterior quando disponível, mês e qualidade da base. O boletim público não
inclui palpites de usuários, probabilidades de “próxima estratégia” ou valores
de prêmio. Não liga comparações através de concursos ausentes.

`build_statistical_reports.py` reúne auditorias, validação, intervalos e boletins
em `src/public_lottery_reports.json`. O arquivo é incluído no Docker pela cópia
existente de `src/`. `public_reports.py` só lê os artefatos durante requisições:
nenhuma simulação ou otimização estatística é executada para abrir um painel.

Cada modalidade possui SHA-256 de seu CSV, normalizado apenas em CRLF/LF para
compatibilidade Windows/Linux. O relatório só é mostrado como atual quando o
conteúdo corresponde ao arquivo carregado. Base alterada sem novo relatório
produz estado “aguardando”, nunca substituição silenciosa por resultado antigo.
`RECIPE` deve ser incrementado quando mudar o significado dos cálculos. Arquivos
são validados e substituídos atomicamente apenas após geração completa.

O workflow `update-results.yml` executa testes, calendário, atualização dos CSVs,
geração/publicação dos relatórios e solicitação de deploy. Simulações ocorrem
fora do Render. Falha na atualização dos CSVs impede publicar relatórios sobre
arquivos parcialmente atualizados; uma atualização válida do calendário ainda
pode solicitar seu próprio deploy. A publicação só aceita os caminhos públicos
explicitamente autorizados, com conferência da estrutura e das bases.

Boletins usam `GET /draw_digest`, público e somente leitura. Auditorias usam
`GET /statistical_report/<modalidade>`, Premium/admin. Ambos usam `no-store`.
Os painéis reconsultam dados ao abrir; a auditoria também reconsulta enquanto
visível e após atualização administrativa. Sem mudança de base, parâmetros ou
receita, o script não regrava apenas o horário e não cria commits desnecessários.

## Comandos e Verificação

```text
python src/build_statistical_reports.py
python src/build_statistical_reports.py --resamples 499 --seed 1729
python -m unittest discover -s tests -v
node tests/browser_advanced.cjs
node tests/browser_analysis.cjs
```

O padrão é 199 simulações; o intervalo permitido é 19–1999. Mais simulações
melhoram a resolução do teste global, não a chance de acertar loterias. Preços,
pagamentos e faixas extremamente raras não são estimados por Monte Carlo: as
probabilidades exatas da consulta continuam usando combinatória.

Os testes de navegador criam contas e bancos temporários. Verificam geração,
salvamento, comparação, mês, relatório desatualizado, regras escondidas no modo
uniforme, proteção Premium e layouts em 320/390/1440 pixels nos dois temas.
Não usam o Supabase de produção nem alteram contas reais.

As APIs utilizadas já existem nas versões fixadas do projeto: SciPy 1.12
(`milp`, `binom`, `false_discovery_control`) e NumPy 1.26
(`Generator.multivariate_hypergeometric`). Referências:

- https://docs.scipy.org/doc/scipy-1.12.0/reference/generated/scipy.optimize.milp.html
- https://docs.scipy.org/doc/scipy-1.12.0/reference/generated/scipy.stats.false_discovery_control.html
- https://numpy.org/doc/1.26/reference/random/generated/numpy.random.Generator.multivariate_hypergeometric.html
