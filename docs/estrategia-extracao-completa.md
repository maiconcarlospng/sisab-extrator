# Estrategia de extracao completa do SISAB

> Especificacao do plano completo. As combinacoes abaixo sao CANDIDATAS por coerencia de dominio, nao uma matriz de compatibilidade confirmada com o SISAB. Somente o CSV real e as mensagens JSF confirmam suporte.

## Dois significados de Todos

- **Todos os CIAP/CID**: selecionar todos os codigos ou grupos disponiveis no filtro, para uma unica consulta. No R 0.3.3/Python 0.1.8, o parametro ciap_cid="auto" aciona isso quando CIAP/CID e linha ou coluna; ciap_cid="all" exige explicitamente. A implementacao cobre seletor HTML multiplo, checkboxes ou uma opcao Todos explicita. Para filtros via JavaScript/AJAX nao identificados, interrompe antes do POST.
- **Todos os dados do portal**: cobrir competencias, medidas, categorias e geografias sem multiplicar indiscriminadamente filtros que produzem resultados redundantes ou sao incompatíveis.

## Inspecao federal em 20/11/2026

O usuario observou 163 competencias, 29 opcoes de linha, 24 de coluna e os tipos Atendimento Individual (4), Atendimento Odontologico (5), Procedimento (7) e Visita Domiciliar (8). Isso comprova disponibilidade de opcoes, NAO compatibilidade de cruzamentos.

Produto cartesiano ingenuo: 163 competencias x 29 linhas x 24 colunas x 18 idades x 2 sexos x 4 tipos = **16.336.512 consultas**, sem contar outros filtros. Isso nao deve ser o plano de coleta.

## Matriz candidata a validar

| Tipo de producao | Dimensoes indicativas para testar | Cuidados |
|---|---|---|
| Atendimento Individual | CIAP/CID, problema/condicao avaliada, tipo/local de atendimento | Filtro CIAP/CID pode ser obrigatorio mesmo quando a coluna e CIAP/CID |
| Atendimento Odontologico | vigilancia em saude bucal, procedimento e conduta sb | Nem todas as dimensoes do atendimento individual se aplicam |
| Procedimento | procedimento e SIGTAP | Pode requerer escolha de codigos em filtro proprio |
| Visita Domiciliar | motivo, desfecho e tipo de imovel | Categorias proprias da visita; testar separadamente |

As linhas desta matriz sao HIPOTESES de validacao, nao comprovacoes do comportamento do portal.

## Fases propostas (modo Baixar tudo ainda NAO implementado)

1. **Descoberta**: catalogar opcoes de competencias, linhas, colunas e filtros condicionais; detectar se Todos e selecao multipla, opcao explicita ou widget AJAX.
2. **Matriz de compatibilidade**: testar uma competencia pequena por cruzamento candidato, e registrar valida, rejeitada ou sem dados. HTTP 200 com HTML nao e CSV.
3. **Plano minimo de cobertura**: preferir geografia mais granular quando suficiente para a pesquisa; distinguir totais e subtotais, para nao somar eventos duplicados. Usar separacoes por idade e sexo apenas quando necessario e disponiveis.
4. **Execucao incremental**: blocos mensais, pausas entre pedidos, retries somente para falhas temporarias, registro SQLite e retomada; nunca iniciar milhoes de consultas automaticamente.
5. **Auditoria**: guardar ZIP original, Parquet, parametros de consulta e resumo de meses, categorias e codigos realmente retornados, consultas sem dados e com erro.
6. **Atualizacoes**: priorizar novas competencias e reprocessar periodos historicos apenas quando houver indicios de retificacao.

## CIAP/CID

- CIAP/CID como linha/coluna implica Todos automaticamente no menu.
- Se HTML permitir selecao multipla, enviar os valores reais em uma consulta, sem criar uma requisicao por codigo.
- Se houver opcao Todos com valor explicito, usar somente ela.
- Se houver dropdown simples sem Todos ou opcoes apenas via JavaScript/AJAX, NAO enviar lsCid vazio nem inventar valores. O suporte completo depende de inspecao do mecanismo de selecao dinamica.
- Todos significa todos os codigos/grupos que o SISAB disponibilizar para esse relatorio e recorte, nao necessariamente todas as classificacoes CIAP-2 e CID-10 existentes.

## Criterio de funcionamento real

Somente considerar uma combinacao comprovada apos exportacao real de CSV, validacao do conteudo e registro do periodo e filtros. Os testes sinteticos comprovam a montagem do pedido, mas nao sua aceitacao pelo SISAB.
