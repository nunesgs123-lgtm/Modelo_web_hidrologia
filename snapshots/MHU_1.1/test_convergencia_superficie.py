"""
Testes numericos do Euler implicito volumetrico superficial (MHU 1.1).

Executar:
  python test_convergencia_superficie.py
"""

from __future__ import annotations

import math
import sys

import numpy as np
import pandas as pd

from app import (
    manning_vazao_superficie,
    run_simulation,
    solve_surface_storage_implicit,
    validar_parametros_superficie_ac,
)


def _passo_unitario(v_disp: float, dt: float, area: float, L: float, n: float, S: float) -> dict:
    return solve_surface_storage_implicit(
        v_disponivel=v_disp,
        dt=dt,
        area_m2=area,
        comprimento_m=L,
        n_eq=n,
        declividade=S,
        ac_id=1,
    )


def test_massa_e_limites():
    area, L, n, S = 10000.0, 200.0, 0.05, 0.01
    v_disp = 25.0
    for dt in (600.0, 300.0, 60.0, 10.0, 5.0):
        sol = _passo_unitario(v_disp, dt, area, L, n, S)
        assert sol["v_novo"] >= 0.0
        assert sol["v_escoado"] >= 0.0
        assert sol["v_escoado"] <= v_disp + 1e-15
        assert abs(sol["v_novo"] + sol["v_escoado"] - v_disp) <= 1e-12
        assert abs(sol["q_out"] * dt - sol["v_escoado"]) <= 1e-12
        q_m = manning_vazao_superficie(sol["v_novo"], area, L, n, S)
        res_m = sol["v_novo"] + dt * q_m - v_disp
        assert abs(res_m) <= max(1e-10, 1e-8 * v_disp)
        assert abs(sol["residuo"]) <= max(1e-10, 1e-8 * v_disp)


def test_parametros_invalidos():
    try:
        validar_parametros_superficie_ac(0.0, 100.0, 0.05, 0.01, ac_id=9)
        raise AssertionError("deveria rejeitar Area_m2=0")
    except ValueError:
        pass
    try:
        solve_surface_storage_implicit(1.0, 60.0, 1000.0, 100.0, 0.0, 0.01)
        raise AssertionError("deveria rejeitar n_eq=0")
    except ValueError:
        pass


def test_convergencia_vs_dt():
    """Compara residuos e balanco em uma AC unica para varios dt internos."""
    area, L, n, S = 85000.0, 350.0, 0.12, 0.015
    fc_mmh = 12.0
    intervalo = 600.0
    chuva = np.array([0.0, 18.0, 42.0, 25.0, 8.0])  # mm/h nos fins de intervalo
    ac = pd.DataFrame(
        [
            {
                "ID_AC": 1,
                "Area_m2": area,
                "L_m": L,
                "S_m_m": S,
                "ACs_montante_ids": "0",
                "h0_m": 0.0,
                "Infiltracao_eq_mm_h": fc_mmh,
                "n_eq": n,
            }
        ]
    )

    linhas = []
    for dt in (600, 300, 120, 60, 30, 10, 5):
        df_s, df_ac = run_simulation(
            dt=float(dt),
            chuva_registros=chuva,
            ac_df=ac,
            exutorio_id=1,
            b_canal=4.0,
            s_canal=0.004,
            n_canal=0.018,
            nivel_base=0.2,
            intervalo_registro_s=intervalo,
            unidade_chuva="mm/h",
            tempo_recessao_s=600.0,
            usar_horton=False,
        )
        res_max = float(np.nanmax(np.abs(df_ac["Residuo_implicito_m3"].to_numpy())))
        vol_inf = float(df_ac["Volume_infiltrado_m3"].sum())
        vol_esc = float(df_ac["Volume_escoado_m3"].sum())
        h_max = float(df_ac["h_m"].max())
        q_max = float(df_s["Q_ex_m3_s"].max())
        # Massa: precip + (sem montante) = infil + escoado + armazenamento final
        p_ms = df_s["P_m_s"].to_numpy()
        # Volume precipitado nos intervalos internos t>=1
        v_prec = float(np.sum(p_ms[1:] * area * dt))
        v_arm_final = float(df_ac.loc[df_ac["Passo"] == df_ac["Passo"].max(), "h_m"].iloc[0] * area)
        balanco = v_prec - (vol_inf + vol_esc + v_arm_final)
        linhas.append(
            {
                "dt_s": dt,
                "n_passos": len(df_s),
                "residuo_max_m3": res_max,
                "Q_pico_m3_s": q_max,
                "h_max_m": h_max,
                "erro_massa_m3": balanco,
                "erro_massa_rel": balanco / max(v_prec, 1e-12),
            }
        )
        assert res_max <= 1e-6
        assert abs(balanco) / max(v_prec, 1.0) <= 1e-6

    return pd.DataFrame(linhas)


def main() -> int:
    test_parametros_invalidos()
    test_massa_e_limites()
    df = test_convergencia_vs_dt()
    print("Convergencia numerica (AC unica, chuva padrao, recessao 600 s):")
    print(df.to_string(index=False, float_format=lambda x: f"{x:.6g}"))
    print("\nTodos os testes passaram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
