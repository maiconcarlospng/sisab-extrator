<p align="center">
  <img src="assets/capa-sisab-extrator.webp" width="100%" alt="SISAB Extrator: ilustração de dados públicos da atenção primária passando de CSV a Parquet, com mapa do Brasil, computador e gráficos." />
</p>

<p align="center">
  <a href="https://maiconcarlospng.r-universe.dev/"><img alt="R-universe" src="https://img.shields.io/badge/R--universe-publica%C3%A7%C3%A3o-128C91?style=for-the-badge" /></a>
  <img alt="R" src="https://img.shields.io/badge/R-4.0%2B-276DC3?style=for-the-badge&logo=r&logoColor=white" />
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img alt="Parquet" src="https://img.shields.io/badge/sa%C3%ADda-Parquet-095E73?style=for-the-badge" />
  <img alt="Licença MIT" src="https://img.shields.io/badge/licen%C3%A7a-MIT-2D715C?style=for-the-badge" />
</p>

<p align="center">
  <strong>Dos relatórios públicos do SISAB à análise de dados no RStudio.</strong>
</p>

<p align="center">
  <a href="https://github.com/maiconcarlospng/sisab-extrator#comece-aqui--instala%C3%A7%C3%A3o-e-uso-em-poucos-comandos">Comece aqui</a> ·
  <a href="https://github.com/maiconcarlospng/sisab-extrator#o-que-ele-faz">Conheça o projeto</a> ·
  <a href="https://github.com/maiconcarlospng/sisab-extrator#pr%C3%A9-requisitos-para-usar-o-sisab-extrator">Pré-requisitos</a> ·
  <a href="https://github.com/maiconcarlospng/sisab-extrator#instala%C3%A7%C3%A3o-no-rstudio">Instale no R</a> ·
  <a href="https://github.com/maiconcarlospng/sisab-extrator#primeiro-download">Primeiro download</a> ·
  <a href="https://github.com/maiconcarlospng/sisab-extrator#onde-ficam-os-dados">Arquivos gerados</a> ·
  <a href="https://github.com/maiconcarlospng/sisab-extrator#perguntas-frequentes">Dúvidas frequentes</a>
</p>

---

## 👋 O que é o SISAB Extrator?

O **SISAB Extrator** é um projeto gratuito e de código aberto para ajudar estudantes, pesquisadores e profissionais de saúde a **consultar, baixar e organizar dados públicos do SISAB** (Sistema de Informação em Saúde para a Atenção Básica).

A ideia é reduzir o trabalho manual de baixar muitos arquivos do portal e facilitar estudos sobre a **Atenção Primária à Saúde (APS)**.

> [!IMPORTANT]
> **Projeto experimental.** O pacote e sua organização de dados foram desenvolvidos e testados, mas a extração nos formulários reais do SISAB ainda precisa ser validada. As opções disponíveis dependem do portal. **Não são microdados de pacientes.**

## Comece aqui — instalação e uso em poucos comandos

No **RStudio**, instale o pacote R uma vez:

```r
if (!requireNamespace("remotes", quietly = TRUE)) install.packages("remotes")
remotes::install_git("https://github.com/maiconcarlospng/sisab-extrator.git", upgrade = "never")
```

Reinicie a sessão do R (menu **Session → Restart R**) e use apenas:

```r
library(sisabextrator)
sisab()
```

O comando **`sisab()` abre um menu** com estas escolhas:

- **Baixar dados:** escolha relatório, competência, linha, coluna e, quando
  necessário, o tipo de produção em listas construídas com as opções reais do
  SISAB; o progresso é mostrado no console
- **Visualizar Parquet:** escolha o arquivo no Explorador do Windows e veja
  as primeiras 100 linhas no RStudio
- **Ver status:** consulte downloads concluídos, pendentes e com erro

