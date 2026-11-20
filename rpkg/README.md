# Pacote R legado

A interface R oficial do SISAB Extrator agora está na **raiz do repositório** para permitir a publicação no R-universe. Prefira:

```r
remotes::install_github("maiconcarlospng/sisab-extrator")
```

Esta pasta `rpkg/` foi mantida temporariamente para compatibilidade e não é a origem das compilações do R-universe.

---

# sisabextrator — interface para R

Permite executar o pacote Python **sisab-extrator** e ler os Parquets gerados pelo R sem importar arquivos grandes inteiros para a RAM.

## Instalação no R

```r
install.packages(c("remotes", "arrow", "dplyr"))
remotes::install_github("maiconcarlospng/sisab-extrator", subdir = "rpkg")
library(sisabextrator)

# Instala o motor num ambiente Python isolado (Git opcional; winget/ZIP como fallback).
sisab_instalar_motor(python = "python")
```

Se o executável Python se chamar `python3`, informe `python = "python3"` nas funções. É possível também instalar o motor fora do R com `python -m pip install https://github.com/maiconcarlospng/sisab-extrator/archive/refs/heads/main.zip` (não exige Git).

## Descobrir opções antes de baixar

```r
sisab_inspecionar(relatorio = "federal")
sisab_inspecionar(relatorio = "municipal")

# Primeiro verifica o plano (não baixa)
sisab_planejar(inicio = "201304", fim = "202512",
              relatorio = "all", linhas = "all", colunas = "all",
              idades = "all", sexos = "both", aceitar_plano_grande = TRUE)
```

**Não comece com o download de todas as combinações antes de conferir se o plano faz sentido**. O site pode oferecer combinações sem resultado ou não suportadas. `auto` respeita competências devolvidas pela página, evitando requisitar meses que não constam do formulário.

## Download e consolidação

```r
# Exemplo pequeno a validar no SISAB (substitua CIAP/CID caso o probe mostre outro nome).
sisab_baixar(inicio = "202401", fim = "202401", relatorio = "municipal",
             linhas = "Municipio", colunas = "CIAP/CID", idades = "none", sexos = "none")

sisab_status()
sisab_consolidar("201304", "202512") # apenas se estes meses já tiverem sido baixados
```

## Consultar sem estouro de memória

```r
library(sisabextrator)
library(dplyr)

# Abre os consolidados anuais como um dataset Arrow (lazy).
ds <- sisab_abrir_anuais(dados = "data")
mg <- sisab_filtrar_mg(ds)

# Filtra antes de coletar, reduzindo drasticamente o uso de RAM.
resumo <- mg |>
  filter(competencia >= "202001", competencia <= "202012", categoria == "E11") |>
  group_by(competencia, ibge, sexo) |>
  summarise(valor = sum(valor, na.rm = TRUE), .groups = "drop") |>
  collect()

# CUIDADO: diferentes linhas/colunas e consultas podem contar os mesmos
# atendimentos em visões distintas. Sempre filtre também relatorio, linha,
# coluna e demais dimensões antes de somar quantidades.
```

Para uma série histórica consolidada: `sisab_abrir_serie("201304", "202512")`.

## Limitações

- R é a interface; a coleta usa Python e necessita dependências Python próprias.
- Exportações CSV originais são mantidas, mas ainda podem surgir variantes de esquema não reconhecidas.
- O Python já normaliza alguns nomes alternativos de UF e município. O dataset guarda `dimensoes_json` para auditoria.
- O CSV bruto de uma única requisição ainda é recebido integralmente pelo cliente HTTP antes de ser compactado. A **conversão do ZIP** e a **consolidação Parquet** usam processamento em lotes.
- O parser da página federal e a coluna CIAP/CID exigem validação no SISAB real.
