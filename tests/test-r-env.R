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

# Se o ambiente ainda nao existir, o usuario recebe uma orientacao util.
if (!file.exists(venv_python)) {
  erro <- tryCatch(
    get(".sisab_python", envir = ns)("auto"),
    error = function(e) conditionMessage(e)
  )
  stopifnot(grepl("sisab_instalar_motor()", erro, fixed = TRUE))
}
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

cat("Configuracao de Python isolado: OK\n")
