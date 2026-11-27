# -*- coding: utf-8 -*-
"""Componentes visuais reutilizáveis do MHU (sem lógica hidrológica)."""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from plot_theme import (
    ALERT,
    BORDER,
    HYDRO,
    LIGHT,
    PETROL,
    TEAL,
    apply_mhu_layout,
    config_export,
)

ASSETS = Path(__file__).parent / "assets"
LOGO_SVG = ASSETS / "logo.svg"
STYLES_CSS = ASSETS / "styles.css"

MHU_VERSION = "MHU 2.0 experimental · núcleo 1.1 preservado"

# Navegação institucional
NAV_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "MODELAGEM",
        [
            ("Visão geral", "🏠"),
            ("Nova simulação", "💧"),
            ("Resultados", "📈"),
            ("Simulações salvas", "💾"),
            ("Balanço hídrico", "⚖️"),
            ("Comparação MHU 1.1 × 2.0", "🔬"),
        ],
    ),
    (
        "ANÁLISE CIENTÍFICA",
        [
            ("Validação", "✅"),
            ("Calibração", "🎯"),
            ("Diagnóstico numérico", "🧮"),
        ],
    ),
    (
        "DOCUMENTAÇÃO",
        [
            ("Metodologia", "📘"),
            ("Instruções", "🧾"),
            ("Glossário de variáveis", "🔤"),
        ],
    ),
]

ALL_PAGES = [p for _, items in NAV_GROUPS for p, _ in items]
PAGE_ICONS = {p: ic for _, items in NAV_GROUPS for p, ic in items}


def inject_mhu_styles() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8") if STYLES_CSS.exists() else ""
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def logo_data_uri() -> str:
    if not LOGO_SVG.exists():
        return ""
    # Inline SVG via HTML img is fine for local assets using markdown
    return LOGO_SVG.read_text(encoding="utf-8")


