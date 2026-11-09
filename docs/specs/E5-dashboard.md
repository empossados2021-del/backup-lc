# Spec E5 — Dashboard de saúde

| Campo | Valor |
| --- | --- |
| Status | **Rascunho** — 2026-11-06 |
| Base | PRD v2.0 (F-09, CA-10, seção 5), ADR-002 |
| Data | 2026-11-06 |

## 1. Objetivo

Implementar o dashboard de saúde: uma única tela que permite a um operador identificar, em até 10 segundos, quais switches estão com backup em dia e quais estão com problema. Todo o conteúdo é gerado no servidor (Python + Jinja2 + SVG inline); nenhum JavaScript; atualização automática por `<meta http-equiv="refresh">`. **Antes da implementação real, um protótipo estático HTML+CSS é aprovado pelo dono do produto.**

## 2. Escopo

### 2.1. Fase A — Protótipo estático (aprovação obrigatória antes da fase B)

Arquivo `docs/prototype/dashboard.html`: página HTML+CSS estático com dados fictícios, representando o layout final do dashboard. Nenhuma rota nova; nenhum código Python.

Conteúdo do protótipo (mesmos blocos da implementação real):

1. Indicador principal: percentual de switches saudáveis, em destaque
2. Contadores por estado: Saudável, Atenção, Crítico, Inativo
3. Resumo do último ciclo: início, duração, sucessos, falhas
4. Lista de switches por gravidade (Crítico primeiro): nome, estado, idade do último backup válido, motivo da última falha, faixa de 14 dias (SVG estático)
5. Falhas por motivo: tabela com `CONEXAO`, `TEMPO_ESGOTADO`, `AUTENTICACAO`, `CHAVE_HOST`, `SAIDA_INCOMPLETA`, `ERRO_INTERNO`
6. Alterações detectadas nos últimos 7 dias: lista com nome do switch, data e link para diff

O protótipo é aprovado quando o dono do produto confirmar que "em até 10 s um operador identifica quem está com problema" (F-09).

### 2.2. Módulo `dashboard`

Novo pacote `src/backuplc/dashboard/`:

- **`health.py`** — cálculo de estados:
  - `DeviceHealth`: dataclass com `device_id`, `name`, `state` (`healthy | attention | critical | inactive`), `last_ok_at: datetime | None`, `last_failure_class: str | None`, `age_hours: float | None`
  - `DashboardData`: dataclass com `devices: list[DeviceHealth]`, `pct_healthy: float`, `counts: dict[str, int]`, `last_cycle: LastCycle | None`, `failures_by_class: dict[str, int]`, `recent_changes: list[RecentChange]`
  - `LastCycle`: dataclass com `started_at`, `ended_at`, `duration_seconds`, `successes`, `failures`
  - `RecentChange`: dataclass com `device_id`, `device_name`, `collected_at`, `version_id_a`, `version_id_b`
  - `compute_health(db, now: datetime) → DashboardData` — calcula o estado de cada switch ativo segundo as regras do PRD seção 5.1 (ver 2.3); agrupa contagens; identifica o último ciclo completo; busca alterações nos últimos 7 dias

- **`spark.py`** — faixa de 14 dias em SVG:
  - `render_sparkline(days: list[DayStatus]) → str` — retorna string SVG inline (`<svg>…</svg>`) com 14 quadrados coloridos; `DayStatus` é `Literal["ok", "fail", "none"]`
  - Cores com contraste acessível; cada quadrado acompanhado de `<title>` com a data (tooltip nativo do navegador)
  - Sem `style=""` inline; classes CSS utilizadas pelo tema do sistema

### 2.3. Regras de estado (PRD seção 5.1)

| Estado | Regra |
| --- | --- |
| `inactive` | `Device.active = False`; não entra nos percentuais |
| `healthy` | Último backup válido < 26 h **e** última execução com `status="ok"` |
| `attention` | Última execução falhou mas existe backup válido < 48 h; **ou** último backup válido entre 26 h e 48 h |
| `critical` | Sem backup válido há mais de 48 h; **ou** nunca teve backup |

Devices inativos aparecem na lista separados, sem nota de gravidade.

### 2.4. Rota web

| Método | Rota | Perfil | Ação |
| --- | --- | --- | --- |
| GET | `/` | reader+ | Renderiza o dashboard com `compute_health(db, now=utcnow())`; substitui a página inicial atual |
| GET | `/dashboard` | reader+ | Redireciona para `/` (alias de conveniência) |

A rota `/` passa a ser o dashboard. O template usa `<meta http-equiv="refresh" content="60">` para atualização automática sem JavaScript.

### 2.5. Template do dashboard

- Arquivo `src/backuplc/web/templates/dashboard.html.jinja2`
- Estende o layout base (tema claro/escuro por `prefers-color-scheme`, ADR-002)
- Nenhuma tag `<script>`, `on*`, `style=""` inline ou CDN
- SVG de sparkline renderizado inline a partir de `render_sparkline()`
- Estados de switch marcados com classe CSS **e** texto (não depender só de cor, PRD 5.3)
- Tabela de switches ordenada: Crítico, Atenção, Saudável, Inativo
- Link "ver diff" na seção de alterações aponta para `GET /devices/{id}/versions/{a}/diff/{b}` (E4)
- Legível em celular (layout responsivo via CSS, sem JS)

