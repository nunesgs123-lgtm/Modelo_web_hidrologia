# Metodologia do Modelo Hidrológico Urbano (MHU)

Documento de referência da implementação atual (`app.py` + `mhu_modo2.py`), alinhado à suíte de testes em `tests/`.

---

## 1. Equações matemáticas implementadas

### 1.1 Precipitação

Registro no fim do intervalo \(k\cdot\Delta t_r\) representa a chuva ocorrida em \(((k-1)\Delta t_r,\,k\Delta t_r]\). Em \(t=0\) não há avanço do balanço.

- Intensidade (mm/h): \(p = P/(3{,}600{,}000)\) 〔m/s〕
- Acumulado no intervalo (mm): \(p = P/(1000\cdot\Delta t_r)\) 〔m/s〕

A taxa \(p\) é constante dentro de cada intervalo de registro, mesmo com passo interno \(\Delta t\le\Delta t_r\).

### 1.2 Infiltração volumétrica

Para cada unidade hidrológica (AC no Modo 1; classe US no Modo 2), no passo que termina em \(t\):

\[
V_{\mathrm{bruto}} = h_{\mathrm{ant}}A + p\,A\,\Delta t + Q_{\mathrm{in}}\,\Delta t
\]

\[
V_{\mathrm{inf}} = \min\!\bigl(V_{\mathrm{bruto}},\, f\,A\,\Delta t\bigr),\qquad
V_{\mathrm{disp}} = V_{\mathrm{bruto}} - V_{\mathrm{inf}}
\]

Capacidade \(f\):

- Constante: \(f = f_c\) (convertida de mm/h).
- Horton: \(f(t)=f_c+(f_0-f_c)\,e^{-k\,t_{\mathrm{úmido}}}\), com \(k\) em h⁻¹ e \(t_{\mathrm{úmido}}\) em h; \(f_0=f_c\cdot(f_0/f_c)\).

### 1.3 Escoamento superficial (Manning em plano inclinado)

\[
W=\frac{A}{L},\qquad h=\frac{V}{A},\qquad
Q=\frac{W}{n}\,h^{5/3}\,\sqrt{S}
\]

### 1.4 Euler implícito conservativo

\[
V_{\mathrm{novo}} + \Delta t\cdot Q(V_{\mathrm{novo}}) = V_{\mathrm{disp}}
\]

Solução por bisseção em \([0,V_{\mathrm{disp}}]\) + polimento Newton. Vazão reportada:

\[
Q_{\mathrm{out}}=\frac{V_{\mathrm{disp}}-V_{\mathrm{novo}}}{\Delta t}
\]

### 1.5 Modo 1 (MHU 1.1) — parâmetros equivalentes

\[
f_{\mathrm{eq}}=\frac{\sum_j A_j f_j}{A},\qquad
n_{\mathrm{eq}}=\frac{\sum_j A_j n_j}{A}
\]

Um armazenamento \(V\) e uma vazão \(Q\) por AC.

### 1.6 Modo 2 (MHU 2.0) — por classe US

\[
W_{ij}=\frac{A_{ij}}{L_i},\quad
h_{ij}=\frac{V_{ij}}{A_{ij}},\quad
Q_{ij}=\frac{W_{ij}}{n_{ij}}\,h_{ij}^{5/3}\,\sqrt{S_i},\quad
Q_i=\sum_j Q_{ij}
\]

Infiltração da AC = soma dos volumes infiltrados nas classes. **Não** se usa média aritmética de Manning.

Distribuição experimental de montante (mistura homogênea):

\[
Q_{\mathrm{in},ij}=Q_{\mathrm{in},i}\,\frac{A_{ij}}{\sum_k A_{ik}}
\]

### 1.7 Rede de ACs

Rede **convergente**: cada AC (exceto o exutório) tem um único destino a jusante. Ordenação topológica montante→jusante; no mesmo passo interno, \(Q_{\mathrm{in}}\) usa \(Q_{\mathrm{out}}\) já calculado dos montantes (aproximação de reservatórios conectados).

### 1.8 Canal retangular (inversão de Manning)

\[
Q=\frac{1}{n}\,A\,R_h^{2/3}\,\sqrt{S},\quad A=B\,y,\quad R_h=\frac{By}{B+2y}
\]

A profundidade \(y\) é obtida por iteração de ponto fixo a partir de \(Q\).

### 1.9 Balanço hídrico (diagnóstico)

\[
\varepsilon_{\mathrm{AC}}=V_{\mathrm{ini}}+V_{\mathrm{prec}}+V_{\mathrm{mont}}-V_{\mathrm{inf}}-V_{\mathrm{saída}}-V_{\mathrm{fin}}
\]

\[
\varepsilon_{\mathrm{bacia}}=V_{\mathrm{ini}}+V_{\mathrm{prec}}-V_{\mathrm{inf}}-V_{\mathrm{exutório}}-V_{\mathrm{fin}}
\]

