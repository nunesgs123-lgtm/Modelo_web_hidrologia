# -*- coding: utf-8 -*-
"""Casos 9 (rede) e 12 (inversão Manning do canal)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from tests.helpers import make_ac


def test_09_rejeita_ciclo_na_rede():
    from app import validar_e_preparar_rede_ac

    ac = pd.DataFrame(
        [
            make_ac(1, montantes="3"),
            make_ac(2, montantes="1"),
            make_ac(3, montantes="2"),
        ]
    )
    with pytest.raises(ValueError) as exc:
        validar_e_preparar_rede_ac(ac, 3)
    msg = str(exc.value).lower()
    assert "ciclo" in msg


def test_09_rejeita_duplicacao_bifurcacao():
    from app import validar_e_preparar_rede_ac

    ac = pd.DataFrame(
        [
            make_ac(1, montantes="0"),
            make_ac(2, montantes="1"),
            make_ac(3, montantes="1"),
        ]
    )
    with pytest.raises(ValueError) as exc:
        validar_e_preparar_rede_ac(ac, 3)
    msg = str(exc.value).lower()
    assert "jusante" in msg or "duplic" in msg or "convergente" in msg


def test_09_rede_convergente_ok():
    from app import validar_e_preparar_rede_ac

    ac = pd.DataFrame(
        [
            make_ac(1, montantes="0"),
            make_ac(2, montantes="0"),
            make_ac(3, montantes="1;2"),
        ]
    )
    ac_ord, meta = validar_e_preparar_rede_ac(ac, 3)
    assert meta["exutorio_id"] == 3
    assert meta["downstream_of"][1] == 3
    assert meta["downstream_of"][2] == 3
    assert set(meta["ordem_ids"]) == {1, 2, 3}


def test_12_inversao_manning_canal():
    """Dado Q, resolve y; a vazão de Manning com esse y deve recuperar Q."""
    from app import solve_channel_depth

    b, s, n = 4.0, 0.004, 0.018
    q_vals = np.array([0.0, 0.5, 1.2, 3.5, 8.0])
    y = solve_channel_depth(q_vals, b, s, n, n_iter=20)

    def q_manning(yk: float) -> float:
        if yk <= 0:
            return 0.0
        a = b * yk
        p = b + 2.0 * yk
        rh = a / p
        return (1.0 / n) * a * (rh ** (2.0 / 3.0)) * math.sqrt(s)

    for qi, yi in zip(q_vals, y):
        if qi <= 0:
            assert yi == 0.0
            continue
        q_rec = q_manning(float(yi))
        assert abs(q_rec - qi) / max(qi, 1e-12) < 1e-3
