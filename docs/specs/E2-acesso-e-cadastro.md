# Spec E2 — Acesso e cadastro

| Campo | Valor |
| --- | --- |
| Status | **Aprovada** — 2026-11-05 |
| Base | PRD v2.0 (F-01, F-02, F-10, F-11, CA-09, R-05), ADR-006 |
| Data | 2026-11-05 |

## 1. Objetivo

Adicionar autenticação, autorização e cadastro básico ao sistema: login com usuários locais, sessões seguras no servidor, perfis Admin e Leitura, proteção CSRF, credenciais SSH cifradas com Fernet e cadastro de switches. Nenhuma página além de `/login` e `/health` fica acessível sem autenticação. Primeiro administrador criado pelo CLI.

## 2. Escopo

1. **Usuários e hashes:** modelo `User` com `username`, `password_hash` (Argon2id), `role` (`admin` | `reader`), `is_active`, `failed_attempts`, `locked_until`. CLI `backuplc create-admin` cria o primeiro administrador (interativo; pede usuário e senha, valida política, exige confirmação).

2. **Política de senha:** mínimo 12 caracteres, pelo menos uma letra maiúscula, uma minúscula e um dígito. Validada no servidor; mensagem de erro não revela qual regra falhou (apenas "Senha não atende à política").

3. **Login:** `GET /login` (formulário) e `POST /login`. Após autenticação bem-sucedida, redireciona para `/` ou para o parâmetro `next` (somente caminhos locais, sem `//` ou `http`). Falha retorna HTTP 200 com mensagem genérica "Usuário ou senha incorretos" (não distingue um do outro).

4. **Bloqueio por falhas consecutivas:** após 5 falhas seguidas, a conta fica bloqueada por 15 minutos. Tentativas durante o bloqueio exibem "Conta bloqueada. Tente novamente em alguns minutos." sem revelar o tempo exato. Falha bem-sucedida zera o contador.

5. **Sessão no servidor:** cookie `session_id` (HttpOnly, Secure¹, SameSite=Lax, path=/), 32 bytes aleatórios, TTL de 8 horas de inatividade. Tabela `sessions` no banco: `id`, `user_id`, `created_at`, `last_seen_at`, `expires_at`. Logout invalida a sessão no banco (DELETE) e limpa o cookie. Nenhum dado de sessão no cookie — só o ID.

   ¹ Em desenvolvimento `Secure` fica desabilitado quando `BLC_ENV=development`.

6. **Middleware de autenticação:** toda rota exceto `/login`, `/health/live` e `/health/ready` exige sessão válida. Requisição não autenticada → redirect `302` para `/login?next=<caminho>`. Sessão expirada é apagada do banco e tratada como não autenticada.

7. **Proteção CSRF:** todo formulário `POST` inclui um campo oculto `csrf_token` (32 bytes, derivado de HMAC-SHA256 sobre `session_id` com a `session_secret`). O middleware valida o token antes de processar qualquer POST. Falha → HTTP 403, sem detalhar o motivo ao usuário. Rotas `/health/*` e `/login` (GET) ficam fora da verificação.

8. **Perfis e autorização:**
   - `admin`: acesso total — ver e alterar usuários, credenciais e switches.
   - `reader`: somente leitura — ver dashboard, histórico e lista de switches; **não** pode criar/editar/excluir switches, credenciais ou usuários.
   - Verificação sempre no backend; resposta 403 para qualquer tentativa não autorizada, mesmo que a rota seja forjada (CA-09).
   - Interface: botões e links de ação são omitidos para `reader`, mas a proteção não depende disso.

9. **Credenciais SSH (`Credential`):** modelo `Credential` com `name`, `username`, `encrypted_password` (Fernet, chave mestra), `description`. Formulários de criação e edição (somente admin). Listagem mostra nome, usuário e quantidade de switches associados; senha nunca aparece em tela, log ou banco em texto puro (ADR-006).

10. **Switches (`Device`):** modelo `Device` com `name`, `ip_address`, `device_type`, `ssh_port` (padrão 22), `credential_id`, `is_active`. Nome e IP únicos. `device_type` é uma enumeração fechada (a ser expandida na E3); por ora aceita `generic`. Formulários de criação e edição (somente admin). Listagem mostra nome, IP, tipo, porta, credencial e estado ativo/inativo.

11. **Registro de eventos (F-11):** `record_event()` já existe. Novos eventos: `USER_LOGIN`, `USER_LOGIN_FAILED`, `USER_LOCKED`, `USER_LOGOUT`, `USER_CREATED`, `CREDENTIAL_CREATED`, `CREDENTIAL_UPDATED`, `CREDENTIAL_DELETED`, `DEVICE_CREATED`, `DEVICE_UPDATED`, `DEVICE_DELETED`. Todos incluem `user_id` (ou `None` para tentativas sem sessão), `ip` e `action`.

12. **Migrações:** `v0002_usuarios_sessoes.py` (tabelas `users` e `sessions`), `v0003_credenciais_dispositivos.py` (tabelas `credentials` e `devices`). Ambas reversíveis.

13. **Templates e navegação:** `/login`, `/logout` (POST), `/users` (admin), `/users/new`, `/users/<id>/edit`, `/credentials` (admin), `/credentials/new`, `/credentials/<id>/edit`, `/devices`, `/devices/new`, `/devices/<id>/edit`. Navegação principal atualizada com os links cabíveis ao perfil do usuário logado.

