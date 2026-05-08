import math
import json
from io import BytesIO
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(page_title="Modelo Hidrologico Urbano", layout="wide")

GLOSSARIO_ROWS = [
    {"Termo": "Delta_t_seg", "Unidade": "s", "Descricao": "Passo de tempo da simulacao."},
    {"Termo": "Duracao_chuva_min", "Unidade": "min", "Descricao": "Duracao total do evento; define o numero de passos ativos."},
    {"Termo": "N_passos_ativos", "Unidade": "-", "Descricao": "Numero de intervalos (inclui passo inicial t=0 quando aplicavel)."},
    {"Termo": "Area_m2", "Unidade": "m2", "Descricao": "Area de contribuicao da AC."},
    {"Termo": "L_m", "Unidade": "m", "Descricao": "Comprimento caracteristico de escoamento na AC."},
    {"Termo": "S_m_m", "Unidade": "m/m", "Descricao": "Declividade da superficie de escoamento na AC."},
    {"Termo": "ACs_montante_ids", "Unidade": "-", "Descricao": "IDs das AC imediatamente a montante, separados por ponto e virgula (ex.: 1;2)."},
    {"Termo": "h0_m", "Unidade": "m", "Descricao": "Lamina inicial de agua superficial na AC."},
    {"Termo": "Infiltracao_eq_mm_h", "Unidade": "mm/h", "Descricao": "Taxa de infiltracao equivalente ponderada por area de US."},
    {"Termo": "n_eq", "Unidade": "-", "Descricao": "Coeficiente de Manning equivalente ponderado por area de US."},
    {"Termo": "P_mm_h", "Unidade": "mm/h", "Descricao": "Intensidade de precipitacao no intervalo."},
    {"Termo": "P_m_s", "Unidade": "m/s", "Descricao": "Precipitacao convertida para unidades SI."},
    {"Termo": "i_excesso_m_s", "Unidade": "m/s", "Descricao": "Chuva efetiva = max(P - infiltracao, 0)."},
    {"Termo": "Q_in_m3_s", "Unidade": "m3/s", "Descricao": "Vazao recebida das AC(s) a montante imediata."},
    {"Termo": "Q_out_m3_s", "Unidade": "m3/s", "Descricao": "Vazao de saida da AC (propagacao por Manning)."},
    {"Termo": "Q_ex_m3_s", "Unidade": "m3/s", "Descricao": "Vazao no exutorio selecionado."},
    {"Termo": "Nivel_m", "Unidade": "m", "Descricao": "Profundidade no canal obtida por Manning (secao retangular)."},
    {"Termo": "Cota_abs_m", "Unidade": "m", "Descricao": "Nivel absoluto = Nivel_m + nivel_base."},
    {"Termo": "B_canal", "Unidade": "m", "Descricao": "Largura do canal na secao retangular."},
    {"Termo": "S_canal", "Unidade": "m/m", "Descricao": "Declividade do canal."},
    {"Termo": "n_canal", "Unidade": "-", "Descricao": "Manning do canal."},
    {"Termo": "nivel_base", "Unidade": "m", "Descricao": "Cota de referencia somada ao nivel para cota absoluta."},
    {"Termo": "NSE / Nash-Sutcliffe", "Unidade": "-", "Descricao": "Eficiencia de Nash-Sutcliffe: 1 - sum((O-S)^2)/sum((O-mean(O))^2). Tambem chamado de Nash."},
    {"Termo": "R2 (Pearson)", "Unidade": "-", "Descricao": "Coeficiente de determinacao linear: quadrado da correlacao de Pearson entre observado e simulado."},
    {"Termo": "RMSE / MAE / Vies", "Unidade": "m", "Descricao": "Erro quadratico medio, erro absoluto medio e vies medio (S - O) para nivel."},
]

# Referencias para calibracao (ordens de grandeza; ajustar ao local e ao evento)
CALIBRACAO_USO_SOLO = [
    {
        "Classe": "Superficies impermeaveis",
        "Exemplos": "Vias pavimentadas, passeios, estacionamentos, telhados e coberturas, patios e pracas com piso impermeavel",
        "Infil_sugerida_mm_h": 1.0,
        "Infil_min_mm_h": 0.0,
        "Infil_max_mm_h": 3.0,
        "n_sugerido": 0.015,
        "n_min": 0.011,
        "n_max": 0.020,
    },
    {
        "Classe": "Superficies semi-impermeaveis",
        "Exemplos": "Ruas nao pavimentadas, estradas vicinais, caminhos de terra e estacionamentos de terra",
        "Infil_sugerida_mm_h": 6.0,
        "Infil_min_mm_h": 2.0,
        "Infil_max_mm_h": 12.0,
        "n_sugerido": 0.035,
        "n_min": 0.020,
        "n_max": 0.060,
    },
    {
        "Classe": "Solo exposto",
        "Exemplos": "Terrenos baldios, taludes expostos e areas com remocao de vegetacao",
        "Infil_sugerida_mm_h": 8.0,
        "Infil_min_mm_h": 2.0,
        "Infil_max_mm_h": 18.0,
        "n_sugerido": 0.040,
        "n_min": 0.020,
        "n_max": 0.080,
    },
    {
        "Classe": "Cobertura vegetal arborea",
        "Exemplos": "Florestas, matas ciliares e fragmentos florestais",
        "Infil_sugerida_mm_h": 35.0,
        "Infil_min_mm_h": 20.0,
        "Infil_max_mm_h": 55.0,
        "n_sugerido": 0.35,
        "n_min": 0.28,
        "n_max": 0.45,
    },
    {
        "Classe": "Cobertura vegetal rasteira",
        "Exemplos": "Campos naturais, areas de grama e capim natural e outras areas verdes nao urbanizadas",
        "Infil_sugerida_mm_h": 22.0,
        "Infil_min_mm_h": 10.0,
        "Infil_max_mm_h": 35.0,
        "n_sugerido": 0.25,
        "n_min": 0.16,
        "n_max": 0.35,
    },
    {
        "Classe": "Area verde urbana",
        "Exemplos": "Quintais residenciais, jardins, pracas com vegetacao, canteiros urbanos, areas verdes de escolas e condominios",
        "Infil_sugerida_mm_h": 18.0,
        "Infil_min_mm_h": 8.0,
        "Infil_max_mm_h": 30.0,
        "n_sugerido": 0.22,
        "n_min": 0.15,
        "n_max": 0.30,
    },
    {
        "Classe": "Pastagem",
        "Exemplos": "Pasto de gado e manejo animal evidenciado",
        "Infil_sugerida_mm_h": 16.0,
        "Infil_min_mm_h": 6.0,
        "Infil_max_mm_h": 30.0,
        "n_sugerido": 0.28,
        "n_min": 0.18,
        "n_max": 0.40,
    },
    {
        "Classe": "Corpos d'agua",
        "Exemplos": "Rios, acudes, lagos e canais abertos",
        "Infil_sugerida_mm_h": 0.0,
        "Infil_min_mm_h": 0.0,
        "Infil_max_mm_h": 0.5,
        "n_sugerido": 0.030,
        "n_min": 0.015,
        "n_max": 0.060,
    },
    {
        "Classe": "Infraestrutura urbana linear",
        "Exemplos": "Ferrovias, patios ferroviarios, corredores de servico e faixas de dutos",
        "Infil_sugerida_mm_h": 4.0,
        "Infil_min_mm_h": 0.5,
        "Infil_max_mm_h": 12.0,
        "n_sugerido": 0.030,
        "n_min": 0.015,
        "n_max": 0.060,
    },
    {
        "Classe": "Superficies drenantes artificiais",
        "Exemplos": "Piso intertravado drenante, pavimento permeavel e valas/trincheiras de infiltracao",
        "Infil_sugerida_mm_h": 25.0,
        "Infil_min_mm_h": 8.0,
        "Infil_max_mm_h": 60.0,
        "n_sugerido": 0.080,
        "n_min": 0.040,
        "n_max": 0.150,
    },
]

CALIBRACAO_CANAL_MANNING = [
    {
        "Tipo_revestimento": "Concreto liso (acabado)",
        "n_sugerido": 0.013,
        "n_min": 0.011,
        "n_max": 0.015,
        "Notas": "Superficies bem acabadas, canalizacoes urbanas tipicas",
    },
    {
        "Tipo_revestimento": "Concreto rugoso / envelhecido",
        "n_sugerido": 0.016,
        "n_min": 0.014,
        "n_max": 0.018,
        "Notas": "Maior rugosidade por desgaste ou junta",
    },
    {
        "Tipo_revestimento": "Alvenaria / pedra aparelhada",
        "n_sugerido": 0.018,
        "n_min": 0.016,
        "n_max": 0.022,
        "Notas": "Muros de canal",
    },
    {
        "Tipo_revestimento": "Pedra seca / enrocamento",
        "n_sugerido": 0.030,
        "n_min": 0.025,
        "n_max": 0.035,
        "Notas": "Leitos dissipativos",
    },
    {
        "Tipo_revestimento": "Terra limpa (sem vegetacao)",
        "n_sugerido": 0.025,
        "n_min": 0.020,
        "n_max": 0.030,
        "Notas": "Canais de terra compactada",
    },
    {
        "Tipo_revestimento": "Terra com vegetacao",
        "n_sugerido": 0.038,
        "n_min": 0.030,
        "n_max": 0.045,
        "Notas": "Leitos com capim ou vegetacao",
    },
    {
        "Tipo_revestimento": "Leito natural (rio / canal nao revestido)",
        "n_sugerido": 0.045,
        "n_min": 0.035,
        "n_max": 0.060,
        "Notas": "Alta variabilidade conforme meandros e material",
    },
]

