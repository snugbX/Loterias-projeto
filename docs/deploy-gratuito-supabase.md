# Render gratuito + Supabase + GitHub Actions

## Antes de publicar

A senha do banco compartilhada no chat deve ser trocada antes da ativacao.
Nao envie a nova senha, DATABASE_URL, chave de backup ou Deploy Hook pelo chat.
A chave `sb_publishable_...` e publica e nao substitui a conexao PostgreSQL.
Nao precisamos de chave service_role para esta integracao.

O codigo esta preparado, mas criar/conectar as contas externas e configurar
os secrets sao etapas manuais. Nao publique esta versao no Render antes de
preparar o banco e o ambiente abaixo: ela recusa SQLite temporario no Render.

Se o Render esta em Auto Deploy, desative-o temporariamente antes de enviar
este codigo ao GitHub. Mantenha a versao atual ate concluir a migracao.

## Estrutura

- Render executa Flask e le CSVs publicos vindos do repositorio.
- Supabase PostgreSQL guarda contas, planos, uso diario, auditoria e historico.
- GitHub Actions testa o app e atualiza somente os cinco CSVs publicos.
- O schema `lottery_private` nao deve ser adicionado aos schemas expostos pela
  Data API. O navegador nunca recebe credenciais do banco.
- `lottery_app` e o usuario restrito do servidor. `postgres` so e usado na
  preparacao/migracao administrativa. O app recusa uma conexao com outro usuario.
- Sem DATABASE_URL, o app local continua usando SQLite. Com DATABASE_URL, falhas
  no banco externo nunca causam retorno silencioso para um SQLite vazio.

## 1. Preparar o Supabase

1. Abra seu projeto no painel Supabase e troque a senha do banco.
2. Em **Connect**, escolha **Session pooler** e copie a conexao PostgreSQL.
   Nao tente adivinhar o host pela URL publica do projeto: o pooler tem outro host.
   A conexao de sessao funciona por IPv4 e normalmente usa a porta 5432.
3. Na configuracao do banco, baixe o certificado raiz em **SSL Configuration**.
   Ative a exigencia de SSL no painel, quando disponivel.
4. Escolha uma senha forte e diferente para o usuario do app, com pelo menos
   24 caracteres. Essa senha sera DATABASE_APP_PASSWORD apenas na preparacao.

O formato administrativo do Session pooler e semelhante a:

```text
postgresql://postgres.REFERENCIA:SENHA_CODIFICADA@HOST_DO_POOLER:5432/postgres
```

Caracteres especiais da senha devem ser percent-encoded na URL. Por exemplo,
`#` vira `%23`, `+` vira `%2B`, `%` vira `%25` e `@` vira `%40`.
Use a URL correta do painel, nao a URL `https://...supabase.co` do projeto.

## 2. Preparar localmente a estrutura privada

Instale as dependencias atualizadas no computador usado para administrar:

```powershell
py -m pip install -r src/requirements-admin.txt
```

Esse conjunto e suficiente para configurar, migrar e fazer backup, sem instalar
NumPy/scikit-learn. O servidor do Render e o CI usam Python 3.11 e o conjunto
completo `src/requirements.txt`. Nao e necessario trocar o Python local apenas
para executar a configuracao administrativa.

Opcao guiada, sem digitar senhas em comandos nem envia-las ao chat:

```powershell
py src/manage_database.py configure
```

Informe a referencia do projeto, o host do Session pooler, o caminho do
certificado baixado e a nova senha do banco (oculta). O comando gera senhas
aleatorias para o usuario restrito e o backup; nao faz conexoes externas nem
sobrescreve arquivos existentes. Prepara `.env.admin` para as operacoes locais
e `.env.render` apenas com as variaveis do servidor. Ambos sao ignorados pelo Git.
No Render, as variaveis de `.env.render` podem ser preenchidas pela opcao de
adicionar variaveis a partir de um arquivo .env. Nao envie esse arquivo ao chat.
Mantenha tambem sua APP_SECRET_KEY fixa e as variaveis admin/Pix existentes.

Se usou a opcao guiada, avance para o comando `init` abaixo. Alternativa manual:

Use `.env.admin.example` como referencia para preencher um arquivo local
`.env.admin` com os campos abaixo. `.env.admin` ja e ignorado pelo Git.

```dotenv
DATABASE_ADMIN_URL=CONEXAO_ADMINISTRATIVA_DO_SESSION_POOLER
DATABASE_APP_PASSWORD=SENHA_FORTE_EXCLUSIVA_DO_APP
DATABASE_SSLMODE=verify-full
DATABASE_SSLROOTCERT=CAMINHO_ABSOLUTO_DO_CERTIFICADO_BAIXADO
LOTTERY_BACKUP_KEY=CHAVE_FERNET_GERADA_LOCALMENTE
```

Para gerar a chave de backup no seu proprio terminal (nao envie o resultado):

