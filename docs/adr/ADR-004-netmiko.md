# ADR-004 — Netmiko para coleta SSH

**Status:** Aceita · 2026-11-04 (dependência adicionada só na E3)

**Contexto:** Os fabricantes dos switches ainda não são conhecidos (P-01). É preciso tratar paginação, prompts e diferenças de comando.

**Decisão:** Netmiko como base. Cada tipo de switch é um "driver" pequeno no sistema: tipo Netmiko, comando permitido, linhas voláteis e marcador de fim.

**Alternativas:** Paramiko puro (muito código por fabricante); Scrapli (bom, mas cobertura menor de fabricantes).

**Consequências:** Novos fabricantes entram como novos drivers, sem mudar o núcleo. A dependência só é baixada na E3, com nova aprovação G-2.