### 1.10 Indicadores estatísticos (validação)

\[
\mathrm{NSE}=1-\frac{\sum(O-S)^2}{\sum(O-\bar O)^2},\quad
R^2=r_{\mathrm{Pearson}}^2,\quad
\mathrm{RMSE}=\sqrt{\overline{(O-S)^2}},\quad
\mathrm{MAE}=\overline{|O-S|},\quad
\mathrm{Viés}=\overline{S-O}
\]

---

## 2. Variáveis e unidades

| Símbolo / campo | Unidade | Significado |
|---|---|---|
| \(A\), `Area_m2` | m² | Área da AC (ou classe US) |
| \(L\), `L_m` | m | Comprimento característico |
| \(S\), `S_m_m` | m/m | Declividade da superfície |
| \(n\), `n_eq` / `n_US` | – | Manning superficial |
| \(f\), `Infiltracao_*_mm_h` | mm/h | Capacidade de infiltração |
| \(h\), `h_m` / `h0_m` | m | Lâmina superficial (inicial em t=0) |
| \(V\) | m³ | Armazenamento superficial |
| \(Q\), `Q_out_m3_s` | m³/s | Vazão |
| \(p\), `P_m_s` | m/s | Taxa de precipitação |
| `P_mm_h` / `P_mm` | mm/h ou mm | Registro de chuva |
| \(\Delta t\), `dt` | s | Passo de integração |
| \(\Delta t_r\) | s | Intervalo de registro da chuva |
| \(B\), `B_canal` | m | Largura do canal |
| \(y\), `Nivel_m` | m | Profundidade no canal |
| \(k\) | h⁻¹ | Constante de decaimento Horton |
| \(f_0/f_c\) | – | Multiplicador Horton |

Glossário completo também na interface (aba **Descrição das variáveis**).

---

## 3. Hipóteses físicas

1. Evento único de chuva–vazão (não contínuo de longo prazo).
2. Lâmina superficial uniforme na unidade hidrológica (AC ou classe).
3. Escoamento em plano inclinado com Manning; sem hidráulica explícita de canais de ligação entre ACs.
4. Transferência montante→jusante no **mesmo** passo interno (aproximação de reservatórios conectados).
5. Rede topologicamente convergente (sem bifurcação da mesma vazão).
6. Infiltração limitada apenas pela capacidade \(f\) e pela água disponível (sem redistribuição vertical de solo).
7. Modo 2: mistura homogênea da vazão de montante entre classes (hipótese experimental).
8. Canal de exutório: seção retangular uniforme; nível obtido por inversão de Manning (regime permanente uniforme por passo).
9. **Não** há armazenamento em depressões \(S_d\) como parâmetro separado (\(S_d\equiv 0\)).

---

## 4. Método de solução numérica

1. Validar rede e ordenar ACs.
2. Em \(t=0\): apenas condições iniciais (\(h_0\), \(Q\) de Manning correspondente); \(P=0\) no balanço.
3. Para cada passo \(t=1..N\):
   - Obter \(p\) do intervalo de registro correspondente.
   - Para cada AC na ordem montante→jusante (Modo 1) ou cada classe (Modo 2):
     - Somar \(Q_{\mathrm{in}}\) dos montantes já resolvidos no passo \(t\).
     - Calcular \(f\) (constante/Horton).
     - Balanço volumétrico até infiltração.
     - Resolver Euler implícito (bisseção + Newton).
   - Verificar \(\sum Q_{\mathrm{in}}=\sum Q_{\mathrm{out}}\) (ACs com destino).
4. Converter \(Q_{\mathrm{ex}}\) → nível no canal.

Tolerâncias típicas do solver superficial: `tol_abs≈1e-12`, `tol_rel≈1e-10`. Tolerância de fechamento do balanço diagnóstico: padrão `1e-6` m³ (critério **numérico**, não validação física).

---

## 5. Sequência dos cálculos (resumo operacional)

```
Entrada (AC, US, chuva, canal, Δt, Δt_r, modo)
  → validação de rede / áreas (Modo 2)
  → parâmetros equivalentes (somente Modo 1, se solicitado)
  → laço temporal (t=0 CI; t≥1 balanço)
  → hidrograma Q_ex e nível
  → diagnóstico de balanço / Excel / validação / calibração Horton
```

---

## 6. Diferenças entre MHU 1.0, 1.1 e 2.0

| Aspecto | MHU 1.0 | MHU 1.1 | MHU 2.0 |
|---|---|---|---|
| Snapshot | `snapshots/MHU_1.0/` | `snapshots/MHU_1.1/` | código atual + Modo 2 |
| Chuva | Foco em mm/h / Δt único | mm e mm/h; Δt ≠ Δt_r; recessão; t=0 CI | Idem 1.1 |
| Infiltração | Forma anterior | Volumétrica (lâmina+chuva+montante) | Idem, por classe no Modo 2 |
| Superfície | Implícito legado | Euler volumétrico + bisseção | Idem por classe |
| Rede | Básica | Convergente validada + grafo | Idem |
| Balanço | Limitado | Aba de diagnóstico | Idem |
| US | Equivalentes por AC | Equivalentes (Modo 1) | Processamento individual (Modo 2) |
| Concepção | Baseline | Refinamento numérico/diagnóstico | **Mudança matemática** no Modo 2 |