```powershell
py -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Guarde uma copia da chave em um gerenciador de senhas ou outro local seguro,
separado dos arquivos .enc. Sem a chave nao e possivel recuperar o backup.
Proteja tambem o arquivo administrativo pelas permissoes do seu computador.

Prepare as tabelas e o usuario restrito:

```powershell
py src/manage_database.py --env-file .env.admin init
```

Esse comando cria o schema privado e define a senha do usuario `lottery_app`.

Se a senha administrativa tiver sido digitada incorretamente ou for trocada no
Supabase, corrija somente a configuracao local com digitação oculta:

```powershell
py src/manage_database.py --env-file .env.admin update-admin-password
```

Esse comando nao troca a senha no Supabase: informe a senha atual correta do
painel. Ele nao altera a senha aleatoria do app nem a chave dos backups.
Nao cria usuarios do site e nao importa nem apaga dados. Reexecutar o comando
redefine a senha de lottery_app para DATABASE_APP_PASSWORD: mantenha-a alinhada
com a conexao configurada no Render.

## 3. Migrar dados existentes, se houver backup confiavel

Use bancos SQLite da mesma instalacao de origem. Um arquivo local de teste nao
e necessariamente o banco de producao. Pare geracoes e cadastros na origem
durante a exportacao para que contas e historicos correspondam entre si.

Se os dados existiam apenas no disco temporario do Render e ja foram apagados,
este processo nao consegue recupera-los. O plano gratuito nao oferece shell SSH;
nao exponha um endpoint publico para baixar o banco ou a configuracao.

Primeiro, valide a origem e gere um backup criptografado sem tocar no destino:

```powershell
py src/manage_database.py --env-file .env.admin migrate --auth-db data/loterias_auth.sqlite3 --history-db data/loterias_history.sqlite3 --output backups_privados/antes-migracao.enc
```

Confirme os caminhos reais. O historico local pode estar em
`resultados_Loterias/loterias_history.sqlite3` em instalacoes antigas. Se nao
existir banco de historico, omita --history-db; as contas ainda podem ser migradas.
Nao omita um banco existente por engano: o destino so aceita importacao quando
estiver vazio. O backup nao sobrescreve arquivos existentes.

Confira o backup e depois importe em um Supabase vazio:

```powershell
py src/manage_database.py --env-file .env.admin verify-backup backups_privados/antes-migracao.enc
py src/manage_database.py --env-file .env.admin restore backups_privados/antes-migracao.enc --apply
```

IDs, emails, hashes de senha e planos sao preservados. Usuarios nao precisam
trocar a senha do site. Historicos com proprietario sao preservados; registros
antigos sem proprietario permanecem `legacy`, sem serem atribuídos a outra conta.
Para incluir tambem CSVs que nunca entraram no SQLite, acrescente
`--history-dir resultados_Loterias` ao comando migrate. Arquivos na raiz ficam
como `legacy`; pastas `user_ID` precisam corresponder a uma conta da mesma origem.
CSVs ja presentes no banco sao conferidos sem duplicacao. Divergencias entre CSV
e banco interrompem a operacao, sem sobrescrever registros. Mantenha os originais.
Referencias de historico para contas ausentes fazem a migracao falhar, sem
confirmar nenhuma parte da importacao. Um destino nao vazio nao e sobrescrito.

Se nao houver dados antigos, pule a importacao e crie as contas no site depois
da ativacao. Configure ADMIN_EMAIL e um ADMIN_SETUP_CODE forte para o primeiro admin.

## 4. Configurar o ambiente do Render

No servico existente, abra **Environment**. Mantenha suas variaveis de admin/Pix
e configure:

```dotenv
DATABASE_URL=CONEXAO_DO_SESSION_POOLER_COM_USUARIO_LOTTERY_APP
DATABASE_SSLMODE=verify-full
DATABASE_SSLROOTCERT=/etc/secrets/supabase-ca.crt
APP_SECRET_KEY=SEGREDO_FIXO_FORTE_DO_APP
SESSION_COOKIE_SECURE=1
LOTTERY_USE_ML=0
LOTTERY_AUTO_UPDATE=0
LOTTERY_PUBLISH_AFTER_UPDATE=0
LOTTERY_AUTO_OPEN_BROWSER=0
```

A conexao do app usa a senha do usuario restrito criada no passo 2, nao a senha
do postgres. Pelo Session pooler, o usuario e `lottery_app.REFERENCIA`:

```text
postgresql://lottery_app.REFERENCIA:SENHA_DO_APP_CODIFICADA@HOST_DO_POOLER:5432/postgres
```

Adicione o certificado baixado como **Secret File** chamado `supabase-ca.crt`.
O caminho deve corresponder a DATABASE_SSLROOTCERT. Nao desative a verificacao
SSL para contornar erro de certificado ou conexao.

No Windows, o driver pode nao reconhecer acentos no caminho do certificado.
O app contorna isso com uma copia temporaria apenas do certificado publico em
um caminho ASCII. A copia e removida depois da conexao; verify-full permanece ativo.
Se o driver do Windows rejeitar caracteres internacionais na senha, o app usa
o parametro oficial `passfile` do PostgreSQL. Esse arquivo temporario fica no
diretorio privado do usuario, nao e registrado em logs e e removido apos a
autenticacao. O mecanismo nao altera a senha nem desativa SSL. Configuracoes de
backup e de conexao nunca devem ser compartilhadas por chat ou repositorio.

Nao coloque DATABASE_ADMIN_URL, DATABASE_APP_PASSWORD ou LOTTERY_BACKUP_KEY no
Render: o processo web so precisa de DATABASE_URL do usuario restrito.
Nao altere APP_SECRET_KEY a cada rebuild. Use um valor forte e fixo; se o valor
antigo nao e confiavel, troque-o uma vez e aceite que as sessoes sejam encerradas.

Configure o **Health Check Path** como `/health`. O Dockerfile atual continua
valido. Em deploy Python nativo, use `src` como diretorio de trabalho e:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn --bind 0.0.0.0:$PORT app:app
```

