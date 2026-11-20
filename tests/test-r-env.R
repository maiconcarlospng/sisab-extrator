# Verificacoes locais da interface R (sem rede nem acesso ao SISAB).
library(sisabextrator)

stopifnot(
  identical(formals(sisab_instalar_motor)$python, "python"),
  identical(formals(sisab_inspecionar)$python, "auto"),
  identical(formals(sisab_planejar)$python, "auto"),
  identical(formals(sisab_baixar)$python, "auto"),
  identical(formals(sisab_consolidar)$python, "auto"),
  identical(formals(sisab_status)$python, "auto")
)

ns <- asNamespace("sisabextrator")
venv_python <- get(".sisab_venv_python", envir = ns)()
stopifnot(
  is.character(venv_python),
  length(venv_python) == 1L,
  grepl("venv", venv_python, fixed = TRUE),
  basename(venv_python) == if (.Platform$OS.type == "windows") "python.exe" else "python"
)

# A verificacao do primeiro uso nunca faz instalacao em CI.
stopifnot(
  is.function(sisab),
  is.function(sisab_visualizar),
  is.function(get(".sisab_assegurar_motor", envir = ns)),
  identical(get(".sisab_motor_min_version", envir = ns), "0.1.9"),
  !get(".sisab_motor_pronto", envir = ns)(file.path(tempdir(), "inexistente.exe")),
  identical(formals(sisab_baixar)$tipo_producao, "none"),
  identical(formals(sisab_baixar)$ciap_cid, "auto"),
  identical(formals(sisab_planejar)$ciap_cid, "auto")
)
erro <- tryCatch(sisab_visualizar(file.path(tempdir(), "nao-existe.parquet")),
                 error = function(e) conditionMessage(e))
stopifnot(grepl(".parquet existente", erro, fixed = TRUE))
stopifnot(identical(get(".sisab_mes_valor", envir = ns)("202401"), "202401"))

network_opts <- get(".sisab_network_opts", envir = ns)
stopifnot(
  identical(network_opts(120, 1), c("--timeout", "120", "--retries", "1")),
  identical(network_opts(900, 0), c("--timeout", "900", "--retries", "0")),
  identical(formals(sisab_baixar)$tempo_limite, 900),
  identical(formals(sisab_baixar)$tentativas, 6)
)
invalid_timeout <- tryCatch(network_opts(0, 1), error = function(e) e)
invalid_retry <- tryCatch(network_opts(120, -1), error = function(e) e)
stopifnot(inherits(invalid_timeout, "error"), inherits(invalid_retry, "error"))
cat("Configuracao de timeout e tentativas: OK\n")

stopifnot(
  is.function(get(".sisab_git_encontrar", envir = ns)),
  is.function(get(".sisab_preparar_git", envir = ns)),
  is.function(get(".sisab_origens_motor", envir = ns))
)
# O instalador oferece alternativa por ZIP, sem depender de git no PATH.
stopifnot(grepl("main.zip", paste(deparse(body(get(".sisab_origens_motor", envir = ns))), collapse = " "), fixed = TRUE))
cat("Configuracao de Python isolado e instalacao sem Git: OK\n")
