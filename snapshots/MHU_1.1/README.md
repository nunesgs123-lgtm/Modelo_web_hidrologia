# Modelo Hidrologico Urbano (Web Local)

Aplicacao web local em `Streamlit` para simular:
- geracao e propagacao do escoamento superficial por AC;
- vazao no exutorio;
- conversao de vazao para nivel no canal (Manning, secao retangular).

## Como executar

1. Abra terminal na pasta do projeto:
   - `C:\Users\obser\OneDrive\Documentos\Gabriel\ESTAGIO\PESQUISA\modelo_web_hidrologia`
2. Instale dependencias:
   - `pip install -r requirements.txt`
3. Rode a aplicacao:
   - `streamlit run app.py`

## Navegacao

Na barra lateral use o **Menu** para alternar entre:

- **Simulacao** — formularios e resultados
- **Instrucoes** — passo a passo de uso
- **Descricao das variaveis** — glossario dos termos
- **Validacao** — niveis observados vs simulados (NSE/Nash, R2, RMSE, MAE)
- **Sugestao de calibracao** — faixas de infiltracao e Manning (US) e n do canal

## Uso rapido

1. Configure `Delta t` e `Duracao da chuva`.
2. Informe parametros do canal.
3. Edite a tabela de ACs (incluindo `ACs_montante_ids`, ex.: `1;2`).
4. Edite a serie de chuva em `P_mm_h` (o passo `t=0` pode ficar 0).
5. Clique em **Rodar simulacao**.
6. Visualize hidrogramas e baixe resultados em Excel.

## Publicar na internet (link publico, sem PowerShell)

Sim: o mesmo app pode rodar em um servidor na nuvem; o usuario so abre o link no navegador.

### Opcao recomendada: Streamlit Community Cloud (gratuito)

1. Crie uma conta em [GitHub](https://github.com) e um **repositorio publico**.
2. Envie **apenas o conteudo** desta pasta (`modelo_web_hidrologia`) para a raiz do repositorio — ou seja, `app.py`, `requirements.txt`, `.streamlit/`, etc., na raiz do repo (facilita o deploy).
3. Acesse [share.streamlit.io](https://share.streamlit.io), faca login com GitHub e clique em **New app**.
4. Escolha o repositorio, branch e arquivo principal: `app.py`.
5. O Streamlit gera um endereco publico (ex.: `https://nome-do-app.streamlit.app`).

### Checklist rapido pre-deploy

- `app.py` na raiz do repositorio.
- `requirements.txt` na raiz com as dependencias Python.
- `runtime.txt` na raiz (Python 3.11 para build consistente).
- `.streamlit/config.toml` opcional (ja incluido neste projeto).
- Repositorio no GitHub atualizado com `git push`.

### Atualizar app ja publicado

1. Faca alteracoes locais.
2. Execute `git add .`, `git commit -m "mensagem"`, `git push origin main`.
3. O Streamlit Cloud reconstrui automaticamente.
4. Se nao atualizar, abra o app no Streamlit Cloud e clique em **Reboot app**.

**Observacoes:**

- Qualquer pessoa com o link pode usar o app (nao ha login por padrao).
- O plano gratuito tem limites de uso; para trafego alto ou privacidade, avalie planos pagos ou outro provedor.
- Se o repositorio tiver o projeto dentro de uma subpasta, em **Advanced settings** informe o **Main file path** (ex.: `pasta/.../app.py`).

### Outras opcoes

- **Railway**, **Render**, **Fly.io**, **Google Cloud Run**: em geral exigem `Dockerfile` ou configuracao de build.
- **ngrok** / **Cloudflare Tunnel**: expoem o `localhost` com um link temporario — ainda e preciso manter o Streamlit rodando no seu PC.

## Subir o projeto para o GitHub (uma vez)

1. Instale o **Git para Windows** se o comando `git` nao existir no PowerShell: [git-scm.com](https://git-scm.com/download/win). Feche e abra o terminal de novo.
2. No GitHub: **New repository**, nome (ex.: `modelo-web-hidrologia`), **Public**, **sem** README inicial (para evitar conflito no primeiro push).
3. No PowerShell, na pasta deste projeto:

```powershell
cd "C:\Users\obser\OneDrive\Documentos\Gabriel\ESTAGIO\PESQUISA\modelo_web_hidrologia"
git init
git branch -M main
git add .
git commit -m "App Streamlit: modelo hidrologico urbano"
git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
git push -u origin main
```

Substitua `SEU_USUARIO` e `SEU_REPOSITORIO` pelo endereco que o GitHub mostrar apos criar o repositorio.

Na primeira vez, o Git pode pedir login: use **Personal Access Token** (GitHub → Settings → Developer settings) em vez de senha, ou instale o **GitHub Desktop** e use a opcao publicar repositorio pela interface.

Alternativa sem Git no terminal: no site do GitHub, **Add file → Upload files** e arraste os arquivos da pasta (menos pratico para atualizacoes futuras).