SIM_STORE_PATH = Path(__file__).parent / "simulacoes_salvas.json"


def carregar_simulacoes_salvas() -> dict:
    if not SIM_STORE_PATH.exists():
        return {"last_id": None, "items": []}
    try:
        data = json.loads(SIM_STORE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "items" in data:
            return data
    except Exception:
        pass
    return {"last_id": None, "items": []}


def salvar_simulacoes_salvas(data: dict) -> None:
    SIM_STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def gerar_payload_simulacao(
    titulo: str,
    dt_seg: int,
    duracao_min: int,
    n_ac: int,
    exutorio_id: int,
    b_canal: float,
    s_canal: float,
    n_canal: float,
    nivel_base: float,
    usar_horton: bool,
    horton_k_h_inv: float,
    horton_f0_multiplicador: float,
    usar_us_para_eq: bool,
    ac_df: pd.DataFrame,
    us_df: pd.DataFrame,
    chuva_df: pd.DataFrame,
) -> dict:
    start_hhmm = st.session_state.get("hora_inicio_evento", "12:00")
    end_hhmm = st.session_state.get("hora_fim_evento", "12:40")
    return {
        "id": datetime.utcnow().strftime("%Y%m%d%H%M%S%f"),
        "titulo": titulo.strip() if titulo.strip() else f"Simulação {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "params": {
            "dt_seg": int(dt_seg),
            "duracao_min": int(duracao_min),
            "n_ac": int(n_ac),
            "exutorio_id": int(exutorio_id),
            "b_canal": float(b_canal),
            "s_canal": float(s_canal),
            "n_canal": float(n_canal),
            "nivel_base": float(nivel_base),
            "usar_horton": bool(usar_horton),
            "horton_k_h_inv": float(horton_k_h_inv),
            "horton_f0_multiplicador": float(horton_f0_multiplicador),
            "usar_us_para_eq": bool(usar_us_para_eq),
            "hora_inicio_evento": str(start_hhmm),
            "hora_fim_evento": str(end_hhmm),
        },
        "ac_df": ac_df.to_dict(orient="records"),
        "us_df": us_df.to_dict(orient="records"),
        "chuva_df": chuva_df.to_dict(orient="records"),
    }


def aplicar_payload_em_session(payload: dict) -> None:
    p = payload.get("params", {})
    st.session_state["dt_seg"] = int(p.get("dt_seg", 600))
    st.session_state["duracao_min"] = int(p.get("duracao_min", 40))
    st.session_state["n_ac"] = int(p.get("n_ac", 3))
    st.session_state["exutorio_id"] = int(p.get("exutorio_id", st.session_state["n_ac"]))
    st.session_state["b_canal"] = float(p.get("b_canal", 4.0))
    st.session_state["s_canal"] = float(p.get("s_canal", 0.004))
    st.session_state["n_canal"] = float(p.get("n_canal", 0.018))
    st.session_state["nivel_base"] = float(p.get("nivel_base", 0.2))
    st.session_state["usar_horton"] = bool(p.get("usar_horton", False))
    st.session_state["horton_k_h_inv"] = float(p.get("horton_k_h_inv", 2.5))
    st.session_state["horton_f0_multiplicador"] = float(p.get("horton_f0_multiplicador", 1.0))
    st.session_state["usar_us_para_eq"] = bool(p.get("usar_us_para_eq", True))
    st.session_state["hora_inicio_evento"] = str(p.get("hora_inicio_evento", "12:00"))
    st.session_state["hora_fim_evento"] = str(p.get("hora_fim_evento", "12:40"))
    st.session_state["ac_df_loaded"] = pd.DataFrame(payload.get("ac_df", []))
    st.session_state["us_df_loaded"] = pd.DataFrame(payload.get("us_df", []))
    st.session_state["chuva_df_loaded"] = pd.DataFrame(payload.get("chuva_df", []))
    st.session_state["titulo_salvar"] = payload.get("titulo", "")
    # Garante que data_editors renderizem os dados carregados, não cache antigo do widget.
    st.session_state.pop("editor_ac", None)
    st.session_state.pop("editor_us", None)
    st.session_state.pop("editor_chuva", None)


def validar_campos_obrigatorios(
    dt_seg: int,
    duracao_min: int,
    n_ac: int,
    exutorio_id: int,
    b_canal: float,
    s_canal: float,
    n_canal: float,
    usar_horton: bool,
    horton_k_h_inv: float,
    horton_f0_multiplicador: float,
    ac_df: pd.DataFrame,
    us_df: pd.DataFrame,
    chuva_df: pd.DataFrame,
) -> list[str]:
    erros = []
    if dt_seg <= 0:
        erros.append("`Delta t (s)` deve ser maior que zero.")
    if duracao_min <= 0:
        erros.append("`Duracao da chuva (min)` deve ser maior que zero.")
    if n_ac <= 0:
        erros.append("`Numero de ACs` deve ser maior que zero.")
    if exutorio_id <= 0:
        erros.append("`ID da AC de exutorio` deve ser maior que zero.")
    if exutorio_id > n_ac:
        erros.append("`ID da AC de exutorio` deve estar dentro do intervalo de ACs informadas.")
    if b_canal <= 0:
        erros.append("`B_canal (m)` deve ser maior que zero.")
    if s_canal <= 0:
        erros.append("`S_canal (m/m)` deve ser maior que zero.")
    if n_canal <= 0:
        erros.append("`n_canal` deve ser maior que zero.")
    if usar_horton and horton_k_h_inv < 0:
        erros.append("`k de Horton (1/h)` deve ser maior ou igual a zero.")
    if usar_horton and horton_f0_multiplicador < 1:
        erros.append("`f0/fc de Horton` deve ser maior ou igual a 1.")
    if ac_df.empty:
        erros.append("Tabela de `Areas de contribuicao (AC)` esta vazia.")
    else:
        for col in ["ID_AC", "Area_m2", "L_m", "S_m_m"]:
            if col not in ac_df.columns or ac_df[col].isna().any():
                erros.append(f"Preencha todos os valores obrigatorios em AC: `{col}`.")
                break
    if us_df.empty:
        erros.append("Tabela de `Unidades de uso do solo (US)` esta vazia.")
    else:
        for col in ["ID_AC", "Area_US_m2", "Infiltracao_US_mm_h", "n_US"]:
            if col not in us_df.columns or pd.to_numeric(us_df[col], errors="coerce").isna().any():
                erros.append(f"Preencha todos os valores obrigatorios em US: `{col}`.")
                break
    if chuva_df.empty or "P_mm_h" not in chuva_df.columns:
        erros.append("Tabela de chuva esta vazia.")
    elif pd.to_numeric(chuva_df["P_mm_h"], errors="coerce").isna().any():
        erros.append("Preencha todos os valores de `P_mm_h` na tabela de chuva.")
    return erros


def montar_tempo_evento_hhmm(n_steps: int, dt_seg: int, hora_inicio: str) -> list[str]:
    h, m = [int(x) for x in hora_inicio.split(":")]
    t0 = datetime(2000, 1, 1, h, m)
    return [(t0 + timedelta(seconds=i * dt_seg)).strftime("%H:%M") for i in range(n_steps)]


def parse_upstream_ids(text: str) -> list[int]:
    if text is None:
        return []
    raw = str(text).strip()
    if raw in {"", "0", "nan", "None"}:
        return []
    ids = []
    for part in raw.split(";"):
        p = part.strip()
        if p.isdigit():
            ids.append(int(p))
    return ids


def ordenar_ac_topologicamente(ac_df: pd.DataFrame) -> pd.DataFrame:
    """Ordena ACs para garantir montante -> jusante no mesmo passo de tempo."""
    ac_work = ac_df.copy()
    ac_work["ID_AC"] = ac_work["ID_AC"].astype(int)
    ac_work = ac_work.reset_index(drop=True)

    ac_ids = ac_work["ID_AC"].tolist()
    id_set = set(ac_ids)
    idx_by_id = {ac_id: i for i, ac_id in enumerate(ac_ids)}

    indeg = {ac_id: 0 for ac_id in ac_ids}
    downstream_adj: dict[int, list[int]] = {ac_id: [] for ac_id in ac_ids}

    for _, row in ac_work.iterrows():
        ac_id = int(row["ID_AC"])
        for up_id in parse_upstream_ids(row["ACs_montante_ids"]):
            if up_id in id_set:
                downstream_adj[up_id].append(ac_id)
                indeg[ac_id] += 1

    fila = deque(sorted([ac_id for ac_id in ac_ids if indeg[ac_id] == 0]))
    ordem_ids: list[int] = []
    while fila:
        atual = fila.popleft()
        ordem_ids.append(atual)
        for ds_id in sorted(downstream_adj[atual]):
            indeg[ds_id] -= 1
            if indeg[ds_id] == 0:
                fila.append(ds_id)

    if len(ordem_ids) != len(ac_ids):
        raise ValueError(
            "A rede de ACs possui ciclo nas relacoes de montante. Corrija `ACs_montante_ids` para uma estrutura aciclica."
        )

    ordem_idx = [idx_by_id[ac_id] for ac_id in ordem_ids]
    return ac_work.iloc[ordem_idx].reset_index(drop=True)