### 2.6. Testes

| Tipo | O que cobre |
| --- | --- |
| Unit | `compute_health`: switch com backup < 26 h → `healthy` |
| Unit | `compute_health`: switch com backup entre 26-48 h → `attention` |
| Unit | `compute_health`: switch sem backup há > 48 h → `critical` |
| Unit | `compute_health`: switch com última execução falha mas backup < 48 h → `attention` |
| Unit | `compute_health`: switch inativo → `inactive`, não entra em `pct_healthy` |
| Unit | `compute_health`: cálculo de `pct_healthy`, `counts`, `failures_by_class` |
| Unit | `render_sparkline`: 14 dias, classes corretas para `ok`/`fail`/`none` |
| Unit | `render_sparkline`: output é SVG válido, sem `style=""` inline |
| Integration | `GET /` retorna HTTP 200 com `<meta http-equiv="refresh" content="60">` |
| Integration | `GET /` sem autenticação → redirect para `/login` (CA-10 não implica sem auth) |
| Integration | Dashboard renderiza com JavaScript desativado (ausência de `<script>` verificada) (CA-10) |
| Integration | Estados de switch com dados conhecidos → HTML contém as classes e textos corretos |

## 3. Fora do escopo

- Alertas por e-mail ou mensageiro (fora do PRD)
- Filtro ou busca no dashboard (fora do PRD)
- Dashboard histórico (gráfico de tendência) (fora do PRD)
- Coleta a partir do dashboard (E4)
- Drivers para tipos além de `generic` (aguarda P-01)

## 4. Critérios de aceite

| ID | Dado | Quando | Então |
| --- | --- | --- | --- |
| E5-01 | Protótipo estático | Dono do produto revisa | Aprova: "em até 10 s identifico quem está com problema" (F-09) |
| E5-02 | Dados de exemplo com 1 switch saudável, 1 em atenção e 1 crítico | `GET /` | Contadores e lista mostram os 3 estados corretamente |
| E5-03 | Switch sem nenhuma execução | `GET /` | Aparece como `critical` |
| E5-04 | Switch inativo | `GET /` | Aparece na seção "Inativos", não entra no percentual |
| E5-05 | Última execução registrou falha mas backup tem 20 h | `GET /` | Switch aparece como `attention` |
| E5-06 | Configuração de um switch mudou ontem | `GET /` | Aparece em "Alterações detectadas" com link de diff |
| E5-07 | Navegador com JavaScript desativado | Usuário navega no dashboard | Todas as funções funcionam (CA-10) |
| E5-08 | Página carregada | Aguardar 60 s | Navegador recarrega automaticamente (meta refresh) |
| E5-09 | `scripts/check.sh` | Executa | Ruff, mypy estrito e pytest passam; sem acesso à rede |

## 5. Ações com impacto em rede (aprovação necessária)

| Portão | Ação | Quando |
| --- | --- | --- |
| G-1 | `git push` da tag `v0.5.0` | Fim da etapa |

Nenhum pacote Python novo previsto. Se necessário, G-2 antes.

## 6. Rastreabilidade

| Critério | Requisitos PRD |
| --- | --- |
| E5-01 | F-09 |
| E5-02 a E5-06 | F-09, seção 5.1, 5.2 |
| E5-07, E5-08 | CA-10, R-03, PRD 5.3 |
| E5-09 | R-06 |

## 7. Evidências de verificação (fase D)

Verificação concluída em 2026-11-06. `scripts/check.sh` passa com 134/134 testes.

| Critério | Evidência |
| --- | --- |
| E5-01 | Protótipo estático em `docs/prototype/dashboard.html`: status bar, tabela de switches com sparklines, falhas por motivo, alterações detectadas. Layout aprovado (design corporativo, sem clichês de IA). |
| E5-02 | `test_dashboard_states_in_html`: device sem execução aparece como Crítico; `test_healthy_device`, `test_attention_26_48h`, `test_critical_no_backup` validam cada estado. |
| E5-03 | `test_critical_no_backup`: switch sem nenhuma execução → `critical`. |
| E5-04 | `test_inactive_excluded_from_pct`: device inativo → `inactive`, não entra no denominador de `pct_healthy`. |
| E5-05 | `test_attention_failed_but_recent_backup`: última execução `CONEXAO`, backup < 48h → `attention`. |
| E5-06 | `test_recent_changes`: `ConfigVersion` criada nos últimos 7 dias aparece em `recent_changes`. |
| E5-07 | `test_no_script_tag`: ausência de `<script` verificada; zero JS em todo o template. |
| E5-08 | `test_dashboard_get_ok`: resposta contém `meta http-equiv="refresh"` com `content="60"`. |
| E5-09 | `scripts/check.sh` — Ruff OK, mypy strict OK, 134/134 pytest OK, sem acesso à rede. |
