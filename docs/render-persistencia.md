# Persistencia no Render

No Render, o filesystem do app e efemero por padrao. Em rebuild, redeploy ou restart,
tudo que foi gravado fora do disco persistente pode sumir.

## Solucao recomendada

Crie um Persistent Disk no servico do Render com:

```text
Mount path: /app/data
Size: 1 GB ou mais
```

Depois configure estas variaveis de ambiente no Render:

```env
AUTH_DB_PATH=/app/data/loterias_auth.sqlite3
LOTTERY_HISTORY_DB=/app/data/loterias_history.sqlite3
LOTTERY_OUTPUT_DIR=/app/data/resultados_Loterias
LOTTERY_DATA_DIR=/app/data/lottery_data
LOTTERY_BACKUP_DIR=/app/data/backups_loterias
LOTTERY_LOG_FILE=/app/data/logs/loterias.log
SESSION_COOKIE_SECURE=1
LOTTERY_AUTO_OPEN_BROWSER=0
```

Mantenha tambem as variaveis secretas do projeto:

```env
APP_SECRET_KEY=uma-chave-grande-e-aleatoria
ADMIN_EMAIL=seu-email-admin
ADMIN_SETUP_CODE=seu-codigo-inicial
PIX_KEY=sua-chave-pix
```

## O que fica salvo

Com essa configuracao, sobrevivem aos rebuilds:

- contas e planos dos usuarios;
- historico de jogos por conta;
- CSVs atualizados das loterias;
- backups dos CSVs;
- logs do app.

## Observacoes

- Sem Persistent Disk, o Render apaga os dados gravados localmente a cada rebuild.
- Apenas arquivos dentro de `/app/data` ficam preservados.
- Discos persistentes ficam disponiveis em runtime, nao durante o build.
- Se usar o plano gratuito sem disco persistente, a alternativa correta e trocar SQLite/arquivos por um banco externo, como Render Postgres ou Supabase.
