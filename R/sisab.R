#' SISAB extrator: interface R para o motor em Python
#'
#' A interface R controla as consultas e usa Apache Arrow para analisar os
#' Parquets sem carregar todos os arquivos em RAM.
#'
#' @param python "auto" prepara e utiliza automaticamente um ambiente Python
#'   isolado no primeiro download e atualiza o motor quando for muito antigo.
#'   Na instalacao manual, indica o Python base (padrao "python").
#' @param dados Diretorio local de dados e do catalogo SQLite.
#' @param relatorio "federal", "municipal" ou "all".
#' @param inicio Competencia AAAAMM ou "auto".
#' @param fim Competencia AAAAMM ou "auto".
#' @param linhas Rotulo/valor de linha ou "all".
#' @param colunas Rotulo/valor de coluna ou "all".
#' @param tipo_producao Rotulo/valor do filtro Tipo de Producao do SISAB,
#'   "none" ou "all". Consulte as opcoes reais com sisab_inspecionar().
#'   Evite "all" sem revisar se as combinacoes sao validas para a coluna.
#' @param ciap_cid "auto" seleciona todos os CIAP/CID quando usados em linha/coluna;
#'   "all" solicita todos explicitamente; "none" ignora este filtro.
#'   Interrompe se o portal nao expuser selecao segura de todos os codigos.
#' @param idades "all", "none" ou uma faixa etaria especifica.
#' @param sexos "both", "none", "Masculino" ou "Feminino".
#' @param aceitar_plano_grande Autorizar mais de 10 mil consultas.
#' @param pausa Pausa minima entre requisicoes HTTP (segundos).
#' @param tempo_limite Tempo maximo de inatividade em cada requisicao HTTP (segundos, padrao 900).
#' @param tentativas Numero de novas tentativas apos falhas (padrao 6).
#' @param consolidar Consolidar automaticamente depois de baixar.
#' @param permitir_parcial Aceitar serie com consultas pendentes ou com erro.
#' @param ano Ano do Parquet anual ou NULL para abrir todos os anuais.
#' @param ds Dataset Arrow retornado por sisab_abrir_serie/anuais.
#' @name sisabextrator
NULL

.sisab_venv_dir <- function() {
  file.path(tools::R_user_dir("sisabextrator", which = "data"), "venv")
}

.sisab_venv_python <- function() {
  file.path(.sisab_venv_dir(), if (.Platform$OS.type == "windows") "Scripts" else "bin",
            if (.Platform$OS.type == "windows") "python.exe" else "python")
}

.sisab_motor_min_version <- "0.1.8"

.sisab_motor_version <- function(executable) {
  if (!file.exists(executable)) return(NA_character_)
  out <- suppressWarnings(tryCatch(
    system2(executable,
            args = c("-m", "pip", "show", "sisab-extrator"),
            stdout = TRUE, stderr = FALSE),
    error = function(e) character()
  ))
  version <- grep("^Version: ", out, value = TRUE)
  if (!length(version)) return(NA_character_)
  trimws(sub("^Version: ", "", version[[1L]]))
}

.sisab_motor_pronto <- function(executable) {
  current <- .sisab_motor_version(executable)
  if (is.na(current)) return(FALSE)
  isTRUE(tryCatch(
    utils::compareVersion(current, .sisab_motor_min_version) >= 0L,
    error = function(e) FALSE
  ))
}


.sisab_git_encontrar <- function() {
  git <- unname(Sys.which("git"))
  if (nzchar(git)) return(git)
  if (.Platform$OS.type != "windows") return("")
  bases <- c(
    Sys.getenv("ProgramFiles"),
    Sys.getenv("ProgramFiles(x86)"),
    file.path(Sys.getenv("LOCALAPPDATA"), "Programs")
  )
  bases <- bases[nzchar(bases)]
  candidatos <- file.path(bases, "Git", "cmd", "git.exe")
  encontrados <- candidatos[file.exists(candidatos)]
  if (!length(encontrados)) return("")
  normalizePath(encontrados[[1L]], winslash = "/", mustWork = FALSE)
}

