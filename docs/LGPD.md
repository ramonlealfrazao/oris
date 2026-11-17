# ORIS e a LGPD

Resumo de como o sistema atende a Lei Geral de Proteção de Dados (Lei nº 13.709/2018). O que o ORIS faz está no código; o que depende de decisão do órgão responsável fica em variáveis de ambiente.

## O que está no sistema

| Exigência | Onde |
|---|---|
| Transparência: controlador, encarregado, finalidade, dados, base legal, operadores, direitos, retenção, incidentes (arts. 6º, 9º, 18 e 41) | Página pública `/privacidade` |
| Registro das operações de tratamento (art. 37) | Tabela na página `/privacidade`, mantida em `app/services/lgpd_service.py` (`OPERACOES_TRATAMENTO`) |
| Acesso e confirmação dos dados (art. 18, I e II) | `/lgpd/meus-dados` mostra cadastro, grupos e ações registradas em nome do usuário |
| Portabilidade (art. 18, V) | Botão "Exportar meus dados" baixa um JSON, sem hash de senha; a exportação é auditada |
| Correção, eliminação, compartilhamento e oposição (art. 18, III, IV, VII e §2º) | Formulário em `/lgpd/meus-dados`; o pedido vira registro em `solicitacoes_titular` com prazo de resposta |
| Atendimento dos pedidos | `/lgpd/solicitacoes` (só Administrador): responde, atende ou nega, com registro na auditoria |
| Anonimização da conta | Ação do Administrador no pedido de eliminação: troca nome e e-mail por valores anônimos, invalida a senha, remove grupos e desativa a conta |
| Segurança (art. 46) | Ver `docs/SEGURANCA.md` |
| Prestação de contas (art. 6º, X) | Trilha de auditoria imutável; indicadores de conformidade em `/governanca` |

Toda ação desta lista gera registro na trilha: `LGPD_SOLICITACAO`, `LGPD_RESPOSTA`, `LGPD_EXPORTACAO` e `LGPD_ANONIMIZACAO`.

## O que a organização precisa definir

Estas decisões não são do código. Ficam no `.env` (ver `.env.example`):

| Variável | Para quê |
|---|---|
| `LGPD_CONTROLADOR` | Nome do controlador (padrão: Secretaria de Saúde do Recife) |
| `LGPD_ENCARREGADO_NOME` e `LGPD_ENCARREGADO_EMAIL` | Encarregado de dados (art. 41); enquanto vazias, a página informa que ainda não foi designado |
| `LGPD_BASE_LEGAL` | Texto da base legal; o padrão é a execução de políticas públicas (art. 7º, III, e art. 23) e precisa ser confirmado pelo jurídico do controlador |
| `LGPD_RETENCAO_AUDITORIA_ANOS` | Prazo mínimo de guarda da trilha (padrão 1) |
| `LGPD_PRAZO_RESPOSTA_DIAS` | Prazo para responder pedidos de titulares (padrão 15) |

## Relatório de impacto simplificado (RIPD, art. 38)

- **Dados:** nome, e-mail, perfil, hash de senha, IP e ações dos usuários do sistema. Sem dados de saúde, de pacientes, CPF, telefone ou endereço.
- **Titulares:** servidores e pessoas autorizadas a usar o ORIS.
- **Riscos aos titulares:** vazamento de e-mail e IP; uso da trilha para avaliar pessoas além da finalidade de segurança.
- **Medidas:** acesso por perfil, trilha restrita a Administrador e Gestão da Informação, HTTPS com HSTS, banco em disco criptografado, senha só como hash, exportação e anonimização sob pedido.
- **Conclusão:** risco baixo com o escopo atual. A análise deve ser refeita se o sistema passar a tratar dados clínicos ou de pacientes.

## Retenção e eliminação

- A trilha é mantida por no mínimo `LGPD_RETENCAO_AUDITORIA_ANOS` e a aplicação não a apaga. O arquivamento depois do prazo é do administrador do banco, com backup testado antes. O painel de governança mostra quantos registros já passaram do prazo.
- A anonimização de uma conta não altera a trilha: os registros continuam ligados ao número da conta, sem nome nem e-mail. A manutenção desses registros se apoia no cumprimento de obrigação legal e na segurança (art. 16, I, e art. 6º, VII). O e-mail digitado em tentativas de login que falham também fica na trilha e não é alterado pelos triggers de imutabilidade.
- Contas desativadas não são apagadas, para preservar a integridade do histórico.

## Incidentes de segurança (art. 48)

1. Quem perceber o problema avisa o Administrador e o encarregado.
2. Conter: desativar contas envolvidas, trocar segredos (`SECRET_KEY`, senhas do banco, chaves), isolar o servidor se necessário.
3. Levantar na trilha de auditoria o que foi acessado, por quem, de que IP e quando.
4. O controlador avalia se há risco ou dano relevante aos titulares. Se houver, comunica a ANPD e os titulares em prazo razoável, com a descrição dos dados afetados, os titulares envolvidos, as medidas de segurança, os riscos e as providências tomadas.
5. Registrar o incidente, a causa e a correção, e atualizar a matriz de riscos em `/governanca/riscos`.

## Limites

- Os dados dos pedidos ficam na tabela `solicitacoes_titular`, no mesmo banco do sistema.
- A hospedagem na AWS em região fora do Brasil caracteriza transferência internacional (arts. 33 a 36), a avaliar pelo controlador.
- Este documento não substitui parecer jurídico.
