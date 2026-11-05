# ADR-007 — Configurações em arquivos endereçados por SHA-256

**Status:** Aceita · 2026-11-04

**Contexto:** É preciso guardar versões, verificar integridade e copiar tudo facilmente.

**Decisão:** Cada versão é gravada em `BLC_DATA_DIR/configs/<aa>/<sha256>`, com gravação em arquivo temporário e renomeação atômica, permissão 600. O banco guarda switch, data, tamanho e hash. Conteúdo idêntico não é gravado duas vezes.

**Alternativas:** Conteúdo no banco (banco cresce e fica difícil de inspecionar); armazenamento de objetos (serviço extra).

**Consequências:** Integridade verificável recalculando o hash. Os arquivos nunca são servidos diretamente; o download passa por rota com autorização.
