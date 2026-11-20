# Revisão Entre Loterias e Assistência

## Correções Implementadas

- O ranking de números frios preserva a ordem de frequência. Antes, uma
  ordenação numérica posterior podia privilegiar dezenas menores em vez das
  menos frequentes. Empates são determinísticos e explicitados; não implicam
  diferença de chance futura.
- Quentes/frios e estatísticas dos modos usam o mesmo leitor de concursos
  validados da consulta e do radar. Dezenas fracionárias, linhas inválidas,
  duplicatas e conflitos seguem os mesmos critérios. Base indisponível retorna
  erro 503 em vez de um ranking vazio que parece válido.
- No Dia de Sorte, a assistência estatística inclui os 12 meses, contagens,
  frequência relativa apenas entre meses válidos e indicação de dados ausentes.
- O filtro histórico foi identificado como filtro de faixas fortes. Não
  alteramos os limiares existentes nem prometemos excluir qualquer prêmio:
  Mega-Sena: 4+; Quina: 4+; Lotofácil: 13+; Dia de Sorte: 5+ acertos numéricos.
  Faixas menores e Mês da Sorte não são todos excluídos. O texto da seleção
  recebe o limite específico da loteria a partir do backend.
- O link do Dia de Sorte aponta para a página oficial da modalidade, em vez
  de uma edição antiga do manual de produtos.

## Verificações

A cobertura automatizada confere quantidade, intervalo e unicidade das dezenas
e regras dos modos viáveis nas quatro loterias. Os modos impossíveis da
Lotofácil permanecem ocultos, assim como Datas da Sorte no Dia de Sorte, cujo
universo inteiro já vai até 31. A ajuda calcula a paridade correta: 3/3 na
Mega-Sena; 2/3 ou 3/2 na Quina; 7/8 ou 8/7 na Lotofácil; 3/4 ou 4/3 no Dia de
Sorte. Mês da Sorte continua exclusivo do Dia de Sorte.

As faixas da consulta permanecem Mega-Sena 4–6, Quina 2–5, Lotofácil 11–15 e
Dia de Sorte 4–7, além do mês independente. Essa revisão não amplia o app para
apostas compostas, não calcula pagamentos de prêmios e não constitui auditoria
de segurança exaustiva.

## Ajuda Contextual

O painel “Ajuda para usar o app” está disponível após login ou acesso visitante,
inclusive para contas gratuitas. O usuário escolhe um dos oito assuntos em um
seletor nativo: preparação do jogo, estratégias, filtro histórico, consulta,
radar, calendário, privacidade ou jogo responsável. O conteúdo muda com a
loteria selecionada e não precisa de chave de IA ou serviço externo.

`GET /user_assistance/<loteria>` requer acesso ao app e retorna somente textos
controlados, configurações públicas e o link oficial. Não recebe texto livre,
não grava conversas e não expõe jogos, usuários ou dados administrativos. As
respostas usam `no-store`; a interface descarta respostas antigas ao trocar
de conta/loteria e tem timeout e tentativa manual ao reabrir o painel.

A ajuda gratuita não libera estatísticas Premium: `/get_hot_cold_numbers`,
consulta e radar mantêm suas próprias verificações de acesso no servidor.
Não é chatbot preditivo nem atendimento humano. As explicações reforçam que
histórico, coocorrências e estratégias não garantem ganhos.

## Testes

```text
python -m unittest discover -s tests -v
node tests/browser_analysis.cjs
```

O teste de navegador cobre ajuda nas quatro modalidades, correspondência dos
modos visíveis com as capacidades do backend, meses na assistência, temas
claro/escuro no celular e acesso gratuito sem liberar os recursos Premium.
