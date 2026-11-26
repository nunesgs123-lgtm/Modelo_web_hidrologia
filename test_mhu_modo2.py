# -*- coding: utf-8 -*-
"""Testes unitários do MHU 2.0 (áreas, montante, agregação Q_i = Σ Q_ij)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from mhu_modo2 import (
    ESTRATEGIA_MONTANTE_AREA,
    distribuir_montante_entre_classes,
    normalizar_areas_us_proporcional,
    verificar_consistencia_areas_us,
)


def test_distribuir_montante_proporcional_area():
    areas = np.array([30.0, 70.0])
    parts = distribuir_montante_entre_classes(10.0, areas, ESTRATEGIA_MONTANTE_AREA)
    assert np.allclose(parts, [3.0, 7.0])
    assert abs(float(parts.sum()) - 10.0) < 1e-12


def test_verificar_areas_inconsistentes_nao_normaliza():
    ac = pd.DataFrame({"ID_AC": [1], "Area_m2": [100.0]})
    us = pd.DataFrame(
        {
            "ID_AC": [1, 1],
            "ID_US": [1, 2],
            "Area_US_m2": [40.0, 50.0],
            "Infiltracao_US_mm_h": [1.0, 10.0],
            "n_US": [0.02, 0.2],
        }
    )
    chk = verificar_consistencia_areas_us(ac, us)
    assert not bool(chk.loc[0, "Consistente"])
    assert abs(float(chk.loc[0, "Erro_abs_m2"]) - (-10.0)) < 1e-9
    assert abs(float(chk.loc[0, "Erro_pct"]) - (-10.0)) < 1e-9
    # US original intacto
    assert float(us["Area_US_m2"].sum()) == 90.0


def test_normalizar_areas_explicito():
    ac = pd.DataFrame({"ID_AC": [1], "Area_m2": [100.0]})
    us = pd.DataFrame(
        {
            "ID_AC": [1, 1],
            "ID_US": [1, 2],
            "Area_US_m2": [40.0, 60.0],
            "Infiltracao_US_mm_h": [1.0, 10.0],
            "n_US": [0.02, 0.2],
        }
    )
    # Já consistente: normalização deve manter soma
    us2 = normalizar_areas_us_proporcional(ac, us)
    assert abs(float(us2["Area_US_m2"].sum()) - 100.0) < 1e-9

    us_bad = us.copy()
    us_bad.loc[:, "Area_US_m2"] = [40.0, 50.0]
    us_n = normalizar_areas_us_proporcional(ac, us_bad)
    assert abs(float(us_n["Area_US_m2"].sum()) - 100.0) < 1e-9
    assert abs(float(us_n.iloc[0]["Area_US_m2"]) - 40.0 * 100.0 / 90.0) < 1e-9


def test_modo2_qi_soma_classes_smoke():
    """Smoke: Q_ex Mode2 finito e df_us presente com mesmas entradas mínimas."""
    import app as mhu

    ac = pd.DataFrame(
        [
            {
                "ID_AC": 1,
                "Area_m2": 10000.0,
                "L_m": 100.0,
                "S_m_m": 0.01,
                "ACs_montante_ids": "0",
                "h0_m": 0.0,
                "Infiltracao_eq_mm_h": 5.0,
                "n_eq": 0.1,
            }
        ]
    )
    us = pd.DataFrame(
        [
            {
                "ID_AC": 1,
                "ID_US": 1,
                "Classe_US": "Imp",
                "Area_US_m2": 6000.0,
                "Infiltracao_US_mm_h": 1.0,
                "n_US": 0.015,
            },
            {
                "ID_AC": 1,
                "ID_US": 2,
                "Classe_US": "Gramado",
                "Area_US_m2": 4000.0,
                "Infiltracao_US_mm_h": 15.0,
                "n_US": 0.20,
            },
        ]
    )
    chuva = np.array([0.0, 30.0, 20.0], dtype=float)
    s2, ac2, us2 = mhu.executar_simulacao_mhu(
        modo=mhu.MODO_MHU_2_0,
        dt=600.0,
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
    )
    assert us2 is not None and not us2.empty
    # Em cada passo, Q_AC == soma Q_US
    for passo in sorted(ac2["Passo"].unique()):
        q_ac = float(ac2.loc[ac2["Passo"] == passo, "Q_out_m3_s"].iloc[0])
        q_us = float(us2.loc[us2["Passo"] == passo, "Q_out_m3_s"].sum())
        assert abs(q_ac - q_us) < 1e-9
    assert float(s2["Q_ex_m3_s"].max()) >= 0.0


if __name__ == "__main__":
    test_distribuir_montante_proporcional_area()
    test_verificar_areas_inconsistentes_nao_normaliza()
    test_normalizar_areas_explicito()
    test_modo2_qi_soma_classes_smoke()
    print("OK test_mhu_modo2")
