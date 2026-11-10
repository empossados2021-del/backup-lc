# Spec E7 — Operação

| Campo | Valor |
| --- | --- |
| Status | **Implementada** — v0.7.0 (2026-11-10) |
| Base | PRD v2.0 (F-13, N-03, N-06, N-07), ADR-007 |
| Data | 2026-11-06 |
| Depende de | E6 concluída; P-06 resolvida pelo cliente |

## 1. Objetivo

Tornar o sistema autossustentável em produção: retenção automática de backups por 365 dias (preservando sempre a última versão válida), runbook completo de instalação, atualização e recuperação, procedimento documentado de cópia de dados e revisão de segurança. Critério final: um terceiro consegue instalar, operar e recuperar o sistema seguindo apenas os documentos deste projeto.

## 2. Escopo

### 2.1. Retenção automática (F-13, aguarda P-06)

Novo job no scheduler (`scheduler/service.py`):

- `run_retention_cleanup(db, data_dir, retention_days: int)` — executado diariamente, após a janela de coleta
- Lógica:
  1. Para cada `Device`, busca as `ConfigVersion` com `collected_at < now - retention_days`
  2. Exclui apenas se **não** for a versão mais recente do dispositivo (preserva sempre a última)
  3. Remove o arquivo físico (`data_dir/configs/…`) e deleta o registro `ConfigVersion`
  4. Registra no log JSON: quantidade de versões removidas, espaço liberado (bytes)
  5. Nunca remove o arquivo se outra `ConfigVersion` ainda referencia o mesmo `sha256_raw` (deduplicação reversa)
- Configuração: `BLC_RETENTION_DAYS` (int, padrão 365); lido do arquivo de configuração do volume
- Execuções (`Execution`) não são removidas; apenas versões de arquivo

### 2.2. Runbook de instalação e atualização

Arquivo `docs/runbooks/instalacao.md` atualizado (ou substituído) com os seguintes procedimentos completos:

**A. Instalação do zero**
1. Pré-requisitos do servidor (Docker, Compose, espaço em disco)
2. Criar usuário e grupo `backup-lc` (uid/gid 10001)
3. Criar estrutura de diretórios (`/opt/backup-lc`, `/var/lib/backup-lc`, `/etc/backup-lc/secrets`)
4. Gerar segredos (`session_secret`, `master_key`) e registrar fora do servidor
5. Clonar o repositório e fazer checkout da tag desejada
6. Criar `.env` a partir de `.env.example`; ajustar `BLC_SCHEDULE_CRON`, `BLC_RETENTION_DAYS`, etc.
7. Portões G-2 (build) e G-3 (porta) com aprovação
8. `docker compose up -d --build`; verificar `/health/ready`

**B. Atualização de versão**
1. Ler o `CHANGELOG.md` da nova versão; identificar migrações e pacotes novos
2. Portão G-1 (fetch da nova tag)
3. Portão G-2 se houver novos pacotes
4. `docker compose down`; `git checkout vX.Y.Z`; `docker compose up -d --build`
5. Verificar `/health/ready` e log de migrações

**C. Recuperação de desastre**
1. Parar o container
2. Restaurar o diretório `/var/lib/backup-lc` a partir da cópia (ver 2.3)
3. Restaurar os segredos de `/etc/backup-lc/secrets`
4. Subir com a mesma tag que estava rodando; verificar `/health/ready`

**D. Desfazer uma migração de banco**
- Instrução com `alembic downgrade` via `docker compose run`; passos exatos

### 2.3. Procedimento de cópia de dados

Novo documento `docs/runbooks/backup-dados.md`:

- Descreve como copiar atomicamente `/var/lib/backup-lc` (banco SQLite + arquivos de configuração)
- Ferramenta recomendada: `rsync --checksum` ou snapshot LVM/ZFS, dependendo do sistema do cliente
- Frequência sugerida: diária, logo após a janela de coleta (configurável pelo operador)
- Verificação: comparar `sha256sum` do banco antes e depois da cópia
- Aviso: a cópia dos segredos (`master_key`) deve ser feita separadamente, em mídia offline, com controle de acesso distinto dos dados

### 2.4. Revisão de segurança

Checklist a ser executado na VM e documentado nas evidências:

