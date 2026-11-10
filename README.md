# HJK Galvanoplastia — Orçamento de Acabamento ENIG  ·  versão 1.1

Aplicativo web para os clientes da HJK calcularem o orçamento do acabamento ENIG
e enviarem a solicitação pelo WhatsApp.

**Cliente informa os dados → servidor calcula o preço → cliente aprova → mensagem pronta no WhatsApp da HJK.**

> **Versão de testes, ainda não publicada.** Nada foi publicado em nenhuma conta.
> Para publicar, siga os manuais da pasta `docs/`, depois de aprovado por Gilmar.
>
> Novidades da 1.1 (resposta à revisão do Fernando): veja [RESPOSTA_REVISAO.md](RESPOSTA_REVISAO.md).

## Arquitetura

| Parte | Tecnologia | Custo |
|---|---|---|
| Páginas (cliente e administração) | HTML + CSS + JavaScript: **GitHub Pages** na fase de testes; **Cloudflare Pages** recomendado para uso comercial | gratuito |
| Banco, cálculo e login | **Supabase**, plano Free (PostgreSQL + Auth) | gratuito |
| Confirmação do pedido | Link `wa.me` para o WhatsApp oficial da HJK | gratuito |

- O **preço por cm²** e o **valor mínimo** ficam num esquema privado do banco, sem acesso pela API pública.
- O **cálculo** é feito por uma função no servidor, que valida as entradas e devolve apenas os resultados.
- **Limites contra consultas automatizadas:** 10 por minuto e 60 por hora por visitante (identificado pelo cabeçalho
  `cf-connecting-ip`, que o cliente não consegue forjar), mais 120 por minuto e 3.000 por dia no site todo.
- O **login do Josias** usa o Supabase Auth (e-mail e senha). Só quem está cadastrado como administrador altera os preços.
- Cada orçamento tem um **identificador com código de verificação de 40 bits** (`HJK-AAMMDD-XXXX-XXXXXXXXXX`) que cobre
  **todos** os dados da mensagem: empresa, referência, data e hora, medidas, quantidade, percentual e valor.
  Na administração, o Josias confere se a mensagem recebida pelo WhatsApp é autêntica.
- Não existe cadastro de clientes nem histórico de pedidos.

## Estrutura

```
index.html              Página do cliente
admin.html              Administração (Josias)
css/estilo.css          Visual
js/config.js            ← ÚNICO arquivo a editar: endereço e chave pública do Supabase
js/comum.js             Números, formatação e mensagem do WhatsApp
js/app.js               Lógica da página do cliente
js/admin.js             Lógica da administração
js/logo.js              Exibe o nome em texto se a imagem da logomarca faltar
js/vendor/              Biblioteca oficial supabase-js 2.119.0 (licença MIT)
assets/logo-hjk.png     Logomarca original da HJK, recortada (ver docs/07)
supabase/01_instalacao.sql        Cria tabelas, funções e permissões
supabase/02_cadastrar_josias.sql  Torna o usuário do Josias administrador
testes/                 Testes automatizados e capturas de tela
docs/                   Manuais
```

## Manuais

1. [docs/01_CONFIGURAR_SUPABASE.md](docs/01_CONFIGURAR_SUPABASE.md): criar o projeto gratuito e instalar o banco
2. [docs/02_ACESSO_DO_JOSIAS.md](docs/02_ACESSO_DO_JOSIAS.md): criar o login de administrador
3. [docs/03_PUBLICAR_NO_GITHUB.md](docs/03_PUBLICAR_NO_GITHUB.md): publicar na conta do Gilmar para testes (só após aprovação)
4. [docs/04_MANUAL_DO_JOSIAS.md](docs/04_MANUAL_DO_JOSIAS.md): alterar os dois preços e conferir orçamentos
5. [docs/05_LIMITES_CUSTOS_E_HOSPEDAGEM.md](docs/05_LIMITES_CUSTOS_E_HOSPEDAGEM.md): limites do plano gratuito e alternativa comercial
6. [docs/06_TRANSFERIR_PARA_HJK.md](docs/06_TRANSFERIR_PARA_HJK.md): transferir tudo para contas da HJK
7. [docs/07_LOGOMARCA.md](docs/07_LOGOMARCA.md): como a logomarca entra no site
8. [docs/08_PUBLICAR_NA_CLOUDFLARE.md](docs/08_PUBLICAR_NA_CLOUDFLARE.md): hospedagem recomendada para uso comercial
9. [testes/RELATORIO_DE_TESTES.md](testes/RELATORIO_DE_TESTES.md): resultado dos testes e roteiro de teste manual

## Testar no próprio computador (sem publicar)

Depois de configurar o Supabase (manual 1) e preencher `js/config.js`:

```
cd hjk-orcamentos-enig
python3 -m http.server 8000
```

Abra `http://localhost:8000` (cliente) e `http://localhost:8000/admin.html` (administração).
Abrir o arquivo com duplo clique não funciona, porque o navegador bloqueia as chamadas ao servidor.

## Fórmula

```
Área ENIG (cm²) = Largura (mm) × Comprimento (mm) × Quantidade × SFA (%) / 10.000
Valor calculado = Área ENIG × Preço por cm²            (arredondado a 2 casas)
Valor final     = MÁXIMO(Valor calculado; Valor mínimo por pedido)
```

O mínimo é aplicado uma única vez ao pedido completo. O SFA (Surface Finish Area do HQ DFM)
já soma as duas faces, por isso aceita até 200% e não é multiplicado por fator algum.