.sisab_preparar_git <- function() {
  git <- .sisab_git_encontrar()
  if (!nzchar(git) && .Platform$OS.type == "windows") {
    winget <- unname(Sys.which("winget"))
    if (nzchar(winget)) {
      message("Git nao encontrado. Tentando instalar automaticamente com winget...")
      status <- tryCatch(suppressWarnings(system2(
        winget,
        args = c("install", "--id", "Git.Git", "--exact", "--source", "winget",
                 "--accept-package-agreements", "--accept-source-agreements", "--silent"),
        stdout = "", stderr = ""
      )), error = function(e) {
        message("Nao foi possivel executar winget: ", conditionMessage(e))
        NA_integer_
      })
      if (!identical(as.integer(status), 0L)) {
        message("Instalacao do Git indisponivel; tentando metodo sem Git.")
      }
      git <- .sisab_git_encontrar()
    } else {
      message("winget nao encontrado; tentando metodo sem Git.")
    }
  }
  if (!nzchar(git)) return(FALSE)
  # Atualiza o PATH desta sessao: o RStudio pode estar aberto desde antes
  # da instalacao do Git e nao reconhecer o executavel novo.
  pasta_git <- dirname(git)
  pastas_path <- strsplit(Sys.getenv("PATH"), .Platform$path.sep, fixed = TRUE)[[1L]]
  if (!pasta_git %in% pastas_path) {
    Sys.setenv(PATH = paste(pasta_git, Sys.getenv("PATH"), sep = .Platform$path.sep))
  }
  TRUE
}

.sisab_origens_motor <- function() {
  zip <- "https://github.com/maiconcarlospng/sisab-extrator/archive/refs/heads/main.zip"
  if (!.sisab_preparar_git()) return(c(zip = zip))
  c(git = "git+https://github.com/maiconcarlospng/sisab-extrator.git",
    zip = zip)
}

.sisab_assegurar_motor <- function() {
  py <- .sisab_venv_python()
  if (.sisab_motor_pronto(py)) return(py)
  has_venv <- file.exists(py)
  message(if (has_venv)
    "Atualizando motor Python do SISAB Extrator automaticamente..."
  else
    "Primeiro uso: instalando motor Python isolado do SISAB Extrator...")
  sisab_instalar_motor(atualizar = has_venv)
  if (!.sisab_motor_pronto(py)) {
    stop("O motor Python nao foi instalado na versao minima exigida (",
         .sisab_motor_min_version, "). Verifique as mensagens da instalacao.",
         call. = FALSE)
  }
  py
}

.sisab_python <- function(python = "auto") {
  if (!is.character(python) || length(python) != 1L ||
      is.na(python) || !nzchar(python)) {
    stop("Informe o executavel Python ou use 'auto'.", call. = FALSE)
  }
  if (identical(python, "auto")) return(.sisab_assegurar_motor())
  binary <- Sys.which(python)
  if (!nzchar(binary)) {
    if (!file.exists(python)) stop("Python nao encontrado: ", python, call. = FALSE)
    return(python)
  }
  unname(binary)
}