def render_sidebar_brand() -> None:
    svg = logo_data_uri()
    st.sidebar.markdown(
        f"""
        <div class="mhu-sidebar-brand">
          <div style="width:42px;height:42px">{svg}</div>
          <div>
            <div class="title">MHU</div>
            <div class="sub">Modelo Hidrológico Urbano</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_nav(default: str = "Visão geral") -> str:
    """Menu lateral agrupado com ícones (radio estilizado via CSS)."""
    render_sidebar_brand()
    st.session_state.setdefault("pagina_menu", default)
    if st.session_state.get("pagina_menu") not in ALL_PAGES:
        st.session_state["pagina_menu"] = default

    # Exibe grupos como legendas + um único radio com labels iconificadas
    labels = []
    for group, items in NAV_GROUPS:
        st.sidebar.markdown(f'<div class="mhu-nav-group">{group}</div>', unsafe_allow_html=True)
        for name, icon in items:
            labels.append(f"{icon}  {name}")

    current = st.session_state.get("pagina_menu", default)
    current_label = f"{PAGE_ICONS.get(current, '•')}  {current}"
    if current_label not in labels:
        current_label = labels[0]

    escolha = st.sidebar.radio(
        "Navegação",
        options=labels,
        index=labels.index(current_label) if current_label in labels else 0,
        label_visibility="collapsed",
        key="pagina_menu_label",
    )
    # Extrai nome sem ícone
    pagina = escolha.split("  ", 1)[-1].strip()
    st.session_state["pagina_menu"] = pagina

    st.sidebar.markdown(
        f'<div class="mhu-sidebar-footer">{MHU_VERSION}</div>',
        unsafe_allow_html=True,
    )
    return pagina


def page_header(title: str, subtitle: str | None = None) -> None:
    sub = f'<p class="muted">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="mhu-section-title">{title}</div>{sub}',
        unsafe_allow_html=True,
    )


def hero(title: str, text: str) -> None:
    st.markdown(
        f"""
        <div class="mhu-hero">
          <h1>{title}</h1>
          <p>{text}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_cards(items: list[dict]) -> None:
    """items: {label, value, unit?} — só renderiza entradas válidas."""
    valid = [i for i in items if i.get("value") is not None and str(i.get("value")) != ""]
    if not valid:
        return
    cols = st.columns(min(len(valid), 4))
    for i, item in enumerate(valid):
        with cols[i % len(cols)]:
            unit = f' <span class="unit">{item.get("unit","")}</span>' if item.get("unit") else ""
            st.markdown(
                f"""
                <div class="mhu-metric">
                  <div class="label">{item["label"]}</div>
                  <div class="value">{item["value"]}{unit}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def info_card(title: str, body: str, *, badge: str | None = None) -> None:
    badge_html = f'<span class="mhu-badge">{badge}</span>' if badge else ""
    st.markdown(
        f"""
        <div class="mhu-card">
          <h4>{title} {badge_html}</h4>
          <p class="muted">{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def module_card(icon: str, title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="mhu-module-card">
          <div class="icon">{icon}</div>
          <h4>{title}</h4>
          <p>{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def chart_container(fig: go.Figure, *, key: str | None = None, filename: str = "grafico_mhu") -> None:
    st.markdown('<div class="mhu-chart-box">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True, config=config_export(filename), key=key)
    st.markdown("</div>", unsafe_allow_html=True)


def fig_canal_secao(
    b_canal: float,
    nivel_m: float | None = None,
    nivel_base: float = 0.0,
    y_max: float | None = None,
) -> go.Figure:
    """Representação esquemática da seção retangular do canal (apenas visual)."""
    b = max(float(b_canal), 0.1)
    y_water = max(float(nivel_m or 0.0), 0.0)
    y_top = float(y_max) if y_max and y_max > 0 else max(y_water * 1.6, 1.0)
    # Geometria: paredes e fundo
    fig = go.Figure()
    # Água
    if y_water > 0:
        fig.add_trace(
            go.Scatter(
                x=[0, b, b, 0, 0],
                y=[0, 0, y_water, y_water, 0],
                fill="toself",
                fillcolor="rgba(23, 107, 135, 0.35)",
                line=dict(color=HYDRO, width=1),
                name="Nível d'água",
                hovertemplate=f"Nível = {y_water:.3f} m<extra></extra>",
            )
        )
    # Contorno do canal
    fig.add_trace(
        go.Scatter(
            x=[0, 0, b, b],
            y=[y_top, 0, 0, y_top],
            mode="lines",
            line=dict(color=PETROL, width=3),
            name="Seção retangular",
            hoverinfo="skip",
        )
    )
    fig.add_annotation(
        x=b / 2,
        y=-0.06 * y_top,
        text=f"B = {b:.2f} m",
        showarrow=False,
        font=dict(color="#64748B"),
    )
    if y_water > 0:
        fig.add_annotation(
            x=b + 0.02 * b,
            y=y_water / 2,
            text=f"y = {y_water:.3f} m",
            showarrow=False,
            xanchor="left",
            font=dict(color=HYDRO, size=11),
        )
    if abs(float(nivel_base)) > 1e-12:
        fig.add_annotation(
            x=b / 2,
            y=y_top * 0.92,
            text=f"nível base = {float(nivel_base):.3f} m",
            showarrow=False,
            font=dict(color=ALERT, size=11),
        )
    apply_mhu_layout(fig, title="Seção transversal do canal (esquema)", height=320)
    fig.update_xaxes(range=[-0.15 * b, 1.25 * b], showticklabels=False, title="")
    fig.update_yaxes(range=[-0.12 * y_top, y_top * 1.05], title="Profundidade (m)")
    fig.update_layout(showlegend=False)
    return fig


def go_to(page: str) -> None:
    """
    Agenda troca de página para o próximo rerun.

    Não altera `pagina_menu_label` aqui: essa chave pertence ao `st.sidebar.radio`
    já instanciado neste run. A sincronização ocorre no início de `_run_streamlit_ui`
    (antes do menu), via `pending_page`.
    """
    st.session_state["pending_page"] = page
