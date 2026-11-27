# -*- coding: utf-8 -*-
"""Casos 14 (simulações salvas), 17 (estatísticas) e helpers de interface."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tests.helpers import make_ac, run_m1


def test_14_compatibilidade_payload_legado():
    """Payload antigo (sem modo_mhu / com dt_seg apenas) deve carregar sem erro."""
    import app as mhu

    payload = {
        "id": "legado20241101000000",
        "titulo": "Simulação legada",
        "created_at": "2024-11-01T12:00:00",
        "params": {
            "dt_seg": 600,
            "duracao_min": 40,
            "n_ac": 1,
            "exutorio_id": 1,
            "b_canal": 4.0,
            "s_canal": 0.004,
            "n_canal": 0.018,
            "nivel_base": 0.2,
            "usar_horton": False,
            "horton_k_h_inv": 2.5,
            "horton_f0_multiplicador": 1.0,
            "usar_us_para_eq": True,
            # sem intervalo_registro_s, dt_integracao_s, unidade_chuva, modo_mhu, tempo_recessao
        },
        "ac_df": [make_ac()],
        "us_df": [
            {
                "ID_AC": 1,
                "ID_US": 1,
                "Classe_US": "Imp",
                "Area_US_m2": 10000.0,
                "Infiltracao_US_mm_h": 1.0,
                "n_US": 0.015,
            }
        ],
        "chuva_df": [
            {"Passo": 0, "Tempo_s": 0.0, "P_mm_h": 0.0},
            {"Passo": 1, "Tempo_s": 600.0, "P_mm_h": 20.0},
        ],
    }
    # aplicar_payload usa session_state do Streamlit — testamos geração + defaults
    # via leitura dos params como a função faria
    p = payload["params"]
    dt_legado = int(p.get("dt_seg", 600))
    intervalo = int(p.get("intervalo_registro_s", dt_legado))
    dt_int = int(p.get("dt_integracao_s", dt_legado))
    unidade = str(p.get("unidade_chuva", mhu.UNIDADE_CHUVA_INTENSIDADE))
    modo = str(p.get("modo_mhu", mhu.MODO_MHU_1_1))
    assert intervalo == 600
    assert dt_int == 600
    assert unidade == mhu.UNIDADE_CHUVA_INTENSIDADE
    assert modo == mhu.MODO_MHU_1_1

    ac = pd.DataFrame(payload["ac_df"])
    chuva = np.array([0.0, 20.0])
    df_s, df_ac = run_m1(ac, chuva, dt=float(dt_int), intervalo=float(intervalo))
    assert len(df_s) > 1
    assert "Q_ex_m3_s" in df_s.columns


def test_14_gerar_e_reconhecer_payload_atual(tmp_path, monkeypatch):
    import app as mhu

    # Evita escrever no arquivo real do projeto
    fake = tmp_path / "simulacoes_salvas.json"
    monkeypatch.setattr(mhu, "SIM_STORE_PATH", fake)

    ac = pd.DataFrame([make_ac()])
    us = pd.DataFrame(
        [
            {
                "ID_AC": 1,
                "ID_US": 1,
                "Classe_US": "G",
                "Area_US_m2": 10000.0,
                "Infiltracao_US_mm_h": 5.0,
                "n_US": 0.05,
            }
        ]
    )
    chuva = pd.DataFrame({"Passo": [0, 1], "Tempo_s": [0.0, 600.0], "P_mm_h": [0.0, 15.0]})
    # gerar_payload acessa st.session_state — garantir chaves
    if "hora_inicio_evento" not in mhu.st.session_state:
        mhu.st.session_state["hora_inicio_evento"] = "12:00"
    if "hora_fim_evento" not in mhu.st.session_state:
        mhu.st.session_state["hora_fim_evento"] = "12:10"

    payload = mhu.gerar_payload_simulacao(
        titulo="teste",
        dt_seg=60,
        duracao_min=10,
        n_ac=1,
        exutorio_id=1,
        b_canal=4.0,
        s_canal=0.004,
        n_canal=0.018,
        nivel_base=0.0,
        usar_horton=False,
        horton_k_h_inv=2.5,
        horton_f0_multiplicador=1.0,
        usar_us_para_eq=True,
        ac_df=ac,
        us_df=us,
        chuva_df=chuva,
        intervalo_registro_s=600,
        dt_integracao_s=60,
        unidade_chuva=mhu.UNIDADE_CHUVA_INTENSIDADE,
        tempo_recessao_min=0.0,
        modo_mhu=mhu.MODO_MHU_2_0,
    )
    assert payload["params"]["modo_mhu"] == mhu.MODO_MHU_2_0
    assert payload["params"]["intervalo_registro_s"] == 600
    mhu.salvar_simulacoes_salvas({"last_id": payload["id"], "items": [payload]})
    loaded = mhu.carregar_simulacoes_salvas()
    assert loaded["items"][0]["titulo"] == "teste"


def test_17_indicadores_estatisticos():
    import app as mhu

    obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    # Simulação perfeita
    assert abs(mhu.nash_sutcliffe_efficiency(obs, obs) - 1.0) < 1e-12
    assert abs(mhu.r2_pearson(obs, obs) - 1.0) < 1e-12
    assert abs(mhu.rmse(obs, obs)) < 1e-12
    assert abs(mhu.mae(obs, obs)) < 1e-12
    assert abs(mhu.vies_medio(obs, obs)) < 1e-12

    # Caso analítico: sim = obs + 1 → vies=1, MAE=1, RMSE=1
    sim = obs + 1.0
    assert abs(mhu.vies_medio(obs, sim) - 1.0) < 1e-12
    assert abs(mhu.mae(obs, sim) - 1.0) < 1e-12
    assert abs(mhu.rmse(obs, sim) - 1.0) < 1e-12
    # NSE = 1 - n*1^2 / sum((o-mean)^2); mean=3, den=10 → NSE=1-5/10=0.5
    assert abs(mhu.nash_sutcliffe_efficiency(obs, sim) - 0.5) < 1e-12
    # r2: correlação perfeita (deslocamento) → R²=1
    assert abs(mhu.r2_pearson(obs, sim) - 1.0) < 1e-12

    # Poucos pontos → NaN no NSE/R2
    assert np.isnan(mhu.nash_sutcliffe_efficiency(np.array([1.0]), np.array([1.0])))


def test_ui_excel_export_contem_abas():
    import app as mhu

    ac = pd.DataFrame([make_ac()])
    chuva = np.array([0.0, 20.0, 10.0])
    df_s, df_ac = run_m1(ac, chuva, dt=300.0, intervalo=600.0)
    bal = mhu.diagnosticar_balanco_hidrico(
        df_saida=df_s,
        df_ac_detalhe=df_ac,
        ac_df=ac,
        exutorio_id=1,
        dt=300.0,
        tempo_chuva_s=1200.0,
    )
    raw = mhu.montar_excel_resultados(df_s, df_ac, bal)
    assert isinstance(raw, (bytes, bytearray))
    assert len(raw) > 1000
    from openpyxl import load_workbook
    from io import BytesIO

    wb = load_workbook(BytesIO(raw))
    nomes = set(wb.sheetnames)
    assert "Exutorio" in nomes
    assert "Detalhe_AC" in nomes
    assert "Balanco_bacia" in nomes


def test_ui_metricas_precipitacao_mm_e_mmh():
    import app as mhu

    vals_mmh = np.array([0.0, 36.0, 18.0])
    m1 = mhu.metricas_precipitacao(vals_mmh, mhu.UNIDADE_CHUVA_INTENSIDADE, 600.0)
    # 36*(600/3600)+18*(600/3600)=6+3=9 mm
    assert abs(m1["P_acum_mm"] - 9.0) < 1e-9
    assert abs(m1["I_max_mm_h"] - 36.0) < 1e-9

    vals_mm = np.array([0.0, 6.0, 3.0])
    m2 = mhu.metricas_precipitacao(vals_mm, mhu.UNIDADE_CHUVA_ACUMULADA, 600.0)
    assert abs(m2["P_acum_mm"] - 9.0) < 1e-9
    assert abs(m2["I_max_mm_h"] - 36.0) < 1e-9


def test_ui_calibracao_grade_minima():
    import app as mhu

    ac = pd.DataFrame([make_ac(area=20000.0, infil_mmh=8.0, n_eq=0.1)])
    chuva = np.array([0.0, 40.0, 20.0])
    df_s, _ = run_m1(ac, chuva, dt=600.0, intervalo=600.0, usar_horton=True)
    # Observado = simulado (deve achar NSE~1 em algum ponto da grade)
    df_obs = pd.DataFrame({"Tempo_s": df_s["Tempo_s"], "Nivel_obs_m": df_s["Nivel_m"]})
    k_vals = np.array([2.5])
    f0fc = np.array([1.0, 1.5])
    res = mhu.calibrar_horton_em_grade(
        df_obs=df_obs,
        dt_seg=600.0,
        chuva_mmh=chuva,
        ac_df=ac,
        exutorio_id=1,
        b_canal=4.0,
        s_canal=0.004,
        n_canal=0.018,
        nivel_base=0.0,
        k_vals=k_vals,
        f0fc_vals=f0fc,
        intervalo_registro_s=600.0,
    )
    assert not res.empty
    assert "NSE" in res.columns or "nse" in [c.lower() for c in res.columns]
