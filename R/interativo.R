#' Menu simples do SISAB Extrator
#'
#' Um comando para escolher baixar dados, visualizar um Parquet existente ou
#' consultar o status. Ao baixar, o motor Python isolado e preparado no primeiro
#' uso (ou atualizado quando estiver desatualizado).
#'
#' @param dados Pasta em que o SISAB Extrator salva os dados. Padrao "data".
#' @return Invisivelmente NULL. As consultas continuam disponiveis em
#'   sisab_baixar() para quem prefere um script reproduzivel.
#' @examples
#' \\dontrun{sisab()}
#' @export
sisab <- function(dados = "data") {
  if (!interactive()) {
    stop("O menu sisab() requer uma sessao interativa do RStudio/R. ",
         "Em scripts, use sisab_baixar() ou sisab_visualizar().", call. = FALSE)
  }
  .sisab_menu_baixar_tudo <- function(dados) {
    resposta <- tolower(trimws(readline(
      "Validar combinacoes em uma competencia e baixar todas as competencias? [s/N] "
    )))
    if (!identical(resposta, "s") && !identical(resposta, "sim")) {
      message("Operacao cancelada.")
      return(invisible(NULL))
    }
    relatorios <- c("Municipal", "Federal", "Todos")
    r <- utils::menu(relatorios, title = "Qual relatorio?")
    if (r == 0L) return(invisible(NULL))
    relatorio <- c("municipal", "federal", "all")[r]
    sisab_baixar_tudo(relatorio = relatorio, dados = dados)
  }
  .sisab_menu_explorar <- function(dados) {
    relatorio <- c("federal", "municipal")[utils::menu(
      c("Federal", "Municipal"), title = "Qual relatorio?"
    )]
    if (is.na(relatorio)) return(invisible(NULL))
    sisab_inspecionar(relatorio = relatorio, dados = dados)
    message("Opcoes e campos reais salvos em ", file.path(dados, "inspecao"),
            ". Use sisab_planejar() para montar uma consulta.")
  }
  .sisab_menu_consolidar <- function(dados) {
    inicio <- .sisab_mes("Competencia inicial (AAAAMM): ")
    fim <- .sisab_mes_valor(trimws(readline("Competencia final (AAAAMM): ")))
    sisab_consolidar(inicio, fim, dados = dados)
  }
  .sisab_menu_configuracoes <- function(dados) {
    message("Diretorio de dados atual: ", normalizePath(dados, mustWork = FALSE))
    message("O motor Python isolado e configurado automaticamente no primeiro uso.")
  }
  repeat {
    escolha <- utils::menu(
      c("Baixar dados", "Baixar tudo (extracao abrangente)",
        "Explorar filtros e combinacoes", "Consultar downloads e progresso",
        "Visualizar arquivos Parquet", "Consolidar dados", "Configuracoes",
        "Sair"),
      title = "SISAB Extrator — escolha uma acao"
    )
    if (escolha == 0L || escolha == 8L) break
    tryCatch(
      switch(escolha,
             .sisab_menu_baixar(dados),
             .sisab_menu_baixar_tudo(dados),
             .sisab_menu_explorar(dados),
             sisab_status(dados = dados),
             sisab_visualizar(),
             .sisab_menu_consolidar(dados),
             .sisab_menu_configuracoes(dados)),
      error = function(e) message("SISAB Extrator: ", conditionMessage(e))
    )
  }

  invisible(NULL)
}

.sisab_menu_escolher <- function(options, titulo) {
  if (is.null(options) || !length(options)) {
    stop("O portal nao apresentou opcoes para: ", titulo, call. = FALSE)
  }
  valores <- unlist(options, use.names = TRUE)
  valores <- valores[!is.na(valores) & nzchar(names(valores))]
  if (!length(valores)) {
    stop("Nenhuma opcao valida para: ", titulo, call. = FALSE)
  }
  labels <- paste0(unname(valores), " [", names(valores), "]")
  i <- utils::menu(labels, title = titulo)
  if (i == 0L) stop("Selecao cancelada.", call. = FALSE)
  list(valor = names(valores)[i], rotulo = unname(valores)[i])
}

.sisab_mes <- function(prompt) {
  mes <- trimws(readline(prompt))
  if (!grepl("^[0-9]{6}$", mes) ||
      !as.integer(substr(mes, 5L, 6L)) %in% 1:12) {
    stop("Competencia invalida. Digite 6 numeros no formato AAAAMM, ",
         "por exemplo 202401.", call. = FALSE)
  }
  mes
}

