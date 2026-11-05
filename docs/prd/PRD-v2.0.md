# PRD v2.0 — Backup de Configurações de Switches (versão simplificada)

| Campo | Valor |
| --- | --- |
| Versão | 2.0 — aprovado em 2026-11-04 |
| Data | 2026-11-04 |
| Substitui | PRD v1.1 (escopo reduzido; o v1.1 não é versionado neste repositório) |
| Metodologia | SDD — Spec-Driven Development (ver `docs/PLANO.md`) |
| Ambiente | Servidor único de produção, on-premises |

> Valores marcados com **[HIP]** são hipóteses a confirmar nas pendências (seção 10).

## 1. Objetivo

Fazer, de forma automática e diária, o backup da configuração dos switches da rede, guardar um histórico verificável dessas configurações e mostrar, em um dashboard claro e bonito, a **saúde dos backups**: quais switches estão em dia, quais falharam e há quanto tempo.

O sistema deve ser **o mais simples possível**. Tudo o que não contribui diretamente para "ter o backup em dia e saber disso em um olhar" fica fora.

## 2. Regras invioláveis

| ID | Regra |
| --- | --- |
| R-01 | **Produção.** O servidor de implantação é produção. Nenhuma ação é executada fora dele. |
| R-02 | **Impacto em rede exige aprovação.** Qualquer ação que possa ter impacto mínimo na rede (conectar a um switch, baixar imagens ou pacotes, `git push`, abrir porta, alterar firewall, mudar horário ou concorrência da coleta) é informada antes e só é executada após aprovação explícita. |
| R-03 | **Zero processamento no frontend.** O navegador apenas exibe HTML e CSS gerados pelo servidor. Não há JavaScript próprio; gráficos são SVG gerados no servidor; filtros, ordenação, diff e validações acontecem no backend. |
| R-04 | **Somente leitura nos switches.** O sistema envia apenas comandos de uma lista permitida por tipo de switch e nunca altera configuração. |
| R-05 | **Segredos protegidos.** Senhas nunca aparecem em texto puro no banco, em logs, no git ou nas telas. |
| R-06 | **SDD.** Nada é implementado sem especificação aprovada (ver `docs/PLANO.md`). |

## 3. Usuários

| Perfil | Pode |
| --- | --- |
| Administrador | Tudo: switches, credenciais, horário da coleta, usuários, backup manual |
| Leitura | Ver dashboard, histórico, diferenças e baixar configurações |

Sem MFA, LDAP ou SSO nesta versão.

## 4. Requisitos funcionais

| ID | Requisito | Critério de aceite |
| --- | --- | --- |
| F-01 | Cadastro de switches: nome, IP, tipo (fabricante/SO), porta SSH, credencial, ativo/inativo | Nome e IP únicos; campos obrigatórios validados no servidor |
| F-02 | Credenciais cifradas e reutilizáveis entre switches | Trocar a credencial uma vez vale para todos os switches associados na próxima coleta |
| F-03 | Coleta da configuração corrente por SSH, com comando definido por tipo de switch | Apenas comandos da lista permitida são enviados (teste automatizado) |
| F-04 | Validação da saída: não vazia, tamanho mínimo, sem mensagem de erro, marcador de fim quando o tipo tiver | Saída truncada nunca vira backup válido |
| F-05 | Armazenamento: cada execução é registrada; nova versão de arquivo só quando a configuração muda (após ignorar linhas voláteis, como data e hora) | Duas coletas iguais geram 1 versão e 2 execuções; arquivo com SHA-256 registrado |
| F-06 | Coleta diária agendada (horário configurável) e botão "Fazer backup agora" (por switch e geral) | Coleta inicia no horário configurado; backup manual registra o usuário |
| F-07 | Até 2 retentativas com 5 min de intervalo [HIP]; falha de autenticação não é retentada | Falha de senha não bloqueia a conta no switch |
| F-08 | Histórico por switch: versões, download e diferença entre duas versões, calculada no servidor | Diff mostra linhas adicionadas e removidas |
| F-09 | Dashboard de saúde (seção 5) | Em até 10 s um operador identifica quem está com problema |
| F-10 | Login com usuários locais, senha com hash Argon2, sessão com expiração | Sem login, nenhuma página além de `/login` e `/health` |
| F-11 | Registro de eventos: login, alterações de cadastro, backups manuais | Cada evento tem usuário, horário e ação |
| F-12 | Verificação de chave SSH do switch: a primeira chave é registrada; se mudar, a coleta falha com aviso | Chave diferente gera falha `CHAVE_HOST` e não coleta |
| F-13 | Retenção: manter versões por 365 dias [HIP], preservando sempre a última versão válida | Limpeza nunca remove a versão mais recente de um switch |

