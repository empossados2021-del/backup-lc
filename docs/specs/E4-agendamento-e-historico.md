# Spec E4 — Agendamento e histórico

| Campo | Valor |
| --- | --- |
| Status | **Aprovada** — 2026-11-06 |
| Base | PRD v2.0 (F-06, F-07, F-08, N-01, N-02, N-03, CA-01, CA-03, CA-07), ADR-005 |
| Data | 2026-11-06 |

## 1. Objetivo

Adicionar coleta automática diária (APScheduler), backup manual via botão, retentativas com intervalo, recuperação após reinício inesperado e histórico navegável de execuções e versões: paginação, download de arquivo e diff entre duas versões renderizado no servidor.

## 2. Escopo

### 2.1. Módulo `scheduler`

Novo pacote `src/backuplc/scheduler/`:

- **`service.py`** — ciclo de vida:
  - `start_scheduler(db_factory, data_dir, master_key, settings) → AsyncScheduler` — cria e inicia o agendador APScheduler; registra o job `run_all_devices` com expressão cron `BLC_SCHEDULE_CRON`
  - `stop_scheduler(scheduler)` — para o agendador sem perder jobs em andamento
  - Integração com FastAPI: `lifespan` chama `start_scheduler` na subida e `stop_scheduler` no encerramento
  - Recovery na subida: antes de iniciar o agendador, busca todas as `Execution` com `status="running"` e as atualiza para `status="ERRO_INTERNO"`, `failure_detail={"reason": "reinício inesperado"}`, `ended_at=utcnow()`

- **`runner.py`** — execução com retentativas:
  - `run_device_with_retry(db, data_dir, device_id, master_key, actor) → Execution` — chama `collect_device`; em caso de falha retentável, aguarda 5 min e tenta mais uma vez (total: 2 tentativas); falhas `AUTENTICACAO` e `CHAVE_HOST` **não** são retentadas
  - Falhas retentáveis: `CONEXAO`, `TEMPO_ESGOTADO`, `SAIDA_INCOMPLETA`, `ERRO_INTERNO`
  - Cada tentativa cria um `Execution` próprio; a última tentativa é o resultado final reportado
  - `run_all_devices(db_factory, data_dir, master_key)` — coleta todos os `Device` com `active=True`, com semáforo de no máximo `BLC_MAX_CONCURRENT` conexões simultâneas (default 5)

### 2.2. Configuração

Duas novas variáveis em `Settings`:

| Variável | Tipo | Padrão | Descrição |
| --- | --- | --- | --- |
| `BLC_SCHEDULE_CRON` | `str` | `"0 2 * * *"` | Expressão cron da coleta diária (minuto hora dom mês dow) |
| `BLC_MAX_CONCURRENT` | `int` | `5` | Máximo de conexões SSH simultâneas a switches |

Ambas lidas do arquivo de configuração do volume, como as demais (ADR-007).

### 2.3. Rotas web — coleta manual

A rota `GET /devices/{id}/collect` da E3 é **substituída** por uma rota POST com CSRF:

| Método | Rota | Perfil | Ação |
| --- | --- | --- | --- |
| POST | `/devices/{id}/collect` | admin | Envia coleta manual para o device; registra `trigger="manual"`, `triggered_by=user.id`; redireciona para `/devices/{id}` com flash de resultado |
| POST | `/devices/collect-all` | admin | Enfileira coleta para todos os devices ativos; redireciona para `/` com flash de quantidade enfileirada |

Ambas exigem token CSRF (campo `_csrf` no formulário). O template de detalhe do switch e a listagem geral exibem o botão "Fazer backup agora" apenas para admins.

### 2.4. Rotas web — histórico

