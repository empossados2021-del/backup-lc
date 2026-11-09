# Spec E3 — Coleta de configuração

| Campo | Valor |
| --- | --- |
| Status | **Aprovada** — 2026-11-05 |
| Base | PRD v2.0 (F-03, F-04, F-05, F-12, N-01, N-02, N-05, N-06, N-08, R-04), ADR-004, ADR-007, ADR-009 |
| Data | 2026-11-05 |

## 1. Objetivo

Implementar o núcleo da coleta: dado um switch cadastrado, conectar por SSH (Netmiko), executar os comandos permitidos para o tipo, validar a saída, verificar a chave do host, deduplicar versões por SHA-256 e registrar a execução no banco. Nenhuma coleta automática ainda (E4); a E3 entrega a primitiva `collect_device()` usada pelas etapas seguintes.

## 2. Escopo

### 2.1. Módulo `collector`

Novo pacote `src/backuplc/collector/`:

- **`driver.py`** — protocolo e registro de drivers:
  - `Driver`: protocolo com método `collect(host, port, username, password, timeout) → RawResult`
  - `RawResult`: dataclass com `output: str`, `host_key: str` (tipo + base64)
  - `DRIVER_REGISTRY`: dicionário `device_type → DriverSpec`; `device_type` = string que casa com `Device.device_type`
  - `DriverSpec`: dataclass com `netmiko_type: str`, `commands: list[str]`, `volatile_patterns: list[str]`, `end_marker: str | None`, `min_chars: int`
  - `get_driver_spec(device_type: str) → DriverSpec`; levanta `UnsupportedTypeError` se o tipo não está registrado
  - Driver `"generic"` registrado na E3 com `netmiko_type="generic"`, comando `"show running-config"`, marcador de fim `None`, `min_chars=100`

- **`runner.py`** — função principal:
  - `collect_device(db, data_dir, device_id, master_key, actor) → Execution`
  - Fluxo:
    1. Carrega `Device` e `Credential`; falha → `ERRO_INTERNO`
    2. Obtém `DriverSpec`; tipo sem suporte → `ERRO_INTERNO`
    3. Verifica chave do host (ver 2.3)
    4. Conecta com Netmiko; `NetmikoTimeoutException` → `TEMPO_ESGOTADO`; `NetmikoAuthenticationException` → `AUTENTICACAO` (sem retentativa); erro de rede → `CONEXAO`
    5. Executa cada comando da lista; concatena saídas com separador `\n`
    6. Valida saída (ver 2.4); inválida → `SAIDA_INCOMPLETA`
    7. Salva versão se necessário (ver 2.5); registra execução com `status="ok"`, `version_id` preenchido ou `None`
  - Cria registro `Execution` no banco antes de conectar (`status="running"`); atualiza ao terminar

### 2.2. Módulo `storage`

Novo pacote `src/backuplc/storage/`:

- **`store.py`**:
  - `save_config(data_dir, device_id, raw_output, volatile_patterns) → Version | None`
  - Normaliza: remove linhas que casam com os padrões voláteis antes de comparar
  - Calcula `sha256_norm` do conteúdo normalizado
  - Se `Version` com mesmo `device_id` + `sha256_norm` já existe → retorna `None` (sem nova versão)
  - Calcula `sha256_raw` do conteúdo bruto
  - Grava em `<data_dir>/configs/<2 primeiros hex do sha256_raw>/<sha256_raw>` via arquivo temporário + `rename` atômico; permissão `0o600`
  - Insere `Version` no banco e retorna

- **`diff.py`**:
  - `compute_diff(text_a: str, text_b: str) → str` — diff unificado simples (stdlib `difflib.unified_diff`); retornado como string pronta para renderizar no servidor
  - Sem dependências extras

### 2.3. Verificação de chave do host (F-12)

- Nova tabela `device_host_keys`: `device_id` (PK, FK → devices RESTRICT), `key_type`, `key_b64`, `registered_at`
- Ao conectar: Netmiko é configurado com `look_for_keys=False`, `allow_agent=False`; a chave apresentada é capturada via callback `rejected_policy` do Paramiko
- Se não há registro para o dispositivo → registra a chave apresentada (`REGISTERED`) e prossegue
- Se há registro → compara; diferente → falha `CHAVE_HOST`, saída imediata, nada é coletado nem gravado
- Deleção do registro de chave: via rota admin `POST /devices/{id}/reset-host-key` (com CSRF); exige confirmação
- Migração `v0004_coleta.py` cria as tabelas `executions`, `config_versions` e `device_host_keys`

### 2.4. Validação de saída (F-04)

