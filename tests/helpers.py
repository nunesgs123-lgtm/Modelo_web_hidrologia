# -*- coding: utf-8 -*-
"""Utilitários para testes do MHU."""

from __future__ import annotations

import numpy as np
import pandas as pd

def make_ac(
    ac_id: int = 1,
    area: float = 10000.0,
    L: float = 200.0,
    S: float = 0.01,
    montantes: str = "0",
    h0: float = 0.0,
    infil_mmh: float = 5.0,
    n_eq: float = 0.05,
) -> dict:
    return {
        "ID_AC": ac_id,
        "Area_m2": area,
        "L_m": L,
        "S_m_m": S,
        "ACs_montante_ids": montantes,
        "h0_m": h0,
        "Infiltracao_eq_mm_h": infil_mmh,
        "n_eq": n_eq,
    }


def run_m1(
    ac_df: pd.DataFrame,
    chuva: np.ndarray,
    *,
    dt: float = 300.0,
    intervalo: float = 600.0,
    exutorio_id: int | None = None,
    tempo_recessao_s: float = 0.0,
    usar_horton: bool = False,
    horton_k_h_inv: float = 2.5,
    horton_f0_multiplicador: float = 1.0,
    unidade: str = "mm/h",
    **canal,
):
    import app as mhu

    canal_kw = dict(b_canal=4.0, s_canal=0.004, n_canal=0.018, nivel_base=0.0)
    canal_kw.update(canal)
    if exutorio_id is None:
        exutorio_id = int(ac_df["ID_AC"].max())
    return mhu.run_simulation(
        dt=dt,
        chuva_registros=chuva,
        ac_df=ac_df,
        exutorio_id=int(exutorio_id),
        intervalo_registro_s=intervalo,
        unidade_chuva=unidade,
        tempo_recessao_s=tempo_recessao_s,
        usar_horton=usar_horton,
        horton_k_h_inv=horton_k_h_inv,
        horton_f0_multiplicador=horton_f0_multiplicador,
        **canal_kw,
    )


def balanco(
    df_s,
    df_ac,
    ac_df,
    *,
    dt: float,
    intervalo: float,
    chuva_len: int,
    exutorio_id: int | None = None,
    tol: float = 1e-6,
):
    import app as mhu

    if exutorio_id is None:
        exutorio_id = int(ac_df["ID_AC"].max())
    tempo_chuva_s = max(chuva_len - 1, 0) * float(intervalo)
    return mhu.diagnosticar_balanco_hidrico(
        df_saida=df_s,
        df_ac_detalhe=df_ac,
        ac_df=ac_df,
        exutorio_id=int(exutorio_id),
        dt=float(dt),
        tempo_chuva_s=tempo_chuva_s,
        tol_fechamento_m3=tol,
    )


def volume_precipitado_m3(df_ac: pd.DataFrame, ac_df: pd.DataFrame, dt: float) -> float:
    """Soma V_prec = P_m_s * A * dt a partir do detalhe (via balanço reconstrói)."""
    # Usa Volume a partir de P no detalhe indiretamente: integrar chuva × área
    areas = {int(r["ID_AC"]): float(r["Area_m2"]) for _, r in ac_df.iterrows()}
    # Prefere colunas do diagnóstico se disponíveis; senão estima por h e volumes
    return float("nan")  # preenchido pelos testes via diagnosticar


def volume_prec_via_balanco(bal: dict, periodo: str = "chuva_mais_recessao") -> float:
    row = bal["df_bacia"][bal["df_bacia"]["Periodo"] == periodo].iloc[0]
    return float(row["V_precipitacao_m3"])