## 5. Dashboard de saúde

### 5.1. Estado de cada switch

| Estado | Regra |
| --- | --- |
| Saudável | Último backup válido há menos de 26 h [HIP] e a última tentativa teve sucesso |
| Atenção | A última tentativa falhou, mas existe backup válido com menos de 48 h; ou o último backup válido tem entre 26 e 48 h |
| Crítico | Sem backup válido há mais de 48 h, ou nunca teve backup |
| Inativo | Switch desativado no cadastro (não entra nos percentuais) |

### 5.2. Conteúdo

1. **Indicador principal:** percentual de switches saudáveis, em destaque.
2. **Contadores** por estado (Saudável, Atenção, Crítico, Inativo).
3. **Último ciclo:** início, duração, quantidade de sucessos e falhas.
4. **Lista de switches** ordenada por gravidade (Crítico primeiro), com idade do último backup válido, motivo da última falha e uma faixa dos últimos 14 dias (um quadrado por dia: sucesso, falha ou sem execução).
5. **Falhas por motivo** (conexão, tempo esgotado, autenticação, chave SSH, saída incompleta).
6. **Alterações detectadas** nos últimos 7 dias, com link para o diff.

### 5.3. Regras de apresentação

- Todo o conteúdo é renderizado no servidor; gráficos em SVG inline.
- Atualização automática por `<meta http-equiv="refresh">` a cada 60 s, sem JavaScript.
- Tema claro e escuro automáticos (`prefers-color-scheme`), legível em celular.
- Cores de estado com contraste acessível e sempre acompanhadas de texto (não depender só de cor).
- Antes da implementação, um protótipo estático do dashboard é aprovado (Etapa E5).

## 6. Classes de falha

| Classe | Significado | Retentar |
| --- | --- | --- |
| `CONEXAO` | Switch inalcançável ou conexão recusada | Sim |
| `TEMPO_ESGOTADO` | Conexão ou comando excedeu o tempo limite | Sim |
| `AUTENTICACAO` | Credencial recusada | Não |
| `CHAVE_HOST` | Chave SSH diferente da registrada | Não |
| `SAIDA_INCOMPLETA` | Saída vazia, truncada ou com erro | Sim |
| `ERRO_INTERNO` | Falha do próprio sistema (ex.: gravar arquivo) | Sim |

## 7. Requisitos não funcionais

| ID | Requisito |
| --- | --- |
| N-01 | Capacidade: até 200 switches [HIP], com ciclo diário completo em menos de 30 min |
| N-02 | Concorrência: no máximo 5 conexões simultâneas a switches [HIP], configurável |
| N-03 | Reinício do sistema não perde dados nem deixa coleta presa |
| N-04 | Implantação com Docker Compose, um único serviço de aplicação e um volume de dados |
| N-05 | Logs em JSON com filtro que mascara segredos; conteúdo de configuração nunca vai para log |
| N-06 | Todo o estado (banco, arquivos de backup) em um único diretório de dados, fácil de copiar |
| N-07 | Container roda sem root, com sistema de arquivos somente leitura exceto o volume de dados |
| N-08 | Arquivos de backup legíveis apenas pelo usuário da aplicação e nunca servidos diretamente pelo servidor web |

## 8. Fora do escopo (desta versão)

MikroTik e backup binário; restauração automática; alertas por e-mail ou mensageiro; MFA, LDAP e SSO; permissões por site; API pública; importação por CSV; múltiplos workers ou fila distribuída. Itens podem voltar em versão futura, sempre por nova especificação.

## 9. Decisões técnicas