def solve_channel_depth(
    q_ex: np.ndarray, b_canal: float, s_canal: float, n_canal: float, n_iter: int = 5
) -> np.ndarray:
    y = np.zeros_like(q_ex, dtype=float)
    if b_canal <= 0 or s_canal <= 0 or n_canal <= 0:
        return y

    for i, q in enumerate(q_ex):
        if q <= 0:
            y[i] = 0.0
            continue
        yk = max((q * n_canal / (b_canal * math.sqrt(s_canal))) ** (3.0 / 5.0), 1e-6)
        for _ in range(n_iter):
            rh = (b_canal * yk) / max((b_canal + 2.0 * yk), 1e-9)
            yk = q * n_canal / (b_canal * math.sqrt(s_canal) * max(rh, 1e-9) ** (2.0 / 3.0))
        y[i] = max(0.0, yk)
    return y


def solve_surface_depth_implicit(
    h_prev: float,
    dt: float,
    input_rate_m_s: float,
    alpha_m_2_3_s: float,
    max_iter: int = 25,
    tol: float = 1e-9,
) -> float:
    """
    Resolve h_(t+1) por Euler implicito para:
      dh/dt = input_rate - alpha * h^(5/3)
    onde alpha = (w_eq / area) * (1/n_eq) * sqrt(S).
    """
    h_prev = max(float(h_prev), 0.0)
    dt = max(float(dt), 0.0)
    input_rate_m_s = float(input_rate_m_s)
    alpha_m_2_3_s = max(float(alpha_m_2_3_s), 0.0)
    if dt <= 0:
        return h_prev

    if alpha_m_2_3_s <= 0:
        return max(0.0, h_prev + dt * input_rate_m_s)

    # Chute inicial explicito truncado em zero.
    h = max(0.0, h_prev + dt * (input_rate_m_s - alpha_m_2_3_s * (h_prev ** (5.0 / 3.0))))
    for _ in range(max_iter):
        h_eps = max(h, 1e-12)
        h_53 = h_eps ** (5.0 / 3.0)
        f = h - h_prev - dt * (input_rate_m_s - alpha_m_2_3_s * h_53)
        df = 1.0 + dt * alpha_m_2_3_s * (5.0 / 3.0) * (h_eps ** (2.0 / 3.0))
        if abs(df) < 1e-15:
            break
        h_new = h - f / df
        h_new = max(0.0, h_new)
        if abs(h_new - h) <= tol:
            h = h_new
            break
        h = h_new
    return max(0.0, h)


