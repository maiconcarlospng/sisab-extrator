\name{sisabextrator}
\alias{sisabextrator}
\alias{sisab_instalar_motor}
\alias{sisab_inspecionar}
\alias{sisab_planejar}
\alias{sisab_baixar}
\alias{sisab_baixar_tudo}
\alias{sisab_consolidar}
\alias{sisab_status}
\alias{sisab_abrir_anuais}
\alias{sisab_abrir_serie}
\alias{sisab_filtrar_mg}
\title{Interface R para o SISAB Extrator}
\description{Controla o motor Python e permite consultar datasets Parquet de forma preguiçosa com Arrow.}
\usage{
sisab_instalar_motor(python = "python", atualizar = FALSE)
sisab_inspecionar(relatorio = "federal", dados = "data", python = "auto", tempo_limite = 900, tentativas = 6)
sisab_planejar(inicio = "auto", fim = "auto", relatorio = "all", linhas = "all", colunas = "all", idades = "all", sexos = "both", dados = "data", aceitar_plano_grande = FALSE, pausa = 2, python = "auto", tempo_limite = 900, tentativas = 6, tipo_producao = "none", ciap_cid = "auto")
sisab_baixar(inicio = "auto", fim = "auto", relatorio = "all", linhas = "all", colunas = "all", idades = "all", sexos = "both", dados = "data", aceitar_plano_grande = FALSE, consolidar = TRUE, pausa = 2, python = "auto", tempo_limite = 900, tentativas = 6, tipo_producao = "none", ciap_cid = "auto")
sisab_baixar_tudo(inicio = "auto", fim = "auto", relatorio = "all", dados = "data", aceitar_plano_grande = FALSE, consolidar = TRUE, pausa = 2, python = "auto", tempo_limite = 900, tentativas = 6, mes_validacao = "auto", matriz_compatibilidade = NULL)
sisab_consolidar(inicio, fim, dados = "data", permitir_parcial = FALSE, python = "auto")
sisab_status(inicio = NULL, fim = NULL, dados = "data", python = "auto")
sisab_abrir_anuais(dados = "data", ano = NULL)
sisab_abrir_serie(inicio, fim, dados = "data")
sisab_filtrar_mg(ds)
}
\arguments{
\item{python}{Ao instalar o motor, nome ou caminho do Python de base (padrão "python"). Nas funções de extração, "auto" utiliza o Python exclusivo criado por \code{sisab_instalar_motor()}; também é possível indicar um executável manualmente.}
\item{atualizar}{Se verdadeiro, atualiza o motor Python.}
\item{relatorio}{Relatório federal, municipal ou all.}
\item{dados}{Diretório de trabalho dos arquivos de dados.}
\item{inicio, fim}{Competências AAAAMM; em consultas podem ser auto.}
\item{linhas, colunas}{Opções exibidas por sisab_inspecionar, ou all.}
\item{tipo_producao}{Filtro Tipo de Produção: rótulo/valor identificado na inspeção, "none" ou "all". É obrigatório quando a Linha/Coluna não contém Tipo de Produção e o portal exige essa seleção. A opção "all" cria consultas separadas por tipo.}
\item{ciap_cid}{auto seleciona todos os codigos CIAP/CID quando aparecem na linha ou coluna; all pede todos explicitamente; none ignora. Para selecionar todos, o portal precisa disponibilizar um controle multiplo ou uma opcao Todos no HTML inicial. Se depender de AJAX sem opcoes estaticas, a consulta e interrompida antes do POST.}
\item{idades}{all, none ou rótulo de uma faixa etária.}
\item{sexos}{both, none, Masculino ou Feminino.}
\item{aceitar_plano_grande}{Autoriza planos com mais de 10.000 consultas.}
\item{pausa}{Pausa mínima em segundos entre requisições.}
\item{tempo_limite}{Tempo limite de inatividade da requisição HTTP em segundos (padrão 900).}
\item{tentativas}{Número de novas tentativas após falha de rede ou resposta inválida (padrão 6).}
\item{consolidar}{Se verdadeiro, consolida ao final do download.}
\item{mes_validacao}{Competência usada para validar a matriz de combinações no modo abrangente; \code{"auto"} usa a primeira competência disponível.}
\item{matriz_compatibilidade}{Arquivo JSON de combinações reais já validadas; NULL gera uma matriz em \code{dados/inspecao}.}
\item{permitir_parcial}{Permite consolidação com consultas não concluídas.}
\item{ano}{Ano desejado; NULL para todos os consolidados anuais.}
\item{ds}{Dataset Arrow retornado pelas funções de leitura.}
}
\value{As operações de extração retornam invisivelmente TRUE; as funções de leitura retornam um Dataset Arrow, sem materializar todas as linhas na memória.}
\details{Este pacote R é uma interface para o motor Python. Execute \code{sisab_instalar_motor()} uma vez para instalar o motor em um ambiente virtual exclusivo e evitar conflitos com PySUS e outras bibliotecas Python. A extração usa esse ambiente automaticamente; o Python principal permanece inalterado. Trabalha com dados públicos agregados do SISAB, não microdados individuais.}