| Item | Como verificar |
| --- | --- |
| Nenhum segredo em texto puro no banco | `sqlite3 backup-lc.db "SELECT * FROM credentials"` — deve mostrar apenas ciphertext |
| Nenhum segredo nos logs | `docker compose logs` com canários injetados nas credenciais |
| Arquivos de backup com permissão `0o600` | `find /var/lib/backup-lc/configs -type f -exec stat -c '%a %n' {} \;` |
| Container sem root | `docker compose exec app id` — deve retornar uid=10001 |
| Sistema de arquivos do container read-only (exceto volume) | `docker inspect backup-lc-app-1 --format '{{.HostConfig.ReadonlyRootfs}}'` |
| Sem JavaScript nas páginas | `grep -r '<script' src/backuplc/web/templates/` — zero resultados |
| Sem `style=""` inline nos templates | `grep -r 'style="' src/backuplc/web/templates/` — zero resultados |
| Headers de segurança HTTP | `curl -I http://localhost:8080/` — verificar `X-Content-Type-Options`, `X-Frame-Options` |
| `scripts/check.sh` passa | Ruff, mypy estrito, pytest |

### 2.5. Testes

| Tipo | O que cobre |
| --- | --- |
| Unit | `run_retention_cleanup`: versões antigas removidas; última versão preservada |
| Unit | `run_retention_cleanup`: arquivo físico não removido se referenciado por outra versão (deduplicação) |
| Unit | `run_retention_cleanup`: device sem versões antigas → nenhuma remoção |
| Unit | `BLC_RETENTION_DAYS=0` → nenhuma versão removida (guarda todas) |
| Integration | Job de retenção executa sem erro com banco de testes populado |
| Integration | Log JSON do job contém `versions_removed` e `bytes_freed` |

## 3. Fora do escopo

- Alertas por e-mail, SMS ou mensageiro (fora do PRD)
- Restauração automática de configuração nos switches (fora do PRD)
- Múltiplos servidores ou replicação (fora do PRD)
- Interface para gerenciar a retenção (fora do PRD)

## 4. Critérios de aceite

| ID | Dado | Quando | Então |
| --- | --- | --- | --- |
| E7-01 | Versões com mais de 365 dias e switch com versão mais recente | Job de retenção roda | Versões antigas removidas; última versão preservada (F-13) |
| E7-02 | Duas versões com mesmo `sha256_raw` (deduplicação), ambas antigas | Job de retenção roda | Arquivo físico só é removido quando **nenhuma** versão restante o referencia |
| E7-03 | Terceiro sem conhecimento prévio do sistema | Segue `docs/runbooks/instalacao.md` | Consegue instalar e ter `/health/ready` respondendo `ok` |
| E7-04 | Falha simulada (banco corrompido) | Terceiro segue procedimento C do runbook | Sistema restaurado a partir da cópia com todos os dados intactos |
| E7-05 | Checklist de segurança (2.4) | Executado na VM | Todos os itens passam |
| E7-06 | `scripts/check.sh` | Executa | Ruff, mypy estrito e pytest passam; sem acesso à rede |

## 5. Ações com impacto em rede (aprovação necessária)

| Portão | Ação | Quando |
| --- | --- | --- |
| G-1 | `git push` da tag `v0.7.0` | Fim da etapa |

Nenhum pacote Python novo previsto. Se necessário, G-2 antes.

## 6. Rastreabilidade

| Critério | Requisitos PRD |
| --- | --- |
| E7-01, E7-02 | F-13 |
| E7-03, E7-04 | N-03, N-06 |
| E7-05 | R-03, R-05, N-07, N-08 |
| E7-06 | R-06 |

## 7. Evidências de verificação (fase D)

| Critério | Resultado | Como verificado |
| --- | --- | --- |
| E7-01 | Passou | `test_versoes_antigas_removidas`, `test_ultima_versao_preservada_mesmo_sendo_antiga`, `test_sem_versoes_antigas_nenhuma_remocao`, `test_retention_days_zero_desabilita_limpeza` — 222/222 testes passando |
| E7-02 | Passou | `test_arquivo_nao_removido_com_dupla_referencia` — deduplicação reversa verificada |
| E7-03 | Passou | `docs/runbooks/instalacao.md` atualizado; procedimentos A (instalação do zero) e B (atualização) completos |
| E7-04 | Passou | `docs/runbooks/backup-dados.md` novo; procedimento de restauração documentado na seção 6 |
| E7-05 | Passou | Checklist de segurança adicionado ao runbook (seção 8); `scripts/check.sh` passa (Ruff, mypy estrito, pytest) |
| E7-06 | Passou | `scripts/check.sh` — 222 testes, 0 erros de lint, 0 erros de tipo |