def run_simulation(
    dt: float,
    chuva_mmh: np.ndarray,
    ac_df: pd.DataFrame,
    exutorio_id: int,
    b_canal: float,
    s_canal: float,
    n_canal: float,
    nivel_base: float,
    usar_horton: bool = False,
    horton_k_h_inv: float = 2.5,
    horton_f0_multiplicador: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    n_steps = len(chuva_mmh)
    tempo_s = np.arange(n_steps) * dt
    chuva_ms = chuva_mmh / 3600000.0

    ac_df = ordenar_ac_topologicamente(ac_df)
    n_ac = len(ac_df)
    ac_ids = ac_df["ID_AC"].tolist()
    id_to_idx = {ac_id: i for i, ac_id in enumerate(ac_ids)}

    h = np.zeros((n_steps, n_ac), dtype=float)
    q_out = np.zeros((n_steps, n_ac), dtype=float)
    q_in = np.zeros((n_steps, n_ac), dtype=float)
    i_excesso = np.zeros((n_steps, n_ac), dtype=float)
    infil_real = np.zeros((n_steps, n_ac), dtype=float)
    t_umido_s = np.zeros(n_ac, dtype=float)

    for j, row in ac_df.iterrows():
        h[0, j] = max(float(row["h0_m"]), 0.0)

    for t in range(n_steps):
        for j, row in ac_df.iterrows():
            area = max(float(row["Area_m2"]), 1e-9)
            comp = max(float(row["L_m"]), 1e-9)
            n_eq = max(float(row["n_eq"]), 1e-9)
            infil_fc_mmh = max(float(row["Infiltracao_eq_mm_h"]), 0.0)
            decliv = max(float(row["S_m_m"]), 1e-9)
            w_eq = area / comp

            h_prev = h[t, j] if t == 0 else h[t - 1, j]
            if usar_horton and chuva_mmh[t] > 0:
                t_umido_s[j] += dt
            t_umido_h = t_umido_s[j] / 3600.0

            if usar_horton:
                infil_f0_mmh = max(infil_fc_mmh * max(horton_f0_multiplicador, 1.0), infil_fc_mmh)
                infil_cap_mmh = infil_fc_mmh + (infil_f0_mmh - infil_fc_mmh) * math.exp(
                    -max(horton_k_h_inv, 0.0) * t_umido_h
                )
            else:
                infil_cap_mmh = infil_fc_mmh
            infil_t_ms = min(chuva_ms[t], infil_cap_mmh / 3600000.0)
            infil_real[t, j] = infil_t_ms

            i_eff = max(chuva_ms[t] - infil_t_ms, 0.0)
            i_excesso[t, j] = i_eff

            upstream_ids = parse_upstream_ids(row["ACs_montante_ids"])
            qin_t = 0.0
            for up_id in upstream_ids:
                if up_id in id_to_idx:
                    qin_t += q_out[t, id_to_idx[up_id]]
            q_in[t, j] = qin_t

            alpha = (w_eq / area) * (1.0 / n_eq) * math.sqrt(decliv)
            input_rate = i_eff + qin_t / area
            h_new = solve_surface_depth_implicit(
                h_prev=h_prev,
                dt=dt,
                input_rate_m_s=input_rate,
                alpha_m_2_3_s=alpha,
            )
            q_unit_new = (1.0 / n_eq) * (h_new ** (5.0 / 3.0)) * math.sqrt(decliv)
            qout_t = q_unit_new * w_eq
            q_out[t, j] = qout_t
            h[t, j] = h_new

    if exutorio_id not in id_to_idx:
        exutorio_id = ac_ids[-1]

    q_ex = q_out[:, id_to_idx[exutorio_id]]
    nivel = solve_channel_depth(q_ex, b_canal, s_canal, n_canal, n_iter=5)
    cota = nivel + nivel_base

    df_saida = pd.DataFrame(
        {
            "Passo": np.arange(n_steps),
            "Tempo_s": tempo_s,
            "P_mm_h": chuva_mmh,
            "P_m_s": chuva_ms,
            "Q_ex_m3_s": q_ex,
            "Nivel_m": nivel,
            "Cota_abs_m": cota,
        }
    )

    registros = []
    for j, ac_id in enumerate(ac_ids):
        df_ac = pd.DataFrame(
            {
                "Passo": np.arange(n_steps),
                "Tempo_s": tempo_s,
                "ID_AC": ac_id,
                "i_excesso_m_s": i_excesso[:, j],
                "Infiltracao_real_m_s": infil_real[:, j],
                "Q_in_m3_s": q_in[:, j],
                "Q_out_m3_s": q_out[:, j],
                "h_m": h[:, j],
            }
        )
        registros.append(df_ac)
    df_ac_detalhe = pd.concat(registros, ignore_index=True)
    return df_saida, df_ac_detalhe


def calcular_parametros_equivalentes_por_us(ac_df: pd.DataFrame, us_df: pd.DataFrame) -> pd.DataFrame:
    ac_out = ac_df.copy()
    us_work = us_df.copy()
    us_work["ID_AC"] = pd.to_numeric(us_work["ID_AC"], errors="coerce")
    us_work["Area_US_m2"] = pd.to_numeric(us_work["Area_US_m2"], errors="coerce")
    us_work["Infiltracao_US_mm_h"] = pd.to_numeric(us_work["Infiltracao_US_mm_h"], errors="coerce")
    us_work["n_US"] = pd.to_numeric(us_work["n_US"], errors="coerce")
    us_work = us_work.dropna(subset=["ID_AC", "Area_US_m2", "Infiltracao_US_mm_h", "n_US"])

    for i, row in ac_out.iterrows():
        ac_id = int(row["ID_AC"])
        area_ac = float(row["Area_m2"])
        us_ac = us_work[us_work["ID_AC"].astype(int) == ac_id]
        if us_ac.empty or area_ac <= 0:
            continue
        infil_eq = float((us_ac["Area_US_m2"] * us_ac["Infiltracao_US_mm_h"]).sum() / area_ac)
        n_eq = float((us_ac["Area_US_m2"] * us_ac["n_US"]).sum() / area_ac)
        ac_out.loc[i, "Infiltracao_eq_mm_h"] = infil_eq
        ac_out.loc[i, "n_eq"] = n_eq
    return ac_out


def nash_sutcliffe_efficiency(obs: np.ndarray, sim: np.ndarray) -> float:
    obs = np.asarray(obs, dtype=float)
    sim = np.asarray(sim, dtype=float)
    mask = np.isfinite(obs) & np.isfinite(sim)
    obs, sim = obs[mask], sim[mask]
    if len(obs) < 2:
        return float("nan")
    den = float(np.sum((obs - np.mean(obs)) ** 2))
    if den < 1e-30:
        return float("nan")
    return 1.0 - float(np.sum((obs - sim) ** 2)) / den


def r2_pearson(obs: np.ndarray, sim: np.ndarray) -> float:
    obs = np.asarray(obs, dtype=float)
    sim = np.asarray(sim, dtype=float)
    mask = np.isfinite(obs) & np.isfinite(sim)
    obs, sim = obs[mask], sim[mask]
    if len(obs) < 2:
        return float("nan")
    r = np.corrcoef(obs, sim)[0, 1]
    return float(r**2) if np.isfinite(r) else float("nan")


def rmse(obs: np.ndarray, sim: np.ndarray) -> float:
    obs = np.asarray(obs, dtype=float)
    sim = np.asarray(sim, dtype=float)
    mask = np.isfinite(obs) & np.isfinite(sim)
    obs, sim = obs[mask], sim[mask]
    if len(obs) < 1:
        return float("nan")
    return float(np.sqrt(np.mean((obs - sim) ** 2)))


def mae(obs: np.ndarray, sim: np.ndarray) -> float:
    obs = np.asarray(obs, dtype=float)
    sim = np.asarray(sim, dtype=float)
    mask = np.isfinite(obs) & np.isfinite(sim)
    obs, sim = obs[mask], sim[mask]
    if len(obs) < 1:
        return float("nan")
    return float(np.mean(np.abs(obs - sim)))


def vies_medio(obs: np.ndarray, sim: np.ndarray) -> float:
    """Vies medio = mean(sim - obs)."""
    obs = np.asarray(obs, dtype=float)
    sim = np.asarray(sim, dtype=float)
    mask = np.isfinite(obs) & np.isfinite(sim)
    obs, sim = obs[mask], sim[mask]
    if len(obs) < 1:
        return float("nan")
    return float(np.mean(sim - obs))


def montar_df_validacao(df_saida: pd.DataFrame, df_obs_antigo: pd.DataFrame | None) -> pd.DataFrame:
    out = df_saida[["Passo", "Tempo_s"]].copy()
    out["Nivel_sim_m"] = df_saida["Nivel_m"].values
    if df_obs_antigo is not None and "Tempo_s" in df_obs_antigo.columns and "Nivel_obs_m" in df_obs_antigo.columns:
        old = df_obs_antigo[["Tempo_s", "Nivel_obs_m"]].drop_duplicates(subset=["Tempo_s"])
        out = out.merge(old, on="Tempo_s", how="left")
    else:
        out["Nivel_obs_m"] = np.nan
    return out


def _montar_grade_parametros(vmin: float, vmax: float, passo: float) -> np.ndarray:
    vmin = float(vmin)
    vmax = float(vmax)
    passo = float(passo)
    if passo <= 0:
        raise ValueError("Passo deve ser maior que zero.")
    if vmax < vmin:
        raise ValueError("Valor maximo deve ser maior ou igual ao minimo.")
    n = int(math.floor((vmax - vmin) / passo + 1e-12)) + 1
    vals = vmin + np.arange(n, dtype=float) * passo
    vals = np.round(vals, 10)
    if vals[-1] < vmax - 1e-9:
        vals = np.append(vals, vmax)
    return vals


def calibrar_horton_em_grade(
    df_obs: pd.DataFrame,
    dt_seg: float,
    chuva_mmh: np.ndarray,
    ac_df: pd.DataFrame,
    exutorio_id: int,
    b_canal: float,
    s_canal: float,
    n_canal: float,
    nivel_base: float,
    k_vals: np.ndarray,
    f0fc_vals: np.ndarray,
) -> pd.DataFrame:
    if df_obs is None or df_obs.empty:
        return pd.DataFrame()

    obs_base = df_obs[["Tempo_s", "Nivel_obs_m"]].copy()
    obs_base["Tempo_s"] = pd.to_numeric(obs_base["Tempo_s"], errors="coerce")
    obs_base["Nivel_obs_m"] = pd.to_numeric(obs_base["Nivel_obs_m"], errors="coerce")
    obs_base = obs_base.dropna(subset=["Tempo_s", "Nivel_obs_m"]).drop_duplicates(subset=["Tempo_s"])
    if len(obs_base) < 2:
        return pd.DataFrame()

    registros = []
    for k_h in k_vals:
        for f0fc in f0fc_vals:
            df_saida_k, _ = run_simulation(
                dt=float(dt_seg),
                chuva_mmh=chuva_mmh,
                ac_df=ac_df,
                exutorio_id=int(exutorio_id),
                b_canal=float(b_canal),
                s_canal=float(s_canal),
                n_canal=float(n_canal),
                nivel_base=float(nivel_base),
                usar_horton=True,
                horton_k_h_inv=float(k_h),
                horton_f0_multiplicador=float(f0fc),
            )
            df_cmp = obs_base.merge(
                df_saida_k[["Tempo_s", "Nivel_m"]].rename(columns={"Nivel_m": "Nivel_sim_m"}),
                on="Tempo_s",
                how="left",
            )
            df_cmp = df_cmp.dropna(subset=["Nivel_sim_m"])
            if len(df_cmp) < 2:
                continue

            obs = df_cmp["Nivel_obs_m"].astype(float).values
            sim = df_cmp["Nivel_sim_m"].astype(float).values
            nse = nash_sutcliffe_efficiency(obs, sim)
            r2 = r2_pearson(obs, sim)
            err_rmse = rmse(obs, sim)
            err_mae = mae(obs, sim)
            vb = vies_medio(obs, sim)

            i_obs_peak = int(np.argmax(obs))
            i_sim_peak = int(np.argmax(sim))
            pico_obs = float(obs[i_obs_peak])
            pico_sim = float(sim[i_sim_peak])
            tempo_obs_peak = float(df_cmp["Tempo_s"].iloc[i_obs_peak])
            tempo_sim_peak = float(df_cmp["Tempo_s"].iloc[i_sim_peak])
            erro_pico_pct = float(100.0 * (pico_sim - pico_obs) / pico_obs) if abs(pico_obs) > 1e-12 else float("nan")
            erro_tempo_pico_min = float((tempo_sim_peak - tempo_obs_peak) / 60.0)

            score_nse_pico = (
                (1.0 - nse if np.isfinite(nse) else 9_999.0)
                + abs(erro_pico_pct) / 100.0
            )

            registros.append(
                {
                    "k_h_inv": float(k_h),
                    "f0_fc": float(f0fc),
                    "NSE": float(nse) if np.isfinite(nse) else np.nan,
                    "R2": float(r2) if np.isfinite(r2) else np.nan,
                    "RMSE_m": float(err_rmse) if np.isfinite(err_rmse) else np.nan,
                    "MAE_m": float(err_mae) if np.isfinite(err_mae) else np.nan,
                    "Vies_m": float(vb) if np.isfinite(vb) else np.nan,
                    "Pico_obs_m": pico_obs,
                    "Pico_sim_m": pico_sim,
                    "Erro_pico_pct": erro_pico_pct,
                    "Erro_tempo_pico_min": erro_tempo_pico_min,
                    "Score_nse_pico": float(score_nse_pico),
                }
            )

    if not registros:
        return pd.DataFrame()
    out = pd.DataFrame(registros)
    out = out.sort_values(by=["Score_nse_pico", "NSE", "Erro_pico_pct"], ascending=[True, False, True]).reset_index(
        drop=True
    )
    return out


if "sim_store_loaded" not in st.session_state:
    store = carregar_simulacoes_salvas()
    st.session_state["sim_store"] = store
    st.session_state["sim_store_loaded"] = True
    st.session_state["titulo_salvar"] = ""
    if store.get("last_id"):
        last = next((x for x in store.get("items", []) if x.get("id") == store.get("last_id")), None)
        if last is not None:
            aplicar_payload_em_session(last)

if "pending_page" not in st.session_state:
    st.session_state["pending_page"] = None

if st.session_state.get("pending_page") is not None:
    st.session_state["pagina_menu"] = st.session_state["pending_page"]
    st.session_state["pending_page"] = None

with st.sidebar:
    st.header("Menu")
    pagina = st.radio(
        "Navegar",
        [
            "Simulacao",
            "Simulacoes salvas",
            "Validacao",
            "Sugestao de calibracao",
            "Instrucoes",
            "Descricao das variaveis",
        ],
        label_visibility="collapsed",
        key="pagina_menu",
    )

if pagina == "Sugestao de calibracao":
    st.title("Sugestao de calibracao")
    st.caption(
        "Valores de referencia para **infiltracao (mm/h)** e **Manning (n)** na superficie (US) e **n do canal**. "
        "Sao ordens de magnitude para eventos urbanos; calibre com dados locais e validacao."
    )
    st.info(
        "Use estas tabelas como **ponto de partida** na aba **Simulacao** (campos US e `n_canal`). "
        "Ajuste dentro das faixas conforme solo, declividade, estado de conservacao e comparacao com observacoes."
    )

    st.subheader("Uso e ocupacao do solo (superficie — plano inclinado)")
    df_us = pd.DataFrame(CALIBRACAO_USO_SOLO)
    st.dataframe(
        df_us,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Classe": st.column_config.TextColumn("Classe", width="medium"),
            "Exemplos": st.column_config.TextColumn("Exemplos", width="large"),
            "Infil_sugerida_mm_h": st.column_config.NumberColumn("Infil. sugerida (mm/h)", format="%.2f"),
            "Infil_min_mm_h": st.column_config.NumberColumn("Infil. min (mm/h)", format="%.2f"),
            "Infil_max_mm_h": st.column_config.NumberColumn("Infil. max (mm/h)", format="%.2f"),
            "n_sugerido": st.column_config.NumberColumn("n sugerido", format="%.3f"),
            "n_min": st.column_config.NumberColumn("n min", format="%.3f"),
            "n_max": st.column_config.NumberColumn("n max", format="%.3f"),
        },
    )

    st.subheader("Canal (coeficiente de Manning do revestimento)")
    df_canal = pd.DataFrame(CALIBRACAO_CANAL_MANNING)
    st.dataframe(
        df_canal,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Tipo_revestimento": st.column_config.TextColumn("Tipo de revestimento", width="large"),
            "n_sugerido": st.column_config.NumberColumn("n sugerido", format="%.3f"),
            "n_min": st.column_config.NumberColumn("n min", format="%.3f"),
            "n_max": st.column_config.NumberColumn("n max", format="%.3f"),
            "Notas": st.column_config.TextColumn("Notas", width="large"),
        },
    )

    st.markdown(
        """
**Referencias usadas para sugerir faixas (valores iniciais de calibracao):**

- **Chow, V. T. (1959)** — *Open-Channel Hydraulics* (faixas classicas de `n` de Manning para canais e superficies).
- **USDA-SCS / NRCS** — manuais hidrologicos e parametros de infiltracao para diferentes coberturas e condicoes de solo.
- **Tucci, C. E. M.** (drenagem urbana, edicoes diversas) — comportamento hidrologico em bacias urbanas brasileiras e uso de parametros de superficie.
- **Akan, A. O. & Houghtalen, R. J.** — *Urban Hydrology, Hydraulics, and Stormwater Quality* (parametros tipicos em drenagem urbana).

**Nota tecnica:** estes valores sao **pontos de partida** para evento unico; devem ser ajustados por calibracao local (chuva-vazao/nivel observado), considerando compactacao, saturacao antecedente, declividade, cobertura vegetal e estado de conservacao das superficies/canais.
        """
    )

