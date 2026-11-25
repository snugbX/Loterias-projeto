# Barra da conta

A navegação reúne marca, identidade e plano, consumo diário e ações da conta.
O e-mail completo quebra linhas quando necessário. Não há novo armazenamento
de dados pessoais, mudança de autenticação ou consulta adicional ao servidor.

## Integração

- Os IDs e os eventos de Pix, usuários, entrada e saída foram preservados.
- `renderAccountState` mantém as regras existentes de acesso e visibilidade.
- `renderAccountUsage` usa exclusivamente o consumo informado pelo servidor.
  O medidor aparece somente para acessos com limite diário; ele não controla
  nem concede permissões. Os limites continuam sendo validados no servidor.
- Os novos ícones são SVGs locais do Lucide 0.468.0, com a licença existente.
- A barra usa uma linha em telas largas e reorganiza os grupos nas menores,
  com botões de pelo menos 44 px, rótulos acessíveis e foco de teclado visível.

## Testes

`tests/browser_account.cjs` usa uma prévia isolada em 5118, contas descartáveis
e respostas de sessão simuladas para os estados de administrador e nomes
longos. Não altera contas reais nem concede privilégios de administrador.
Confere visitante, gratuito, Premium e administrador, temas claro e escuro,
larguras de 320 a 1440 px, fonte ampliada, Pix, saída e retorno ao login.
Capturas `tests/account-*.png` são arquivos gerados ignorados pelo Git.