**Não é necessário executar `sisab_instalar_motor()` separadamente.**
No primeiro download, o programa cria um ambiente Python próprio e instala o
motor automaticamente; quando detectar uma versão antiga do motor, atualiza-a
sem alterar o Python utilizado por PySUS ou outros programas. Para baixar,
você ainda precisa ter **Python 3.10+ e Git** instalados no computador.
Para apenas visualizar um Parquet, o programa instala os pacotes R
`arrow` e `dplyr` na primeira utilização, caso estejam ausentes.

**Prefere digitar comandos?** Também funciona sem menu:

```r
library(sisabextrator)
sisab_baixar(
  inicio = "202401", fim = "202401",
  relatorio = "municipal", linhas = "Municipio", colunas = "CIAP/CID",
  tipo_producao = "Atendimento Individual",
  idades = "none", sexos = "none"
)
```

O filtro `tipo_producao` acima é **somente um exemplo** e deve ser
compatível com o recorte da pesquisa; no menu, você escolhe uma das opções
realmente oferecidas pelo portal. A disponibilidade do CSV depende do SISAB,
e o download ainda precisa ser validado na página real para cada combinação.

Para abrir um arquivo sem o menu:

```r
sisab_visualizar() # abre o seletor de arquivos .parquet
```

Os exemplos avançados e o diagnóstico de erros continuam nas seções abaixo.

## O que ele faz?

| | Recurso | Para que serve |
|:--:|---|---|
| 🔎 | **Explorar filtros** | Descobrir competências, linhas e colunas disponíveis nos relatórios públicos. |
| 📥 | **Baixar dados** | Consultar períodos selecionados e guardar os arquivos CSV originais. |
| 🗓️ | **Organizar o histórico** | Salvar resultados mensais, consolidar cada ano e depois a série completa. |
| 💾 | **Trabalhar com Parquet** | Usar um formato adequado para consultar bases grandes sem abrir tudo na memória. |
| 🔁 | **Retomar o trabalho** | Reaproveitar downloads anteriores e identificar consultas com erro. |
| 📊 | **Analisar no RStudio** | Ler os Parquets com `arrow` e selecionar apenas os dados de interesse. |

**Exemplos de informações:** município, mês de referência, sexo, idade e CIAP/CID, **quando o relatório permitir essas opções e combinações**.

## 🔄 Como os dados são organizados?

<p align="center">
  <img src="assets/fluxo-dados.svg" width="100%" alt="Fluxo dos dados: relatórios públicos do SISAB, downloads mensais com CSV e Parquet, consolidação anual e série histórica consultada no RStudio." />
</p>

O programa preserva o arquivo recebido do SISAB, gera Parquets por consulta e reúne os resultados **primeiro por ano, depois por período completo**. A consolidação **não soma automaticamente** consultas diferentes, porque elas podem representar contagens sobrepostas.

---

## Pré-requisitos para usar o SISAB Extrator

Antes de instalar, confira se seu computador tem os programas abaixo. O **R é
a interface de trabalho**, e o **Python faz a coleta e a geração dos Parquets**.