elif pagina == "Instrucoes":
    st.title("Instrucoes de uso")
    st.markdown(
        """
### Fluxo recomendado

1. **Configuracao** (barra lateral): defina `Delta t` e a duracao total da chuva em minutos.
2. **Parametros do canal**: largura, declividade, Manning e nivel de base (cota opcional).
3. **Areas de contribuicao (AC)**: informe geometria, declividade, montantes (`ACs_montante_ids` com IDs separados por `;`) e lamina inicial `h0_m`.
4. **Unidades de uso do solo (US)**: preencha areas e parametros por classe. Com a opcao automatica ativada, `Infiltracao_eq_mm_h` e `n_eq` sao calculados por media ponderada pela area da AC.
5. **Chuva**: edite `P_mm_h` por passo. O passo inicial (`t = 0`) pode ser zero; a chuva efetiva costuma comecar no passo seguinte, conforme seu evento.
6. Clique em **Rodar simulacao** e visualize os hidrogramas de nivel e vazao. Baixe os resultados em Excel se desejar.
7. Aba **Validacao**: informe niveis medidos em campo (grade ou CSV) e compare com a serie simulada (NSE, R2, RMSE, etc.).
8. Aba **Sugestao de calibracao**: consulte faixas de infiltracao, n na superficie e n do canal antes de preencher a simulacao.

### Observacoes

- O modelo usa passo de tempo discreto e evento unico de chuva.
- A propagacao superficial usa Manning em plano inclinado; a conversao para nivel no canal usa Manning em secao retangular.
- Se alterar `Numero de ACs`, recarregue a pagina se necessario para atualizar linhas padrao das US.
        """
    )

elif pagina == "Descricao das variaveis":
    st.title("Descricao das variaveis e termos")
    st.caption("Tabela de referencia alinhada a metodologia do modelo.")
    st.dataframe(
        pd.DataFrame(GLOSSARIO_ROWS),
        use_container_width=True,
        hide_index=True,
    )

elif pagina == "Simulacoes salvas":
    st.title("Simulacoes salvas")
    st.caption("Carregue, exclua e reutilize simulacoes anteriores.")

    store = st.session_state.get("sim_store", {"last_id": None, "items": []})
    items = store.get("items", [])
    if not items:
        st.info("Nenhuma simulacao salva ainda. Salve uma simulacao na aba **Simulacao**.")
    else:
        for item in sorted(items, key=lambda x: x.get("created_at", ""), reverse=True):
            titulo = item.get("titulo", "Sem titulo")
            created = item.get("created_at", "")
            with st.container(border=True):
                st.markdown(f"**{titulo}**")
                st.caption(f"Criada em: {created}")
                c1, c2 = st.columns(2)
                if c1.button("Usar nesta simulacao", key=f"load_{item.get('id')}"):
                    aplicar_payload_em_session(item)
                    st.session_state["sim_store"]["last_id"] = item.get("id")
                    salvar_simulacoes_salvas(st.session_state["sim_store"])
                    st.session_state["pending_page"] = "Simulacao"
                    st.rerun()
                if c2.button("Excluir", key=f"del_{item.get('id')}"):
                    st.session_state["sim_store"]["items"] = [
                        x for x in st.session_state["sim_store"]["items"] if x.get("id") != item.get("id")
                    ]
                    if st.session_state["sim_store"].get("last_id") == item.get("id"):
                        st.session_state["sim_store"]["last_id"] = None
                    salvar_simulacoes_salvas(st.session_state["sim_store"])
                    st.rerun()

