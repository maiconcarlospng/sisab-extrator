#' SISAB extrator: interface R para o motor em Python
#'
#' A interface R controla as consultas e usa Apache Arrow para analisar os
#' Parquets sem carregar todos os arquivos em RAM.
#'
#' @param python Executavel Python com o pacote sisab-extrator instalado.
#' @param dados Diretorio local de dados e do catalogo SQLite.
#' @param relatorio "federal", "municipal" ou "all".
#' @param inicio Competencia AAAAMM ou "auto".
#' @param fim Competencia AAAAMM ou "auto".
#' @param linhas Rotulo/valor de linha ou "all".
#' @param colunas Rotulo/valor de coluna ou "all".
#' @param idades "all", "none" ou uma faixa etaria especifica.
#' @param sexos "both", "none", "Masculino" ou "Feminino".
#' @param aceitar_plano_grande Autorizar mais de 10 mil consultas.
#' @param pausa Pausa minima entre requisicoes HTTP (segundos).
#' @param consolidar Consolidar automaticamente depois de baixar.
#' @param permitir_parcial Aceitar serie com consultas pendentes ou com erro.
#' @param ano Ano do Parquet anual ou NULL para abrir todos os anuais.
#' @param ds Dataset Arrow retornado por sisab_abrir_serie/anuais.
#' @name sisabextrator
NULL

.sisab_python <- function(python) {
  if (length(python) != 1L || is.na(python) || !nzchar(python)) {
    stop("Informe o executavel Python, ex.: 'python' ou 'python3'.", call. = FALSE)
  }
  binary <- Sys.which(python)
  if (!nzchar(binary)) {
    if (!file.exists(python)) stop("Python nao encontrado: ", python, call. = FALSE)
    return(python)
  }
  unname(binary)
}

.sisab_cli <- function(comando, opcoes = character(), python = "python") {
  py <- .sisab_python(python)
  args <- c("-m", "sisab_extrator", comando, opcoes)
  status <- suppressWarnings(system2(py, args = vapply(args, shQuote, character(1L)),
                                      stdout = "", stderr = ""))
  if (!identical(as.integer(status), 0L)) {
    stop("Falha ao executar SISAB Extrator (codigo ", status,
         "). Verifique o log acima e o resultado de sisab_inspecionar().", call. = FALSE)
  }
  invisible(TRUE)
}

.sisab_opts <- function(dados, relatorio, inicio, fim, linhas, colunas, idades,
                        sexos, aceitar_plano_grande, pausa) {
  relatorio <- match.arg(relatorio, c("all", "federal", "municipal"))
  sexos <- match.arg(sexos, c("both", "none", "Masculino", "Feminino"))
  if (length(pausa) != 1L || !is.finite(pausa) || pausa < 0) {
    stop("'pausa' precisa ser um numero finito nao negativo.", call. = FALSE)
  }
  opts <- c("--report", relatorio, "--start", inicio, "--end", fim,
            "--lines", linhas, "--columns", colunas, "--ages", idades,
            "--sexes", sexos, "--data-dir", dados, "--delay", as.character(pausa))
  if (isTRUE(aceitar_plano_grande)) opts <- c(opts, "--allow-large-plan")
  opts
}

#' @rdname sisabextrator
#' @export
sisab_instalar_motor <- function(python = "python", atualizar = FALSE) {
  py <- .sisab_python(python)
  origem <- "git+https://github.com/maiconcarlospng/sisab-extrator.git"
  args <- c("-m", "pip", "install")
  if (isTRUE(atualizar)) {
    # A versão Python pode permanecer igual entre commits: refazer a instalação.
    # --no-deps evita reinstalar as bibliotecas já presentes no ambiente.
    args <- c(args, "--upgrade", "--force-reinstall", "--no-deps")
  }
  args <- c(args, origem)
  status <- suppressWarnings(system2(py, vapply(args, shQuote, character(1L)),
                                      stdout = "", stderr = ""))
  if (!identical(as.integer(status), 0L)) stop("Falha ao instalar pacote Python.", call. = FALSE)
  invisible(TRUE)
}

