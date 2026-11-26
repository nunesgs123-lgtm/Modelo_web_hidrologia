# Diagnóstico de arquitetura — MHU 1.0 → preparação MHU 1.1

**Data:** 2026-11-26  
**Escopo:** análise integral de `app.py` (núcleo monolítico Streamlit + física).  
**Estado:** equações **não** modificadas nesta etapa.

---

## 1. Visão geral da arquitetura

O MHU 1.0 concentra **toda** a lógica em um único arquivo `app.py` (~1600 linhas):

| Camada | Responsabilidade | Localização típica |
|--------|------------------|--------------------|
| Configuração / glossário / tabelas de calibração | Constantes de UI e referência | topo do arquivo (`GLOSSARIO_*`, `CALIBRACAO_*`) |
| Persistência | Save/load de simulações | `carregar_*`, `salvar_*`, `gerar_payload_*`, `aplicar_payload_*` |
| Núcleo físico | Chuva → infiltração → h → Q → nível | `run_simulation` + solvers |
| Métricas / calibração | NSE, grade Horton | `nash_*`, `calibrar_horton_em_grade` |
| Interface Streamlit | Menu, editores, gráficos, validação | bloco principal após as `def` |

Fluxo físico por passo de tempo `t`:

1. Precipitação `P_mm_h[t]` → `P_m_s`.
2. Capacidade de infiltração (constante ou Horton) → excesso `i_eff`.
3. Soma de vazões montante `Q_in` (mesma coluna `t`, após ordenação topológica).
4. Balanço de lâmina `h` implícito (Manning plano).
5. `Q_out` da AC; no exutório, `solve_channel_depth` → `Nivel_m`.

---

## 2. Mapa de funções por processo

### 2.1 Precipitação *(atualizado em MHU 1.1 — discretização)*

| Função / trecho | Papel |
|-----------------|--------|
| UI + `chuva_df` (`P_mm_h` ou `P_mm`) | Entrada por **intervalo de registro** |
| `converter_precipitacao_para_taxa_m_s` / `taxa_chuva_no_passo` | Conversão mm ou mm/h → m/s; registro no fim = intervalo anterior |
| `metricas_precipitacao` | Acumulado total, I máx., duração |
| `run_simulation` | Integração com `dt` interno ≠ intervalo de registro; `t=0` só CI; recessão opcional |

**Observação:** chuva uniforme espacialmente (mesmo hietograma para todas as ACs). Intensidade constante dentro de cada intervalo de registro.

### 2.2 Infiltração

| Função / trecho | Papel |
|-----------------|--------|
| `calcular_parametros_equivalentes_por_us` | `Infiltracao_eq_mm_h` e `n_eq` ponderados por área US |
| `run_simulation` (bloco Horton / `infil_cap` / `infil_t_ms`) | Capacidade e infiltração real limitada pela chuva |
| `calibrar_horton_em_grade` | Busca em grade de `k` e `f0/fc` |

**Modo atual:** (a) taxa constante equivalente; (b) Horton opcional com `t_umido` acumulado só quando `P>0`.

### 2.3 Armazenamento superficial

| Função | Papel |
|--------|--------|
| `solve_surface_depth_implicit` | Euler implícito: `dh/dt = input_rate − α h^(5/3)` |
| `run_simulation` (`h[0]=h0`, atualização `h[t,j]`) | Estado de lâmina por AC e passo |

### 2.4 Propagação do escoamento

| Função / trecho | Papel |
|-----------------|--------|
| `run_simulation` (`alpha`, `q_unit_new`, `qout_t = q_unit * w_eq`) | Manning em plano inclinado; saída da AC |
| `solve_surface_depth_implicit` | Acopla armazenamento e saída no mesmo passo implícito |

### 2.5 Conectividade entre áreas de contribuição

| Função | Papel |
|--------|--------|
| `parse_upstream_ids` | Parse de `ACs_montante_ids` (`1;2`) |
| `ordenar_ac_topologicamente` | Kahn / BFS — ordem montante→jusante; erro se houver ciclo |
| `run_simulation` (`qin_t` no mesmo `t`) | Soma `Q_out` das montantes já resolvidas no passo |