.sisab_menu_baixar <- function(dados) {
  relatorios <- c("Municipal", "Federal")
  r <- utils::menu(relatorios, title = "Qual relatorio?")
  if (r == 0L) return(invisible(NULL))
  relatorio <- c("municipal", "federal")[r]
  inicio <- .sisab_mes("Mes inicial (AAAAMM, exemplo 202401): ")
  fim <- trimws(readline("Mes final (Enter para o mesmo mes): "))
  if (!nzchar(fim)) {
    fim <- inicio
  } else {
    fim <- .sisab_mes_valor(fim)
  }
  if (fim < inicio) stop("Mes final anterior ao inicial.", call. = FALSE)

  message("Consultando as opcoes reais do portal SISAB...")
  sisab_inspecionar(relatorio = relatorio, dados = dados)
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    message("Instalando jsonlite para apresentar o menu de filtros...")
    utils::install.packages("jsonlite")
    if (!requireNamespace("jsonlite", quietly = TRUE)) {
      stop("Nao foi possivel instalar jsonlite.", call. = FALSE)
    }
  }
  path <- file.path(dados, "inspecao", paste0(relatorio, ".json"))
  info <- jsonlite::fromJSON(path, simplifyVector = FALSE)

  linha <- .sisab_menu_escolher(info$linha$options, "Selecione a linha do relatorio")
  coluna <- .sisab_menu_escolher(info$coluna$options, "Selecione a coluna do relatorio")
  eh_tipo <- function(x) {
    valor <- iconv(x, from = "", to = "ASCII//TRANSLIT", sub = "")
    grepl("tipo de producao", tolower(valor), fixed = TRUE)
  }
  tipo_producao <- "none"
  if (!eh_tipo(linha$rotulo) && !eh_tipo(coluna$rotulo)) {
    tipo <- .sisab_menu_escolher(info$tipo_producao$options,
                                "Tipo de Producao (obrigatorio nessa combinacao)")
    tipo_producao <- tipo$valor
    message("Tipo de Producao escolhido: ", tipo$rotulo)
  }
  eh_ciap <- function(x, rotulo) {
    identical(x, "CID") || grepl("ciap/cid", tolower(rotulo), fixed = TRUE)
  }
  ciap_cid <- if (eh_ciap(linha$valor, linha$rotulo) ||
                  eh_ciap(coluna$valor, coluna$rotulo)) "all" else "none"
  if (ciap_cid == "all") {
    message("CIAP/CID: TODOS os codigos e grupos oferecidos pelo formulario.")
    if (is.null(info$ciap_cid) || !length(info$ciap_cid$options)) {
      message("A lista CIAP/CID aparece depois da selecao da coluna. ",
              "Tentaremos ativar o evento JSF do portal antes do download; ",
              "se o evento nao for reconhecido, um diagnostico sera salvo.")
    }
  }
  message("Preparando download de ", inicio, " a ", fim,
          " | ", relatorio, " | ", linha$rotulo, " x ", coluna$rotulo)
  sisab_baixar(
    inicio = inicio, fim = fim, relatorio = relatorio,
    linhas = linha$valor, colunas = coluna$valor,
    tipo_producao = tipo_producao,
    ciap_cid = ciap_cid,
    idades = "none", sexos = "none",
    dados = dados
  )
  invisible(TRUE)
}

.sisab_mes_valor <- function(mes) {
  if (!grepl("^[0-9]{6}$", mes) ||
      !as.integer(substr(mes, 5L, 6L)) %in% 1:12) {
    stop("Competencia invalida. Use AAAAMM, exemplo 202401.", call. = FALSE)
  }
  mes
}

#' Visualizar um arquivo Parquet pelo seletor de arquivos
#'
#' Abre uma janela para escolher um arquivo .parquet e mostra uma amostra de
#' linhas no visualizador do RStudio. Instala arrow/dplyr se estiverem ausentes.
#'
#' @param arquivo Caminho de um arquivo Parquet, ou NULL para usar file.choose().
#' @param n Numero maximo de linhas mostradas na visualizacao. Padrao 100.
#' @return Invisivelmente um data.frame com as primeiras n linhas.
#' @examples
#' \\dontrun{sisab_visualizar()}
#' @export
sisab_visualizar <- function(arquivo = NULL, n = 100L) {
  if (is.null(arquivo)) {
    if (!interactive()) {
      stop("Em scripts, informe o caminho do Parquet em 'arquivo'.", call. = FALSE)
    }
    arquivo <- file.choose()
  }
  if (!is.character(arquivo) || length(arquivo) != 1L ||
      !file.exists(arquivo) || !grepl("\\.parquet$", arquivo, ignore.case = TRUE)) {
    stop("Selecione um arquivo .parquet existente.", call. = FALSE)
  }
  if (!is.numeric(n) || length(n) != 1L || is.na(n) ||
      n < 1 || n > 10000 || n != as.integer(n)) {
    stop("'n' deve ser um inteiro de 1 a 10000.", call. = FALSE)
  }
  for (pacote in c("arrow", "dplyr")) {
    if (!requireNamespace(pacote, quietly = TRUE)) {
      message("Instalando ", pacote, " para visualizar os dados...")
      utils::install.packages(pacote)
      if (!requireNamespace(pacote, quietly = TRUE)) {
        stop("Nao foi possivel instalar o pacote R '", pacote, "'.", call. = FALSE)
      }
    }
  }
  dataset <- arrow::open_dataset(arquivo)
  # Suporta versoes diferentes de Arrow sem carregar o Parquet inteiro.
  preview <- tryCatch(
    dplyr::collect(dplyr::slice_head(dataset, n = as.integer(n))),
    error = function(e) NULL
  )
  if (is.null(preview)) {
    preview <- tryCatch(dplyr::collect(utils::head(dataset, n)),
                        error = function(e) NULL)
  }
  if (is.null(preview) && file.info(arquivo)$size <= 50 * 1024^2) {
    # Fallback apenas para arquivos pequenos, evitando usar RAM excessiva.
    preview <- utils::head(arrow::read_parquet(arquivo), n)
  }
  if (is.null(preview)) {
    stop("Nao foi possivel gerar a amostra do Parquet sem carregar um arquivo ",
         "muito grande na memoria. Atualize arrow e dplyr.", call. = FALSE)
  }
  message("Exibindo ate ", n, " linhas de ", basename(arquivo), ".")
  if (interactive()) utils::View(preview, title = basename(arquivo))
  invisible(preview)
}
