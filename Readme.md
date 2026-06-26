# Gerador de Jogos de Loterias

Este repositório contém o código-fonte de um aplicativo web interativo projetado para auxiliar entusiastas de loterias na geração de jogos. A aplicação oferece uma interface amigável para criar apostas para as principais loterias brasileiras, como Mega Sena, Lotofácil e Quina, além de fornecer ferramentas de análise e um histórico organizado.

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

### **Atualização automática dos resultados:**

Para baixar os resultados mais recentes da Mega Sena, Lotofácil e Quina, execute o arquivo:

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

Se algum link do site mudar no futuro, você pode informar uma URL direta de download usando uma destas variáveis:

```bat
set ASLOTERIAS_MEGASENA_URL=https://...
set ASLOTERIAS_LOTOFACIL_URL=https://...
set ASLOTERIAS_QUINA_URL=https://...
```

---

### **Tecnologias Utilizadas:**

* **Backend:** **Python com Flask**
    Um microframework web leve e flexível, utilizado para criar a API que gerencia a lógica de geração dos números, o acesso aos dados históricos e o gerenciamento de arquivos.

* **Frontend:** **HTML, CSS (Tailwind CSS) e JavaScript**
    A interface do usuário é construída com HTML para estrutura, JavaScript para interatividade dinâmica e lógica de frontend, e Tailwind CSS para um design responsivo, moderno e altamente personalizável. O Tailwind permite a construção rápida de componentes e garante que a aplicação seja agradável e funcional em diferentes tamanhos de tela.

---