#' @rdname sisabextrator
#' @export
sisab_inspecionar <- function(relatorio = "federal", dados = "data", python = "python") {
  .sisab_cli("probe", c("--report", match.arg(relatorio, c("federal", "municipal", "all")),
                        "--data-dir", dados), python)
}

#' @rdname sisabextrator
#' @export
sisab_planejar <- function(inicio = "auto", fim = "auto", relatorio = "all",
                           linhas = "all", colunas = "all", idades = "all",
                           sexos = "both", dados = "data", aceitar_plano_grande = FALSE,
                           pausa = 2, python = "python") {
  .sisab_cli("plan", .sisab_opts(dados, relatorio, inicio, fim, linhas, colunas,
                                 idades, sexos, aceitar_plano_grande, pausa), python)
}

#' @rdname sisabextrator
#' @export
sisab_baixar <- function(inicio = "auto", fim = "auto", relatorio = "all",
                         linhas = "all", colunas = "all", idades = "all",
                         sexos = "both", dados = "data", aceitar_plano_grande = FALSE,
                         consolidar = TRUE, pausa = 2, python = "python") {
  opts <- .sisab_opts(dados, relatorio, inicio, fim, linhas, colunas,
                      idades, sexos, aceitar_plano_grande, pausa)
  if (!isTRUE(consolidar)) opts <- c(opts, "--no-consolidate")
  .sisab_cli("download", opts, python)
}

#' @rdname sisabextrator
#' @export
sisab_consolidar <- function(inicio, fim, dados = "data", permitir_parcial = FALSE,
                              python = "python") {
  opts <- c("--start", inicio, "--end", fim, "--data-dir", dados)
  if (isTRUE(permitir_parcial)) opts <- c(opts, "--allow-partial")
  .sisab_cli("consolidate", opts, python)
}

#' @rdname sisabextrator
#' @export
sisab_status <- function(inicio = NULL, fim = NULL, dados = "data", python = "python") {
  opts <- c("--data-dir", dados)
  if (!is.null(inicio)) opts <- c(opts, "--start", inicio)
  if (!is.null(fim)) opts <- c(opts, "--end", fim)
  .sisab_cli("status", opts, python)
}

.sisab_arrow <- function(path) {
  if (!requireNamespace("arrow", quietly = TRUE)) {
    stop("Instale o pacote R 'arrow': install.packages('arrow').", call. = FALSE)
  }
  if (!all(file.exists(path))) stop("Parquet nao encontrado: ", paste(path[!file.exists(path)], collapse = ", "), call. = FALSE)
  arrow::open_dataset(path, format = "parquet", unify_schemas = TRUE)
}

#' @rdname sisabextrator
#' @export
sisab_abrir_anuais <- function(dados = "data", ano = NULL) {
  pasta <- file.path(dados, "consolidado", "anual")
  if (is.null(ano)) {
    arquivos <- list.files(pasta, pattern = "^sisab_[0-9]{4}\\.parquet$", full.names = TRUE)
    if (!length(arquivos)) stop("Nao ha Parquets anuais em: ", pasta, call. = FALSE)
    return(.sisab_arrow(arquivos))
  }
  .sisab_arrow(file.path(pasta, paste0("sisab_", ano, ".parquet")))
}

#' @rdname sisabextrator
#' @export
sisab_abrir_serie <- function(inicio, fim, dados = "data") {
  path <- file.path(dados, "consolidado", "serie", paste0("sisab_", inicio, "_", fim, ".parquet"))
  .sisab_arrow(path)
}

#' @rdname sisabextrator
#' @export
sisab_filtrar_mg <- function(ds) {
  if (!requireNamespace("dplyr", quietly = TRUE)) {
    stop("Instale dplyr: install.packages('dplyr').", call. = FALSE)
  }
  dplyr::filter(ds, rlang::.data[["uf"]] %in% c("MG", "31", "310000"))
}