.sisab_cli <- function(comando, opcoes = character(), python = "auto") {
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

.sisab_network_opts <- function(tempo_limite, tentativas) {
  if (length(tempo_limite) != 1L || is.na(tempo_limite) ||
      !is.numeric(tempo_limite) || !is.finite(tempo_limite) ||
      tempo_limite <= 0 || tempo_limite != as.integer(tempo_limite)) {
    stop("'tempo_limite' deve ser um numero inteiro positivo de segundos.", call. = FALSE)
  }
  if (length(tentativas) != 1L || is.na(tentativas) ||
      !is.numeric(tentativas) || !is.finite(tentativas) ||
      tentativas < 0 || tentativas != as.integer(tentativas)) {
    stop("'tentativas' deve ser um numero inteiro >= 0.", call. = FALSE)
  }
  c("--timeout", as.character(as.integer(tempo_limite)),
    "--retries", as.character(as.integer(tentativas)))
}

.sisab_opts <- function(dados, relatorio, inicio, fim, linhas, colunas, idades,
                        sexos, aceitar_plano_grande, pausa, tipo_producao = "none",
                        ciap_cid = "auto") {
  relatorio <- match.arg(relatorio, c("all", "federal", "municipal"))
  sexos <- match.arg(sexos, c("both", "none", "Masculino", "Feminino"))
  ciap_cid <- match.arg(ciap_cid, c("auto", "all", "none"))
  if (length(pausa) != 1L || !is.finite(pausa) || pausa < 0) {
    stop("'pausa' precisa ser um numero finito nao negativo.", call. = FALSE)
  }
  opts <- c("--report", relatorio, "--start", inicio, "--end", fim,
            "--lines", linhas, "--columns", colunas, "--ages", idades,
            "--sexes", sexos, "--production-type", tipo_producao,
            "--ciap-cid", ciap_cid,
            "--data-dir", dados, "--delay", as.character(pausa))
  if (isTRUE(aceitar_plano_grande)) opts <- c(opts, "--allow-large-plan")
  opts
}

#' @rdname sisabextrator
#' @export
sisab_instalar_motor <- function(python = "python", atualizar = FALSE) {
  # Nunca instalar no Python global: o PySUS pode exigir chardet incompatível
  # com requests. Um ambiente exclusivo evita conflitos com outros projetos.
  py_base <- .sisab_python(python)
  dir_venv <- .sisab_venv_dir()
  py_venv <- .sisab_venv_python()
  if (!file.exists(py_venv)) {
    dir.create(dirname(dir_venv), recursive = TRUE, showWarnings = FALSE)
    message("Criando ambiente Python exclusivo do SISAB Extrator...")
    args_venv <- c("-m", "venv", dir_venv)
    status <- suppressWarnings(system2(
      py_base, args = vapply(args_venv, shQuote, character(1L)),
      stdout = "", stderr = ""
    ))
    if (!identical(as.integer(status), 0L) || !file.exists(py_venv)) {
      stop("Nao foi possivel criar ambiente Python isolado. Verifique se ",
           "o Python possui suporte ao modulo venv.", call. = FALSE)
    }
  }
  args <- c("-m", "pip", "install")
  if (isTRUE(atualizar)) {
    # Atualiza o motor e suas dependencias, mas somente dentro do ambiente isolado.
    args <- c(args, "--upgrade", "--force-reinstall")
  }
  origens <- .sisab_origens_motor()
  for (metodo in names(origens)) {
    message("Instalando motor SISAB via ", metodo, "...")
    args_instalar <- c(args, unname(origens[[metodo]]))
    status <- tryCatch(suppressWarnings(system2(
      py_venv, args = vapply(args_instalar, shQuote, character(1L)),
      stdout = "", stderr = ""
    )), error = function(e) {
      message("Falha na tentativa via ", metodo, ": ", conditionMessage(e))
      NA_integer_
    })
    if (identical(as.integer(status), 0L)) {
      message("Motor SISAB instalado no ambiente isolado: ", py_venv)
      return(invisible(TRUE))
    }
    message("Nao foi possivel instalar via ", metodo, ".")
  }
  stop("Falha ao instalar o motor no ambiente isolado pelos metodos disponiveis. ",
       "Confira as mensagens do pip acima.", call. = FALSE)
}

#' @rdname sisabextrator
#' @export
sisab_inspecionar <- function(relatorio = "federal", dados = "data", python = "auto",
                             tempo_limite = 900, tentativas = 6) {
  opts <- c("--report", match.arg(relatorio, c("federal", "municipal", "all")),
            "--data-dir", dados, .sisab_network_opts(tempo_limite, tentativas))
  .sisab_cli("probe", opts, python)
}

#' @rdname sisabextrator
#' @export
sisab_planejar <- function(inicio = "auto", fim = "auto", relatorio = "all",
                           linhas = "all", colunas = "all", idades = "all",
                           sexos = "both", dados = "data", aceitar_plano_grande = FALSE,
                           pausa = 2, python = "auto", tempo_limite = 900, tentativas = 6,
                           tipo_producao = "none", ciap_cid = "auto") {
  opts <- c(.sisab_opts(dados, relatorio, inicio, fim, linhas, colunas,
                        idades, sexos, aceitar_plano_grande, pausa,
                        tipo_producao, ciap_cid),
            .sisab_network_opts(tempo_limite, tentativas))
  .sisab_cli("plan", opts, python)
}

#' @rdname sisabextrator
#' @export
sisab_baixar <- function(inicio = "auto", fim = "auto", relatorio = "all",
                         linhas = "all", colunas = "all", idades = "all",
                         sexos = "both", dados = "data", aceitar_plano_grande = FALSE,
                         consolidar = TRUE, pausa = 2, python = "auto",
                         tempo_limite = 900, tentativas = 6,
                         tipo_producao = "none", ciap_cid = "auto") {
  opts <- c(.sisab_opts(dados, relatorio, inicio, fim, linhas, colunas,
                        idades, sexos, aceitar_plano_grande, pausa,
                        tipo_producao, ciap_cid),
            .sisab_network_opts(tempo_limite, tentativas))
  if (!isTRUE(consolidar)) opts <- c(opts, "--no-consolidate")
  .sisab_cli("download", opts, python)
}

#' @rdname sisabextrator
#' @export
sisab_consolidar <- function(inicio, fim, dados = "data", permitir_parcial = FALSE,
                              python = "auto") {
  opts <- c("--start", inicio, "--end", fim, "--data-dir", dados)
  if (isTRUE(permitir_parcial)) opts <- c(opts, "--allow-partial")
  .sisab_cli("consolidate", opts, python)
}

#' @rdname sisabextrator
#' @export
sisab_status <- function(inicio = NULL, fim = NULL, dados = "data", python = "auto") {
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
