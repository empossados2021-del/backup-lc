# ADR-006 — Credenciais cifradas com chave em arquivo

**Status:** Aceita · 2026-11-04

**Contexto:** Senhas dos switches nunca podem ficar em texto puro (R-05).

**Decisão:** Cifra autenticada Fernet (biblioteca `cryptography`). Chave mestra em arquivo (`BLC_MASTER_KEY_FILE`, permissão 600) fora do diretório de dados. O banco guarda apenas texto cifrado e o identificador da chave. A senha decifrada só existe na memória durante a coleta e nunca é exibida de volta na tela.

**Alternativas:** Cofre dedicado (mais um serviço para operar).

**Consequências:** A chave mestra precisa de cópia de segurança separada; sem ela, as credenciais são perdidas (as configurações já coletadas continuam legíveis). Rotação de chave fica para versão futura.