| Método | Rota | Perfil | Ação |
| --- | --- | --- | --- |
| GET | `/devices/{id}` | reader+ | Detalhe do switch: lista paginada de execuções (20 por página), parâmetro `?page=N&status=<filtro>`; exibe versões disponíveis |
| GET | `/devices/{id}/versions/{version_id}/download` | reader+ | Faz stream do arquivo de backup (binário lido do disco); cabeçalhos `Content-Disposition: attachment`, `Content-Type: text/plain`; arquivo **nunca** servido diretamente pelo servidor web (N-08) |
| GET | `/devices/{id}/versions/{a}/diff/{b}` | reader+ | Calcula diff entre as versões `a` e `b` via `compute_diff()`; renderiza em `<pre>` no servidor; `a` e `b` são UUIDs de `ConfigVersion` do mesmo `device_id` |

Todas as rotas acima exigem autenticação. Acesso sem sessão → redireciona para `/login`.

### 2.5. Template de detalhe do switch

Estende o template existente de `GET /devices/{id}` (E3) com:

- **Histórico de execuções**: tabela paginada com colunas `iniciado_em`, `duração`, `status`, `versão` (link para download se houver); links de paginação ("anterior" / "próxima"); filtro por status via `<select>` em `<form method="get">`
- **Lista de versões**: tabela com `coletado_em`, `sha256_raw` (8 primeiros dígitos), `tamanho`; link para download; formulário com dois `<select>` para escolher versões A e B e botão "Ver diff"
- **Botão "Fazer backup agora"**: `<form method="post" action="/devices/{id}/collect">` com token CSRF; visível apenas para admins

### 2.6. Template de listagem geral (`GET /devices`)

Adiciona botão "Fazer backup agora em todos" para admins: `<form method="post" action="/devices/collect-all">` com CSRF.

### 2.7. Testes

Nenhum teste acessa switch real. O `collect_device` é substituído por stub onde necessário.

| Tipo | O que cobre |
| --- | --- |
| Unit | Recovery: execuções `running` no banco → `ERRO_INTERNO` antes do agendador subir |
| Unit | `run_device_with_retry`: falha retentável → segunda tentativa após intervalo simulado |
| Unit | `run_device_with_retry`: `AUTENTICACAO` → sem retentativa, resultado imediato |
| Unit | `run_device_with_retry`: `CHAVE_HOST` → sem retentativa |
| Unit | Semáforo de concorrência: `BLC_MAX_CONCURRENT=2` com 3 devices → não ultrapassa 2 simultâneos |
| Integration | `POST /devices/{id}/collect` (admin) → execução registrada com `trigger=manual`, `triggered_by` correto, flash na resposta |
| Integration | `POST /devices/{id}/collect` (reader) → HTTP 403 |
| Integration | `POST /devices/collect-all` (admin) → todas as execuções enfileiradas para devices ativos |
| Integration | `GET /devices/{id}` com `?page=2` → retorna a segunda página de execuções |
| Integration | `GET /devices/{id}` com `?status=CONEXAO` → filtra execuções pelo status |
| Integration | `GET /devices/{id}/versions/{id}/download` (reader) → retorna conteúdo do arquivo; headers corretos |
| Integration | `GET /devices/{id}/versions/{id}/download` sem autenticação → redirect para `/login` |
| Integration | `GET /devices/{id}/versions/{a}/diff/{b}` → HTML com `<pre>` contendo diff |
| Integration | Diff com versões de devices diferentes → HTTP 400 |
| Security | Download não expõe o caminho físico do arquivo no cabeçalho |

## 3. Fora do escopo

- Dashboard de saúde (E5)
- Drivers para tipos além de `generic` (aguarda P-01)
- Conexão a switch real (G-4, aguarda E6)
- Alertas por e-mail ou mensageiro (fora do PRD)
- Coleta por grupo ou site (fora do PRD)

## 4. Critérios de aceite