14. **Testes:** testes `unit` para hash, política de senha, CSRF, bloqueio e Fernet; testes `integration` para login, sessão, logout, fluxo de bloqueio, CRUD de switches e credenciais, autorização (CA-09), canários de senha (CA-08). `test_frontend.py` atualizado com as novas páginas. `test_canaries.py` cobre os novos fluxos que lidam com senha e chave Fernet.

## 3. Fora do escopo

Coleta SSH (E3), agendamento (E4), dashboard de saúde com dados reais (E5), TLS (antes da E6), gerenciamento de chave SSH de switches (E3), recuperação de senha, login externo (OAuth/SAML), 2FA, rate-limiting por IP.

## 4. Critérios de aceite

| ID | Dado | Quando | Então |
| --- | --- | --- | --- |
| E2-01 | Nenhum usuário cadastrado | `backuplc create-admin` é chamado com usuário e senha válidos | Um administrador é criado; `check-config` não falha; login funciona imediatamente |
| E2-02 | Usuário não autenticado | Acessa `GET /` ou qualquer rota protegida | Recebe redirect 302 para `/login?next=<caminho>` |
| E2-03 | Credenciais corretas | `POST /login` | Sessão criada no banco; cookie `session_id` enviado; redirect para destino |
| E2-04 | Credenciais incorretas (5 vezes) | `POST /login` repetido | Conta bloqueada; 6ª tentativa retorna mensagem de bloqueio; nenhuma das tentativas revela se o usuário existe |
| E2-05 | Conta bloqueada (15 min passados) | `POST /login` com credenciais corretas | Login bem-sucedido; contador zerado |
| E2-06 | Sessão válida | `POST /logout` | Sessão removida do banco; cookie limpo; redirect para `/login` |
| E2-07 | Sessão expirada (> 8 h sem atividade) | Qualquer requisição autenticada | Sessão apagada; redirect para `/login` |
| E2-08 | Formulário POST sem token CSRF válido | Qualquer `POST` protegido | HTTP 403, sem detalhe |
| E2-09 | Usuário com perfil `reader` | Tenta `POST /devices/new` ou qualquer mutação | HTTP 403; evento `DEVICE_CREATED` **não** é registrado |
| E2-10 | Admin cria uma credencial | Senha informada no formulário | Senha jamais aparece em log, banco (texto puro) ou resposta HTTP; apenas `encrypted_password` no banco |
| E2-11 | Admin cadastra um switch com credencial existente | Formulário submetido | Switch aparece na listagem com nome, IP, tipo e estado |
| E2-12 | Canários injetados como senha de credencial | Fluxo de criação e edição roda | Nenhum canário em logs, banco (texto puro) ou arquivos (CA-08) |
| E2-13 | JavaScript desabilitado no navegador | Todas as telas são usadas | Todas as funções operam normalmente (CA-10) |
| E2-14 | `scripts/check.sh` | Executa | Ruff, mypy estrito e pytest passam; sem acesso à rede |

## 5. Ações com impacto em rede (aprovação necessária)

Nenhuma nova ação de rede nesta etapa. Os pacotes necessários (`argon2-cffi`, `cryptography`) já estão no `uv.lock` desde a E1. Portão G-1 ao final da etapa.

## 6. Rastreabilidade

| Critério | Requisitos PRD |
| --- | --- |
| E2-01 a E2-07 | F-10 |
| E2-08 | R-05, ADR-002 |
| E2-09 | CA-09 |
| E2-10, E2-12 | F-02, ADR-006, R-05 |
| E2-11 | F-01 |
| E2-13 | CA-10 |
| E2-14 | R-06 |

## 7. Evidências de verificação (fase D)

Verificação concluída em 2026-11-05 com `scripts/check.sh` (Docker sem rede).

| Critério | Teste | Resultado |
| --- | --- | --- |
| E2-01 | `test_cli.py::test_create_admin_*` | PASSED |
| E2-02 | `test_e2.py::test_home_sem_auth_redireciona`, `test_devices_sem_auth_redireciona` | PASSED |
| E2-03 | `test_e2.py::test_login_sucesso_cria_cookie` | PASSED |
| E2-04 | `test_e2.py::test_login_falha_mensagem_generica`, `test_login_usuario_inexistente_mensagem_generica`, `test_bloqueio_apos_5_falhas` | PASSED |
| E2-05 | `test_auth.py::test_login_apos_bloqueio_expirado` | PASSED |
| E2-06 | `test_e2.py::test_logout_invalida_sessao` | PASSED |
| E2-07 | `test_auth.py::test_sessao_expirada_retorna_none` | PASSED |
| E2-08 | `test_e2.py::test_csrf_invalido_retorna_403` | PASSED |
| E2-09 | `test_e2.py::test_reader_nao_cria_switch`, `test_reader_nao_cria_credencial` | PASSED |
| E2-10 | `test_canaries.py::test_credential_password_not_in_db` | PASSED |
| E2-11 | `test_e2.py::test_admin_cria_switch` | PASSED |
| E2-12 | `test_canaries.py` | PASSED |
| E2-13 | `test_e2.py::test_paginas_e2_sem_javascript`, `test_frontend.py::test_templates_sem_javascript` | PASSED |
| E2-14 | `scripts/check.sh` — 79 testes, Ruff, mypy estrito | PASSED |

**Decisão técnica registrada:** `request.body()` é chamado antes de `request.form()` no middleware CSRF para garantir que o `_CachedRequest` do Starlette 1.9 armazene o corpo em `_body` antes de consumi-lo via `stream()`, permitindo que o handler de rota releia os dados do formulário.
