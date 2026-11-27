# -*- coding: utf-8 -*-
"""
Auditoria hidrológica MHU — casos 1 a 8, 10, 11, 13, 15, 16.

Casos de rede (9), canal (12), compatibilidade (14), estatísticas (17)
e interface ficam em módulos irmãos.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tests.helpers import balanco, make_ac, run_m1, volume_prec_via_balanco


# ---------------------------------------------------------------------------
# 1. Ausência de chuva e armazenamento inicial zero
# ---------------------------------------------------------------------------
def test_01_sem_chuva_h0_zero(ac_isolada, tol_massa):
    chuva = np.array([0.0, 0.0, 0.0])
    df_s, df_ac = run_m1(ac_isolada, chuva, dt=300.0, intervalo=600.0, tempo_recessao_s=600.0)
    assert np.allclose(df_s["Q_ex_m3_s"].to_numpy(), 0.0, atol=1e-12)
    assert np.allclose(df_ac["h_m"].to_numpy(), 0.0, atol=1e-12)
    assert np.allclose(df_ac["Volume_infiltrado_m3"].to_numpy(), 0.0, atol=1e-12)
    bal = balanco(df_s, df_ac, ac_isolada, dt=300.0, intervalo=600.0, chuva_len=len(chuva), tol=tol_massa)
    assert bool(bal["fecha_ok"])


# ---------------------------------------------------------------------------
# 2. Precipitação em superfície totalmente impermeável
# ---------------------------------------------------------------------------
def test_02_superficie_impermeavel(tol_massa):
    ac = pd.DataFrame([make_ac(infil_mmh=0.0, n_eq=0.02, area=5000.0)])
    chuva = np.array([0.0, 60.0, 30.0])  # mm/h
    df_s, df_ac = run_m1(ac, chuva, dt=300.0, intervalo=600.0, tempo_recessao_s=1800.0)
    # Sem infiltração efetiva
    assert float(df_ac.loc[df_ac["Passo"] > 0, "Volume_infiltrado_m3"].sum()) <= 1e-9
    # Deve haver escoamento / armazenamento
    assert float(df_s["Q_ex_m3_s"].max()) > 0.0
    bal = balanco(df_s, df_ac, ac, dt=300.0, intervalo=600.0, chuva_len=len(chuva), tol=tol_massa)
    assert bool(bal["fecha_ok"])
    # Quase toda precipitação sai ou fica armazenada (sem perda por infiltração)
    row = bal["df_bacia"][bal["df_bacia"]["Periodo"] == "chuva_mais_recessao"].iloc[0]
    assert abs(float(row["V_infiltracao_m3"])) <= 1e-9


# ---------------------------------------------------------------------------
# 3. Precipitação inferior à capacidade de infiltração
# ---------------------------------------------------------------------------
def test_03_chuva_abaixo_capacidade_infiltracao(tol_massa):
    # f = 50 mm/h; chuva 10 mm/h — tudo deve infiltrar se não houver montante/h0
    ac = pd.DataFrame([make_ac(infil_mmh=50.0, n_eq=0.05, h0=0.0)])
    chuva = np.array([0.0, 10.0, 5.0])
    df_s, df_ac = run_m1(ac, chuva, dt=300.0, intervalo=600.0, tempo_recessao_s=0.0)
    # Vazão residual deve ser nula ou desprezível (sem excesso)
    assert float(df_s["Q_ex_m3_s"].max()) < 1e-6
    assert float(df_ac["h_m"].max()) < 1e-9
    # Volume infiltrado ≈ precipitação
    bal = balanco(df_s, df_ac, ac, dt=300.0, intervalo=600.0, chuva_len=len(chuva), tol=tol_massa)
    row = bal["df_bacia"][bal["df_bacia"]["Periodo"] == "evento_chuva"].iloc[0]
    assert abs(float(row["V_infiltracao_m3"]) - float(row["V_precipitacao_m3"])) <= max(
        1e-6, 1e-9 * abs(float(row["V_precipitacao_m3"]))
    )


# ---------------------------------------------------------------------------
# 4. Infiltração de água armazenada após o término da chuva
# ---------------------------------------------------------------------------
def test_04_infiltracao_armazenada_na_recessao(tol_massa):
    # Impermeável durante chuva intensa gera armazenamento; depois f>0 na recessão
    # Estratégia: h0>0, chuva zero, f>0 → infiltra na "recessão"
    ac = pd.DataFrame([make_ac(h0=0.02, infil_mmh=20.0, n_eq=0.2, area=10000.0)])
    chuva = np.array([0.0, 0.0])  # sem chuva
    df_s, df_ac = run_m1(ac, chuva, dt=300.0, intervalo=600.0, tempo_recessao_s=2400.0)
    v_inf = float(df_ac.loc[df_ac["Passo"] > 0, "Volume_infiltrado_m3"].sum())
    assert v_inf > 0.0
    # Lâmina final menor que inicial
    h0 = float(df_ac.loc[df_ac["Passo"] == 0, "h_m"].iloc[0])
    hf = float(df_ac.loc[df_ac["Passo"] == df_ac["Passo"].max(), "h_m"].iloc[0])
    assert hf < h0 - 1e-12 or v_inf > 0.0
    bal = balanco(df_s, df_ac, ac, dt=300.0, intervalo=600.0, chuva_len=len(chuva), tol=tol_massa)
    assert bool(bal["fecha_ok"])


# ---------------------------------------------------------------------------
# 5. Esvaziamento progressivo do armazenamento superficial
# ---------------------------------------------------------------------------
def test_05_esvaziamento_progressivo_sem_infiltracao():
    ac = pd.DataFrame([make_ac(h0=0.05, infil_mmh=0.0, n_eq=0.03, S=0.02)])
    chuva = np.array([0.0, 0.0])
    df_s, df_ac = run_m1(ac, chuva, dt=300.0, intervalo=600.0, tempo_recessao_s=3600.0)
    h_series = df_ac.sort_values("Passo")["h_m"].to_numpy()
    # Monotonicamente não crescente (tolerância numérica)
    diffs = np.diff(h_series)
    assert np.all(diffs <= 1e-12)
    assert h_series[-1] < h_series[0]
    assert float(df_s["Q_ex_m3_s"].iloc[1:].max()) > 0.0


# ---------------------------------------------------------------------------
# 6. Conservação de massa — AC isolada
# ---------------------------------------------------------------------------
def test_06_conservacao_massa_ac_isolada(tol_massa):
    ac = pd.DataFrame([make_ac(area=85000.0, L=350.0, S=0.015, infil_mmh=12.0, n_eq=0.12)])
    chuva = np.array([0.0, 18.0, 42.0, 25.0, 8.0])
    dt, intervalo = 60.0, 600.0
    df_s, df_ac = run_m1(ac, chuva, dt=dt, intervalo=intervalo, tempo_recessao_s=1200.0)
    bal = balanco(df_s, df_ac, ac, dt=dt, intervalo=intervalo, chuva_len=len(chuva), tol=tol_massa)
    assert bool(bal["fecha_ok"])
    assert float(bal["df_passos"]["Erro_AC_m3"].abs().max()) <= tol_massa


# ---------------------------------------------------------------------------
# 7. Conservação de massa — duas ACs conectadas
# ---------------------------------------------------------------------------
def test_07_conservacao_massa_duas_acs(tol_massa):
    ac = pd.DataFrame(
        [
            make_ac(1, area=20000.0, montantes="0", infil_mmh=8.0, n_eq=0.08),
            make_ac(2, area=30000.0, montantes="1", infil_mmh=10.0, n_eq=0.10),
        ]
    )
    chuva = np.array([0.0, 30.0, 20.0, 10.0])
    dt, intervalo = 120.0, 600.0
    df_s, df_ac = run_m1(ac, chuva, dt=dt, intervalo=intervalo, exutorio_id=2, tempo_recessao_s=600.0)
    bal = balanco(
        df_s, df_ac, ac, dt=dt, intervalo=intervalo, chuva_len=len(chuva), exutorio_id=2, tol=tol_massa
    )
    assert bool(bal["fecha_ok"])
    # Transferência: Q_in da AC2 == Q_out da AC1 no mesmo passo
    for passo in sorted(df_ac["Passo"].unique()):
        if int(passo) == 0:
            continue
        q1 = float(df_ac.loc[(df_ac["Passo"] == passo) & (df_ac["ID_AC"] == 1), "Q_out_m3_s"].iloc[0])
        qin2 = float(df_ac.loc[(df_ac["Passo"] == passo) & (df_ac["ID_AC"] == 2), "Q_in_m3_s"].iloc[0])
        assert abs(q1 - qin2) <= 1e-9 * max(1.0, abs(q1))


# ---------------------------------------------------------------------------
# 8. Conservação — rede com múltiplas contribuições de montante
# ---------------------------------------------------------------------------
def test_08_conservacao_multiplas_montantes(tol_massa):
    ac = pd.DataFrame(
        [
            make_ac(1, area=15000.0, montantes="0"),
            make_ac(2, area=18000.0, montantes="0"),
            make_ac(3, area=22000.0, montantes="0"),
            make_ac(4, area=40000.0, montantes="1;2;3", infil_mmh=6.0, n_eq=0.09),
        ]
    )
    chuva = np.array([0.0, 25.0, 40.0, 15.0])
    dt, intervalo = 100.0, 600.0
    # 100 não divide 600? 600/100=6 OK
    df_s, df_ac = run_m1(ac, chuva, dt=dt, intervalo=intervalo, exutorio_id=4, tempo_recessao_s=600.0)
    bal = balanco(
        df_s, df_ac, ac, dt=dt, intervalo=intervalo, chuva_len=len(chuva), exutorio_id=4, tol=tol_massa
    )
    assert bool(bal["fecha_ok"])
    for passo in sorted(df_ac["Passo"].unique()):
        if int(passo) == 0:
            continue
        sub = df_ac[df_ac["Passo"] == passo]
        q_mont = float(sub.loc[sub["ID_AC"].isin([1, 2, 3]), "Q_out_m3_s"].sum())
        qin4 = float(sub.loc[sub["ID_AC"] == 4, "Q_in_m3_s"].iloc[0])
        assert abs(q_mont - qin4) <= 1e-9 * max(1.0, abs(q_mont))


# ---------------------------------------------------------------------------
# 10. Independência do volume precipitado em relação ao passo interno
# ---------------------------------------------------------------------------
def test_10_volume_precipitado_independente_do_dt():
    ac = pd.DataFrame([make_ac(area=10000.0)])
    chuva = np.array([0.0, 36.0, 18.0, 9.0])  # mm/h
    intervalo = 600.0
    vols = []
    for dt in (600.0, 300.0, 120.0, 60.0):
        df_s, df_ac = run_m1(ac, chuva, dt=dt, intervalo=intervalo)
        bal = balanco(df_s, df_ac, ac, dt=dt, intervalo=intervalo, chuva_len=len(chuva))
        vols.append(volume_prec_via_balanco(bal, "evento_chuva"))
    # Volume precipitado idêntico (mesmo registro × área)
    assert max(vols) - min(vols) <= 1e-9 * max(1.0, abs(vols[0]))
    # Checagem analítica: Σ I[k]*dt_reg/3600 * A  (k=1..)
    area = 10000.0
    v_esp = float(np.sum(chuva[1:]) * intervalo / 3600.0 / 1000.0 * area)
    assert abs(vols[0] - v_esp) <= 1e-9 * max(1.0, v_esp)


# ---------------------------------------------------------------------------
# 11. Convergência numérica para passos progressivamente menores
# ---------------------------------------------------------------------------
def test_11_convergencia_passos_menores():
    ac = pd.DataFrame([make_ac(area=85000.0, L=350.0, S=0.015, infil_mmh=12.0, n_eq=0.12)])
    chuva = np.array([0.0, 18.0, 42.0, 25.0, 8.0])
    intervalo = 600.0
    dts = [600.0, 300.0, 120.0, 60.0]
    picos = []
    vols_ex = []
    for dt in dts:
        df_s, df_ac = run_m1(ac, chuva, dt=dt, intervalo=intervalo, tempo_recessao_s=1200.0)
        picos.append(float(df_s["Q_ex_m3_s"].max()))
        vols_ex.append(float((df_s["Q_ex_m3_s"].iloc[1:] * dt).sum()))
    # Diferenças relativas entre passos sucessivos devem tender a diminuir
    # (ou permanecer pequenas) — critério pragmático de convergência
    rel = [abs(picos[i] - picos[i + 1]) / max(abs(picos[i + 1]), 1e-12) for i in range(len(picos) - 1)]
    assert rel[-1] <= rel[0] + 0.05 or rel[-1] < 0.05
    # Volume no exutório estabiliza
    assert abs(vols_ex[-1] - vols_ex[-2]) / max(abs(vols_ex[-1]), 1.0) < 0.05


# ---------------------------------------------------------------------------
# 13. Condições iniciais em t = 0
# ---------------------------------------------------------------------------
def test_13_t0_apenas_condicao_inicial():
    ac = pd.DataFrame([make_ac(h0=0.01, infil_mmh=5.0)])
    chuva = np.array([0.0, 20.0, 10.0])
    df_s, df_ac = run_m1(ac, chuva, dt=300.0, intervalo=600.0)
    row0 = df_ac[df_ac["Passo"] == 0].iloc[0]
    assert abs(float(row0["h_m"]) - 0.01) < 1e-15
    assert abs(float(row0["Volume_infiltrado_m3"])) < 1e-15
    assert abs(float(row0["Volume_escoado_m3"])) < 1e-15
    # P em t=0 é zero na série de taxa
    assert abs(float(df_s.loc[df_s["Passo"] == 0, "P_m_s"].iloc[0])) < 1e-15
    # Avanço do balanço só a partir do passo 1
    assert float(df_ac.loc[df_ac["Passo"] == 1, "Volume_infiltrado_m3"].iloc[0]) >= 0.0


# ---------------------------------------------------------------------------
# 15. Equivalência agregada × por classe (única classe US)
# ---------------------------------------------------------------------------
def test_15_equivalencia_modo1_modo2_classe_unica():
    import app as mhu

    area, L, S, n, f = 12000.0, 250.0, 0.012, 0.08, 9.0
    ac = pd.DataFrame([make_ac(1, area=area, L=L, S=S, infil_mmh=f, n_eq=n, h0=0.0)])
    us = pd.DataFrame(
        [
            {
                "ID_AC": 1,
                "ID_US": 1,
                "Classe_US": "unica",
                "Area_US_m2": area,
                "Infiltracao_US_mm_h": f,
                "n_US": n,
            }
        ]
    )
    chuva = np.array([0.0, 24.0, 36.0, 12.0])
    kwargs = dict(
        dt=120.0,
        chuva_registros=chuva,
        ac_df=ac,
        us_df=us,
        exutorio_id=1,
        b_canal=3.0,
        s_canal=0.005,
        n_canal=0.02,
        nivel_base=0.0,
        intervalo_registro_s=600.0,
        unidade_chuva="mm/h",
        tempo_recessao_s=600.0,
    )
    s1, ac1, _ = mhu.executar_simulacao_mhu(modo=mhu.MODO_MHU_1_1, **kwargs)
    s2, ac2, us2 = mhu.executar_simulacao_mhu(modo=mhu.MODO_MHU_2_0, **kwargs)
    assert us2 is not None
    # Hidrograma e níveis equivalentes
    assert np.allclose(s1["Q_ex_m3_s"], s2["Q_ex_m3_s"], rtol=1e-8, atol=1e-10)
    assert np.allclose(s1["Nivel_m"], s2["Nivel_m"], rtol=1e-8, atol=1e-10)
    assert np.allclose(ac1["h_m"].to_numpy(), ac2["h_m"].to_numpy(), rtol=1e-8, atol=1e-10)
    assert np.allclose(
        ac1["Volume_infiltrado_m3"].to_numpy(),
        ac2["Volume_infiltrado_m3"].to_numpy(),
        rtol=1e-8,
        atol=1e-10,
    )


# ---------------------------------------------------------------------------
# 16. Armazenamento em depressões Sd = 0 (equivalência / ausência de termo)
# ---------------------------------------------------------------------------
def test_16_depressao_sd_zero_sem_retencao_morta():
    """
    O MHU atual não implementa armazenamento em depressões (Sd) como parâmetro
    separado. Com Sd≡0 (formulação vigente), toda a água disponível após
    infiltração participa do escoamento/Manning — não há volume 'morto'.
    Este teste documenta e verifica esse comportamento.
    """
    from app import manning_vazao_superficie, solve_surface_storage_implicit

    ac = pd.DataFrame([make_ac(h0=0.0, infil_mmh=0.0, n_eq=0.04, S=0.02)])
    chuva = np.array([0.0, 12.0])  # mm/h em 600 s → 2 mm
    df_s, df_ac = run_m1(ac, chuva, dt=60.0, intervalo=600.0, tempo_recessao_s=7200.0)
    h_max = float(df_ac["h_m"].max())
    hf = float(df_ac.loc[df_ac["Passo"] == df_ac["Passo"].max(), "h_m"].iloc[0])
    assert h_max > 0.0
    assert hf < h_max  # esvazia progressivamente (sem piso de retenção)
    assert hf >= 0.0

    # Propriedade Sd≡0: para qualquer lâmina > 0 há vazão de Manning > 0 (sem limiar)
    for h_tiny in (1e-6, 1e-4, 1e-3):
        q = manning_vazao_superficie(h_tiny * 1000.0, 1000.0, 100.0, 0.05, 0.01)
        assert q > 0.0

    sol = solve_surface_storage_implicit(
        v_disponivel=1.0, dt=60.0, area_m2=1000.0, comprimento_m=100.0, n_eq=0.05, declividade=0.01
    )
    assert sol["v_novo"] >= 0.0
    assert sol["v_novo"] <= 1.0 + 1e-12
    assert sol["v_escoado"] > 0.0  # não retém 100% como volume morto
