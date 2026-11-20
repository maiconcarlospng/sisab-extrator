# Verifica o mapeamento dos niveis territoriais encontrados no SISAB.
library(sisabextrator)

filtro <- get(".sisab_opcoes_geograficas", envir = asNamespace("sisabextrator"))

opcoes <- list(
  "BRASIL" = "Brasil",
  "ATD.CO_REGIAO" = "Regiao",
  "ATD.CO_UF_IBGE" = "Estado",
  "REGSAU.CO_SEQ_REGIAO_SAUDE" = "Regiao de Saude",
  "MUN.CO_MUNICIPIO_IBGE" = "Municipio",
  "CID" = "CIAP/CID",
  "NU_COMPETENCIA" = "Competencia"
)

result <- filtro(opcoes)
esperadas <- names(opcoes)[seq_len(5L)]
stopifnot(
  identical(names(result), esperadas),
  identical(unname(unlist(result)), unname(unlist(opcoes[esperadas]))),
  length(filtro(list(CID = "CIAP/CID"))) == 0L
)
cat("Unidades geograficas: niveis territoriais corretamente filtrados.\n")
