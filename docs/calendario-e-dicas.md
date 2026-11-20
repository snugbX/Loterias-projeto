# Calendário e dicas do dia

O calendário consulta os PDFs mensais publicados na página oficial de regras dos
sorteios da CAIXA. Usa datas e concursos por modalidade, não uma lista fixa de
dias da semana. Assim, considera domingos, feriados e concursos especiais quando
constam no cronograma publicado.

- Fonte: https://loterias.caixa.gov.br/Paginas/regras-sorteios.aspx
- Rota pública, somente leitura: `GET /draw_calendar`.
- Semana de segunda a domingo, com datas no horário de Brasília.
- Cache em memória por processo: uma hora após sucesso; novas tentativas após
  cinco minutos em caso de falha. Não armazena dados de usuários.
- O deploy inclui `src/public_draw_calendar.json`, cópia validada do cronograma
  atual e, quando disponível, do mês seguinte. O Render usa essa cópia sem
  precisar baixar PDFs para atender cada reinício ou processo do servidor.
- A cópia pública é consultada nos horários do atualizador do GitHub Actions.
  Mudanças de programação são publicadas; sem mudanças, a data de verificação
  só é renovada após 12 horas, evitando commits a cada consulta. A validade de
  atualização é de 36 horas. Depois disso, a agenda fica marcada como antiga
  e a atualização direta em segundo plano continua disponível como tentativa.
- Downloads ocorrem em segundo plano. A rota responde imediatamente para que
  lentidão na CAIXA não ocupe o atendimento do app. Na primeira carga, a tela
  consulta a conclusão a cada cinco segundos, por até 30 segundos, enquanto a
  aba estiver visível. A rota também limita o estado de carregamento: falhas
  não deixam a mensagem “Consultando” eternamente.
- A tela verifica novidades a cada 15 minutos enquanto visível, ao voltar à aba
  e ao detectar uma nova data no Brasil. O botão consulta o cache compartilhado,
  sem disparar um download para cada clique.
- A data da última consulta é exibida. Se a fonte falhar, os dados anteriores
  ficam identificados como não confirmados. Sem dados anteriores, aparece
  “A confirmar”, nunca “Sem sorteios previstos”.
- Datas sem sorteio só são indicadas após leitura válida do cronograma mensal.
  Alterações no formato do PDF são rejeitadas em vez de adivinhadas. O link
  oficial continua disponível para conferência de avisos, horários e prazos.
- Não precisa de novo secret, banco ou disco persistente. O workflow existente
  publica a cópia validada e solicita o deploy mesmo quando só o calendário muda.
  A publicação aceita exclusivamente os quatro CSVs já permitidos e o caminho
  exato dessa cópia pública, com validação de campos; não inclui arquivos privados.

As dicas são editoriais, gratuitas e rotacionam por dia no Brasil. Incluem uma
orientação de uso/segurança/jogo responsável e um resumo da agenda do dia. Não
são recomendações de números nem previsões de resultados. Para editar os textos,
altere `daily_tips` em `src/draw_calendar.py`.

## Verificação

```text
python -m unittest discover -s tests -v
node tests/browser_calendar.cjs
```

O teste de navegador usa contas e banco temporários e respostas simuladas para
domingos, feriados e indisponibilidade. Não altera contas reais. As imagens de
verificação ficam em `tmp/calendar-qa`, fora do Git.
