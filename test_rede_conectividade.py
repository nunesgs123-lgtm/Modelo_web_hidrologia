"""Testes da rede convergente de ACs (MHU 1.1)."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from app import run_simulation, validar_e_preparar_rede_ac


def _ac_row(ac_id: int, montantes: str, area: float = 1.0e4) -> dict:
    return {
        "ID_AC": ac_id,
        "Area_m2": area,
        "L_m": 200.0,
        "S_m_m": 0.01,
        "ACs_montante_ids": montantes,
        "h0_m": 0.0,
        "Infiltracao_eq_mm_h": 5.0,
        "n_eq": 0.05,
    }


def test_rede_14_acs_convergente():
    """14 ACs: 1..13 → 14 (exutorio); todas contribuem sem duplicacao."""
    rows = [_ac_row(i, "0") for i in range(1, 14)]
    rows.append(_ac_row(14, ";".join(str(i) for i in range(1, 14)), area=2.0e4))
    ac = pd.DataFrame(rows)
    ac_ord, meta = validar_e_preparar_rede_ac(ac, 14)
    assert meta["n_ac"] == 14
    assert meta["todas_contribuem"] is True
    assert meta["exutorio_id"] == 14
    assert meta["downstream_of"][14] is None
    for i in range(1, 14):
        assert meta["downstream_of"][i] == 14
    assert set(meta["ordem_ids"]) == set(range(1, 15))
    assert ac_ord.iloc[-1]["ID_AC"] == 14

    chuva = np.array([0.0, 20.0, 10.0])
    df_s, df_ac = run_simulation(
        dt=300.0,
        chuva_registros=chuva,
        ac_df=ac,
        exutorio_id=14,
        b_canal=4.0,
        s_canal=0.004,
        n_canal=0.018,
        nivel_base=0.0,
        intervalo_registro_s=600.0,
        unidade_chuva="mm/h",
        tempo_recessao_s=0.0,
    )
    assert len(df_s) > 1
    # Em cada passo t>=1, soma Q_in = soma Q_out das 13 ACs de montante
    for t in df_ac["Passo"].unique():
        if int(t) == 0:
            continue
        sub = df_ac[df_ac["Passo"] == t]
        qin = float(sub["Q_in_m3_s"].sum())
        qout_m = float(sub.loc[sub["ID_AC"] != 14, "Q_out_m3_s"].sum())
        assert abs(qin - qout_m) <= 1e-9 * max(1.0, abs(qout_m))


def test_bifurcacao_rejeitada():
    """AC1 nao pode alimentar AC2 e AC3 ao mesmo tempo."""
    ac = pd.DataFrame(
        [
            _ac_row(1, "0"),
            _ac_row(2, "1"),
            _ac_row(3, "1;2"),
        ]
    )
    try:
        validar_e_preparar_rede_ac(ac, 3)
        raise AssertionError("deveria rejeitar bifurcacao da AC1")
    except ValueError as exc:
        msg = str(exc)
        assert "1" in msg
        assert "destino" in msg.lower() or "Duplicacao" in msg or "jusante" in msg.lower()


def test_exutorio_invalido_sem_fallback():
    ac = pd.DataFrame([_ac_row(1, "0"), _ac_row(2, "1")])
    try:
        validar_e_preparar_rede_ac(ac, 99)
        raise AssertionError("deveria rejeitar exutorio 99")
    except ValueError as exc:
        assert "99" in str(exc)
        assert "substituto" in str(exc).lower() or "nao existe" in str(exc).lower()


def main() -> int:
    test_exutorio_invalido_sem_fallback()
    test_bifurcacao_rejeitada()
    test_rede_14_acs_convergente()
    print("test_rede_conectividade: OK (inclui 14 ACs -> exutorio sem duplicacao).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
