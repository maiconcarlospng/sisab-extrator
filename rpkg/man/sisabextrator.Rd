\name{sisabextrator}
\alias{sisabextrator}
\alias{sisab_instalar_motor}
\alias{sisab_inspecionar}
\alias{sisab_planejar}
\alias{sisab_baixar}
\alias{sisab_consolidar}
\alias{sisab_status}
\alias{sisab_abrir_anuais}
\alias{sisab_abrir_serie}
\alias{sisab_filtrar_mg}
\title{Interface R para o SISAB Extrator}
\description{Controla o motor Python e permite consultar datasets Parquet de forma preguiçosa com Arrow.}
\usage{
sisab_instalar_motor(python = "python", atualizar = FALSE)
sisab_inspecionar(relatorio = "federal", dados = "data", python = "python")
sisab_planejar(inicio = "auto", fim = "auto", relatorio = "all", linhas = "all", colunas = "all", idades = "all", sexos = "both", dados = "data", aceitar_plano_grande = FALSE, pausa = 2, python = "python")
sisab_baixar(inicio = "auto", fim = "auto", relatorio = "all", linhas = "all", colunas = "all", idades = "all", sexos = "both", dados = "data", aceitar_plano_grande = FALSE, consolidar = TRUE, pausa = 2, python = "python")
sisab_consolidar(inicio, fim, dados = "data", permitir_parcial = FALSE, python = "python")
sisab_status(inicio = NULL, fim = NULL, dados = "data", python = "python")
sisab_abrir_anuais(dados = "data", ano = NULL)
sisab_abrir_serie(inicio, fim, dados = "data")
sisab_filtrar_mg(ds)
}
\arguments{
\item{python}{Executável Python que contém o motor de extração.}
\item{atualizar}{Se verdadeiro, atualiza o motor Python.}
\item{relatorio}{Relatório federal, municipal ou all.}
\item{dados}{Diretório de trabalho dos arquivos de dados.}
\item{inicio, fim}{Competências AAAAMM; em consultas podem ser auto.}
\item{linhas, colunas}{Opções exibidas por sisab_inspecionar, ou all.}
\item{idades}{all, none ou rótulo de uma faixa etária.}
\item{sexos}{both, none, Masculino ou Feminino.}
\item{aceitar_plano_grande}{Autoriza planos com mais de 10.000 consultas.}
\item{pausa}{Pausa mínima em segundos entre requisições.}
\item{consolidar}{Se verdadeiro, consolida ao final do download.}
\item{permitir_parcial}{Permite consolidação com consultas não concluídas.}
\item{ano}{Ano desejado; NULL para todos os consolidados anuais.}
\item{ds}{Dataset Arrow retornado pelas funções de leitura.}
}
\value{As operações de extração retornam invisivelmente TRUE; as funções de leitura retornam um Dataset Arrow, sem materializar todas as linhas na memória.}
\details{Este pacote R é uma interface para o motor Python do mesmo repositório. Requer sua instalação separada. Trabalha com dados públicos agregados do SISAB, não microdados individuais.}
