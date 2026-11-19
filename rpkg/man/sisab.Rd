\name{sisab}
\alias{sisab}
\title{Menu interativo do SISAB Extrator}
\description{Abre um menu no RStudio para baixar dados, visualizar um arquivo Parquet ou consultar o status. O motor Python e instalado ou atualizado automaticamente no primeiro comando que o exige.}
\usage{
sisab(dados = "data")
}
\arguments{
\item{dados}{Pasta para os dados do SISAB (padrao \code{"data"}).}
}
\value{Retorna invisivelmente \code{NULL}. Os resultados ficam nos arquivos escolhidos.}
\details{Requer uma sessao interativa do R/RStudio. Ao baixar, solicita periodo e relatorio, consulta as opcoes reais do portal e apresenta menus de linha, coluna e Tipo de Producao quando necessario. Nao escolhe o tipo de producao arbitrariamente.}
\examples{
\dontrun{sisab()}
}