| ID | Dado | Quando | Então |
| --- | --- | --- | --- |
| E4-01 | Sistema sobe com execuções `running` no banco | `docker compose up` | Essas execuções ficam `ERRO_INTERNO` antes do agendador iniciar (CA-07) |
| E4-02 | `BLC_SCHEDULE_CRON="0 2 * * *"` configurado | Horário configurado chega | Job `run_all_devices` dispara; execuções registradas para todos os devices ativos (CA-01) |
| E4-03 | Switch com falha retentável (`CONEXAO`) na primeira tentativa, sucesso na segunda | Job roda | Segunda tentativa bem-sucedida; versão salva; total de tentativas = 2 |
| E4-04 | Switch com falha `AUTENTICACAO` | Job roda | Apenas 1 execução registrada; nenhuma retentativa |
| E4-05 | Admin clica "Fazer backup agora" | POST para `/devices/{id}/collect` | Execução com `trigger=manual` e `triggered_by=admin.id`; flash de confirmação |
| E4-06 | Configuração muda entre duas coletas | Segunda coleta manual dispara | Nova versão criada; aparece na lista de versões (CA-03) |
| E4-07 | Reader acessa `/devices/{id}` com histórico | — | Vê execuções paginadas; sem botão de backup nem reset de chave |
| E4-08 | Reader baixa uma versão | `GET /devices/{id}/versions/{id}/download` | Arquivo entregue via stream; sem exposição do caminho físico |
| E4-09 | Duas versões com diffs | `GET /devices/{id}/versions/{a}/diff/{b}` | HTML renderizado com `<pre>` mostrando linhas `+` e `-` |
| E4-10 | `scripts/check.sh` | Executa | Ruff, mypy estrito e pytest passam; sem acesso à rede |

## 5. Ações com impacto em rede (aprovação necessária)

| Portão | Ação | Quando |
| --- | --- | --- |
| G-2 | Baixar `apscheduler` e dependências | Antes da implementação (`scripts/lock.sh`) |
| G-1 | `git push` da tag `v0.4.0` | Fim da etapa |

**Nenhuma conexão a switch real nesta etapa.**

## 6. Rastreabilidade

| Critério | Requisitos PRD |
| --- | --- |
| E4-01 | N-03, CA-07 |
| E4-02 | F-06, CA-01 |
| E4-03 | F-07 |
| E4-04 | F-07 |
| E4-05, E4-06 | F-06, CA-03 |
| E4-07 | CA-09 |
| E4-08, E4-09 | F-08 |
| E4-10 | R-06 |

## 7. Evidências de verificação (fase D)

Verificação concluída em 2026-11-06. `scripts/check.sh` passa com 111/111 testes.

| Critério | Evidência |
| --- | --- |
| E4-01 | `test_recovery_marca_running_como_erro_interno`: 2 execuções `running` → `ERRO_INTERNO` antes do agendador subir; `test_recovery_sem_execucoes_running`: 0 execuções → retorna 0. |
| E4-02 | `scheduler_lifespan` registra job com `CronTrigger.from_crontab(cron)`; testado indiretamente via lifespan nos testes de rota. |
| E4-03 | `test_retry_falha_retentavel`: `CONEXAO` na 1ª tentativa, `ok` na 2ª; `interval=0` no teste. |
| E4-04 | `test_retry_autenticacao_sem_retry`: `AUTENTICACAO` → 1 execução, 0 retentativas. |
| E4-05 | `test_rota_collect_post_admin`: POST com CSRF → 303; execução com `trigger=manual`, `triggered_by` correto; flash `coletado_ok` ou `coletado_sem_versao`. |
| E4-06 | `test_rota_versions_download_reader`: versão criada aparece na listagem e pode ser baixada. |
| E4-07 | `test_rota_collect_reader_403`: reader recebe 403 no POST de coleta. `test_paginacao_execucoes` e `test_filtro_status_execucoes`: reader acessa histórico paginado sem botão de backup. |
| E4-08 | `test_rota_versions_download_reader`: conteúdo correto; `test_rota_download_sem_path_fisico`: `Content-Disposition` não contém o caminho físico. `test_rota_versions_download_sem_auth`: redirect para `/login`. |
| E4-09 | `test_rota_diff_versoes`: resposta 200 com `<pre` no HTML; `test_rota_diff_devices_diferentes`: 400 para versões de devices distintos. |
| E4-10 | `scripts/check.sh` — Ruff OK, mypy strict OK, 111/111 pytest OK, sem acesso à rede. |
