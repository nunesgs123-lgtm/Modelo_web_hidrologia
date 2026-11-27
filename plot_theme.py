# -*- coding: utf-8 -*-
"""Tema Plotly compartilhado do MHU (apenas visual)."""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# Paleta institucional
PETROL = "#103B53"
HYDRO = "#176B87"
TEAL = "#26A69A"
LIGHT = "#EAF3F8"
TEXT = "#243746"
MUTED = "#64748B"
BORDER = "#DCE5EC"
ALERT = "#D97736"
WHITE = "#FFFFFF"

COLOR_SIM = HYDRO
COLOR_OBS = ALERT
COLOR_INFIL = TEAL
COLOR_PREC = "#7EB6D4"
COLOR_MHU11 = HYDRO
COLOR_MHU20 = "#0F766E"
COLOR_LEVEL = PETROL
COLOR_Q = HYDRO

MHU_LAYOUT = dict(
    paper_bgcolor=WHITE,
    plot_bgcolor=WHITE,
    font=dict(family="Inter, Roboto, sans-serif", color=TEXT, size=13),
    title=dict(font=dict(size=15, color=PETROL)),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="left",
        x=0,
        bgcolor="rgba(255,255,255,0.85)",
        bordercolor=BORDER,
        borderwidth=0,
    ),
    margin=dict(t=70, r=50, l=55, b=50),
    xaxis=dict(
        showgrid=True,
        gridcolor="#EEF2F6",
        zeroline=False,
        linecolor=BORDER,
        title_font=dict(color=MUTED, size=12),
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor="#EEF2F6",
        zeroline=True,
        zerolinecolor="#E2E8F0",
        linecolor=BORDER,
        title_font=dict(color=MUTED, size=12),
    ),
    colorway=[HYDRO, TEAL, ALERT, PETROL, COLOR_PREC, "#5B8A9A"],
)


def register_mhu_plotly_theme() -> None:
    """Registra template Plotly 'mhu'."""
    pio.templates["mhu"] = go.layout.Template(layout=MHU_LAYOUT)
    pio.templates.default = "mhu"


def apply_mhu_layout(fig: go.Figure, *, title: str | None = None, height: int | None = 420) -> go.Figure:
    kw = dict(**MHU_LAYOUT)
    if title:
        kw["title"] = dict(text=title, font=dict(size=15, color=PETROL))
    if height:
        kw["height"] = height
    fig.update_layout(**kw)
    return fig


def annotate_peak(
    fig: go.Figure,
    x,
    y,
    text: str,
    *,
    color: str = HYDRO,
    yref: str = "y",
) -> go.Figure:
    fig.add_annotation(
        x=x,
        y=y,
        xref="x",
        yref=yref,
        text=text,
        showarrow=True,
        arrowhead=2,
        arrowcolor=color,
        font=dict(size=11, color=color),
        bgcolor="rgba(255,255,255,0.9)",
        bordercolor=BORDER,
        borderwidth=1,
        ax=0,
        ay=-35,
    )
    return fig


def config_export(filename: str = "grafico_mhu") -> dict:
    """Config Plotly com exportação PNG/SVG de alta resolução."""
    return {
        "displayModeBar": True,
        "displaylogo": False,
        "toImageButtonOptions": {
            "format": "png",
            "filename": filename,
            "height": 800,
            "width": 1400,
            "scale": 2,
        },
        "modeBarButtonsToAdd": ["toImage"],
    }
