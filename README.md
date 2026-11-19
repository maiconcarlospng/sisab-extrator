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
  <a href="https://github.com/maiconcarlospng/sisab-extrator#o-que-ele-faz">Conheça o projeto</a> ·
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

Depois de instalar o pacote R, execute uma vez:

```r
sisab_instalar_motor()
```

**Pronto!** O SISAB Extrator cria automaticamente um **ambiente Python exclusivo**
e instala nele suas próprias bibliotecas. Isso evita conflitos com o **PySUS**
e com outras ferramentas instaladas no seu computador.

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

Para **abrir Parquets já existentes**, o motor Python não é necessário.

## Primeiro download

Recomendamos começar com **apenas uma competência**, para conferir como o SISAB responde.

**Passo 1 — descubra os filtros disponíveis:**

```r
sisab_inspecionar(relatorio = "federal")
sisab_inspecionar(relatorio = "municipal")
```

As informações ficam em `data/inspecao/`. Use `getwd()` para descobrir onde essa pasta foi criada no seu computador.

**Passo 2 — prepare uma consulta de teste (sem baixar ainda):**

```r
sisab_planejar(
  inicio = "202401",
  fim = "202401",
  relatorio = "municipal",
  linhas = "Municipio",
  colunas = "CIAP/CID",
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
  idades = "none",
  sexos = "none"
)

sisab_status()
```

> **Antes dos passos 2 e 3:** confirme na inspeção se as opções **Município** e **CIAP/CID** realmente existem no relatório escolhido. Se os nomes ou cruzamentos forem diferentes, adapte o exemplo. O portal pode mudar e algumas consultas podem não ser aceitas.

### Se o download demorar muito

Desde o **pacote R 0.2.2 / motor Python 0.1.2**, o console informa
quando o programa consulta o site, recebe o CSV, converte para Parquet e
inicia a consolidação. Para identificar rapidamente um problema de rede,
você pode limitar a espera por **inatividade de uma requisição**, sem desligar
a pausa entre consultas nem sobrecarregar o portal:

```r
sisab_baixar(
  inicio = "202401", fim = "202401",
  relatorio = "municipal",
  linhas = "Municipio", colunas = "CIAP/CID",
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

O comando `sisab_status()` executado **após** `sisab_baixar()` só começa
quando o download terminar (ou retornar erro).

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
