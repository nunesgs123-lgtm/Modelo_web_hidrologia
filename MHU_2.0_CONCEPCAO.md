# MHU 2.0 — Mudança de concepção matemática

**Importante:** o processamento hidrológico **por classe de uso do solo** no MHU 2.0
representa uma **mudança na concepção matemática do modelo**, e **não** apenas uma
correção de programação do MHU 1.1.

A baseline **MHU 1.1** permanece integralmente preservada (snapshot em
`snapshots/MHU_1.1/` e **Modo 1** na interface).

---

## Modo 1 — Parâmetros equivalentes por AC (MHU 1.1)

Para cada área de contribuição \(i\), os parâmetros de infiltração e Manning são
agregados a partir das classes US por **média ponderada pela área**:

\[
f_{\mathrm{eq},i} = \frac{\sum_j A_{ij}\, f_{ij}}{A_i},\qquad
n_{\mathrm{eq},i} = \frac{\sum_j A_{ij}\, n_{ij}}{A_i}
\]

Há **um** armazenamento superficial \(V_i\), uma lâmina \(h_i = V_i/A_i\) e uma
vazão \(Q_i\) por AC, com Manning:

\[
W_i = \frac{A_i}{L_i},\qquad
Q_i = \frac{W_i}{n_{\mathrm{eq},i}}\, h_i^{5/3}\,\sqrt{S_i}
\]

---

## Modo 2 — Processamento individual por classe (MHU 2.0)

Cada classe \(j\) da AC \(i\) possui:

- área \(A_{ij}\);
- Manning \(n_{ij}\);
- capacidade de infiltração \(f_{ij}\) (constante ou Horton próprio/derivado);
- armazenamento \(V_{ij}\), lâmina \(h_{ij} = V_{ij}/A_{ij}\);
- vazão de saída \(Q_{ij}\).

Formulação:

\[
W_{ij} = \frac{A_{ij}}{L_i},\qquad
h_{ij} = \frac{V_{ij}}{A_{ij}},\qquad
Q_{ij} = \frac{W_{ij}}{n_{ij}}\, h_{ij}^{5/3}\,\sqrt{S_i}
\]

\[
Q_i = \sum_j Q_{ij}
\]

A infiltração total da AC é o **somatório dos volumes efetivamente infiltrados**
em cada classe. **Não** se calcula média aritmética de Manning no Modo 2.

### Consistência de áreas

Deve-se verificar \(\sum_j A_{ij} = A_i\). Diferenças são apresentadas em erro
absoluto (m²) e percentual. A normalização proporcional **só** ocorre com
**autorização explícita** do usuário — nunca silenciosamente.

### Contribuição de montante (hipótese experimental)

A vazão recebida de montante \(Q_{\mathrm{in},i}\) é, nesta versão experimental,
distribuída entre classes **proporcionalmente à área** (mistura homogênea):

\[
Q_{\mathrm{in},ij} = Q_{\mathrm{in},i}\,\frac{A_{ij}}{\sum_k A_{ik}}
\]

O código (`mhu_modo2.distribuir_montante_entre_classes` e o registro
`ESTRATEGIAS_DISTRIBUICAO_MONTANTE`) está estruturado para permitir outras
estratégias no futuro.

---

## O que é preservado

- Conservação de massa (balanço volumétrico por classe/AC).
- Método de Euler implícito na superfície (`V + dt·Q(V) = V_disp`, bisseção).
- Rede convergente de ACs, chuva (mm/mm·h), recessão, Horton opcional,
  balanço hídrico, validação e demais funcionalidades do MHU 1.1.

## Comparação

A aba **Comparação MHU 1.1 × 2.0** executa ambos os modos com os **mesmos dados
de entrada** e resume diferenças de pico, volume no exutório e infiltração.