Nao e necessario disco pago para contas e historicos. AUTH_DB_PATH e
LOTTERY_HISTORY_DB nao sao usados quando DATABASE_URL esta configurada.
Pastas de log e de CSV publico podem continuar temporarias: nao armazenam os
dados privados autoritativos. Nao ative o atualizador dentro do Render nesse
fluxo; o Actions atualiza os CSVs no repositorio, que chegam no proximo deploy.

## 5. Configurar o GitHub Actions e o deploy

1. No Render, abra **Settings > Deploy Hook** do servico e obtenha o hook.
2. No GitHub, abra **Settings > Secrets and variables > Actions** e crie o
   repository secret `RENDER_DEPLOY_HOOK` com esse valor. Nao o envie pelo chat.
3. Mantenha o Auto Deploy do Render desativado para evitar publicacao antes dos
   testes e builds duplicados. O workflow CI solicita o deploy depois dos testes.
4. Envie o codigo e configure as permissoes de Actions para permitir ao workflow
   de resultados escrever no repositorio. Regras de protecao da branch podem
   exigir ajuste ou um fluxo de pull request; nao use force push.
5. Em **Actions**, execute manualmente **Atualizar resultados publicos** para
   conferir a fonte. A agenda faz tres verificacoes ao dia, em UTC: 01:17,
   04:17 e 12:17 (22:17 do dia anterior, 01:17 e 09:17 na Bahia).

O CI tem PostgreSQL descartavel para testar o acesso real ao banco, sem usar
credenciais de producao. Pull requests so testam; nao recebem o Deploy Hook.
O workflow agendado publica apenas os cinco CSVs oficiais permitidos e chama
o Deploy Hook somente se houve commit novo. Nenhum banco, historico privado,
senha, certificado ou backup entra nos commits/artifacts.

Push feito por GITHUB_TOKEN nao aciona outro workflow de push. Por isso o proprio
workflow de resultados executa testes e solicita o deploy depois de publicar.
O hook apenas solicita o deploy: confira a conclusao no Render. Se o hook falhar
depois do commit dos CSVs, solicite Manual Deploy no Render para aplicar o commit.
Se RENDER_DEPLOY_HOOK estiver ausente, a etapa informa que nao solicitou deploy.

Agendas do GitHub podem atrasar; em repositorios publicos inativos podem ser
desativadas pelo GitHub. O agendamento depende da disponibilidade da fonte e dos
limites da sua conta. Ele nao e uma notificacao instantanea de sorteio.

## 6. Conferir e manter

- Confira `/health`, cadastro/login, alteracao de plano e historicos separados.
- Gere um jogo, refaca o deploy e confira se a conta e o historico continuam.
- Teste que uma conta nao consegue ler o historico de outra.
- Nao apague os backups de origem antes de concluir essa verificacao.
- O Supabase gratuito pode pausar por inatividade e tem limites. A pausa exige
  restauracao pelo painel; nao e motivo para o app recriar contas localmente.
- O Render gratuito pode dormir, mas as contas continuam no banco externo.

## Backup e restauracao

Execute periodicamente no computador administrativo (por exemplo, semanalmente
e antes de alteracoes importantes), com nome diferente para cada copia:

```powershell
py src/manage_database.py --env-file .env.admin backup --output backups_privados/backup-AAAA-MM-DD.enc
py src/manage_database.py --env-file .env.admin verify-backup backups_privados/backup-AAAA-MM-DD.enc
```

Mantenha uma copia criptografada fora do computador e a chave separada. Nao ha
backup automatico ativado nesta entrega. A copia cobre as quatro tabelas privadas
do aplicativo, nao todo o projeto Supabase nem outros schemas.

Para restaurar, prepare um novo destino vazio com `init` e use `restore ... --apply`.
Nao use comandos de exclusao no banco ativo para forcar a restauracao. Teste a
recuperacao em um projeto separado antes de depender do backup.

## Fontes

- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/docs/guides/platform/ssl-enforcement
- https://supabase.com/pricing
- https://render.com/docs/free
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow
