\name{sisab_visualizar}
\alias{sisab_visualizar}
\title{Visualizar amostra de um arquivo Parquet}
\description{Escolhe um arquivo .parquet e mostra ate n linhas em uma tabela no RStudio.}
\usage{
sisab_visualizar(arquivo = NULL, n = 100L)
}
\arguments{
\item{arquivo}{Caminho para um arquivo Parquet; com \code{NULL}, abre o seletor de arquivos em sessao interativa.}
\item{n}{Numero maximo de linhas para visualizar (1 a 10000).}
}
\value{Retorna invisivelmente um \code{data.frame} com uma amostra do arquivo.}
\details{Apenas para a visualizacao, instala os pacotes R \code{arrow} e \code{dplyr} se nao estiverem presentes. A leitura da amostra e realizada via Arrow e nao requer o motor Python SISAB.}
\examples{
\dontrun{sisab_visualizar()}
}
