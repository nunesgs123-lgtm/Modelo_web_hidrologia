# Modelo Hidrológico Urbano (Web Local)

Aplicação web local em `Streamlit` para simular:
- geração e propagação do escoamento superficial por AC;
- vazão no exutório;
- conversão de vazão para nível no canal (Manning, seção retangular).

Versões: **MHU 1.1** (Modo 1, parâmetros equivalentes — preservado) e **MHU 2.0** experimental
(Modo 2, processamento por classe de uso do solo). Ver `MHU_2.0_CONCEPCAO.md` e `METODOLOGIA_MODELO.md`.

Interface com identidade visual hidrológica (`assets/`, `ui_components.py`, `plot_theme.py`) — exclusivamente organizacional/visual.

## Como executar

1. Abra terminal na pasta do projeto:
   - `C:\Users\obser\OneDrive\Documentos\Gabriel\ESTAGIO\PESQUISA\modelo_web_hidrologia`
2. Instale dependências:
   - `pip install -r requirements.txt`
3. Rode a aplicação:
   - `streamlit run app.py`

## Testes automatizados

```powershell
pip install -r requirements.txt
python -m pytest tests
```

A suíte em `tests/` cobre precipitação, infiltração, conservação de massa, rede, Manning do canal, equivalência Modo 1×2, estatísticas, Excel/simulações salvas e checagem básica da UI Streamlit (`AppTest`). Metodologia e resultados: `METODOLOGIA_MODELO.md`.

## Documentação

- `METODOLOGIA_MODELO.md` — equações, hipóteses, sequência numérica, limitações, calibração
- `MHU_2.0_CONCEPCAO.md` — mudança conceitual do Modo 2
- `CONVERGENCIA_NUMERICA.md` — solver implícito superficial
- `CHANGELOG.md` — histórico de versões
- Snapshots: `snapshots/MHU_1.0/`, `snapshots/MHU_1.1/`

## Navegação

Na barra lateral use o **Menu** para alternar entre:

- **Simulação** — formulários e resultados (escolha Modo 1 ou Modo 2)
- **Balanço Hídrico** — fechamento numérico de massa
- **Comparação MHU 1.1 × 2.0** — mesmos dados nos dois modos
- **Instruções** — passo a passo de uso
- **Descrição das variáveis** — glossário dos termos
- **Validação** — níveis observados vs simulados (NSE/Nash, R², RMSE, MAE)
- **Sugestão de calibração** — faixas de infiltração e Manning (US) e n do canal

## Uso rápido

1. Escolha a formulação (Modo 1 = MHU 1.1 ou Modo 2 = MHU 2.0).
2. Configure intervalo de registro, passo de integração e duração da chuva.
3. Informe parâmetros do canal.
4. Edite a tabela de ACs (incluindo `ACs_montante_ids`, ex.: `1;2`).
5. Edite as US; no Modo 2 a soma das áreas deve fechar com a AC.
6. Edite a série de chuva (o passo `t=0` é só condição inicial).
7. Clique em **Rodar simulação**.
8. Visualize hidrogramas (e detalhe por US no Modo 2) e baixe o Excel.

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

