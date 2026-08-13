# Gerador de Jogos de Loterias

Este repositório contém o código-fonte de um aplicativo web interativo projetado para auxiliar entusiastas de loterias na geração de jogos. A aplicação oferece uma interface amigável para criar apostas para as principais loterias brasileiras, como Mega Sena, Lotofácil, Quina e Dia de Sorte, além de fornecer ferramentas de análise e um histórico organizado.

---

### **Projetista e Desenvolvedor Principal:**
* Everlan Santos

---

### **Funcionalidades Detalhadas:**

* **Geração Inteligente de Jogos:**
    Gere uma quantidade personalizável de jogos (de 1 a 100) para a loteria selecionada. Os números são gerados com base em análises de frequência de sorteios anteriores, utilizando um algoritmo que prioriza números "quentes" (mais sorteados) e "frios" (menos sorteados ou nunca sorteados), proporcionando uma abordagem mais estratégica do que a simples escolha aleatória.

* **Histórico Completo de Jogos:**
    Todos os jogos gerados são automaticamente salvos e organizados por tipo de loteria e data/hora. Os usuários podem acessar facilmente um histórico detalhado, visualizar os números de cada jogo em formato de "bolinhas" intuitivas, e gerenciar os arquivos de histórico, incluindo a opção de excluir registros específicos ou limpar o histórico de uma loteria inteira.

* **Assistência e Análise de Números:**
    Acesse uma funcionalidade de assistência que exibe os números considerados "quentes" (aqueles que mais apareceram em sorteios passados) e "frios" (aqueles que menos apareceram ou ainda não foram sorteados). Esta ferramenta oferece insights valiosos para aqueles que gostam de basear suas escolhas em estatísticas.

* **Cópia Rápida para Aposta:**
    Após gerar seus jogos, com um único clique, você pode copiar todos os números formatados diretamente para a área de transferência. Isso agiliza o processo de preenchimento de volantes físicos ou a inserção em plataformas de apostas online.

* **Personalização da Interface do Usuário:**
    Adapte a experiência visual da aplicação às suas preferências com um alternador de tema (claro/escuro). Além disso, a aplicação permite ajustar dinamicamente o tamanho da fonte, garantindo legibilidade e conforto visual para todos os usuários, independentemente do dispositivo ou preferências pessoais.

---

### **Base de Dados:**
Os dados históricos utilizados para a análise de números e a geração de jogos são obtidos e mantidos atualizados através do site:
* [asloterias.com.br](https://asloterias.com.br/home) - Uma fonte confiável para resultados e estatísticas de loterias.

---

### **Contas, planos e seguranca:**

O app separa visitantes, usuarios gratuitos, usuarios Premium e admin.

* **Visitante:** pode ver resultados e calendario.
* **Gratuito:** pode gerar jogos com limite diario em `FREE_DAILY_GAME_LIMIT`.
* **Premium:** libera recursos avancados, como assistencia de numeros quentes/frios e uso sem limite diario.
* **Admin:** pode atualizar dados e gerenciar planos dos usuarios.

As senhas nao sao salvas em texto puro. Elas ficam protegidas por hash seguro no banco configurado em `AUTH_DB_PATH`.

Os dados sensiveis ficam no arquivo `.env`, que nao deve ser enviado ao GitHub:

```env
APP_SECRET_KEY=gere-uma-chave-grande-e-aleatoria
ADMIN_EMAIL=admin@exemplo.com
ADMIN_SETUP_CODE=troque-este-codigo-inicial
PIX_KEY=sua-chave-pix
AUTH_DB_PATH=data/loterias_auth.sqlite3
FREE_DAILY_GAME_LIMIT=20
SESSION_COOKIE_SECURE=0
```

Para criar a primeira conta admin, use na tela **Criar Conta** o e-mail configurado em `ADMIN_EMAIL` e informe o codigo de `ADMIN_SETUP_CODE`. Depois disso, o admin consegue ver usuarios e trocar plano gratuito/Premium pela interface.

Em producao com HTTPS, configure:

```env
SESSION_COOKIE_SECURE=1
```

O Pix configurado aqui deve ser usado apenas para assinatura Premium do app. A aposta em loteria continua sendo finalizada pelo usuario no canal oficial.

---

### **Atualização automática dos resultados:**

Para baixar os resultados mais recentes da Mega Sena, Lotofácil, Quina e Dia de Sorte, execute o arquivo:

```bat
Atualizar Dados.cmd
```

O script acessa as páginas de download do site As Loterias, baixa as planilhas em ordem de sorteio, converte para CSV e substitui os arquivos que a aplicação já usa. Antes de substituir, ele cria um backup em `backups_loterias/`.

Também é possível rodar manualmente:

```bat
py -3 src\update_lottery_data.py
```

Para testar sem alterar os CSVs:

```bat
py -3 src\update_lottery_data.py --dry-run
```

O atualizador verifica o concurso salvo localmente antes de substituir os CSVs. Se o site informar o mesmo concurso que ja esta no projeto, ele pula a loteria e evita criar backup, alterar arquivo ou abrir publicacao sem necessidade.

Para atualizar e enviar os CSVs alterados ao GitHub em seguida, use:

```bat
Atualizar Dados e GitHub.cmd
```

Ou rode manualmente:

```bat
py -3 src\update_lottery_data.py --publish
```

Esse fluxo chama `src\publish_lottery_data.py`, que faz commit e push apenas dos CSVs que realmente foram atualizados. Para simular sem commitar nem enviar:

```bat
py -3 src\update_lottery_data.py --publish --publish-dry-run
```

Na interface web tambem existe o painel **Status dos Dados**, que mostra o concurso salvo localmente de cada loteria e permite acionar a atualizacao pelo botao **Atualizar Resultados**. Essa acao usa protecao admin quando `ADMIN_TOKEN` estiver configurado.

O sistema tambem faz manutencao automatica:

* o log `loterias.log` usa rotacao por tamanho;
* os backups antigos em `backups_loterias/` sao limpos pelo atualizador, mantendo por padrao as ultimas 5 pastas.

Se algum link do site mudar no futuro, você pode informar uma URL direta de download usando uma destas variáveis:

```bat
set ASLOTERIAS_MEGASENA_URL=https://...
set ASLOTERIAS_LOTOFACIL_URL=https://...
set ASLOTERIAS_QUINA_URL=https://...
set ASLOTERIAS_DIADESORTE_URL=https://...
```

---

### **Tecnologias Utilizadas:**

* **Backend:** **Python com Flask**
    Um microframework web leve e flexível, utilizado para criar a API que gerencia a lógica de geração dos números, o acesso aos dados históricos e o gerenciamento de arquivos.

* **Frontend:** **HTML, CSS (Tailwind CSS) e JavaScript**
    A interface do usuário é construída com HTML para estrutura, JavaScript para interatividade dinâmica e lógica de frontend, e Tailwind CSS para um design responsivo, moderno e altamente personalizável. O Tailwind permite a construção rápida de componentes e garante que a aplicação seja agradável e funcional em diferentes tamanhos de tela.

---
