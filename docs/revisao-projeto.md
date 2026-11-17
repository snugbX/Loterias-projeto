# Revisao do projeto - 17/11/2026

## Escopo

Revisao local de autenticacao, permissoes, historico, arquivos publicos,
persistencia, geracao, estrategias e integracao do frontend. Nao equivale a
um teste de invasao, auditoria de dependencias ou verificacao do Render em producao.
Nenhum segredo, conta real ou historico foi alterado para os testes.

As quatro bases locais revisadas terminam em 11/10/2026. Atualizar os resultados
antes de apresentar a consulta como atualizada; os calculos historicos usam apenas
o que esta nesses arquivos, nao uma consulta online ao ultimo concurso.

## Situacao atual

- Flask e frontend modular, com quatro loterias e separacao de visitante,
  gratuito, Premium e administrador.
- Senhas com hash PBKDF2 e salt; cookies HttpOnly/SameSite e CSRF nas principais
  operacoes autenticadas. Hash de senha nao e criptografia reversivel.
- Historicos consultados por proprietario tanto no SQLite quanto nos CSVs.
- Caminhos de dados configuraveis para disco persistente; o disco e as variaveis
  precisam estar configurados no Render. O repositorio nao confirma essa configuracao.
- Nova consulta isolada em `src/game_analysis.py` e `src/js/gameAnalysis.js`.
- Testes de servico e rotas em `tests/test_game_analysis.py`.

## Prioridades encontradas

1. **Alta: cadastro inicial do administrador.** Em `src/app.py`, `auth_register`
   concede o papel admin ao email configurado quando nao existe admin. O codigo
   inicial so e exigido se `ADMIN_SETUP_CODE` estiver preenchido. Exigir um codigo
   forte e impedir esse cadastro quando nao houver configuracao segura; considerar
   provisionamento administrativo fora do cadastro publico. Nao foi alterado aqui
   para nao bloquear a configuracao existente sem uma migracao planejada.
2. **Alta: limites de abuso.** `LOGIN_ATTEMPTS` existe somente na memoria de cada
   processo, cresce com novos emails e nao cobre cadastro/consultas. `/auth/guest`
   cria uma nova sessao com contador zerado. Adotar limites compartilhados por
   conta/IP, expiracao dos registros e controle de concorrencia. A consulta nova
   tem validacao, limite de corpo e cache de quatro bases, mas ainda precisa desse
   controle distribuido antes de atender volumes maiores.
3. **Alta: segredo e persistencia em producao.** `APP_SECRET_KEY` ausente gera
   chave aleatoria por processo, invalidando sessoes entre reinicios/workers.
   Validar configuracao na inicializacao de producao; manter cookie Secure, backup
   externo e teste de restauracao. Criar disco nao substitui backup. Nao trocar
   caminhos de bancos existentes antes de exportar os dados que ainda existirem.
4. **Media: validacao das rotas antigas.** Varias rotas de autenticacao aceitam
   JSON sem confirmar objeto e tipos antes de usar `.get`/`.strip`. O aceite usa
   `bool(...)`, portanto uma string nao vazia como `"false"` pode ser aceita.
   Padronizar validacao estrita e respostas JSON; usar a nova consulta como exemplo.
5. **Media: significado de Sem premio historico.** O gerador existente verifica
   4+ acertos na Mega-Sena/Quina, 13+ na Lotofacil e 5+ no Dia de Sorte. Isso nao
   inclui todas as faixas da Quina/Lotofacil/Dia de Sorte, nem o mes. A consulta
   verifica todas as faixas atuais, mas preserva a classificacao do filtro antigo
   e explica seu alcance. Decidir entre renomear o modo para "Sem premios maiores
   na base" ou mudar o filtro, considerando que pode nao haver combinacoes viaveis.
6. **Media: armazenamento e migracoes.** SQLite e CSV duplicam registros; erros
   ao salvar podem ser apenas registrados no log, enquanto o jogo e entregue.
   Centralizar a fonte de verdade, tornar falhas visiveis, testar migracoes
   concorrentes e consolidar a normalizacao de diretorios de proprietario.
7. **Media: manutencao e dependencias.** Ha versoes fixadas antigas, sem auditoria
   de vulnerabilidades executada nesta revisao. Revisar compatibilidade e atualizar
   com testes. Tailwind via CDN adiciona dependencia externa ao carregamento;
   preferir CSS compilado local e planejar CSP/cabecalhos de seguranca.
8. **Media: arquitetura e cobertura.** `src/app.py`, `src/gerador_loterias.py` e
   `src/js/main.js` concentram muitas responsabilidades. Extrair servicos/blueprints
   progressivamente, adicionar testes de isolamento de historico, geracao, atualizacao,
   limites e restauracao, e executa-los no CI. Evitar uma reescrita ampla de uma vez.

## Melhorias entregues nesta rodada

- Consulta somente para Premium/admin, validada no servidor com CSRF.
- Aposta simples: 6 Mega-Sena, 5 Quina, 15 Lotofacil, 7 + mes Dia de Sorte.
- Todas as faixas numericas e o mes; concursos premiaveis contados uma unica vez,
  mesmo quando mes e dezenas coincidem. Lista dos 30 mais recentes, resumo de toda
  a base valida e aviso de lacunas, linhas descartadas e meses ausentes.
- Probabilidades combinatorias exatas por faixa; chance de qualquer premio no
  Dia de Sorte desconta a sobreposicao entre mes e dezenas.
- Compatibilidade com estrategias existentes, perfil par/impar, soma e sequencias.
  Nao e possivel deduzir o algoritmo usado apenas pelas dezenas finais.
- Historico e apresentado como simulacao pelas regras atuais, nao como comprovante
  de pagamento ou reconstituicao das regras antigas de cada concurso.
- Arquivos estaticos somente pela lista de permissoes; rota automatica do Flask
  desativada. Corpo de requisicoes limitado a 16 KiB. Correcoes de texto no cliente.
- Consulta recolhida, cores do tema, campos rotulados, foco de teclado, avisos
  persistentes na propria consulta e cancelamento/limpeza ao mudar conta ou loteria.
- A consulta nao salva os palpites nem os envia a servicos externos.

## Regras e calculos

Para aposta simples com k dezenas em universo N, a chance de exatamente r acertos
e `C(k,r) * C(N-k,k-r) / C(N,k)`. A chance do premio principal e `1 / C(N,k)`.
No Dia de Sorte o mes tem chance `1/12`, independente dos numeros; a uniao de
qualquer premio e `1 - (1 - P(premio numerico)) * 11/12`.

- Mega-Sena: https://loterias.caixa.gov.br/Paginas/Mega-Sena.aspx
- Quina: https://loterias.caixa.gov.br/Paginas/Quina.aspx
- Lotofacil: https://loterias.caixa.gov.br/Paginas/Lotofacil.aspx
- Dia de Sorte: https://www.caixa.gov.br/Downloads/loterias-manual-de-produtos/MANUAL_DE_PRODUTOS_v19.pdf

Uma combinacao especifica nao ganha mais chance por parecer equilibrada ou por
nunca ter sido premiavel. Frequencia historica nao e probabilidade futura.

## Verificacao local

Testes: `python -m unittest discover -s tests -v` (ou `py -m unittest discover -s tests -v`).
Teste visual: `node tests/browser_analysis.cjs`, com Playwright e Edge instalados.
O teste visual cria contas em banco temporario e encerra o servidor de teste ao final.
Capturas PNG em `tests/` sao ignoradas pelo Git.
