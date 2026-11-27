# -*- coding: utf-8 -*-
"""Fixtures compartilhadas da suíte de auditoria do MHU."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


from tests.helpers import make_ac


@pytest.fixture
def canal_padrao():
    return dict(b_canal=4.0, s_canal=0.004, n_canal=0.018, nivel_base=0.0)


@pytest.fixture
def ac_isolada():
    return pd.DataFrame([make_ac()])


@pytest.fixture
def chuva_simples():
    """t=0 CI; depois 2 intervalos com intensidade mm/h."""
    return np.array([0.0, 36.0, 18.0], dtype=float)


@pytest.fixture
def tol_massa():
    return 1e-6