elif pagina == "Validacao":
    st.title("Validacao: nivel observado vs simulado")
    st.caption(
        "Compare niveis medidos em campo com a serie simulada no exutorio. "
        "O Nash-Sutcliffe (NSE) e o mesmo indicador frequentemente chamado de Nash."
    )

    df_sim = st.session_state.get("df_saida_validacao")
    if df_sim is None:
        st.warning(
            "Nenhuma simulacao disponivel. Va em **Simulacao**, preencha os dados e clique em **Rodar simulacao**."
        )
    else:
        st.info(
            f"Serie simulada carregada: **{len(df_sim)}** passos. "
            "Unidade de nivel: metros (mesma referencia do modelo)."
        )

        tab_manual, tab_csv = st.tabs(["Entrada manual na grade", "Importar CSV"])

        with tab_manual:
            prev = st.session_state.get("df_validacao_obs")
            base_val = df_sim[["Passo", "Tempo_s"]].copy()
            base_val["Nivel_sim_m"] = df_sim["Nivel_m"].values
            df_val = base_val.copy()
            df_val["Nivel_obs_m"] = np.nan

            if isinstance(prev, pd.DataFrame) and "Nivel_obs_m" in prev.columns:
                prev_work = prev.copy()
                prev_work["Nivel_obs_m"] = pd.to_numeric(prev_work["Nivel_obs_m"], errors="coerce")
                if "Tempo_s" in prev_work.columns:
                    prev_work["Tempo_s"] = pd.to_numeric(prev_work["Tempo_s"], errors="coerce")
                    obs_old = prev_work[["Tempo_s", "Nivel_obs_m"]].drop_duplicates(subset=["Tempo_s"])
                    df_val = base_val.merge(obs_old, on="Tempo_s", how="left")
                else:
                    n_copy = min(len(df_val), len(prev_work))
                    if n_copy > 0:
                        df_val.loc[: n_copy - 1, "Nivel_obs_m"] = prev_work.iloc[:n_copy]["Nivel_obs_m"].values
            df_edit = st.data_editor(
                df_val,
                num_rows="fixed",
                use_container_width=True,
                hide_index=True,
                disabled=["Passo", "Tempo_s", "Nivel_sim_m"],
                column_config={
                    "Nivel_obs_m": st.column_config.NumberColumn(
                        "Nivel observado (m)",
                        help="Medicao de campo no mesmo instante de Tempo_s (deixe vazio para ignorar o passo nas metricas).",
                        format="%.4f",
                    ),
                },
                key="editor_validacao_manual",
            )
            st.session_state["df_validacao_obs"] = df_edit.copy()

        with tab_csv:
            st.markdown(
                "Arquivo **CSV** com colunas `Tempo_s` e `Nivel_obs_m` (opcional: `Passo`). "
                "Valores separados por virgula ou ponto e virgula."
            )
            up = st.file_uploader("Carregar CSV de niveis observados", type=["csv"])
            if up is not None:
                try:
                    raw = up.read()
                    df_up = None
                    for sep in [";", ",", "\t"]:
                        try:
                            df_try = pd.read_csv(BytesIO(raw), sep=sep)
                            if len(df_try.columns) >= 2:
                                df_up = df_try
                                break
                        except Exception:
                            continue
                    if df_up is None:
                        df_up = pd.read_csv(BytesIO(raw))

                    df_up.columns = [c.strip() for c in df_up.columns]
                    if "Tempo_s" not in df_up.columns and "tempo_s" in df_up.columns:
                        df_up = df_up.rename(columns={"tempo_s": "Tempo_s"})
                    if "Nivel_obs_m" not in df_up.columns:
                        for cand in ["Nivel_obs_m", "nivel_obs", "Nivel_obs", "obs", "y"]:
                            if cand in df_up.columns:
                                df_up = df_up.rename(columns={cand: "Nivel_obs_m"})
                                break

                    if "Tempo_s" not in df_up.columns or "Nivel_obs_m" not in df_up.columns:
                        st.error("O CSV precisa ter colunas Tempo_s e Nivel_obs_m (ou nomes equivalentes).")
                    else:
                        df_up["Tempo_s"] = pd.to_numeric(df_up["Tempo_s"], errors="coerce")
                        df_up["Nivel_obs_m"] = pd.to_numeric(df_up["Nivel_obs_m"], errors="coerce")
                        df_up = df_up.dropna(subset=["Tempo_s", "Nivel_obs_m"])
                        base = df_sim[["Passo", "Tempo_s"]].copy()
                        base["Nivel_sim_m"] = df_sim["Nivel_m"].values
                        merged = base.merge(
                            df_up[["Tempo_s", "Nivel_obs_m"]].drop_duplicates(subset=["Tempo_s"]),
                            on="Tempo_s",
                            how="left",
                        )
                        st.session_state["df_validacao_obs"] = merged
                        st.success(f"Importados {len(df_up)} pontos; alinhados por Tempo_s a grade da simulacao.")
                except Exception as exc:
                    st.error(f"Erro ao ler CSV: {exc}")

        df_obs = st.session_state.get("df_validacao_obs")
        if df_obs is not None and "Nivel_obs_m" in df_obs.columns and "Nivel_sim_m" in df_obs.columns:
            mask = df_obs["Nivel_obs_m"].notna()
            n_valid = int(mask.sum())
            calibracao_habilitada = n_valid >= 2

            if not calibracao_habilitada:
                st.warning("Informe pelo menos **2** valores de nivel observado para calcular metricas e habilitar a calibracao.")
            else:
                obs = df_obs.loc[mask, "Nivel_obs_m"].astype(float).values
                sim = df_obs.loc[mask, "Nivel_sim_m"].astype(float).values

                nse = nash_sutcliffe_efficiency(obs, sim)
                r2 = r2_pearson(obs, sim)
                err_rmse = rmse(obs, sim)
                err_mae = mae(obs, sim)
                vb = vies_medio(obs, sim)

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("NSE (Nash-Sutcliffe)", f"{nse:.4f}")
                m2.metric("R2 (Pearson)", f"{r2:.4f}")
                m3.metric("RMSE (m)", f"{err_rmse:.4f}")
                m4.metric("MAE (m)", f"{err_mae:.4f}")
                st.metric("Vies medio (sim - obs) (m)", f"{vb:.4f}")
                st.caption("Vies medio: media de (simulado - observado) nos passos com observacao.")

            st.divider()
            st.subheader("Calibracao automatica (grade Horton)")
            st.caption(
                "Varre combinacoes de `k` e `f0/fc`, simula novamente e ranqueia automaticamente por `Score_nse_pico = (1 - NSE) + |erro_pico_pct|/100`."
            )

            c1, c2, c3 = st.columns(3)
            k_min = c1.number_input("k min (1/h)", min_value=0.0, value=1.0, step=0.1, key="cal_k_min")
            k_max = c2.number_input("k max (1/h)", min_value=0.0, value=5.0, step=0.1, key="cal_k_max")
            k_step = c3.number_input("k passo", min_value=0.1, value=0.5, step=0.1, key="cal_k_step")

            c4, c5, c6 = st.columns(3)
            f_min = c4.number_input("f0/fc min", min_value=1.0, value=1.0, step=0.1, key="cal_f_min")
            f_max = c5.number_input("f0/fc max", min_value=1.0, value=3.0, step=0.1, key="cal_f_max")
            f_step = c6.number_input("f0/fc passo", min_value=0.1, value=0.2, step=0.1, key="cal_f_step")

            top_n = st.number_input("Top resultados exibidos", min_value=3, max_value=50, value=10, step=1, key="cal_top_n")

            if st.button(
                "Rodar calibracao automatica",
                key="btn_calibracao_horton",
                disabled=not calibracao_habilitada,
                help="Disponivel apos informar pelo menos 2 niveis observados validos.",
            ):
                try:
                    k_vals = _montar_grade_parametros(float(k_min), float(k_max), float(k_step))
                    f_vals = _montar_grade_parametros(float(f_min), float(f_max), float(f_step))
                    n_comb = int(len(k_vals) * len(f_vals))
                    if n_comb > 500:
                        st.error(
                            f"Foram solicitadas {n_comb} combinacoes. Reduza as faixas/passos para no maximo 500."
                        )
                    else:
                        ac_loaded = st.session_state.get("ac_df_loaded")
                        chuva_loaded = st.session_state.get("chuva_df_loaded")
                        if ac_loaded is None or chuva_loaded is None or len(ac_loaded) == 0 or len(chuva_loaded) == 0:
                            st.error("Dados de simulacao nao encontrados. Rode a simulacao novamente antes de calibrar.")
                        else:
                            ac_cal = ac_loaded.copy()
                            ac_cal["ID_AC"] = pd.to_numeric(ac_cal["ID_AC"], errors="coerce").astype(int)
                            for col in ["Area_m2", "L_m", "S_m_m", "h0_m", "Infiltracao_eq_mm_h", "n_eq"]:
                                ac_cal[col] = pd.to_numeric(ac_cal[col], errors="coerce").astype(float)

                            chuva_cal = (
                                pd.to_numeric(chuva_loaded["P_mm_h"], errors="coerce").astype(float).to_numpy()
                            )
                            df_rank = calibrar_horton_em_grade(
                                df_obs=df_obs,
                                dt_seg=float(st.session_state.get("dt_seg", 600)),
                                chuva_mmh=chuva_cal,
                                ac_df=ac_cal,
                                exutorio_id=int(st.session_state.get("exutorio_id", int(ac_cal["ID_AC"].max()))),
                                b_canal=float(st.session_state.get("b_canal", 4.0)),
                                s_canal=float(st.session_state.get("s_canal", 0.004)),
                                n_canal=float(st.session_state.get("n_canal", 0.018)),
                                nivel_base=float(st.session_state.get("nivel_base", 0.2)),
                                k_vals=k_vals,
                                f0fc_vals=f_vals,
                            )
                            if df_rank.empty:
                                st.error("Nao foi possivel calibrar: sem pontos observados suficientes apos alinhamento por Tempo_s.")
                            else:
                                st.session_state["df_calibracao_horton"] = df_rank
                                st.success(
                                    f"Calibracao concluida com {len(df_rank)} combinacoes validas."
                                )
                except Exception as exc:
                    st.error(f"Erro na calibracao automatica: {exc}")

            df_rank = st.session_state.get("df_calibracao_horton")
            if isinstance(df_rank, pd.DataFrame) and not df_rank.empty:
                st.markdown("**Melhor combinacao encontrada**")
                best = df_rank.iloc[0]
                cbest1, cbest2, cbest3, cbest4 = st.columns(4)
                cbest1.metric("k (1/h)", f"{best['k_h_inv']:.3f}")
                cbest2.metric("f0/fc", f"{best['f0_fc']:.3f}")
                cbest3.metric("NSE", f"{best['NSE']:.4f}")
                cbest4.metric("Score NSE+pico", f"{best['Score_nse_pico']:.4f}")
                st.metric("Erro de pico (%)", f"{best['Erro_pico_pct']:.2f}")

                st.dataframe(
                    df_rank.head(int(top_n)),
                    use_container_width=True,
                    hide_index=True,
                )

                if st.button("Aplicar melhor conjunto e re-simular", key="btn_aplicar_calibracao_horton"):
                    try:
                        st.session_state["horton_k_h_inv"] = float(best["k_h_inv"])
                        st.session_state["horton_f0_multiplicador"] = float(best["f0_fc"])

                        ac_ap = st.session_state.get("ac_df_loaded").copy()
                        ac_ap["ID_AC"] = pd.to_numeric(ac_ap["ID_AC"], errors="coerce").astype(int)
                        for col in ["Area_m2", "L_m", "S_m_m", "h0_m", "Infiltracao_eq_mm_h", "n_eq"]:
                            ac_ap[col] = pd.to_numeric(ac_ap[col], errors="coerce").astype(float)
                        chuva_ap = (
                            pd.to_numeric(st.session_state.get("chuva_df_loaded")["P_mm_h"], errors="coerce")
                            .astype(float)
                            .to_numpy()
                        )
                        df_saida_best, _ = run_simulation(
                            dt=float(st.session_state.get("dt_seg", 600)),
                            chuva_mmh=chuva_ap,
                            ac_df=ac_ap,
                            exutorio_id=int(st.session_state.get("exutorio_id", int(ac_ap["ID_AC"].max()))),
                            b_canal=float(st.session_state.get("b_canal", 4.0)),
                            s_canal=float(st.session_state.get("s_canal", 0.004)),
                            n_canal=float(st.session_state.get("n_canal", 0.018)),
                            nivel_base=float(st.session_state.get("nivel_base", 0.2)),
                            usar_horton=True,
                            horton_k_h_inv=float(best["k_h_inv"]),
                            horton_f0_multiplicador=float(best["f0_fc"]),
                        )
                        st.session_state["df_saida_validacao"] = df_saida_best.copy()
                        st.session_state["df_validacao_obs"] = montar_df_validacao(
                            df_saida_best, st.session_state.get("df_validacao_obs")
                        )
                        st.success(
                            "Melhor conjunto aplicado. Serie simulada da validacao foi atualizada com os novos parametros."
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Erro ao aplicar melhor conjunto: {exc}")

            if calibracao_habilitada:
                st.subheader("Grafico comparativo")
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=df_obs["Tempo_s"],
                        y=df_obs["Nivel_sim_m"],
                        name="Nivel simulado",
                        mode="lines",
                        line=dict(color="#1f77b4", width=2),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=df_obs.loc[mask, "Tempo_s"],
                        y=obs,
                        name="Nivel observado",
                        mode="markers+lines",
                        line=dict(color="#d62728", dash="dot"),
                        marker=dict(size=8),
                    )
                )
                fig.update_layout(
                    title="Nivel no canal: observado vs simulado",
                    xaxis_title="Tempo (s)",
                    yaxis_title="Nivel (m)",
                    legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
                )
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("Tabela de comparacao (passos com observacao)")
                st.dataframe(
                    df_obs.loc[mask].reset_index(drop=True),
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.divider()
            st.subheader("Calibracao automatica (grade Horton)")
            st.caption(
                "Preencha dados observados na grade ou via CSV para habilitar a calibracao automatica."
            )
            st.button(
                "Rodar calibracao automatica",
                key="btn_calibracao_horton_sem_dados",
                disabled=True,
                help="Disponivel apos informar pelo menos 2 niveis observados validos.",
            )

else:
    st.title("Modelo Hidrologico Urbano - Escoamento e Nivel no Canal")
    st.caption("Versao web local para simulacao de evento unico de chuva-vazao.")

    # Defaults (ou ultimo salvo carregado)
    st.session_state.setdefault("dt_seg", 600)
    st.session_state.setdefault("duracao_min", 40)
    st.session_state.setdefault("b_canal", 4.0)
    st.session_state.setdefault("s_canal", 0.004)
    st.session_state.setdefault("n_canal", 0.018)
    st.session_state.setdefault("nivel_base", 0.2)
    st.session_state.setdefault("usar_horton", False)
    st.session_state.setdefault("horton_k_h_inv", 2.5)
    st.session_state.setdefault("horton_f0_multiplicador", 1.0)
    st.session_state.setdefault("n_ac", 3)
    st.session_state.setdefault("exutorio_id", 3)
    st.session_state.setdefault("usar_us_para_eq", True)
    st.session_state.setdefault("titulo_salvar", "")
    st.session_state.setdefault("hora_inicio_evento", "12:00")
    st.session_state.setdefault("hora_fim_evento", "12:40")
    st.session_state.setdefault("_clear_sim_requested", False)
    st.session_state.setdefault("_show_clear_notice", False)

    if st.session_state.get("_clear_sim_requested"):
        st.session_state["ac_df_loaded"] = pd.DataFrame(
            columns=["ID_AC", "Area_m2", "L_m", "S_m_m", "ACs_montante_ids", "h0_m", "Infiltracao_eq_mm_h", "n_eq"]
        )
        st.session_state["us_df_loaded"] = pd.DataFrame(
            columns=["ID_AC", "ID_US", "Classe_US", "Area_US_m2", "Infiltracao_US_mm_h", "n_US"]
        )
        st.session_state["chuva_df_loaded"] = pd.DataFrame(columns=["Passo", "Tempo_s", "P_mm_h"])
        st.session_state["titulo_salvar"] = ""
        st.session_state["hora_inicio_evento"] = "12:00"
        st.session_state["hora_fim_evento"] = "12:40"
        # Limpa estado interno dos widgets antes de renderizar novamente.
        st.session_state.pop("editor_ac", None)
        st.session_state.pop("editor_us", None)
        st.session_state.pop("editor_chuva", None)
        st.session_state["_clear_sim_requested"] = False
        st.session_state["_show_clear_notice"] = True

    if st.session_state.get("_show_clear_notice"):
        st.info("Campos da simulacao limpos. Preencha novamente para iniciar do zero.")
        st.session_state["_show_clear_notice"] = False

    with st.sidebar:
        st.header("Configuracao")
        dt_seg = st.number_input("Delta t (s)", min_value=60, step=60, key="dt_seg")
        duracao_min = st.number_input("Duracao da chuva (min)", min_value=10, step=10, key="duracao_min")
        st.divider()
        usar_horton = st.checkbox("Usar infiltracao variavel (Horton)", key="usar_horton")
        if usar_horton:
            st.caption("Modo avancado de infiltracao para calibracao.")
            horton_k_h_inv = st.number_input("k de Horton (1/h)", min_value=0.0, step=0.1, key="horton_k_h_inv")
            horton_f0_multiplicador = st.number_input(
                "f0/fc de Horton", min_value=1.0, step=0.1, key="horton_f0_multiplicador"
            )
        else:
            st.caption("Modo metodologia: infiltracao constante por US/AC.")
            horton_k_h_inv = float(st.session_state.get("horton_k_h_inv", 2.5))
            horton_f0_multiplicador = float(st.session_state.get("horton_f0_multiplicador", 1.0))
        n_passos = int(math.ceil((duracao_min * 60) / dt_seg) + 1)
        st.write(f"Passos ativos: {n_passos} (inclui t=0)")

    st.subheader("1) Parametros do canal")
    col1, col2, col3, col4 = st.columns(4)
    b_canal = col1.number_input("B_canal (m)", min_value=0.1, key="b_canal")
    s_canal = col2.number_input("S_canal (m/m)", min_value=0.0001, format="%.4f", key="s_canal")
    n_canal = col3.number_input("n_canal", min_value=0.001, format="%.3f", key="n_canal")
    nivel_base = col4.number_input("Nivel base (m)", format="%.3f", key="nivel_base")

    st.subheader("2) Areas de contribuicao (AC)")
    n_ac = st.number_input("Numero de ACs", min_value=1, max_value=20, step=1, key="n_ac")
    exutorio_id = st.number_input("ID da AC de exutorio", min_value=1, max_value=20, step=1, key="exutorio_id")

    default_ac = pd.DataFrame(
        [
            {
                "ID_AC": 1,
                "Area_m2": 85000.0,
                "L_m": 350.0,
                "S_m_m": 0.015,
                "ACs_montante_ids": "0",
                "h0_m": 0.0,
                "Infiltracao_eq_mm_h": 12.0,
                "n_eq": 0.12,
            },
            {
                "ID_AC": 2,
                "Area_m2": 92000.0,
                "L_m": 420.0,
                "S_m_m": 0.012,
                "ACs_montante_ids": "1",
                "h0_m": 0.0,
                "Infiltracao_eq_mm_h": 10.0,
                "n_eq": 0.10,
            },
            {
                "ID_AC": 3,
                "Area_m2": 130000.0,
                "L_m": 500.0,
                "S_m_m": 0.010,
                "ACs_montante_ids": "1;2",
                "h0_m": 0.0,
                "Infiltracao_eq_mm_h": 8.0,
                "n_eq": 0.09,
            },
        ]
    )
    if n_ac > len(default_ac):
        for idx in range(len(default_ac) + 1, n_ac + 1):
            default_ac.loc[len(default_ac)] = {
                "ID_AC": idx,
                "Area_m2": 100000.0,
                "L_m": 400.0,
                "S_m_m": 0.01,
                "ACs_montante_ids": "0",
                "h0_m": 0.0,
                "Infiltracao_eq_mm_h": 10.0,
                "n_eq": 0.1,
            }
    ac_df_edit = default_ac.head(n_ac).copy()
    ac_loaded = st.session_state.get("ac_df_loaded")
    if isinstance(ac_loaded, pd.DataFrame) and not ac_loaded.empty:
        ac_df_edit = ac_loaded.copy().head(n_ac)

    ac_df = st.data_editor(
        ac_df_edit,
        num_rows="fixed",
        use_container_width=True,
        hide_index=True,
        key="editor_ac",
    )

    st.subheader("3) Unidades de uso do solo (US) - editavel")
    usar_us_para_eq = st.checkbox(
        "Calcular Infiltracao_eq_mm_h e n_eq automaticamente a partir das US",
        key="usar_us_para_eq",
    )
    classes_padrao = ["Superficie impermeavel", "Gramado", "Vegetacao arborea"]
    rows_us = []
    for ac_id in range(1, int(n_ac) + 1):
        if ac_id == 1:
            areas = [34000.0, 28000.0, 23000.0]
        elif ac_id == 2:
            areas = [46000.0, 25000.0, 21000.0]
        elif ac_id == 3:
            areas = [78000.0, 31000.0, 21000.0]
        else:
            area_ac = float(ac_df.loc[ac_df["ID_AC"] == ac_id, "Area_m2"].iloc[0])
            areas = [0.6 * area_ac, 0.25 * area_ac, 0.15 * area_ac]
        for idx, classe in enumerate(classes_padrao, start=1):
            rows_us.append(
                {
                    "ID_AC": ac_id,
                    "ID_US": idx,
                    "Classe_US": classe,
                    "Area_US_m2": areas[idx - 1],
                    "Infiltracao_US_mm_h": [1.0, 15.0, 30.0][idx - 1],
                    "n_US": [0.015, 0.20, 0.35][idx - 1],
                }
            )
    us_default_df = pd.DataFrame(rows_us)
    us_loaded = st.session_state.get("us_df_loaded")
    if isinstance(us_loaded, pd.DataFrame) and not us_loaded.empty:
        us_default_df = us_loaded.copy()
    us_df = st.data_editor(
        us_default_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="editor_us",
    )

    if usar_us_para_eq:
        ac_preview = calcular_parametros_equivalentes_por_us(ac_df, us_df)
        st.caption("Parametros equivalentes calculados por US (ponderados pela area da AC).")
        st.dataframe(
            ac_preview[["ID_AC", "Infiltracao_eq_mm_h", "n_eq"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        ac_preview = ac_df.copy()

    st.subheader("4) Chuva (mm/h)")
    c_t1, c_t2 = st.columns(2)
    hora_inicio_str = c_t1.text_input("Horario de inicio do evento (HH:MM)", key="hora_inicio_evento")
    hora_fim_str = c_t2.text_input("Horario de termino do evento (HH:MM)", key="hora_fim_evento")
    horario_ok = True
    try:
        inicio_h, inicio_m = [int(x) for x in hora_inicio_str.split(":")]
        fim_h, fim_m = [int(x) for x in hora_fim_str.split(":")]
        t_ini = datetime(2000, 1, 1, inicio_h, inicio_m)
        t_fim = datetime(2000, 1, 1, fim_h, fim_m)
        if t_fim < t_ini:
            t_fim = t_fim + timedelta(days=1)
        duracao_horario_min = int((t_fim - t_ini).total_seconds() / 60)
        duracao_modelo_min = int((n_passos - 1) * dt_seg / 60)
        if duracao_horario_min != duracao_modelo_min:
            st.warning(
                f"Duracao por horario ({duracao_horario_min} min) difere da duracao do modelo ({duracao_modelo_min} min). "
                "O eixo sera discretizado por Delta t a partir do horario de inicio."
            )
    except Exception:
        horario_ok = False
        st.error("Formato de horario invalido. Use HH:MM, ex.: 12:00.")

    tempo_vec = np.arange(n_passos) * dt_seg
    default_chuva = np.zeros(n_passos)
    if n_passos >= 5:
        default_chuva[1:5] = [18, 42, 25, 8]
    chuva_df = pd.DataFrame({"Passo": np.arange(n_passos), "Tempo_s": tempo_vec, "P_mm_h": default_chuva})
    chuva_loaded = st.session_state.get("chuva_df_loaded")
    if isinstance(chuva_loaded, pd.DataFrame) and not chuva_loaded.empty:
        chuva_loaded = chuva_loaded.copy()
        if "P_mm_h" in chuva_loaded.columns:
            chuva_df["P_mm_h"] = np.nan
            n_copy = min(len(chuva_df), len(chuva_loaded))
            chuva_df.loc[: n_copy - 1, "P_mm_h"] = pd.to_numeric(
                chuva_loaded.iloc[:n_copy]["P_mm_h"], errors="coerce"
            )
    chuva_df_edit = st.data_editor(
        chuva_df,
        num_rows="fixed",
        use_container_width=True,
        hide_index=True,
        disabled=["Passo", "Tempo_s"],
        key="editor_chuva",
    )

    st.subheader("5) Gestao da simulacao")
    st.text_input("Titulo da simulacao para salvar", key="titulo_salvar", placeholder="Ex.: Evento 12/03/2026")
    g1, g2 = st.columns(2)
    if g1.button("Salvar simulacao"):
        payload = gerar_payload_simulacao(
            titulo=st.session_state.get("titulo_salvar", ""),
            dt_seg=int(dt_seg),
            duracao_min=int(duracao_min),
            n_ac=int(n_ac),
            exutorio_id=int(exutorio_id),
            b_canal=float(b_canal),
            s_canal=float(s_canal),
            n_canal=float(n_canal),
            nivel_base=float(nivel_base),
            usar_horton=bool(usar_horton),
            horton_k_h_inv=float(horton_k_h_inv),
            horton_f0_multiplicador=float(horton_f0_multiplicador),
            usar_us_para_eq=bool(usar_us_para_eq),
            ac_df=ac_preview,
            us_df=us_df,
            chuva_df=chuva_df_edit,
        )
        store = st.session_state.get("sim_store", {"last_id": None, "items": []})
        store["items"] = [x for x in store.get("items", []) if x.get("id") != payload["id"]]
        store["items"].append(payload)
        store["last_id"] = payload["id"]
        st.session_state["sim_store"] = store
        salvar_simulacoes_salvas(store)
        st.success("Simulacao salva com sucesso.")

    if g2.button("Limpar simulacao"):
        st.session_state["_clear_sim_requested"] = True
        st.rerun()

    if st.button("Rodar simulacao", type="primary"):
        try:
            if not horario_ok:
                st.error("Corrija os horarios de inicio/fim antes de rodar a simulacao.")
                st.stop()
            erros = validar_campos_obrigatorios(
                dt_seg=int(dt_seg),
                duracao_min=int(duracao_min),
                n_ac=int(n_ac),
                exutorio_id=int(exutorio_id),
                b_canal=float(b_canal),
                s_canal=float(s_canal),
                n_canal=float(n_canal),
                usar_horton=bool(usar_horton),
                horton_k_h_inv=float(horton_k_h_inv),
                horton_f0_multiplicador=float(horton_f0_multiplicador),
                ac_df=ac_df,
                us_df=us_df,
                chuva_df=chuva_df_edit,
            )
            if erros:
                st.error("A simulacao nao pode rodar. Corrija os campos obrigatorios:")
                for e in erros:
                    st.markdown(f"- {e}")
                st.stop()

            chuva_mmh = pd.to_numeric(chuva_df_edit["P_mm_h"], errors="coerce").astype(float).to_numpy()
            ac_df = ac_preview.copy()
            ac_df["ID_AC"] = ac_df["ID_AC"].astype(int)
            for col in ["Area_m2", "L_m", "S_m_m", "h0_m", "Infiltracao_eq_mm_h", "n_eq"]:
                ac_df[col] = ac_df[col].astype(float)

            df_saida, df_ac_detalhe = run_simulation(
                dt=float(dt_seg),
                chuva_mmh=chuva_mmh,
                ac_df=ac_df,
                exutorio_id=int(exutorio_id),
                b_canal=float(b_canal),
                s_canal=float(s_canal),
                n_canal=float(n_canal),
                nivel_base=float(nivel_base),
                usar_horton=bool(usar_horton),
                horton_k_h_inv=float(horton_k_h_inv),
                horton_f0_multiplicador=float(horton_f0_multiplicador),
            )

            st.session_state["df_saida_validacao"] = df_saida.copy()
            st.session_state["df_validacao_obs"] = montar_df_validacao(
                df_saida, st.session_state.get("df_validacao_obs")
            )
            st.session_state["ac_df_loaded"] = ac_df.copy()
            st.session_state["us_df_loaded"] = us_df.copy()
            st.session_state["chuva_df_loaded"] = chuva_df_edit.copy()

            st.success("Simulacao concluida.")
            tempo_hhmm = montar_tempo_evento_hhmm(len(df_saida), int(dt_seg), hora_inicio_str)
            df_saida = df_saida.copy()
            df_saida["Tempo_hhmm"] = tempo_hhmm
            c1, c2, c3 = st.columns(3)
            c1.metric("Pico de vazao (m3/s)", f"{df_saida['Q_ex_m3_s'].max():.4f}")
            c2.metric("Pico de nivel (m)", f"{df_saida['Nivel_m'].max():.4f}")
            c3.metric("Horario do pico", f"{df_saida.loc[df_saida['Nivel_m'].idxmax(), 'Tempo_hhmm']}")

            fig_nivel = px.line(
                df_saida,
                x="Tempo_hhmm",
                y="Nivel_m",
                markers=False,
                title="Hidrograma de nivel no canal",
            )
            fig_nivel.update_layout(xaxis_title="Horario", yaxis_title="Nivel (m)")
            st.plotly_chart(fig_nivel, use_container_width=True)

            fig_q = px.line(df_saida, x="Tempo_hhmm", y="Q_ex_m3_s", title="Hidrograma de vazao no exutorio")
            fig_q.update_layout(xaxis_title="Horario", yaxis_title="Vazao (m3/s)")
            st.plotly_chart(fig_q, use_container_width=True)

            st.subheader("Saida - exutorio")
            st.dataframe(df_saida, use_container_width=True, hide_index=True)

            st.subheader("Saida detalhada por AC")
            st.dataframe(df_ac_detalhe, use_container_width=True, hide_index=True)

            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_saida.to_excel(writer, index=False, sheet_name="Exutorio")
                df_ac_detalhe.to_excel(writer, index=False, sheet_name="Detalhe_AC")
            st.download_button(
                "Baixar resultados em Excel",
                data=output.getvalue(),
                file_name="resultado_modelo_hidrologico.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as exc:
            st.error(f"Erro na simulacao: {exc}")