| Requisito | Necessário para | Observações |
|---|---|---|
| **R 4.0.0 ou superior** | Instalar e usar o pacote R | [Baixar R](https://cran.r-project.org/) |
| **Python 3.10 ou superior** | Inspecionar o portal, planejar, baixar e converter os dados | Precisa estar acessível pelo comando `python`; deve incluir `pip` e o módulo `venv`. [Baixar Python](https://www.python.org/downloads/) |
| **Git** | Instalar ou atualizar o motor Python direto do GitHub | Precisa estar acessível pelo comando `git`. [Baixar Git](https://git-scm.com/downloads) |
| **Internet e acesso HTTPS** | Instalação e extração | A rede deve permitir acesso ao GitHub, ao PyPI (dependências Python) e a `sisab.saude.gov.br`. Para instalar pacotes R, também é preciso acessar o repositório R escolhido |
| **Espaço em disco e permissão de escrita** | Guardar o ambiente Python isolado, CSV ZIP, Parquets e catálogo SQLite | O espaço necessário varia com os períodos e filtros selecionados; reserve espaço para downloads e consolidações |

**Opcionais:** o [RStudio](https://posit.co/download/rstudio-desktop/) facilita o
uso do R, mas não é obrigatório; o pacote R `remotes` é necessário **somente**
para a alternativa de instalação pelo GitHub indicada abaixo. Para **analisar
Parquets no R**, instale `arrow`; `dplyr` facilita filtros e tabelas.
Para ler os JSON de inspeção no R, você pode usar `jsonlite`.

### Verificar os pré-requisitos no RStudio

Cole o código abaixo no **Console** do RStudio. Ele apenas verifica as
instalações — não altera pacotes, não instala programas e não baixa dados:

```r
cat("Versão do R:", as.character(getRversion()), "\n")
if (getRversion() < "4.0.0") {
  stop("É necessário R 4.0.0 ou superior.")
}

programas <- Sys.which(c("python", "git"))
print(programas)

if (!nzchar(programas[["python"]])) {
  stop("Python não encontrado. Instale Python 3.10+ e confira o PATH.")
}
if (!nzchar(programas[["git"]])) {
  stop("Git não encontrado. Instale o Git e confira o PATH.")
}

system2(programas[["python"]], "--version")
system2(programas[["python"]], c("-m", "pip", "--version"))
system2(programas[["git"]], "--version")

cat("Confira acima se o Python é 3.10 ou superior.\n")
```

No **Windows**, durante a instalação do Python, habilite a opção de
adicioná-lo ao `PATH`, quando disponível. Se você acabou de instalar Python
ou Git e `Sys.which()` ainda estiver vazio, **feche e reabra o RStudio**.
Se `pip` ou `venv` não estiverem disponíveis, corrija a instalação do
Python antes de executar `sisab_instalar_motor()`.

**Não é necessário instalar manualmente** `requests`, `beautifulsoup4`,
`pyarrow` ou alterar o `chardet` do PySUS: `sisab_instalar_motor()` cria
um **ambiente Python separado** e instala as bibliotecas necessárias nele.
Para apenas **ler Parquets já existentes pelo R**, Python, Git e acesso ao
SISAB não são necessários; basta R e `arrow`.

> **Acesso aos dados:** o projeto usa relatórios **públicos e agregados**.
> A disponibilidade de competências e combinações de filtros depende do
> portal SISAB. A instalação correta não garante que qualquer combinação
> gere um CSV; valide uma consulta pequena antes de baixar uma série histórica.

## Instalação no RStudio

### 1. Instale o pacote R

**Pelo R-universe**, quando o pacote estiver listado na [página de publicação](https://maiconcarlospng.r-universe.dev/):

```r
install.packages(
  "sisabextrator",
  repos = c(
    "https://maiconcarlospng.r-universe.dev",
    "https://cloud.r-project.org"
  )
)

library(sisabextrator)
```

> **Ainda não encontrou o pacote?** A primeira compilação do R-universe pode levar cerca de uma hora. Uma compilação aprovada no GitHub não significa que ele já esteja disponível no R-universe. Veja a [orientação oficial](https://docs.r-universe.dev/publish/set-up.html#wait-first-build).

**Alternativa pelo GitHub:**

```r
install.packages("remotes")
remotes::install_github("maiconcarlospng/sisab-extrator")
library(sisabextrator)
```

Caso o RStudio não consiga acessar a API do GitHub, uma alternativa é `remotes::install_git("https://github.com/maiconcarlospng/sisab-extrator.git")`, desde que o programa Git esteja instalado.

### 2. Prepare o motor de downloads

O R é a interface para usar o projeto. **A coleta dos dados é feita em Python**, portanto você precisará de **Python 3.10+ e Git** no computador.

Para quem utiliza **`sisab()`**, **`sisab_baixar()`**, `sisab_inspecionar()` ou
`sisab_planejar()`, a instalação do motor Python é **automática no primeiro uso**.
O SISAB Extrator cria um ambiente Python exclusivo, instala as bibliotecas
necessárias e o atualiza quando está abaixo da versão mínima exigida.
Isso evita conflitos com PySUS e outras ferramentas do computador.

A instalação manual continua disponível como opção avançada:

```r
sisab_instalar_motor()
```

Para inspecionar, planejar e baixar dados, você não precisa configurar caminhos
nem indicar `python = ...`: as funções R usam esse ambiente automaticamente.

Para atualizar o motor depois:

```r
sisab_instalar_motor(atualizar = TRUE)
```

> **Para quem já usava uma versão anterior:** atualize primeiro o pacote R para
> a versão **0.2.1 ou superior** (pelo R-universe, quando disponível, ou pelo
> GitHub). As versões anteriores instalavam o motor no Python compartilhado.
> A partir da versão 0.2.1, o ambiente próprio é o padrão.

### 3. Confira se o pacote R e o motor Python estão atualizados

**Não é preciso preencher nada:** copie e execute este código no Console do RStudio
depois da instalação. Ele mostra a versão do pacote R e a versão do motor Python
isolado, sem instalar ou modificar nenhum programa.

```r
library(sisabextrator)

# 1. Verificar a versão instalada do pacote R
packageVersion("sisabextrator")

# 2. Localizar automaticamente o Python exclusivo do SISAB Extrator
python_sisab <- get(
  ".sisab_venv_python",
  envir = asNamespace("sisabextrator")
)()

# 3. Mostrar a versão do motor Python instalado
system2(
  python_sisab,
  c("-m", "pip", "show", "sisab-extrator")
)
```

**Versões esperadas nesta atualização:**

| Componente | Versão |
|---|---|
| Pacote R `sisabextrator` | **0.3.0** |
| Motor Python `sisab-extrator` | **0.1.6** |

No resultado do Python, procure a linha `Version: 0.1.6`. Não é necessário
digitar o caminho do Python: o próprio código o descobre.

Se o pacote **R** estiver antigo, atualize pelo procedimento do passo 1,
reinicie a sessão do R e carregue `library(sisabextrator)` novamente.
Se apenas o motor **Python** estiver antigo ou ainda não instalado,
basta executar `sisab()` ou `sisab_baixar()`: o programa fará a preparação
automática antes de acessar o portal. Também é possível executar manualmente
`sisab_instalar_motor(atualizar = TRUE)` se preferir.

**O que você precisa preencher de fato:** ao baixar dados, escolha o período,
o relatório e os filtros adequados à pesquisa, especialmente
`tipo_producao` quando exigido pelo SISAB. Já os comandos de verificação
acima são automáticos.

**Sobre os campos de `pip show`:** `Name`, `Version`, `Summary`,
`Author`, `Author-email`, `License` e links do projeto vêm dos
metadados do pacote, definidos pelos desenvolvedores no `pyproject.toml`.
Desde o motor **0.1.6**, o projeto informa a autoria, o contato do GitHub
e os endereços de repositório, documentação e problemas. Em metadados
Python modernos, esses endereços aparecem como `Project-URL`;
o campo legado `Home-page` pode continuar vazio sem indicar erro.
`Location` é escolhido automaticamente pelo Python, `Requires`
é preenchido pelas dependências e `Required-by` fica vazio quando
nenhum outro pacote Python instalado depende diretamente do extrator.
**Não digite valores para esses campos no RStudio.**

Para **abrir Parquets já existentes**, o motor Python não é necessário.

## Primeiro download

**Filtro obrigatório (R 0.3.0 / motor Python 0.1.6):** o SISAB exige
que a variável **Tipo de Produção** esteja na linha/coluna ou que pelo
menos uma opção seja escolhida nesse filtro. A opção `CIAP/CID`
não substitui esse filtro. Por isso, nas consultas abaixo usamos
`tipo_producao = "Atendimento Individual"` **somente como exemplo**:
primeiro confirme que esse rótulo existe na inspeção e escolha o recorte
correto para o seu estudo.

Recomendamos começar com **apenas uma competência**, para conferir como o SISAB responde.

**Passo 1 — descubra os filtros disponíveis:**

```r
sisab_inspecionar(relatorio = "federal")
sisab_inspecionar(relatorio = "municipal")
```

As informações ficam em `data/inspecao/`. Use `getwd()` para descobrir onde essa pasta foi criada no seu computador.
Na versão atual, o console também mostra os **tipos de produção
disponíveis**, com seus rótulos e valores. Se preferir ver isso no JSON:

```r
# Se necessário, execute install.packages("jsonlite") uma única vez.
arquivo <- file.path("data", "inspecao", "municipal.json")
opcoes <- jsonlite::fromJSON(arquivo, simplifyVector = FALSE)
opcoes$tipo_producao$options
```

Escolha uma opção realmente listada pelo portal. Se o objetivo for consultar
todos os tipos, `tipo_producao = "all"` cria consultas **separadas por tipo**
e pode incluir combinações não aceitas com a coluna escolhida.

**Passo 2 — prepare uma consulta de teste (sem baixar ainda):**

```r
sisab_planejar(
  inicio = "202401",
  fim = "202401",
  relatorio = "municipal",
  linhas = "Municipio",
  colunas = "CIAP/CID",
  tipo_producao = "Atendimento Individual", # confirme na inspeção
  idades = "none",
  sexos = "none"
)
```

**Passo 3 — baixe a mesma consulta:**

```r
sisab_baixar(
  inicio = "202401",
  fim = "202401",
  relatorio = "municipal",
  linhas = "Municipio",
  colunas = "CIAP/CID",
  tipo_producao = "Atendimento Individual", # confirme na inspeção
  idades = "none",
  sexos = "none"
)

sisab_status()
```

> **Antes dos passos 2 e 3:** confirme na inspeção se as opções **Município**, **CIAP/CID** e **Atendimento Individual** realmente existem no relatório escolhido. Se os nomes ou cruzamentos forem diferentes, adapte o exemplo. O portal pode mudar e algumas consultas podem não ser aceitas. Nenhum tipo de produção é escolhido silenciosamente.

### Se o download demorar muito

Com o **pacote R 0.2.2 / motor Python 0.1.4**, o console informa
quando o programa consulta o site, recebe o CSV, converte para Parquet e
inicia a consolidação. Para identificar rapidamente um problema de rede,
você pode limitar a espera por **inatividade de uma requisição**, sem desligar
a pausa entre consultas nem sobrecarregar o portal:

```r
sisab_baixar(
  inicio = "202401", fim = "202401",
  relatorio = "municipal",
  linhas = "Municipio", colunas = "CIAP/CID",
  tipo_producao = "Atendimento Individual", # confira o rótulo no portal
  idades = "none", sexos = "none",
  tempo_limite = 120, # segundos de inatividade tolerados pelo HTTP
  tentativas = 1,     # uma nova tentativa após falha
  consolidar = FALSE  # diagnosticar apenas download e conversão
)
```

Isso **não acelera o processamento do SISAB**: pode encerrar uma resposta
legitimamente lenta. Para coletas completas, mantenha os padrões conservadores
(`tempo_limite = 900`, `tentativas = 6`, `pausa = 2`).

O projeto [`rfsaldanha/sisab_scrapper`](https://github.com/rfsaldanha/sisab_scrapper)
também usa formulários JSF, pausas e novas tentativas. Entretanto, ele
separa os relatórios por **18 faixas etárias e 2 sexos (36 downloads por mês)**,
enquanto uma consulta com `idades = "none"` e `sexos = "none"` no
SISAB Extrator tenta um resultado mais amplo, que pode ser mais pesado.

Para receber o progresso detalhado e o filtro Tipo de Produção, use
o pacote R **0.3.0** (o motor Python 0.1.6 será instalado ou atualizado
automaticamente no primeiro uso):

```r
library(sisabextrator)
sisab() # ou sisab_baixar(...) para usar os argumentos diretamente
```

O console agora mostra **FASE 1/4** (identificar filtros),
**FASE 2/4** (validar e registrar consultas), **FASE 3/4** (baixar e converter)
e **FASE 4/4** (consolidar ou explicar por que não foi possível).
Cada consulta também percorre até **5 etapas**: mostrar os filtros, solicitar
CSV, salvar ZIP, converter Parquet e concluir. Na conversão, o programa
informa quantas linhas já foram gravadas.

Exemplo ilustrativo de mensagens (não é uma execução real do portal):

```text
FASE 1/4 | Abrindo relatório do SISAB e identificando filtros...
FASE 2/4 | Plano validado: 1 consulta(s)
FASE 3/4 | Iniciando download e conversão em Parquet...
Consulta 1/1 | ETAPA 1/5 | municipal | mês 202401 | ...
Consulta 1/1 | ETAPA 2/5 | Solicitando CSV ao SISAB...
SISAB POST ... | tentativa 1/2 | limite 120s
Consulta 1/1 | ETAPA 3/5 | CSV recebido; salvando ZIP...
Consulta 1/1 | ETAPA 4/5 | Lendo CSV e convertendo para Parquet...
Consulta 1/1 | ETAPA 4/5 | 25000 linhas convertidas até agora
Consulta 1/1 | ETAPA 5/5 | Concluído ...
PROGRESSO: 1/1 consultas finalizadas (100.0%)
FASE 4/4 | Consolidando arquivos anuais e série histórica...
```

**Importante:** a porcentagem representa as **consultas concluídas**, não
a quantidade de bytes recebidos. Enquanto o SISAB ainda processa a resposta
HTTP, o programa informa a espera, mas não consegue saber o percentual
real da resposta antes de recebê-la.

O comando `sisab_status()` executado **após** `sisab_baixar()` só começa
quando o download terminar (ou retornar erro). Para mostrar o status mesmo
que o download falhe, use:

```r
try(sisab_baixar(
  inicio = "202401", fim = "202401",
  relatorio = "municipal", linhas = "Municipio",
  colunas = "CIAP/CID", tipo_producao = "Atendimento Individual",
  idades = "none", sexos = "none",
  tempo_limite = 120, tentativas = 0, consolidar = FALSE
))

sisab_status()
```



### 📂 Abrir um arquivo escolhido por você

Se você já baixou os dados e quer abrir **um arquivo Parquet específico**, não
precisa descobrir a pasta manualmente. No RStudio, execute:

```r
install.packages("arrow") # apenas na primeira vez
arquivo <- file.choose()  # abre a janela para escolher o arquivo
dados <- arrow::read_parquet(arquivo)

View(dados)             # abre a tabela no RStudio
```

Escolha um arquivo com extensão **`.parquet`** na pasta
`data/mensal/`, `data/consolidado/anual/` ou `data/consolidado/serie/`.
O exemplo lê o arquivo selecionado para a memória: para bases muito grandes,
prefira `arrow::open_dataset(arquivo)` e aplique filtros antes de
`dplyr::collect()`. A janela `file.choose()` funciona em sessões
interativas do RStudio; se cancelar, o R pode mostrar um erro de seleção.

## 📈 Analisando os dados no R

Quando os Parquets já estiverem disponíveis:

```r
install.packages(c("arrow", "dplyr"))

library(sisabextrator)
library(dplyr)

# Abrir todos os arquivos anuais como um conjunto de dados
dados <- sisab_abrir_anuais(dados = "data")

# Trazer somente um recorte para a memória
resultado <- dados |>
  filter(competencia == "202401", relatorio == "municipal") |>
  select(competencia, municipio, categoria, valor) |>
  collect()
```

Isso evita tentar carregar todos os anos de uma vez. Em bases muito grandes, **filtre antes de usar `collect()`**.

**Atenção:** antes de somar `valor`, selecione o relatório e as mesmas dimensões de análise para não contar atendimentos em duplicidade.

## Onde ficam os dados?

Ao baixar, o projeto cria a pasta `data/` no diretório de trabalho:

```text
data/
├── inspecao/             Informações sobre as opções do portal
├── brutos/               Arquivos CSV originais (guardados em ZIP)
├── mensal/               Parquets das consultas de cada mês
└── consolidado/
    ├── anual/            Um Parquet por ano
    └── serie/            Série histórica do período baixado
```

**O que é Parquet?** É um formato de arquivo para guardar tabelas de forma eficiente, especialmente útil em bases grandes. No R, você pode lê-lo com `arrow`.

## 🌎 Quero baixar toda a série disponível

Primeiro, gere um **plano** com todos os períodos e as opções identificadas:

```r
sisab_planejar(
  inicio = "auto",
  fim = "auto",
  relatorio = "all",
  linhas = "all",
  colunas = "all",
  tipo_producao = "all", # uma consulta por tipo listado pelo portal
  idades = "all",
  sexos = "both",
  aceitar_plano_grande = TRUE
)
```

O modo `auto` consulta o intervalo de competências oferecido pelo portal. **Revise o plano e valide uma competência antes de tentar todas as combinações:** algumas podem não ser suportadas, e a coleta completa pode exigir milhares de requisições.

Depois de confirmar o plano, use `sisab_baixar()` com os mesmos parâmetros. Ao concluir os downloads, a ferramenta tenta consolidar os arquivos por ano e, por fim, pelo período completo. Se houver consultas pendentes ou com erro, a consolidação completa é bloqueada para evitar uma série incompleta apresentada como definitiva.

## 🛠️ Se aparecer “Campos não encontrados”

Esse erro significa que a página recebida do SISAB não tinha o formulário
esperado. **Não é causado pelo aviso de `chardet`**.

Atualize o pacote R e o motor isolado e tente uma inspeção:

```r
sisab_instalar_motor(atualizar = TRUE)
sisab_inspecionar(relatorio = "federal")
```

Se o erro continuar, verifique
`data/inspecao/diagnostico_federal.json` ou
`data/inspecao/diagnostico_municipal.json`. O arquivo reúne informações
limitadas sobre a página recebida, sem salvar cookies ou valores de formulários,
para ajudar a corrigir diferenças do portal.

**Aviso `RequestsDependencyWarning`:** em versões antigas, o extrator
compartilhava o Python do PySUS, que usa uma versão diferente de `chardet`.
A versão **0.2.1** do pacote R cria e usa um Python isolado por padrão.
Não é necessário alterar nem desinstalar bibliotecas do PySUS para usar
o SISAB Extrator.

## Perguntas frequentes

<details>
<summary><strong>O pacote já vem com todos os dados do Brasil?</strong></summary>

Não. O pacote é uma ferramenta para consultar e baixar os dados públicos. Os arquivos serão criados no seu computador.
</details>

<details>
<summary><strong>Posso baixar uma linha por atendimento ou por paciente?</strong></summary>

Não por meio desses relatórios. Eles fornecem <strong>contagens agregadas</strong>, e não registros individuais.
</details>

<details>
<summary><strong>Consigo obter todos os códigos CIAP/CID?</strong></summary>

Somente os códigos, agrupamentos e combinações que o SISAB disponibilizar. A integração com a coluna CIAP/CID ainda precisa de validação prática.
</details>

<details>
<summary><strong>Preciso saber programar em Python?</strong></summary>

Não. Você usa funções no RStudio; apenas precisa instalar Python e Git para executar os downloads. Para analisar arquivos Parquet já existentes, basta R com `arrow`.
</details>

<details>
<summary><strong>O que acontece se um download falhar?</strong></summary>

O programa registra o andamento e permite reaproveitar consultas já concluídas. Use `sisab_status()` para encontrar falhas.
</details>

### Se o portal solicitar "Tipo de Produção"

Em novembro de 2026, uma tentativa de baixar `Município × CIAP/CID`
retornou a seguinte mensagem do próprio SISAB:

> Por favor, selecione a variável "Tipo de Produção" como opção na Linha/Coluna ou selecione uma das opções no filtro Tipo de Produção*.

A versão **R 0.2.3 + Python 0.1.6** permite escolher esse campo com
`tipo_producao`, registra o filtro no plano e o preserva nos arquivos
Parquet. Exemplo (após conferir as opções com `sisab_inspecionar()`):

```r
sisab_planejar(
  inicio = "202401", fim = "202401", relatorio = "municipal",
  linhas = "Municipio", colunas = "CIAP/CID",
  tipo_producao = "Atendimento Individual",
  idades = "none", sexos = "none"
)

try(sisab_baixar(
  inicio = "202401", fim = "202401", relatorio = "municipal",
  linhas = "Municipio", colunas = "CIAP/CID",
  tipo_producao = "Atendimento Individual",
  idades = "none", sexos = "none",
  tentativas = 0, tempo_limite = 120, consolidar = FALSE
))
sisab_status()
```

Isso corrige o **envio de um filtro obrigatório conhecido**. Ainda não prova
que a combinação completa de filtros seja aceita pelo SISAB ou que o
CSV esteja disponível, pois a extração real requer validação após a atualização.

### Quando o SISAB responde com HTML, mas não entrega CSV

Um `HTTP 200` significa que o servidor respondeu, **não que o CSV tenha sido
gerado**. Para evitar tentativas desnecessárias, faça apenas uma exportação de
diagnóstico após atualizar o motor Python para **0.1.3**:

```r
sisab_instalar_motor(atualizar = TRUE)

try(sisab_baixar(
  inicio = "202401", fim = "202401",
  relatorio = "municipal",
  linhas = "Municipio", colunas = "CIAP/CID",
  tipo_producao = "Atendimento Individual", # confira o rótulo no portal
  idades = "none", sexos = "none",
  tentativas = 0, tempo_limite = 120,
  consolidar = FALSE
))

arquivo <- file.path("data", "inspecao", "diagnostico_exportacao_municipal.json")
if (file.exists(arquivo)) cat(readLines(arquivo, warn = FALSE), sep = "\n")
```

Se o SISAB devolver outra página HTML, o extrator salva
`data/inspecao/diagnostico_exportacao_municipal.json` com o tipo de resposta,
os nomes de campos enviados e eventuais mensagens de validação do site.
**O arquivo não contém cookies, ViewState nem o HTML completo.**

**Prefere escolher o arquivo com o mouse?** No RStudio, execute:

```r
arquivo <- file.choose()  # escolha o diagnóstico .json no Explorador
cat(readLines(arquivo, warn = FALSE, encoding = "UTF-8"), sep = "\n")
```

Você também pode abrir o arquivo na aba **Files** do RStudio.
Para localizar a pasta criada pelo download, use `getwd()`.
O seletor não faz o download: ele abre um arquivo **já existente** no computador.

A opção `CIAP/CID` pode depender de filtros adicionais. O fato de ela aparecer
na lista de colunas não garante que o servidor aceite a exportação. Antes de
alterar o envio de dados, é preciso verificar esse diagnóstico.

## 📚 Documentação e contribuições

- 📘 [Guia técnico: comandos Python, formatos e limitações](docs/guia-tecnico.md)
- 📦 [Publicação e instalação pelo R-universe](r-universe/README.md)
- 🐛 [Relatar problema ou sugerir melhoria](https://github.com/maiconcarlospng/sisab-extrator/issues)
- 🌐 [Portal oficial do SISAB](https://sisab.saude.gov.br/)

---

<p align="center">
  <strong>Feito para facilitar pesquisas com dados públicos da Atenção Primária à Saúde.</strong><br/>
  Desenvolvido por <a href="https://github.com/maiconcarlospng">Maicon Carlos</a>, inspirado no projeto
  <a href="https://github.com/rfsaldanha/sisab_scrapper">sisab_scrapper</a> de Rafael Saldanha.<br/>
  Licença <a href="LICENSE">MIT</a> · Projeto independente, sem vínculo oficial com o Ministério da Saúde.
</p>