Para cada `DriverSpec`, na ordem:
1. `len(output.strip()) == 0` → `SAIDA_INCOMPLETA` ("saída vazia")
2. `len(output) < min_chars` → `SAIDA_INCOMPLETA` ("saída muito curta")
3. Presença de qualquer linha que case com `error_patterns` do driver (ex.: `"% Error"`, `"% Invalid"`, `"% Ambiguous"`) → `SAIDA_INCOMPLETA` ("saída contém erro")
4. Se `end_marker` está definido e não aparece na saída → `SAIDA_INCOMPLETA` ("marcador de fim ausente")

### 2.5. Deduplicação de versões (F-05)

- Conteúdo normalizado = saída com as `volatile_patterns` removidas linha a linha
- SHA-256 do normalizado (`sha256_norm`) é a chave de deduplicação por dispositivo
- Se a última versão do dispositivo tem o mesmo `sha256_norm` → nenhuma nova versão; execução registrada com `version_id=None`
- Arquivo físico endereçado pelo `sha256_raw` (conteúdo bruto, antes da normalização)

### 2.6. Modelos de banco

**`Execution`** (`executions`):
| Coluna | Tipo | Notas |
| --- | --- | --- |
| id | UUID (PK) | — |
| device_id | UUID (FK → devices RESTRICT) | — |
| started_at | DateTime UTC | — |
| ended_at | DateTime UTC, nullable | null enquanto rodando |
| status | String(30) | `running`, `ok`, `CONEXAO`, `TEMPO_ESGOTADO`, `AUTENTICACAO`, `CHAVE_HOST`, `SAIDA_INCOMPLETA`, `ERRO_INTERNO` |
| version_id | UUID (FK → config_versions SET NULL), nullable | preenchido só em `ok` com nova versão |
| failure_detail | JSON (Text), nullable | — |
| trigger | String(10) | `scheduled`, `manual` |
| triggered_by | UUID (FK → users SET NULL), nullable | null para coleta agendada |

**`ConfigVersion`** (`config_versions`):
| Coluna | Tipo | Notas |
| --- | --- | --- |
| id | UUID (PK) | — |
| device_id | UUID (FK → devices RESTRICT) | — |
| collected_at | DateTime UTC | — |
| sha256_raw | String(64) | hash do arquivo físico |
| sha256_norm | String(64) | hash pós-normalização (deduplicação) |
| file_path | String(512) | relativo a `data_dir` |
| size_bytes | Integer | tamanho bruto |

**`DeviceHostKey`** (`device_host_keys`):
| Coluna | Tipo | Notas |
| --- | --- | --- |
| device_id | UUID (PK, FK → devices CASCADE) | um registro por dispositivo |
| key_type | String(50) | ex.: `ssh-ed25519` |
| key_b64 | Text | chave pública em base64 |
| registered_at | DateTime UTC | — |

### 2.7. Novas rotas web

Todas exigem perfil `admin`, com CSRF:

| Método | Rota | Ação |
| --- | --- | --- |
| GET | `/devices/{id}/collect` | Aciona coleta manual; redireciona para `/devices/{id}` com flash (E4 substitui por POST) |
| POST | `/devices/{id}/reset-host-key` | Remove o registro de chave do host após confirmação |
| GET | `/devices/{id}` | Detalhe do switch: últimas 20 execuções, última versão, botão de coleta manual e reset de chave |

Perfil `reader`: pode ver `/devices/{id}` (somente leitura).

### 2.8. Configurações

Nenhuma nova variável de ambiente. O diretório `<data_dir>/configs/` é criado na primeira escrita, permissão `0o700`.

### 2.9. Testes

Testes **não** acessam switches reais. O Netmiko é substituído por um stub (`monkeypatch`) que retorna saídas pré-programadas.

| Tipo | O que cobre |
| --- | --- |
| Unit | `save_config`: deduplicação, gravação atômica, permissões |
| Unit | Validação de saída (vazia, curta, com erro, sem marcador) |
| Unit | `compute_diff`: linhas adicionadas e removidas |
| Unit | Verificação de chave do host: primeira vez registra; mesmo → prossegue; diferente → `CHAVE_HOST` |
| Integration | `collect_device` com stub OK → execução `ok`, versão criada |
| Integration | `collect_device` stub OK segunda vez (config igual) → execução `ok`, nenhuma nova versão |
| Integration | Falha de autenticação → `AUTENTICACAO`, sem nova versão |
| Integration | Saída truncada → `SAIDA_INCOMPLETA`, sem nova versão |
| Integration | Chave de host diferente → `CHAVE_HOST`, sem nova versão |
| Integration | Canários de senha nunca aparecem em banco, logs ou arquivos (CA-08) |
| Integration | Rota `GET /devices/{id}/collect` (admin) dispara coleta e redireciona |
| Integration | Rota `GET /devices/{id}/collect` (reader) retorna 403 |

