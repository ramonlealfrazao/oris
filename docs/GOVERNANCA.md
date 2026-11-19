# Governança no ORIS

A área **Governança** (menu lateral, `/governanca`) reúne o alinhamento do sistema com a ISO/IEC 38500 e os instrumentos de governança pedidos nas unidades SR1 e SR2. Todos os perfis autenticados podem consultar. Só números agregados aparecem; nenhum dado pessoal.

| Requisito | Unidade | Onde no sistema |
|---|---|---|
| Alinhamento com a ISO 38500 | SR1 | `/governanca`: os seis princípios, cada um com indicadores calculados na hora, evidência e lacuna |
| Mapeamento de riscos (probabilidade × impacto) | SR1 | `/governanca/riscos`: 12 riscos, nível calculado, mapa de calor |
| Matriz RACI | SR1 | `/governanca/raci` |
| COBIT 2019 | SR1 | `/governanca/cobit` |
| Conformidade com a LGPD | SR1 | `/privacidade`, `/lgpd/meus-dados`, `/lgpd/solicitacoes` (ver `docs/LGPD.md`) |
| Plano de auditoria | SR2 | `/governanca/auditoria`: cronograma, checklist e atalhos para a trilha |
| Trilha de auditoria | SR2 | `/auditoria` e `/governanca/auditoria` (elementos e garantias de integridade) |
| Dilemas éticos | SR2 | `/governanca/etica` |
| Governança em nuvem | SR2 | `/governanca/nuvem`: responsabilidade AWS × grupo |
| Plano de mitigação | SR2 | `/governanca/riscos`: ação, responsável, prazo e se mexe no sistema |

## Indicadores ao vivo

Calculados a cada acesso por `app/services/governanca_service.py`, sem tabela nova:

- **Responsabilidade:** usuários ativos por perfil e contas vindas do diretório.
- **Estratégia:** unidades e serviços ativos, equipamentos cadastrados.
- **Aquisição:** equipamentos em manutenção, manutenções abertas e custos.
- **Desempenho:** percentual de equipamentos operantes e unidades Críticas (menos de 50%) e em Atenção (menos de 80%), a mesma regra de `fn_classificar_unidade`.
- **Conformidade:** registros na trilha, falhas dos últimos 30 dias, pedidos de titulares abertos e vencidos, registros além da retenção.
- **Comportamento humano:** alterações pendentes, aprovadas, rejeitadas e taxa de rejeição.

## Onde editar o conteúdo

Os textos (princípios, riscos, RACI, COBIT, plano de auditoria, dilemas, nuvem e mitigação) ficam em `app/services/governanca_dados.py`. Probabilidades e impactos dos riscos são estimativas do grupo; ao mudar `p` ou `i`, o nível e o mapa de calor se atualizam sozinhos.

## Implantação

A mudança cria uma tabela nova (`solicitacoes_titular`) com `db.create_all()`, que o `database/aplicar_migracoes.py` já executa na subida do contêiner. Nenhuma tabela existente é alterada. As variáveis `LGPD_*` são opcionais.