| ADR | Decisão | Motivo |
| --- | --- | --- |
| ADR-001 | Python 3.13 + FastAPI | Tipagem e validação no servidor |
| ADR-002 | Jinja2 + CSS, **sem JavaScript** | Cumpre R-03 e reduz superfície de ataque |
| ADR-003 | SQLite (modo WAL) + SQLAlchemy + Alembic | Sem serviço de banco extra; suficiente para um servidor e poucas centenas de switches |
| ADR-004 | Netmiko para coleta SSH | Suporte pronto a muitos fabricantes, paginação e prompts |
| ADR-005 | Agendador e coletor no mesmo processo (APScheduler + pool limitado) | Um único serviço; estado das execuções no banco |
| ADR-006 | Credenciais cifradas (Fernet, biblioteca `cryptography`) com chave em arquivo fora do banco | Segredo protegido sem cofre externo |
| ADR-007 | Configurações em arquivos no volume de dados, nome pelo SHA-256, metadados no banco | Simples de verificar e copiar |
| ADR-008 | Docker Compose, imagem própria, usuário não root | Instalação reprodutível |
| ADR-009 | `uv` (lock), Ruff, mypy, pytest; testes de coleta contra servidor SSH simulado local, sem tocar a rede | Qualidade sem risco à produção |
| ADR-010 | Verificação (lint, tipos, testes) no próprio servidor, sem CI externo | Cumpre R-01 |
| ADR-011 | ~~Dashboard publicado só em `127.0.0.1` até P-03~~ — substituída pela ADR-012 | — |
| ADR-012 | Dashboard publicado em `0.0.0.0:8080`; TLS e redes de origem antes do piloto | Acesso direto pedido pelo dono do produto |

Detalhes em [`docs/adr/`](../adr/README.md).

## 10. Pendências

| ID | Pendência | Bloqueia |
| --- | --- | --- |
| P-01 | Lista de switches: fabricantes, modelos, versão de SO e quantidade | E3 (tipos suportados) |
| P-02 | Conta de serviço nos switches com privilégio mínimo para ler a configuração | E6 |
| P-03 | Acesso ao dashboard — **porta definida em 2026-11-04: 0.0.0.0:8080 (ADR-012)**; faltam redes de origem permitidas e certificado TLS | E6 |
| P-04 | Horário da coleta diária e janela permitida | E6 |
| P-05 | ~~Repositório GitHub público ou privado~~ — **resolvida 2026-11-04: público**; nenhum dado do cliente (IPs, nomes, configurações) entra no git | — |
| P-06 | Retenção (365 dias proposto) | E7 |
| P-07 | Aprovação dos downloads: imagem base Python e pacotes (lista enviada antes) | E1 |

## 11. Critérios de aceite do produto

| ID | Dado | Quando | Então |
| --- | --- | --- | --- |
| CA-01 | Um switch ativo com credencial válida | O horário da coleta chega | Uma execução bem-sucedida é registrada e o switch fica Saudável |
| CA-02 | Uma configuração sem mudança desde a última coleta | Nova coleta é feita | Nenhuma nova versão é criada; a execução é registrada |
| CA-03 | Uma configuração alterada | Nova coleta é feita | Nova versão é criada e aparece em "Alterações detectadas" com diff |
| CA-04 | Uma saída truncada | A validação roda | Execução marcada `SAIDA_INCOMPLETA`; versão anterior segue como última válida |
| CA-05 | Senha errada | A coleta roda | Falha `AUTENTICACAO`, sem retentativa |
| CA-06 | Chave SSH do switch alterada | A coleta roda | Falha `CHAVE_HOST`, nada é coletado |
| CA-07 | Sistema reiniciado durante uma coleta | Ele volta | Nenhuma execução fica presa em andamento |
| CA-08 | Valores de senha marcadores (canários) | Fluxos de sucesso e falha rodam | Canários não aparecem em banco, logs ou arquivos |
| CA-09 | Usuário de Leitura | Tenta alterar cadastro ou disparar backup | Servidor recusa (403), mesmo com requisição forjada |
| CA-10 | Navegador com JavaScript desativado | Dashboard e telas são usados | Todas as funções funcionam |