O Modo 2 **não** é correção de bug do Modo 1: é formulação distinta (ver `MHU_2.0_CONCEPCAO.md`).

---

## 7. Limitações hidrológicas e hidráulicas

1. Sem modelagem de solo multicamada, evapotranspiração ou fluxo de base.
2. Sem armazenamento em depressões \(S_d\) explícito.
3. Sem hidráulica de canais/galerias entre ACs (só transferência de vazão).
4. Rede restrita a topologia convergente (sem divisão de vazão).
5. Canal: Manning uniforme por passo; sem remanso dinâmico / Saint-Venant.
6. Mistura homogênea montante→classes (Modo 2) é hipótese experimental.
7. Calibração automática atual limita-se à grade Horton (\(k\), \(f_0/f_c\)).
8. Equivalência Modo 1 ↔ Modo 2 só é esperada com **uma** classe US idêntica à AC; com múltiplas classes os resultados **divergem por concepção**.

---

## 8. Resultados dos testes (suíte pytest)

Comando: `pytest` (ou `python -m pytest tests`).

**26 testes aprovados** (última execução da auditoria), cobrindo no mínimo:

| # | Caso | Teste |
|---|---|---|
| 1 | Sem chuva, h0=0 | `test_01_sem_chuva_h0_zero` |
| 2 | Superfície impermeável | `test_02_superficie_impermeavel` |
| 3 | P < f | `test_03_chuva_abaixo_capacidade_infiltracao` |
| 4 | Infiltração na recessão | `test_04_infiltracao_armazenada_na_recessao` |
| 5 | Esvaziamento progressivo | `test_05_esvaziamento_progressivo_sem_infiltracao` |
| 6 | Massa — AC isolada | `test_06_conservacao_massa_ac_isolada` |
| 7 | Massa — 2 ACs | `test_07_conservacao_massa_duas_acs` |
| 8 | Massa — multi-montante | `test_08_conservacao_multiplas_montantes` |
| 9 | Ciclos / duplicação | `test_09_rejeita_*` |
| 10 | Volume P vs Δt | `test_10_volume_precipitado_independente_do_dt` |
| 11 | Convergência Δt | `test_11_convergencia_passos_menores` |
| 12 | Inversão Manning canal | `test_12_inversao_manning_canal` |
| 13 | t=0 CI | `test_13_t0_apenas_condicao_inicial` |
| 14 | Simulações salvas | `test_14_*` |
| 15 | Modo1 ≡ Modo2 (1 classe) | `test_15_equivalencia_modo1_modo2_classe_unica` |
| 16 | Sd≡0 | `test_16_depressao_sd_zero_sem_retencao_morta` |
| 17 | NSE/R²/RMSE/MAE/Viés | `test_17_indicadores_estatisticos` |

Extras: Excel, métricas de chuva, calibração Horton mínima, AppTest Streamlit (menu/navegação/botão).

Scripts legados na raiz (`test_convergencia_superficie.py`, `test_rede_conectividade.py`, `test_mhu_modo2.py`) permanecem executáveis isoladamente.

---

## 9. Orientações para calibração e validação

1. Use a aba **Sugestão de calibração** apenas como ponto de partida (faixas de \(f\) e \(n\)).
2. Preferir ajustar \(f\) e \(n\) por classe US (Modo 2) ou equivalentes (Modo 1) com dados locais.
3. Aba **Validação**: comparar nível observado vs simulado (NSE, R², RMSE, MAE, viés). NSE próximo de 1 não prova universalidade do modelo.
4. Calibração automática Horton: grade em \(k\) e \(f_0/f_c\); ranqueia por `Score_nse_pico`. Não altere equações só para melhorar o score.
5. Verifique o **Balanço Hídrico** (fechamento numérico) antes de interpretar erros físicos.
6. No Modo 2, confirme \(\sum A_{ij}=A_i\) (ou autorize normalização explicitamente).
7. Compare Modo 1 × Modo 2 com os **mesmos** dados na aba de comparação — diferenças são esperadas com múltiplas classes.

---

## 10. Referências internas

- `MHU_2.0_CONCEPCAO.md` — mudança conceitual do Modo 2
- `CONVERGENCIA_NUMERICA.md` — solver implícito
- `DIAGNOSTICO_ARQUITETURA_MHU.md` — arquitetura
- `CHANGELOG.md` — histórico de versões
- Snapshots: `snapshots/MHU_1.0/`, `snapshots/MHU_1.1/`
