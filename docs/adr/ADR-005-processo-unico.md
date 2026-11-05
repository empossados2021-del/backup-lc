# ADR-005 — Agendador e coletor no mesmo processo

**Status:** Aceita · 2026-11-04

**Contexto:** O sistema deve ser o mais simples possível e rodar num único servidor.

**Decisão:** Um processo com a web, o agendador (APScheduler, adicionado na E4) e um pool limitado de threads de coleta. O estado das execuções fica no banco; ao iniciar, execuções "em andamento" de um processo anterior são marcadas como falha.

**Alternativas:** Fila em banco com workers separados; broker dedicado. Ambos acrescentam peças sem necessidade no volume previsto.

**Consequências:** Um único worker Uvicorn. Reinício interrompe coletas em curso, que são refeitas pela retentativa.
