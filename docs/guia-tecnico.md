# Guia técnico e histórico da documentação

> **Atualização (pacote R 0.2.1):** `sisab_instalar_motor()` agora cria
> automaticamente um ambiente Python exclusivo, independente do PySUS.
> `sisab_inspecionar()`, `sisab_planejar()`, `sisab_baixar()` e demais funções
> passam a usar esse ambiente sem informar `python`. Comandos antigos deste
> histórico podem descrever o funcionamento anterior. Veja o
> [README atual](../README.md) para o procedimento recomendado.

Este documento guarda as instruções completas da versão anterior do README, incluindo comandos Python, caminhos dos arquivos, detalhes do formato Parquet e limitações do extrator.

Para uma introdução simples e passo a passo no RStudio, consulte o **[README principal](../README.md)**.

---

# SISAB Extrator

Extrator em Python de **relatórios agregados públicos** do SISAB. Inspirado na
organização do projeto [`rfsaldanha/sisab_scrapper`](https://github.com/rfsaldanha/sisab_scrapper),
com configuração dos filtros encontrados no formulário, cache das respostas originais,
Parquet por consulta, **consolidação anual e, em seguida, da série histórica**.

> **Estado: protótipo experimental.** A lógica básica e os testes locais foram
> desenvolvidos, mas o formulário federal e o municipal **não foram testados
> contra o site ao vivo**. A disponibilidade de colunas, opções, competências e
> combinações depende do SISAB. Não há nenhuma promessa de acesso a microdados
> individuais ou de extração de CIDs não oferecidos pelo relatório público.

## O que faz

- `probe`: lê o formulário JSF e lista **competências, linhas, colunas e demais campos** encontrados. Não inventa códigos para opções do portal.
- `plan`: gera `.jsonl` com consultas por competência, linha, coluna, faixa etária e sexo. É possível selecionar `--columns "CIAP/CID"` **se essa opção aparecer no `probe`**.
- `download`: baixa os CSVs originais disponíveis, preserva-os em ZIP, transforma em Parquet (uma linha por categoria/contagem), registra no SQLite e retoma a execução.
- **Ao concluir os downloads:** reúne os Parquets mensais em um Parquet **anual** por ano e usa os anuais para gerar um Parquet da **série histórica** do período solicitado.
- `consolidate`: refaz os consolidados sem baixar novamente; `status`: mostra progresso e falhas.

## Instalação

Python 3.10+:

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows (PowerShell): .venv\\Scripts\\Activate.ps1
pip install -e .
sisab-extrator --help
```

## Comece pela inspeção

```bash
sisab-extrator probe --report federal
sisab-extrator probe --report municipal
```

Isso grava `data/inspecao/federal.json` e `data/inspecao/municipal.json`.
Abra esses arquivos para confirmar **os rótulos e valores reais** de `selectLinha` e `selectcoluna`.
O relatório federal pode usar controles diferentes da implementação conhecida
para o municipal. Nesse caso, o comando avisa que é necessário adaptar o parser.

## Plano de download: CIAP/CID por município

Exemplo a validar após inspecionar o portal:

```bash
sisab-extrator plan \
  --report federal \
  --start 201801 --end 202512 \
  --lines Municipio --columns 'CIAP/CID' \
  --ages all --sexes both \
  --allow-large-plan
```

As escolhas por rótulo não diferenciam acentos em `Municipio` e `Município`;
se houver erro de correspondência, forneça o **valor** da opção mostrado no `probe`.

## Todos os anos, todas as linhas e colunas

**Primeiro confira o plano**: todas as combinações podem levar a dezenas de
milhares de requisições e algumas podem ser inválidas para o portal.

```bash
sisab-extrator plan \
  --report all --start auto --end auto \
  --lines all --columns all --ages all --sexes both \
  --allow-large-plan
```

Para iniciar os downloads com esses mesmos parâmetros:

```bash
sisab-extrator download \
  --report all --start auto --end auto \
  --lines all --columns all --ages all --sexes both \
  --allow-large-plan
```

**Atenção:** `--allow-large-plan` não acelera o SISAB. O comando espera pelo
portal entre requisições (padrão 2 segundos), aplica tentativas com espera
progressiva e registra erros. O plano pode gerar consultas sem dados ou não
suportadas pelo site. Não use execução paralela agressiva.

### Faça primeiro uma execução pequena

```bash
sisab-extrator download \
  --report municipal --start 202401 --end 202401 \
  --lines Municipio --columns 'CIAP/CID' \
  --ages none --sexes none
```

Substitua a coluna pelo valor que o `probe` realmente mostrar caso necessário.

## Resultados

```text
data/
  consultas.sqlite
  inspecao/
    federal.json
    municipal.json
  planos/
    plano.jsonl
  brutos/
    federal/2024/202401/<id_da_consulta>.csv.zip
  mensal/
    federal/2024/202401/<id_da_consulta>.parquet
  consolidado/
    anual/
      sisab_2023.parquet
      sisab_2024.parquet
    serie/
      sisab_202301_202412.parquet
      sisab_202301_202412.manifesto.json
```

Os arquivos mensais são **Parquets por consulta**, organizados por competência.
O anual é a concatenação das consultas completas conhecidas daquele ano e a
série é a concatenação dos anuais **filtrada para o período solicitado**.

### Refazer consolidação

```bash
sisab-extrator consolidate --start 201801 --end 202512
sisab-extrator status
```

Se houver consultas pendentes ou com erro, a consolidação é bloqueada por
padrão, para não produzir uma série enganosa. `--allow-partial` serve apenas
para uma análise explicitamente incompleta.

## Colunas Parquet

`consulta_id`, `competencia`, `ano`, `relatorio`, `fonte_url`, `linha`,
`coluna`, `faixa_etaria`, `sexo`, `uf`, `ibge`, `municipio`, `categoria`,
`valor`, `dimensoes_json`.

- `categoria` é o **nome exato da coluna de medida retornada no CSV**. Se
  `selectcoluna=CIAP/CID`, pode ser um código de CID/CIAP, mas **não se
  assume** que todos os valores sejam códigos válidos.
- `dimensoes_json` preserva os rótulos e valores das dimensões da tabela.
- Célula vazia ou suprimida (`-`) é **ausente**, não zero. Contagem `0`
  explicitamente fornecida é preservada.
- Uma consulta pode aparecer em diversas visões; **não some indiscriminadamente
  registros de consultas com linhas/colunas diferentes**. O consolidado não
  faz soma ou desduplicação automática de indicadores diferentes.

## Limites e validação necessária

1. **Sem microdados individuais:** os arquivos públicos são tabulações agregadas.
2. **CID:** o código do projeto de referência contém um campo `lsCid`, mas
   isso não comprova que ele possa ser usado livremente como filtro. Esta
   versão permite consultar CIAP/CID **como coluna quando a opção existe**.
3. **Campos variáveis:** alguns relatórios federais, linhas de equipes e
   estabelecimentos podem ter cabeçalhos não reconhecidos pelo parser.
   Os CSVs originais são preservados e erros são registrados, sem fabricar
   medidas. Amplie `DIMENSIONS` conforme os CSVs reais.
4. **Não é um crawler ilimitado do portal:** o MVP abrange os dois endereços
   conhecidos de produção/saúde. Outros relatórios públicos podem ser
   testados com `--report-url https://sisab.saude.gov.br/.../Relatorio.xhtml`,
   desde que usem estrutura compatível.
5. A página usa JSF e pode mudar controles, sessão, ViewState e resposta
   AJAX. Ajustes podem ser necessários após validar no portal ao vivo.
6. Não contorna autenticação, CAPTCHA, medidas de segurança nem limites
   administrativos; use respeitando as condições de acesso.

## Testes locais

```bash
pip install -e '.[dev]'
pytest -q
```

Os testes não fazem requisições ao SISAB. Para validar o download real,
inspecione a página, rode uma competência e compare o CSV exportado manualmente.

## Referência / créditos

Projeto original de referência: [rfsaldanha/sisab_scrapper](https://github.com/rfsaldanha/sisab_scrapper).
Esta implementação é independente, voltada à parametrização, rastreabilidade
e à consolidação em Parquet; não é endossada pelo Ministério da Saúde.

## Repositório

[Código-fonte do SISAB Extrator](https://github.com/maiconcarlospng/sisab-extrator).

## Pacote R — instalação pelo GitHub e R-universe

A interface R `sisabextrator` agora fica na **raiz** deste repositório,
com `DESCRIPTION`, `NAMESPACE`, `R/` e `man/`. A subpasta
`rpkg/` é mantida temporariamente apenas para compatibilidade.

### Instalação pelo GitHub (disponível)

```r
install.packages("remotes")
remotes::install_github("maiconcarlospng/sisab-extrator")
library(sisabextrator)
```

### Instalação pelo R-universe (depois de ativar o universo)

```r
install.packages(
  "sisabextrator",
  repos = c("https://maiconcarlospng.r-universe.dev", "https://cloud.r-project.org")
)
library(sisabextrator)
```

**Primeira publicação:** o repositório de configuração
[`maiconcarlospng.r-universe.dev`](https://github.com/maiconcarlospng/maiconcarlospng.r-universe.dev)
e seu `packages.json` já foram criados. O GitHub App foi autorizado com acesso
a todos os repositórios. Segundo a [etapa de primeira compilação da documentação
do R-universe](https://docs.r-universe.dev/publish/set-up.html#wait-first-build),
o processamento inicial pode levar **cerca de 1 hora**. Durante esse intervalo,
a mensagem `No packages found for this owner or maintainer` e a ausência do
índice `PACKAGES` podem indicar apenas que a indexação ainda não terminou.

**A compilação aprovada no GitHub Actions não substitui a compilação no
R-universe.** Só tente instalar pelo repositório R-universe quando o pacote
estiver listado em https://maiconcarlospng.r-universe.dev/.

Se, **após pelo menos 1 hora** desde a ativação, o universo permanecer vazio,
consulte os registros do serviço e a
[documentação de publicação](https://docs.r-universe.dev/publish/set-up.html)
antes de alterar a configuração. Não é necessário criar novamente os
repositórios ou reinstalar o GitHub App.

O pacote R pode ser instalado sem Python para leitura de arquivos Parquet;
**para baixar do SISAB**, o motor Python 3.10+ é instalado separadamente:

```r
sisab_instalar_motor(python = "python")
sisab_inspecionar(relatorio = "federal")
```

Para análise das bases Parquet, instale `arrow` e `dplyr` e filtre
os dados antes de `collect()`:

```r
install.packages(c("arrow", "dplyr"))
library(dplyr)
dados <- sisab_abrir_anuais()
mg <- sisab_filtrar_mg(dados)
recorte <- mg |>
  filter(competencia == "202401", coluna == "CIAP/CID") |>
  collect()
```

**Atenção:** exemplos de filtros dependem da nomenclatura real das opções
encontradas em `sisab_inspecionar()`; o motor é experimental e os relatórios
SISAB públicos trazem contagens agregadas, não prontuários individuais.
Consultas diferentes podem medir os mesmos atendimentos. Não some visões
sobrepostas.

### Publicar no R-universe

O R-universe requer um **outro** repositório público chamado
[`maiconcarlospng.r-universe.dev`](https://github.com/maiconcarlospng/maiconcarlospng.r-universe.dev)
na mesma conta do GitHub. Nele, crie um `packages.json` na raiz com o
conteúdo de [`r-universe/packages.json`](r-universe/packages.json).
**Não use `subdir`**: o pacote R está agora na raiz de `sisab-extrator`.

Depois, instale o
[GitHub App R-universe](https://github.com/apps/r-universe/installations/new)
na conta `maiconcarlospng`, concedendo acesso ao repositório do universo e
ao repositório do pacote. Consulte a
[documentação oficial](https://docs.r-universe.dev/publish/set-up.html).
A primeira compilação pode levar cerca de 1 hora; verifique a página e os registros do R-universe antes de diagnosticar falhas.

### Histórico de grandes volumes

- **Memória:** os ZIPs e os Parquets são tratados por lotes; análises no R
  usam `arrow::open_dataset()` e filtros preguiçosos.
- **Esquema:** os Parquets usam esquema canônico para evitar conflitos de
  tipagem entre os anos. Respostas originais são preservadas para auditoria.
- **2013:** o modo automático usa as competências disponibilizadas no site,
  sem assumir `201301` a `201303` como disponíveis.
- **Falhas de rede:** estado de consultas no SQLite, retomada e tentativas
  com espera progressiva.
- O download HTTP de **uma resposta individual** ainda pode consumir RAM
  proporcional ao tamanho dessa resposta.
