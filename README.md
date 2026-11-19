# SISAB Extrator 📊

**Baixe e organize dados públicos do SISAB para usar no R e em pesquisas em saúde.**

O **SISAB Extrator** é um projeto gratuito e de código aberto que ajuda a consultar os relatórios públicos do [SISAB](https://sisab.saude.gov.br/) (Sistema de Informação em Saúde para a Atenção Básica), guardar os resultados e organizá-los por mês, ano e período completo.

Ele foi pensado para estudantes, pesquisadores e profissionais de saúde que precisam trabalhar com muitos dados sem baixar e juntar manualmente dezenas de arquivos.

> **Importante:** o projeto ainda está em desenvolvimento. Os testes do código foram feitos, mas a extração completa dos relatórios reais do SISAB **ainda precisa ser validada**. Algumas combinações de filtros podem não funcionar no site.

## O que é possível fazer?

- **Descobrir os filtros disponíveis** no relatório do SISAB.
- **Escolher o período**, os tipos de relatório e as opções de organização dos dados.
- **Baixar os arquivos** e retomar o trabalho caso uma consulta falhe.
- **Guardar em Parquet**, um formato adequado para bases de dados grandes.
- **Organizar automaticamente os resultados:** primeiro por mês, depois por ano e, por último, em uma série histórica.
- **Abrir os dados pelo RStudio** sem carregar todos os anos na memória de uma vez.

### Que dados podem aparecer?

Dependendo do relatório e dos filtros disponíveis no SISAB, é possível trabalhar com informações por **município, competência (mês), sexo, faixa etária, CIAP/CID e tipo de produção**.

**Não são microdados de pacientes:** cada linha do resultado representa uma contagem ou categoria da tabela pública, não um atendimento individual identificado.

---

## Comece pelo RStudio

### 1. Instale o pacote R

A forma mais simples será pelo **R-universe**, assim que a primeira publicação estiver concluída:

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

**O pacote ainda pode não aparecer no R-universe:** a primeira compilação pode levar **cerca de uma hora**, conforme a [documentação oficial](https://docs.r-universe.dev/publish/set-up.html#wait-first-build). Consulte [a página do pacote](https://maiconcarlospng.r-universe.dev/sisabextrator) antes de instalar. Se continuar ausente depois desse período, será necessário verificar a publicação.

**Alternativa pelo GitHub**, sem esperar o R-universe:

```r
install.packages("remotes")
remotes::install_github("maiconcarlospng/sisab-extrator")
library(sisabextrator)
```

Se o RStudio não conseguir acessar a API do GitHub, o problema pode ser de conexão. Uma opção que usa o programa Git instalado no computador é `remotes::install_git("https://github.com/maiconcarlospng/sisab-extrator.git")`.

### 2. Prepare o programa que faz os downloads

O pacote R é a interface. Para **baixar do SISAB**, ele utiliza um programa escrito em **Python**.

Você precisará ter **Python 3.10 ou mais recente** e **Git** instalados no computador. Depois de instalar o pacote R, execute **uma vez**:

```r
sisab_instalar_motor()
```

Se o Windows informar que não encontrou `python`, confira a instalação do Python e se ele está disponível no terminal.

> Para **abrir arquivos Parquet que já foram baixados**, não é necessário executar o motor Python.

### 3. Veja quais opções estão disponíveis

Antes de começar os downloads, descubra quais filtros o próprio SISAB está oferecendo:

```r
sisab_inspecionar(relatorio = "federal")
sisab_inspecionar(relatorio = "municipal")
```

As informações encontradas serão salvas na pasta `data/inspecao/`, no diretório de trabalho do R. Para descobrir qual é essa pasta, execute `getwd()`.

### 4. Faça primeiro um teste pequeno

Comece com **um mês**, em vez de tentar baixar todos os anos de uma vez.

O exemplo abaixo usa município e CIAP/CID. **Confirme na inspeção anterior se essas opções existem e quais são seus nomes no relatório escolhido.** Caso contrário, troque pelos nomes encontrados.

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

Esse comando **só prepara o plano**. Ele não baixa dados.

Para fazer o download da mesma consulta:

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
```

Depois, confira o andamento:

```r
sisab_status()
```

Se houver erro de formulário ou de exportação, a estrutura do site pode ter mudado. Nesse caso, o projeto precisará de ajustes: **os exemplos acima não são garantia de que o SISAB aceite essa combinação**.

### 5. Trabalhe com os resultados no R

Instale os pacotes de leitura e análise:

```r
install.packages(c("arrow", "dplyr"))
library(dplyr)
```

Quando já existirem arquivos anuais, abra-os sem carregar tudo na memória:

```r
dados <- sisab_abrir_anuais(dados = "data")

# Exemplo: selecionar informações de uma competência
recorte <- dados |>
  filter(competencia == "202401", relatorio == "municipal") |>
  select(competencia, municipio, categoria, valor) |>
  collect()
```

O `collect()` carrega **apenas o resultado filtrado** no R. Em bases muito grandes, acrescente outros filtros antes de usá-lo.

**Cuidado ao somar valores:** relatórios e consultas diferentes podem contabilizar os mesmos atendimentos. Escolha uma mesma visão de dados antes de calcular totais.

---

## Onde ficam os arquivos?

O programa cria uma pasta chamada `data` no local em que você estiver trabalhando:

| Pasta | O que você encontra |
|---|---|
| `data/brutos/` | Arquivos originais recebidos do SISAB |
| `data/mensal/` | Resultados organizados por mês, em Parquet |
| `data/consolidado/anual/` | Arquivos que reúnem os resultados de cada ano |
| `data/consolidado/serie/` | Arquivo final com o período completo |
| `data/inspecao/` | Informações sobre as opções oferecidas pelo site |

**Parquet** é um formato de arquivo eficiente para armazenar e consultar tabelas grandes. Você pode abri-lo com o pacote `arrow` no R.

O consolidado **reúne** as consultas realizadas, mas não soma automaticamente indicadores, porque algumas consultas podem se sobrepor.

## Quero baixar todos os anos disponíveis

É possível pedir ao programa que examine todos os períodos oferecidos pelo relatório e gere um plano maior. **Antes de executar milhares de consultas, valide um mês e confira os filtros disponíveis.**

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

A palavra `auto` significa: **usar o primeiro e o último mês que o site informar como disponíveis**. O programa não deve presumir que meses ausentes no início de 2013 estejam disponíveis.

O plano pode gerar um número muito grande de consultas e incluir combinações que o portal não permita. Para executar o plano depois de verificá-lo, use `sisab_baixar()` com as mesmas opções.

A consolidação acontece após os downloads concluídos: **mensal → anual → série histórica**. Se alguma consulta prevista falhar, a consolidação completa é bloqueada até que seja corrigida; assim você não recebe uma base incompleta como se estivesse pronta.

## Dúvidas frequentes

**O pacote já vem com todos os dados do Brasil?**  
Não. Ele é uma ferramenta para consultar e baixar os dados públicos. Os arquivos serão criados no seu computador.

**Consigo baixar uma linha por atendimento realizado?**  
Não pelos relatórios públicos utilizados aqui. Eles mostram **quantidades agregadas**, e não registros individuais de pacientes.

**Posso selecionar qualquer CID?**  
Somente as opções e combinações que o relatório público do SISAB realmente oferecer. A coluna CIAP/CID ainda precisa de validação prática.

**Preciso saber Python para usar no RStudio?**  
Não é necessário programar em Python. Mas você precisa instalá-lo para executar os downloads. Para analisar Parquets já existentes, basta o R com `arrow`.

**E se a internet cair?**  
O programa registra as consultas realizadas e tenta reaproveitar os arquivos já baixados. Falhas devem ser conferidas com `sisab_status()`.

**Por que o pacote ainda não aparece no R-universe?**  
A primeira publicação depende de uma compilação feita pelo serviço e pode levar aproximadamente uma hora. O código passar nos testes do GitHub não significa que já foi publicado no R-universe.

## Para quem prefere Python ou quer entender o funcionamento

Há uma versão de linha de comando em Python e uma explicação mais detalhada dos arquivos, parâmetros e limitações no **[guia técnico](docs/guia-tecnico.md)**.

## Autoria e créditos

Projeto mantido por [Maicon Carlos](https://github.com/maiconcarlospng), inspirado no trabalho de [Rafael Saldanha — `sisab_scrapper`](https://github.com/rfsaldanha/sisab_scrapper).

Código aberto sob a licença MIT. Este projeto é independente e **não é uma ferramenta oficial do Ministério da Saúde**.

Sugestões, dúvidas e problemas podem ser registrados em [Issues](https://github.com/maiconcarlospng/sisab-extrator/issues).
