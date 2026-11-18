# Publicar o sisabextrator no R-universe

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
4. Verifique a compilação em https://maiconcarlospng.r-universe.dev e, se
   houver erros, consulte os logs. O pacote R da raiz precisa passar nos
   checks antes de ficar disponível.
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
