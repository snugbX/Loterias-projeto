# Histórico, Favoritos e Conferência

## Regra Principal

Todo jogo começa como **não efetivado**, inclusive registros antigos e favoritos.
Somente a ação explícita de marcar **Efetivado**, informar o concurso do bilhete
e salvar permite conferir uma combinação. Desmarcar suspende imediatamente a
conferência. Favoritar, gerar ou abrir o histórico não efetiva uma aposta.

Essa informação é declarada pelo usuário: não existe integração que comprove
pagamento ou registro de aposta. O app mostra correspondência com faixas de
prêmio, não certifica bilhetes nem calcula valores de pagamento.

## Funcionalidades

- Histórico por jogo, em páginas de 20 itens, com filtros por dezenas (todas as
  informadas), período de geração, concurso, favoritos, efetivação e situação.
- Preferências por proprietário, arquivo e índice estável do jogo. Admins também
  acessam somente seu próprio histórico nestas rotas.
- Exclusão individual lógica preserva índices e os demais jogos do lote. As
  rotas antigas de leitura também omitem esses jogos. A exclusão de todo o
  histórico da modalidade remove os lotes, arquivos locais e preferências.
- Dezenas e concursos são validados no servidor. Alterações e exclusões exigem
  sessão e proteção CSRF; leituras privadas não são armazenadas em cache HTTP.
- Registros locais antigos em CSV continuam legíveis. Ao salvar a primeira
  preferência, o lote correspondente também é persistido no banco local.
- A consulta é limitada aos 1.000 lotes/50.000 jogos mais recentes por modalidade
  e avisa explicitamente quando esse limite é atingido.

## Conferência Adaptada

As faixas numéricas são reutilizadas de `game_analysis.PRIZE_MATCHES`:
Mega-Sena 4–6, Quina 2–5, Lotofácil 11–15 e Dia de Sorte 4–7. No Dia de Sorte,
o mês é conferido separadamente e pode produzir uma faixa mesmo sem acerto
numérico. Mês ausente na base gera indicação de conferência parcial, não perda.

Referências: [Mega-Sena](https://loterias.caixa.gov.br/Paginas/Mega-Sena.aspx),
[Quina](https://loterias.caixa.gov.br/Paginas/Quina.aspx),
[Lotofácil](https://loterias.caixa.gov.br/Paginas/Lotofacil.aspx) e
[Dia de Sorte](https://loterias.caixa.gov.br/Paginas/Dia-de-Sorte.aspx).

Concurso posterior ao último disponível fica aguardando resultado. Concurso
ausente, histórico indisponível ou dados inválidos nunca são classificados como
“sem prêmio”. A conferência é refeita sobre a base validada a cada consulta,
sem gravar resultados financeiros presumidos nem alterar as dezenas originais.

## Atualização Automática

O painel consulta novamente a cada 60 segundos enquanto aberto e visível e ao
retornar à aba. Não substitui edições de efetivação pendentes. Fechar o painel
cancela consultas e temporizadores; trocar conta ou modalidade limpa os dados.

O fluxo público existente continua atualizando os CSVs e solicitando o deploy
quando há novidades. O cron foi ampliado para as janelas posteriores aos sorteios
noturnos e de domingo, além da revisão matinal. Não é uma garantia de resultado
na hora exata: dependemos da publicação da fonte, do agendamento do GitHub e da
conclusão do deploy. Até lá, o concurso permanece aguardando.

Dados particulares de apostas, favoritos e efetivação **não** alimentam a base
pública e **não** são enviados ao GitHub pelo atualizador.

## Banco e Deploy

SQLite cria `history_tracking` automaticamente, com chave estrangeira e exclusão
em cascata por lote. PostgreSQL usa a migração idempotente
`src/migrations/002_history_tracking.sql`, no esquema privado existente.

Antes de publicar o código em um banco PostgreSQL ainda não atualizado:

```powershell
py src/manage_database.py --env-file .env.admin backup --output backups_privados/antes-historico.enc
py src/manage_database.py --env-file .env.admin upgrade
py src/manage_database.py --env-file .env.admin check
py src/manage_database.py --env-file .env.admin backup --output backups_privados/depois-historico.enc
```

`upgrade` não troca senhas, não altera dados e concede à conta restrita somente
as operações necessárias na nova tabela privada. Nunca envie `.env.admin`, a
chave de criptografia ou backups ao repositório. O backup criptografado inclui
as preferências; versões anteriores sem essa tabela continuam restituíveis.

## Testes

`tests/test_history_manager.py` cobre efetivação obrigatória, isolamento de
contas, favoritos, filtros, exclusão individual, regras das quatro modalidades,
mês, atualização da base, dados faltantes e rotas com sessão/CSRF.
`tests/browser_history.cjs` usa contas e bancos temporários para verificar a
navegação, paginação, favoritos, efetivação, exclusões, atualização automática,
temas e telas pequenas. A integração PostgreSQL existente também verifica
preferências, isolamento e exclusão em cascata no banco descartável do CI.
