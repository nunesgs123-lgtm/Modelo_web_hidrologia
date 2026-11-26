# CHANGELOG — Modelo Hidrológico Urbano (MHU)

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento semântico adaptado ao ciclo do MHU (`MAJOR.MINOR`).

## [Unreleased] — MHU 1.1 (em preparação)

### Changed — infiltração por balanço volumétrico

- Substitui `infil = min(chuva, f)` por balanço por AC e passo:
  `V_disp = h·A + p·A·dt + Q_in·dt`, `V_inf = min(V_disp, f·A·dt)`, depois propagação sobre `V_restante`.
- Permite infiltrar lâmina armazenada e vazão de montante mesmo sem precipitação instantânea (recessão).
- Mantém infiltração constante e Horton `f(t)=fc+(f0-fc)·exp(-k·t_úmido)` (`k` em h⁻¹, `t_úmido` em h).
- Garantias: `V_inf ≥ 0`, `V_inf ≤ V_disp`, `f=0` ⇒ sem perdas, sem dupla contagem no Manning, `h ≥ 0`.
- Saídas: `Infiltracao_cap_m_s`, `Infiltracao_real_m_s`, `Volume_infiltrado_m3`, `Volume_infiltrado_acum_m3`.
- Parâmetros equivalentes por AC (ponderação US) **não** alterados nesta etapa.

### Changed — precipitação e discretização temporal

- Entrada de chuva em **intensidade (mm/h)** ou **acumulado por intervalo (mm)**:
  - mm: `p = P / (1000 × intervalo_registro_s)`
  - mm/h: `p = P / 3600000`
- Separação entre **intervalo de registro** da precipitação e **passo de integração** interno (`600, 300, 120, 60, 30, 10, 5` s, divisor do intervalo).
- Intensidade constante dentro de cada intervalo de registro (volume precipitado preservado com subpassos).
- `t = 0` apenas como condição inicial (sem avanço do balanço hídrico nesse instante).
- Registro no fim do intervalo representa a chuva do intervalo anterior.
- Período opcional de **recessão** após a chuva com `P = 0`.
- Interface: precipitação acumulada total, intensidade máxima e duração do evento.
- Compatibilidade: simulações antigas com `P_mm_h` interpretadas explicitamente como mm/h; `dt_seg` legado mapeado para intervalo e integração iguais.
- Glossário, instruções e persistência (`unidade_chuva`, `intervalo_registro_s`, `dt_integracao_s`, `tempo_recessao_min`) atualizados.

### Adicionado (etapa de preparação)

- Diagnóstico arquitetural em `DIAGNOSTICO_ARQUITETURA_MHU.md`.
- Congelamento da baseline **MHU 1.0** em `snapshots/MHU_1.0/`.
- Branch Git `MHU-1.1` para evolução incremental.
- Script auxiliar `preparar_mhu_1_1.ps1` (reexecução local de snapshot/branch, se necessário).

### Restrições de compatibilidade (vigentes)

- Preservar funcionalidades da interface Streamlit.
- Preservar compatibilidade de leitura/escrita com `simulacoes_salvas.json`.
- Não alterar parâmetros físicos das simulações já cadastradas no store.

## [1.0.0] — 2026-11-26

### Congelado

- Cópia integral da versão atual em `snapshots/MHU_1.0/` (`app.py`, `requirements.txt`, `README.md`, `.streamlit/config.toml`).
- Núcleo monolítico em `app.py`: UI Streamlit + persistência + simulação chuva–escoamento–nível + validação + calibração Horton em grade.
- Persistência esperada em `simulacoes_salvas.json` (arquivo pode ainda não existir até o primeiro save).

### Conteúdo funcional da baseline

- Simulação por evento com `Δt` discreto.
- Rede de ACs com conectividade montante→jusante (`ACs_montante_ids`) e ordenação topológica.
- Infiltração constante equivalente ou Horton opcional.
- Armazenamento superficial implícito (Manning em plano inclinado).
- Conversão vazão do exutório → profundidade em canal retangular (Manning).
- Validação (NSE, R², RMSE, MAE, viés) e sugestões tabulares de calibração US/canal.
- Calibração automática de parâmetros Horton (`k`, `f0/fc`) por grade + score NSE/pico.