### 2.6 Conversão vazão → nível

| Função | Papel |
|--------|--------|
| `solve_channel_depth` | Manning seção retangular; iteração fixa (`n_iter=5`) a partir de chute wide-channel |
| `run_simulation` (pós-processo no exutório) | `Q_ex` → `Nivel_m` → `Cota_abs_m = Nivel + nivel_base` |

### 2.7 Calibração

| Função / trecho | Papel |
|-----------------|--------|
| `CALIBRACAO_USO_SOLO` / `CALIBRACAO_CANAL_MANNING` | Tabelas de referência na UI (não entram no solver) |
| `_montar_grade_parametros` | Vetores de busca |
| `calibrar_horton_em_grade` | Reexecuta `run_simulation` + métricas; ordena por `Score_nse_pico` |
| `nash_sutcliffe_efficiency`, `r2_pearson`, `rmse`, `mae`, `vies_medio` | Indicadores de validação/calibração |

### 2.8 Persistência e UI (não alterar sem necessidade)

| Função | Papel |
|--------|--------|
| `carregar_simulacoes_salvas` / `salvar_simulacoes_salvas` | JSON `simulacoes_salvas.json` |
| `gerar_payload_simulacao` / `aplicar_payload_em_session` | Schema de payload (manter compatível) |
| `validar_campos_obrigatorios` | Pré-checagem antes de rodar |

---

## 3. Pontos de atenção (diagnóstico, sem mudança de equação)

Estes itens orientam **próximas etapas** de consistência física/numérica; ainda **não** foram alterados:

1. **Precipitação espacialmente uniforme** — pode ser insuficiente em bacias com ACs distintas.
2. **Infiltração vs. lâmina** — infiltração limitada à chuva do intervalo (`min(P, f)`), sem depleção explícita da lâmina armazenada após o fim da chuva.
3. **Relógio Horton** — `t_umido` só avança com `P>0`; recuperação entre pulsos não modelada.
4. **Média ponderada de `n_eq`** — média aritmética por área; alternativa hidráulica (ex. harmônica / composição) pode ser mais consistente.
5. **Propagação no mesmo passo** — montante→jusante instantânea dentro de `Δt` (atraso só via armazenamento `h`).
6. **Canal** — seção retangular uniforme, regime normal aproximado, iterações fixas; sem remanso/backwater.
7. **Monólito** — física acoplada à UI dificulta testes unitários e versionamento das equações.

---

## 4. Funções a modificar nas próximas etapas (prioridade sugerida)

Ordem recomendada para a evolução **MHU 1.1** (equações ainda a definir e registrar no CHANGELOG):

| Prioridade | Função | Motivo |
|------------|--------|--------|
| P1 | `run_simulation` | Orquestra precipitação, infiltração, balanço e rede; ponto central de consistência |
| P1 | `solve_surface_depth_implicit` | Núcleo numérico do armazenamento/propagação superficial |
| P1 | `solve_channel_depth` | Consistência hidráulica Q→y e critérios de convergência |
| P2 | bloco Horton dentro de `run_simulation` (ou extrair função dedicada) | Física de infiltração temporal |
| P2 | `calcular_parametros_equivalentes_por_us` | Equivalência hidrológica/hidráulica US→AC |
| P2 | `ordenar_ac_topologicamente` / `parse_upstream_ids` | Robustez da rede (já sólida; revisar só se mudar regra de atraso) |
| P3 | `calibrar_horton_em_grade` | Acompanhar novos parâmetros/métricas sem quebrar UI |
| P3 | métricas (`nash_*`, etc.) | Somente se novos alvos de calibração forem definidos |

**Não priorizar alteração** (salvo bug de interface): payload JSON, menu Streamlit, tabelas `CALIBRACAO_*`, glossário — para preservar UX e simulações salvas.

---

## 5. Garantias desta etapa

- Snapshot **MHU 1.0** em `snapshots/MHU_1.0/`.
- Branch Git **`MHU-1.1`**.
- Equações matemáticas **inalteradas**.
- Interface e schema de `simulacoes_salvas.json` **inalterados**.
- Parâmetros de simulações cadastradas **não tocados** (arquivo ausente na pasta até o primeiro save do usuário).
