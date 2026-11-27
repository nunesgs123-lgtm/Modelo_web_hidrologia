# -*- coding: utf-8 -*-
"""Verificação básica da interface Streamlit via AppTest."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def app_test():
    try:
        from streamlit.testing.v1 import AppTest
    except ImportError:
        pytest.skip("streamlit.testing.v1.AppTest indisponível")
    at = AppTest.from_file("app.py", default_timeout=45)
    at.run()
    return at


def test_streamlit_carrega_sem_excecao(app_test):
    assert not app_test.exception


def test_streamlit_menu_navegacao(app_test):
    assert len(app_test.sidebar.radio) >= 1
    radio = app_test.sidebar.radio[0]
    opcoes = list(radio.options)
    # Labels com ícones — verificar substrings dos nomes de página
    joined = " | ".join(opcoes)
    assert "Visão geral" in joined
    assert "Nova simulação" in joined
    assert "Balanço hídrico" in joined
    assert "Validação" in joined
    assert "Instruções" in joined
    assert "Metodologia" in joined

    # Navega para Instruções
    alvo = next(o for o in opcoes if "Instruções" in o)
    radio.set_value(alvo)
    app_test.run()
    assert not app_test.exception


def test_streamlit_pagina_simulacao_tem_botao_rodar(app_test):
    radio = app_test.sidebar.radio[0]
    opcoes = list(radio.options)
    alvo = next(o for o in opcoes if "Nova simulação" in o)
    radio.set_value(alvo)
    app_test.run()
    assert not app_test.exception
    labels = [b.label for b in app_test.button]
    assert any("Rodar simulação" in (lab or "") for lab in labels)