Cobertura de CA-02, CA-04, CA-05, CA-06, CA-08.

## 3. Fora do escopo

- Coleta agendada (E4)
- Backup manual via botão da listagem geral (E4)
- Retentativas automáticas (E4)
- Download de arquivo de configuração (E4/E5)
- Diff na interface (E5)
- Drivers para tipos específicos além de `generic` (aguarda P-01)
- Conexão a switch real (G-4, aguarda P-02 e E6)

## 4. Critérios de aceite

| ID | Dado | Quando | Então |
| --- | --- | --- | --- |
| E3-01 | Switch do tipo `generic` com stub que retorna saída válida | `collect_device()` é chamado | Execução `ok`; versão gravada em `configs/<2hex>/<sha256_raw>`; banco contém `sha256_raw` e `sha256_norm` corretos |
| E3-02 | Segunda coleta com saída idêntica (após normalização) | `collect_device()` é chamado | Execução `ok`; `version_id=None`; nenhum novo arquivo gravado |
| E3-03 | Segunda coleta com saída diferente | `collect_device()` é chamado | Nova versão criada; arquivo novo no disco |
| E3-04 | Stub retorna saída vazia ou muito curta | `collect_device()` é chamado | Execução `SAIDA_INCOMPLETA`; nenhuma versão criada |
| E3-05 | Stub simula falha de autenticação | `collect_device()` é chamado | Execução `AUTENTICACAO`; nenhuma retentativa |
| E3-06 | Primeira conexão a um dispositivo sem chave registrada | `collect_device()` é chamado | Chave registrada em `device_host_keys`; coleta prossegue |
| E3-07 | Chave do host diferente da registrada | `collect_device()` é chamado | Execução `CHAVE_HOST`; nenhuma versão criada; nenhuma escrita no disco |
| E3-08 | Admin acessa `GET /devices/{id}/collect` | — | Coleta é disparada; flash confirma resultado; página de detalhe exibe a execução |
| E3-09 | Reader acessa `GET /devices/{id}/collect` | — | HTTP 403 |
| E3-10 | Canários injetados como senha de credencial | Fluxo de coleta roda (stub) | Nenhum canário em banco, logs ou arquivos (CA-08) |
| E3-11 | `scripts/check.sh` | Executa | Ruff, mypy estrito e pytest passam; sem acesso à rede |

## 5. Ações com impacto em rede (aprovação necessária)

| Portão | Ação | Quando |
| --- | --- | --- |
| G-2 | Baixar `netmiko` e dependências (`paramiko`, `textfsm`, etc.) | Antes da implementação (`scripts/lock.sh`) |
| G-1 | `git push` da tag `v0.3.0` | Fim da etapa |

**Nenhuma conexão a switch real nesta etapa.** Testes usam stub local.

## 6. Rastreabilidade

| Critério | Requisitos PRD |
| --- | --- |
| E3-01 a E3-05 | F-03, F-04, F-05 |
| E3-06, E3-07 | F-12 |
| E3-08, E3-09 | F-06 (parcial), CA-09 |
| E3-10 | CA-08, R-05 |
| E3-11 | R-06 |

## 7. Evidências de verificação (fase D)

| ID | Verificação | Resultado |
| --- | --- | --- |
| E3-01 | `test_collect_device_ok` — stub OK, versão criada em `configs/<2hex>/<sha256>`, hashes corretos | OK |
| E3-02 | `test_collect_device_sem_nova_versao` — mesma saída → `version_id=None` | OK |
| E3-03 | `test_save_config_nova_versao_conteudo_diferente` — saída diferente → nova versão | OK |
| E3-04 | `test_validacao_saida_vazia`, `test_validacao_saida_curta`, `test_validacao_saida_com_erro` — saídas inválidas → `SAIDA_INCOMPLETA` | OK |
| E3-05 | `test_collect_device_autenticacao_falha` — `AUTENTICACAO`, sem retentativa | OK |
| E3-06 | `test_collect_device_chave_host_nova` — chave registrada em `device_host_keys`, coleta prossegue | OK |
| E3-07 | `test_collect_device_chave_host_diferente` — `CHAVE_HOST`, nenhuma versão criada | OK |
| E3-08 | `test_rota_collect_admin` — redireciona com flash | OK |
| E3-09 | `test_rota_collect_reader_403` — HTTP 403 | OK |
| E3-10 | `test_collect_device_canarios` — nenhum canário em arquivos | OK |
| E3-11 | `scripts/check.sh` — ruff, mypy estrito, 95 testes passam sem rede | OK |
