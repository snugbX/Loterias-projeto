# Radar de padroes

## O que esta disponivel

Contas Premium e administrador tem acesso ao painel recolhido "Radar de padroes"
abaixo da consulta de jogos. A primeira versao analisa os perfis exatos de pares
e impares de Mega-Sena, Quina, Lotofacil e Dia de Sorte. O mes nao entra nesse radar.
Nao tenta prever modos dinamicos como "Quentes e frios" ou "Sem premio historico".

Por padrao compara o perfil do ultimo concurso com os concursos imediatamente
seguintes a ocorrencias anteriores do mesmo perfil. Tambem permite escolher outro
perfil anterior. A tabela mostra:

- Quantidade de ocorrencias e tamanho da amostra condicional.
- Frequencia condicional, frequencia geral e referencia matematica.
- Diferenca em pontos percentuais e intervalo aproximado de Wilson de 95%.
- Aviso para amostras menores que 30 transicoes.
- Periodo da base, ultimo concurso e falhas/lacunas encontradas.

Somente pares de concursos com numeros consecutivos entram nas transicoes.
Um salto de 100 para 102 nao e tratado como se fosse o proximo sorteio.

O teste temporal usa os primeiros 70% dos concursos para ajustar uma matriz de
transicoes, congelada antes de avaliar os 30% finais. A distribuicao de cada linha
e suavizada por 20 observacoes equivalentes da referencia matematica. Linhas sem
amostra voltam integralmente a referencia. A tela apresenta acerto do perfil modal
e Brier multiclasse, soma dos erros quadraticos por concurso (menor e melhor).
Nao e validacao independente definitiva; o recorte e recalculado a cada base nova.
Nao ha selecao automatica de estrategia vencedora nem promessa de vantagem.

Referencia matematica para k dezenas em universo N: a chance de e pares e
`C(floor(N/2),e) * C(ceil(N/2),k-e) / C(N,k)`.

Referencias metodologicas:
- Wilson: https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm
- Separacao treino/teste: https://otexts.com/fpp3/toolbox.html

Os intervalos sao aproximados e descritivos. Nao ajustam multiplas comparacoes
nem demonstram dependencia entre sorteios. Um perfil engloba varias combinacoes;
frequencia do perfil nao e a chance de uma aposta especifica ganhar.

## Atualizacao dos calculos

O radar nao mantem um segundo banco ou arquivo de estatisticas para sincronizar.
Usa o mesmo CSV validado da aplicacao e cache por caminho, data de modificacao
com precisao de nanossegundos, tamanho e configuracao de leitura. Quando o arquivo
e substituido, cada processo web recalcula sua propria copia na proxima consulta.

O atualizador verifica o radar apos cada CSV realmente alterado e informa no
console o concurso e o numero de transicoes. Se o arquivo nao mudou, nao recalcula.
Simulacao (--dry-run) nao atualiza CSV nem radar. A interface consulta o radar a
cada 60 segundos somente quando o painel esta aberto, visivel e o usuario e Premium;
tambem atualiza ao retornar a aba e apos atualizacao manual pela interface.

## Atualizacao periodica da base

O comando comum continua executando uma unica verificacao. Para manter verificando
a cada hora enquanto o processo estiver aberto:

```powershell
py src/update_lottery_data.py --watch --interval 3600 --no-publish
```

Intervalo permitido: 900 a 86400 segundos. Sem concurso novo, o atualizador evita
substituicao, backup e recalculo. Falhas sao reportadas e tentadas novamente no
ciclo seguinte. Uma trava de arquivo impede atualizacoes simultaneas entre o modo
periodico e o botao do administrador, desde que usem o mesmo diretorio de dados.

Para iniciar esse processo junto com `py app.py`, configure no ambiente:

```dotenv
LOTTERY_AUTO_UPDATE=1
LOTTERY_AUTO_UPDATE_INTERVAL=3600
```

No Render com o Dockerfile do projeto, essas mesmas variaveis ativam um processo
periodico dentro do mesmo servico que monta o disco persistente. O Procfile tambem
inclui esse inicio opcional. Em deploy nativo com Start Command personalizado,
o comando precisa incluir o processo periodico; apenas `gunicorn app:app` nao o inicia.
Exemplo quando o diretorio de trabalho e `src`:

```sh
sh -c 'python -u update_lottery_data.py --watch --interval 3600 --no-publish & exec gunicorn --bind 0.0.0.0:$PORT app:app'
```

Mantenha `LOTTERY_DATA_DIR` e os demais caminhos no disco persistente configurado.
O processo de atualizacao precisa acessar os mesmos arquivos do servidor web;
um worker separado com outro disco nao atualiza os CSVs deste servico.

Nao foi ativada nenhuma configuracao na conta Render. As variaveis precisam ser
adicionadas ao deploy. O modo automatico nao publica no GitHub. O fluxo manual
--publish permanece disponivel. Por padrao LOTTERY_AUTO_UPDATE esta desativado.

Isso e verificacao periodica, nao notificacao oficial de sorteio: depende da
disponibilidade da fonte e do atraso ate a proxima verificacao. O servico precisa
estar em execucao; quando estiver suspenso/desligado, nao consegue baixar dados.
Nao adicione o modo --watch ao Build Command.

## Testes

```powershell
python -m unittest discover -s tests -v
node tests/browser_analysis.cjs
```

Testes cobrem combinatoria, transicoes, lacunas, amostras vazias, intervalos,
separacao temporal, invalidacao do cache, permissoes e integracao com atualizador.
