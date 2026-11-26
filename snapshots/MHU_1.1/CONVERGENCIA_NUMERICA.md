# Convergência numérica — Euler implícito superficial (MHU 1.1)

## Formulação

Para cada AC e passo interno, após precipitação, montante e infiltração:

\[
V_{\mathrm{novo}} + \Delta t\, Q(V_{\mathrm{novo}}) = V_{\mathrm{disponivel}}
\]

com Manning em plano inclinado:

\[
Q(V)=\frac{W}{n}\left(\frac{V}{A}\right)^{5/3}\sqrt{S},\quad W=\frac{A}{L}
\]

Solver: **bisseção** em \([0, V_{\mathrm{disponivel}}]\) + polimento Newton; tolerâncias absoluta e relativa; resíduo verificado.

A vazão reportada preserva massa no passo: \(Q_{\mathrm{out}}=(V_{\mathrm{disponivel}}-V_{\mathrm{novo}})/\Delta t\).

## Teste automatizado

```bash
python test_convergencia_superficie.py
```

Caso: 1 AC (`A=85000`, `L=350`, `n=0.12`, `S=0.015`, `f_c=12 mm/h`), chuva `[0,18,42,25,8]` mm/h a cada 600 s, recessão 600 s.

### Resultados (executados em 2026-11-26)

| dt (s) | passos | |resíduo| máx (m³) | Q pico (m³/s) | h máx (m) | erro massa relativo |
|--------|--------|------------------|---------------|-----------|---------------------|
| 600 | 6 | ~4.4e-08 | 0.0688 | 0.00735 | ~1e-16 |
| 300 | 11 | ~2.9e-08 | 0.0708 | 0.00747 | ~0 |
| 120 | 26 | ~5.4e-08 | 0.0719 | 0.00754 | ~0 |
| 60 | 51 | ~5.9e-08 | 0.0723 | 0.00757 | ~0 |
| 30 | 101 | ~5.8e-08 | 0.0725 | 0.00758 | ~0 |
| 10 | 301 | ~6.2e-08 | 0.0726 | 0.00758 | ~1e-15 |
| 5 | 601 | ~6.1e-08 | 0.0726 | 0.00759 | ~7e-15 |

Interpretação: o resíduo do residual implícito permanece ~1e-8 m³; o erro de massa do balanço global da AC é numérico (~1e-15 relativo). O pico de vazão estabiliza ao refinar `dt` (diferença < 1% entre 60 s e 5 s).

## Garantias verificadas nos testes unitários

- \(V_{\mathrm{novo}}\ge 0\), \(V_{\mathrm{escoado}}\ge 0\), \(V_{\mathrm{escoado}}\le V_{\mathrm{disponivel}}\)
- \(V_{\mathrm{novo}}+V_{\mathrm{escoado}}=V_{\mathrm{disponivel}}\)
- \(Q_{\mathrm{out}}\cdot\Delta t=V_{\mathrm{escoado}}\)
- Parâmetros `Area_m2`, `L_m`, `n_eq`, `S_m_m` inválidos → `ValueError` (sem clamp silencioso)
