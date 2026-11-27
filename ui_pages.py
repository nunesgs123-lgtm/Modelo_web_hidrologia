# -*- coding: utf-8 -*-
"""Páginas de UI do MHU (organização visual; importa lógica de app sob demanda)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from plot_theme import (
    ALERT,
    COLOR_INFIL,
    COLOR_MHU11,
    COLOR_MHU20,
    COLOR_OBS,
    COLOR_PREC,
    COLOR_Q,
    COLOR_SIM,
    HYDRO,
    TEAL,
    annotate_peak,
    apply_mhu_layout,
    config_export,
)
from ui_components import (
    chart_container,
    go_to,
    hero,
    info_card,
    metric_cards,
    module_card,
    page_header,
)


ROOT = Path(__file__).parent


def _fmt(v, nd=3):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return None
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    return f"{float(v):.{nd}f}"


def _mhu_core():
    """
    Acesso às funções hidrológicas sem `import app` (que reexecutaria a UI
    e causaria StreamlitDuplicateElementKey no menu lateral).
    No Streamlit, o entrypoint já está em sys.modules['__main__'].
    """
    import sys

    main = sys.modules.get("__main__")
    if main is not None and hasattr(main, "diagnosticar_balanco_hidrico"):
        return main
    # Fallback (testes / execução fora do Streamlit)
    import importlib

    return importlib.import_module("app")


def render_visao_geral() -> None:
    hero(
        "Modelo Hidrológico Urbano (MHU)",
        "Plataforma científica para simulação de eventos de chuva–vazão em bacias urbanas: "
        "áreas de contribuição, uso do solo, infiltração, escoamento superficial (Manning) "
        "e conversão de vazão em nível no canal. Formulações MHU 1.1 (equivalente) e "
        "MHU 2.0 experimental (por classe de uso do solo).",
    )

    cta1, cta2, cta3 = st.columns([1, 1, 2])
    if cta1.button("Iniciar nova simulação", type="primary", use_container_width=True):
        go_to("Nova simulação")
        st.rerun()
    if cta2.button("Ver metodologia", use_container_width=True):
        go_to("Metodologia")
        st.rerun()

    # Caracterização a partir de dados cadastrados (dinâmico)
    ac = st.session_state.get("ac_df_loaded")
    us = st.session_state.get("us_df_loaded")
    meta = st.session_state.get("sim_meta_balanco")
    df_s = st.session_state.get("df_saida_validacao")

    page_header("Área de estudo (dados cadastrados)")
    n_ac = int(len(ac)) if isinstance(ac, pd.DataFrame) and not ac.empty else 0
    area_total = (
        float(pd.to_numeric(ac["Area_m2"], errors="coerce").sum())
        if n_ac
        else None
    )
    n_us = int(len(us)) if isinstance(us, pd.DataFrame) and not us.empty else 0
    metric_cards(
        [
            {"label": "Áreas de contribuição", "value": _fmt(n_ac, 0) if n_ac else "—", "unit": "AC"},
            {
                "label": "Área total cadastrada",
                "value": _fmt(area_total / 1e4, 2) if area_total else "—",
                "unit": "ha",
            },
            {"label": "Classes de uso do solo", "value": _fmt(n_us, 0) if n_us else "—", "unit": "US"},
            {
                "label": "Exutório",
                "value": str(meta.get("exutorio_id")) if meta else "—",
                "unit": "ID",
            },
        ]
    )
    if n_ac == 0:
        st.caption("Nenhum dado de AC carregado ainda. Os indicadores serão preenchidos após cadastrar ou simular.")

    page_header("Formulações disponíveis")
    f1, f2 = st.columns(2)
    with f1:
        info_card(
            "MHU 1.1 — Modo 1",
            "Parâmetros equivalentes por área de contribuição (média ponderada por área das classes US). "
            "Formulação preservada e congelada em snapshots/MHU_1.1/.",
            badge="Estável",
        )
    with f2:
        info_card(
            "MHU 2.0 — Modo 2",
            "Processamento hidrológico individual por classe de uso do solo (V, h, n, f, Q próprios). "
            "Mudança de concepção matemática — experimental.",
            badge="Experimental",
        )

    page_header("Módulos")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        module_card("💧", "Nova simulação", "Configure evento, canal, ACs, US e precipitação.")
    with m2:
        module_card("⚖️", "Balanço hídrico", "Fechamento numérico de massa por AC e bacia.")
    with m3:
        module_card("✅", "Validação", "Compare nível observado e simulado (NSE, R², RMSE…).")
    with m4:
        module_card("🔬", "Comparação 1.1 × 2.0", "Mesmos dados nas duas formulações.")

    page_header("Última simulação")
    if df_s is None or not isinstance(df_s, pd.DataFrame) or df_s.empty:
        st.info("Nenhuma simulação executada nesta sessão. Inicie em **Nova simulação**.")
    else:
        modo = (meta or {}).get("modo_mhu", df_s.get("Modo_hidrologico", pd.Series(["—"])).iloc[0] if "Modo_hidrologico" in df_s.columns else "—")
        metric_cards(
            [
                {"label": "Modo", "value": str(modo)},
                {"label": "Q pico", "value": _fmt(df_s["Q_ex_m3_s"].max(), 4), "unit": "m³/s"},
                {"label": "Nível pico", "value": _fmt(df_s["Nivel_m"].max(), 4), "unit": "m"},
                {
                    "label": "Δt integração",
                    "value": _fmt((meta or {}).get("dt"), 0) if meta else "—",
                    "unit": "s",
                },
            ]
        )
        b1, b2 = st.columns(2)
        if b1.button("Abrir resultados", use_container_width=True):
            go_to("Resultados")
            st.rerun()
        if b2.button("Ir para validação", use_container_width=True):
            go_to("Validação")
            st.rerun()

    # Espaço opcional para mapa
    with st.expander("Mapa da área de estudo (opcional)", expanded=False):
        st.caption(
            "Espaço reservado para futura integração de mapa (ex.: coordenadas da bacia). "
            "Não há mapa embutido nesta versão."
        )


def render_metodologia() -> None:
    page_header("Metodologia do MHU")
    path = ROOT / "METODOLOGIA_MODELO.md"
    if path.exists():
        st.markdown(path.read_text(encoding="utf-8"))
    else:
        st.warning("Arquivo METODOLOGIA_MODELO.md não encontrado.")
    cpath = ROOT / "MHU_2.0_CONCEPCAO.md"
    if cpath.exists():
        with st.expander("Concepção MHU 2.0", expanded=False):
            st.markdown(cpath.read_text(encoding="utf-8"))


def render_diagnostico_numerico() -> None:
    page_header(
        "Diagnóstico numérico",
        "Resíduos do solver implícito e documentação de convergência. "
        "Não altera equações — apenas exposita resultados já calculados.",
    )
    df_ac = st.session_state.get("df_ac_detalhe")
    if isinstance(df_ac, pd.DataFrame) and not df_ac.empty and "Residuo_implicito_m3" in df_ac.columns:
        ativos = df_ac[df_ac["Passo"] > 0]
        metric_cards(
            [
                {
                    "label": "|Resíduo| máximo",
                    "value": _fmt(ativos["Residuo_implicito_m3"].abs().max(), 6),
                    "unit": "m³",
                },
                {
                    "label": "|Resíduo| médio",
                    "value": _fmt(ativos["Residuo_implicito_m3"].abs().mean(), 6),
                    "unit": "m³",
                },
            ]
        )
        fig = px.line(
            ativos,
            x="Tempo_s",
            y="Residuo_implicito_m3",
            color="ID_AC",
            title="Resíduo do Euler implícito por AC",
        )
        apply_mhu_layout(fig)
        chart_container(fig, filename="residuo_implicito")
        st.dataframe(ativos[["Passo", "Tempo_s", "ID_AC", "Residuo_implicito_m3", "Volume_escoado_m3"]], use_container_width=True, hide_index=True)
    else:
        st.info("Execute uma simulação para visualizar resíduos numéricos por passo.")

    conv = ROOT / "CONVERGENCIA_NUMERICA.md"
    if conv.exists():
        with st.expander("Documentação de convergência numérica", expanded=False):
            st.markdown(conv.read_text(encoding="utf-8"))


def render_resultados() -> None:
    mhu = _mhu_core()

    page_header("Resultados da simulação")
    df_s = st.session_state.get("df_saida_validacao")
    df_ac = st.session_state.get("df_ac_detalhe")
    df_us = st.session_state.get("df_us_detalhe")
    meta = st.session_state.get("sim_meta_balanco")
    ac_ref = st.session_state.get("ac_df_loaded")

    if df_s is None or not isinstance(df_s, pd.DataFrame) or df_s.empty:
        st.warning("Nenhum resultado disponível. Execute uma simulação em **Nova simulação**.")
        if st.button("Ir para nova simulação", type="primary"):
            go_to("Nova simulação")
            st.rerun()
        return

    df_s = df_s.copy()
    if "Tempo_hhmm" not in df_s.columns and "Tempo_s" in df_s.columns:
        df_s["Tempo_hhmm"] = df_s["Tempo_s"].astype(str)

    # Métricas de precipitação se meta tiver info
    p_acum = i_max = dur = None
    if meta and "intervalo_registro_s" in meta:
        try:
            unidade = str(meta.get("unidade_chuva", mhu.UNIDADE_CHUVA_INTENSIDADE))
            chuva_df = st.session_state.get("chuva_df_loaded")
            if isinstance(chuva_df, pd.DataFrame) and not chuva_df.empty:
                vals = mhu.extrair_valores_chuva_df(chuva_df, unidade)
                met = mhu.metricas_precipitacao(vals, unidade, float(meta["intervalo_registro_s"]))
                p_acum, i_max, dur = met["P_acum_mm"], met["I_max_mm_h"], met["Duracao_evento_min"]
        except Exception:
            pass

    q_max = float(df_s["Q_ex_m3_s"].max())
    n_max = float(df_s["Nivel_m"].max())
    idx_pico = int(df_s["Nivel_m"].idxmax())
    hora_pico = df_s.loc[idx_pico, "Tempo_hhmm"] if "Tempo_hhmm" in df_s.columns else df_s.loc[idx_pico, "Tempo_s"]

    v_esc = v_inf = v_arm = None
    if isinstance(df_ac, pd.DataFrame) and not df_ac.empty and meta and isinstance(ac_ref, pd.DataFrame):
        try:
            bal = mhu.diagnosticar_balanco_hidrico(
                df_saida=df_s,
                df_ac_detalhe=df_ac,
                ac_df=ac_ref,
                exutorio_id=int(meta["exutorio_id"]),
                dt=float(meta["dt"]),
                tempo_chuva_s=float(meta["tempo_chuva_s"]),
            )
            row = bal["df_bacia"][bal["df_bacia"]["Periodo"] == "chuva_mais_recessao"].iloc[0]
            v_esc = float(row["V_exutorio_m3"])
            v_inf = float(row["V_infiltracao_m3"])
            v_arm = float(row["V_final_m3"])
        except Exception:
            if "Volume_escoado_m3" in df_ac.columns:
                v_esc = float(df_ac.loc[df_ac["Passo"] > 0, "Volume_escoado_m3"].sum())
            if "Volume_infiltrado_m3" in df_ac.columns:
                v_inf = float(df_ac.loc[df_ac["Passo"] > 0, "Volume_infiltrado_m3"].sum())

    metric_cards(
        [
            {"label": "Precipitação acumulada", "value": _fmt(p_acum, 2) if p_acum is not None else None, "unit": "mm"},
            {"label": "Intensidade máxima", "value": _fmt(i_max, 2) if i_max is not None else None, "unit": "mm/h"},
            {"label": "Duração do evento", "value": _fmt(dur, 1) if dur is not None else None, "unit": "min"},
            {"label": "Vazão máxima", "value": _fmt(q_max, 4), "unit": "m³/s"},
            {"label": "Nível máximo", "value": _fmt(n_max, 4), "unit": "m"},
            {"label": "Horário do pico", "value": str(hora_pico)},
            {"label": "Volume escoado (exutório)", "value": _fmt(v_esc, 2) if v_esc is not None else None, "unit": "m³"},
            {"label": "Volume infiltrado", "value": _fmt(v_inf, 2) if v_inf is not None else None, "unit": "m³"},
            {"label": "Armazenamento final", "value": _fmt(v_arm, 2) if v_arm is not None else None, "unit": "m³"},
        ]
    )

    a1, a2, a3 = st.columns(3)
    if a1.button("Salvar simulação", use_container_width=True):
        go_to("Nova simulação")
        st.rerun()
    if a2.button("Exportar Excel", use_container_width=True):
        st.session_state["_focus_export"] = True
    if a3.button("Ir para validação", use_container_width=True):
        go_to("Validação")
        st.rerun()

    fig_n = mhu.fig_nivel_com_hietograma(df_s)
    chart_container(fig_n, filename="nivel_hietograma")

    fig_q = go.Figure()
    fig_q.add_trace(
        go.Scatter(
            x=df_s["Tempo_hhmm"] if "Tempo_hhmm" in df_s.columns else df_s["Tempo_s"],
            y=df_s["Q_ex_m3_s"],
            mode="lines",
            name="Q_ex (m³/s)",
            line=dict(color=COLOR_Q, width=2.5),
            fill="tozeroy",
            fillcolor="rgba(23,107,135,0.12)",
            hovertemplate="Q = %{y:.4f} m³/s<extra></extra>",
        )
    )
    i_q = int(df_s["Q_ex_m3_s"].idxmax())
    x_peak = df_s.loc[i_q, "Tempo_hhmm"] if "Tempo_hhmm" in df_s.columns else df_s.loc[i_q, "Tempo_s"]
    annotate_peak(fig_q, x_peak, q_max, f"Pico {q_max:.3f} m³/s", color=COLOR_Q)
    apply_mhu_layout(fig_q, title="Hidrograma de vazão no exutório")
    chart_container(fig_q, filename="hidrograma_vazao")

    with st.expander("Tabelas detalhadas", expanded=False):
        st.subheader("Exutório")
        st.dataframe(df_s, use_container_width=True, hide_index=True)
        if isinstance(df_ac, pd.DataFrame):
            st.subheader("Por AC")
            st.dataframe(df_ac, use_container_width=True, hide_index=True)
        if isinstance(df_us, pd.DataFrame) and df_us is not None and not df_us.empty:
            st.subheader("Por classe US")
            st.dataframe(df_us, use_container_width=True, hide_index=True)

    if st.session_state.get("_focus_export") and isinstance(df_ac, pd.DataFrame) and meta and isinstance(ac_ref, pd.DataFrame):
        try:
            bal = mhu.diagnosticar_balanco_hidrico(
                df_saida=df_s,
                df_ac_detalhe=df_ac,
                ac_df=ac_ref,
                exutorio_id=int(meta["exutorio_id"]),
                dt=float(meta["dt"]),
                tempo_chuva_s=float(meta["tempo_chuva_s"]),
            )
            st.download_button(
                "Baixar Excel de resultados",
                data=mhu.montar_excel_resultados(df_s, df_ac, bal, df_us_detalhe=df_us if isinstance(df_us, pd.DataFrame) else None),
                file_name="resultado_modelo_hidrologico.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as exc:
            st.error(f"Falha ao montar Excel: {exc}")


def enhance_fig_nivel(df_saida: pd.DataFrame) -> go.Figure:
    """Versão visual do hidrograma nível+hietograma (mesmos dados)."""
    x = df_saida["Tempo_hhmm"] if "Tempo_hhmm" in df_saida.columns else df_saida["Tempo_s"]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x,
            y=df_saida["P_mm_h"],
            name="Precipitação (mm/h)",
            marker=dict(color=COLOR_PREC, line=dict(width=0)),
            yaxis="y2",
            hovertemplate="Precipitação: %{y:.2f} mm/h<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df_saida["Nivel_m"],
            name="Nível simulado (m)",
            mode="lines",
            line=dict(color=COLOR_SIM, width=2.6),
            hovertemplate="Nível: %{y:.4f} m<extra></extra>",
        )
    )
    p_max = float(pd.to_numeric(df_saida["P_mm_h"], errors="coerce").max() or 0.0)
    i_n = int(pd.to_numeric(df_saida["Nivel_m"], errors="coerce").idxmax())
    annotate_peak(fig, x.iloc[i_n] if hasattr(x, "iloc") else x[i_n], float(df_saida.loc[i_n, "Nivel_m"]), f"Pico {float(df_saida.loc[i_n, 'Nivel_m']):.3f} m")
    apply_mhu_layout(fig, title="Hidrograma de nível e hietograma de precipitação", height=440)
    fig.update_layout(
        xaxis=dict(title="Horário", type="category"),
        yaxis=dict(title="Nível no canal (m)", side="left"),
        yaxis2=dict(
            title="Precipitação (mm/h)",
            overlaying="y",
            side="right",
            showgrid=False,
            range=[max(p_max * 1.25, 1.0), 0.0],
        ),
        bargap=0.05,
    )
    return fig
