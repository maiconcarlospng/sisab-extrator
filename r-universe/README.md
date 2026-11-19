# Publicar o sisabextrator no R-universe

> **Desde a versão R 0.2.1:** `sisab_instalar_motor()` prepara
> automaticamente um ambiente Python separado do PySUS; as funções de extração
> usam esse ambiente por padrão. Não é necessário modificar as dependências
> do Python principal.

O arquivo `packages.json` **deste diretório** é somente um modelo.
O R-universe NÃO lê a configuração daqui.

1. Na conta GitHub `maiconcarlospng`, crie um **novo repositório público**
   com o nome exato **`maiconcarlospng.r-universe.dev`**.
2. Na raiz do novo repositório, crie um arquivo `packages.json` e copie
   o conteúdo de [packages.json](packages.json).
3. Abra https://github.com/apps/r-universe/installations/new, instale o
   aplicativo na conta `maiconcarlospng` e conceda acesso aos repositórios
   `maiconcarlospng.r-universe.dev` e `sisab-extrator` (ou selecione
   todos os repositórios, se preferir).
4. A [primeira compilação](https://docs.r-universe.dev/publish/set-up.html#wait-first-build)
   pode levar **cerca de 1 hora**. Verifique o estado em
   https://maiconcarlospng.r-universe.dev; antes de terminar, a mensagem
   `No packages found for this owner or maintainer` pode ser transitória.
   Se, passado esse prazo, ainda não aparecer, consulte os registros do
   R-universe. Um check aprovado no GitHub Actions não confirma publicação.
5. Após a publicação, instale no R:

```r
install.packages("sisabextrator", repos = c(
  "https://maiconcarlospng.r-universe.dev",
  "https://cloud.r-project.org"
))
library(sisabextrator)
```

A instalação R não inclui as dependências Python; para executar extração,
use `sisab_instalar_motor()` (requer Python 3.10+ e Git).

Documentação: https://docs.r-universe.dev/publish/set-up.html
