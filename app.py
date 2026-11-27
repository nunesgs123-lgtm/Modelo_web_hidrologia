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


GLOSSARIO_ROWS = [
    {"Termo": "Intervalo_registro_s", "Unidade": "s", "Descricao": "Intervalo temporal entre registros de precipitação (ex.: 600 s)."},
    {"Termo": "Delta_t_integracao_s", "Unidade": "s", "Descricao": "Passo interno de integração numerica do modelo (pode ser menor que o intervalo de registro)."},
    {"Termo": "Duracao_chuva_min", "Unidade": "min", "Descricao": "Duração do período com registros de chuva (exclui recessão)."},
    {"Termo": "Tempo_recessao_min", "Unidade": "min", "Descricao": "Período adicional após o fim da chuva com P=0 para avaliar a recessão do hidrograma."},
    {"Termo": "Unidade_chuva", "Unidade": "-", "Descricao": "Unidade de entrada: intensidade (mm/h) ou acumulado por intervalo (mm). Simulações antigas: P_mm_h = mm/h."},
    {"Termo": "N_passos_ativos", "Unidade": "-", "Descricao": "Número de instantes de saída (inclui t=0 apenas como condição inicial)."},
    {"Termo": "Area_m2", "Unidade": "m2", "Descricao": "Area de contribuição da AC."},
    {"Termo": "L_m", "Unidade": "m", "Descricao": "Comprimento característico de escoamento na AC."},
    {"Termo": "S_m_m", "Unidade": "m/m", "Descricao": "Declividade da superfície de escoamento na AC."},
    {
        "Termo": "ACs_montante_ids",
        "Unidade": "-",
        "Descricao": (
            "IDs das AC imediatamente a montante, separados por `;` (ex.: 1;2). "
            "Rede convergente: cada AC (exceto o exutorio) tem um unico destino a jusante. "
            "A transferencia no mesmo passo e aproximacao de reservatorios conectados, nao hidraulica explicita de canais."
        ),
    },
    {"Termo": "h0_m", "Unidade": "m", "Descricao": "Lâmina inicial de água superficial na AC (condição em t=0)."},
    {"Termo": "Infiltracao_eq_mm_h", "Unidade": "mm/h", "Descricao": "Taxa de infiltração equivalente ponderada por area de US."},
    {"Termo": "n_eq", "Unidade": "-", "Descricao": "Coeficiente de Manning equivalente ponderado por area de US."},
    {"Termo": "P_mm_h", "Unidade": "mm/h", "Descricao": "Intensidade de precipitação. Em registros, o valor no fim do intervalo representa a chuva do intervalo anterior."},
    {"Termo": "P_mm", "Unidade": "mm", "Descricao": "Precipitação acumulada no intervalo de registro. O valor no fim do intervalo é a lâmina caida no intervalo anterior."},
    {"Termo": "P_m_s", "Unidade": "m/s", "Descricao": "Taxa de precipitação em unidades SI usada no balanço (constante dentro de cada intervalo de registro)."},
    {"Termo": "i_excesso_m_s", "Unidade": "m/s", "Descricao": "Taxa líquida após infiltração volumétrica: max(p + Q_in/A - f_real, 0)."},
    {"Termo": "Infiltracao_cap_m_s", "Unidade": "m/s", "Descricao": "Capacidade de infiltração f no passo (constante ou Horton)."},
    {"Termo": "Infiltracao_real_m_s", "Unidade": "m/s", "Descricao": "Taxa média de infiltração real no passo = V_infiltração / (A * dt)."},
    {"Termo": "Volume_infiltrado_m3", "Unidade": "m3", "Descricao": "Volume infiltrado no intervalo de integração."},
    {"Termo": "Volume_infiltrado_acum_m3", "Unidade": "m3", "Descricao": "Volume infiltrado acumulado desde t=0."},
    {"Termo": "Volume_escoado_m3", "Unidade": "m3", "Descricao": "Volume escoado no passo = V_disponivel - V_novo (= Q_out * dt)."},
    {"Termo": "Residuo_implicito_m3", "Unidade": "m3", "Descricao": "Resíduo de V_novo + dt*Q_Manning(V_novo) - V_disponivel após o solver."},
    {
        "Termo": "Erro_AC_m3",
        "Unidade": "m3",
        "Descricao": "Resíduo do balanço por AC: V_ini+V_prec+V_mont-V_inf-V_saída-V_fin. Fechamento numérico ≠ validação física.",
    },
    {
        "Termo": "Erro_bacia_m3",
        "Unidade": "m3",
        "Descricao": "Resíduo global: V_ini+V_prec-V_inf-V_exutório-V_fin (transferências internas excluídas).",
    },
    {
        "Termo": "Tol_balanco_m3",
        "Unidade": "m3",
        "Descricao": "Tolerância configurável de fechamento numérico do balanço hídrico (padrão 1e-6 m3).",
    },
    {"Termo": "Q_in_m3_s", "Unidade": "m3/s", "Descricao": "Vazão recebida das AC(s) a montante imediata."},
    {"Termo": "Q_out_m3_s", "Unidade": "m3/s", "Descricao": "Vazão de saída da AC (propagação por Manning)."},
    {"Termo": "Q_ex_m3_s", "Unidade": "m3/s", "Descricao": "Vazão no exutório selecionado."},
    {"Termo": "Nivel_m", "Unidade": "m", "Descricao": "Profundidade no canal obtida por Manning (seção retangular)."},
    {"Termo": "Cota_abs_m", "Unidade": "m", "Descricao": "Nível absoluto = Nivel_m + nivel_base."},
    {"Termo": "B_canal", "Unidade": "m", "Descricao": "Largura do canal na seção retangular."},
    {"Termo": "S_canal", "Unidade": "m/m", "Descricao": "Declividade do canal."},
    {"Termo": "n_canal", "Unidade": "-", "Descricao": "Manning do canal."},
    {"Termo": "nivel_base", "Unidade": "m", "Descricao": "Cota de referência somada ao nivel para cota absoluta."},
    {"Termo": "NSE / Nash-Sutcliffe", "Unidade": "-", "Descricao": "Eficiência de Nash-Sutcliffe: 1 - sum((O-S)^2)/sum((O-mean(O))^2). Também chamado de Nash."},
    {"Termo": "R2 (Pearson)", "Unidade": "-", "Descricao": "Coeficiente de determinação linear: quadrado da correlacao de Pearson entre observado e simulado."},
    {"Termo": "RMSE / MAE / Vies", "Unidade": "m", "Descricao": "Erro quadrático médio, erro absoluto médio e viés médio (S - O) para nível."},
    {
        "Termo": "Modo_MHU_1.1",
        "Unidade": "-",
        "Descricao": (
            "Parâmetros equivalentes por AC (média ponderada por área das US). "
            "Formulação do MHU 1.1 preservada."
        ),
    },
    {
        "Termo": "Modo_MHU_2.0",
        "Unidade": "-",
        "Descricao": (
            "Processamento hidrológico individual por classe US (V, h, n, f, Q próprios). "
            "Mudança de concepção matemática — não é apenas correção de código. "
            "Q_i = Σ Q_ij; W_ij = A_ij/L_i; Q_ij = (W_ij/n_ij)·h_ij^(5/3)·√S_i."
        ),
    },
    {
        "Termo": "Estrategia_montante",
        "Unidade": "-",
        "Descricao": (
            "Como Q_in da AC é repartida entre classes no Modo 2. "
            "Hipótese experimental atual: proporcional_area (mistura homogênea). "
            "Interface preparada para outras estratégias."
        ),
    },
]

PASSOS_INTEGRACAO_PERMITIDOS = [600, 300, 120, 60, 30, 10, 5]
UNIDADE_CHUVA_INTENSIDADE = "mm/h"
UNIDADE_CHUVA_ACUMULADA = "mm"
# Tolerancia de fechamento NUMERICO do balanco hidrico (nao e validacao fisica).
TOL_BALANCO_HIDRICO_M3_DEFAULT = 1e-6
MODO_MHU_1_1 = "MHU_1.1_equivalente"
MODO_MHU_2_0 = "MHU_2.0_por_classe"

# Referencias para calibracao (ordens de grandeza; ajustar ao local e ao evento)
CALIBRACAO_USO_SOLO = [
    {
        "Classe": "Superfícies impermeáveis",
        "Exemplos": "Vias pavimentadas, passeios, estacionamentos, telhados e coberturas, pátios e praças com piso impermeável",
        "Infil_sugerida_mm_h": 1.0,
        "Infil_min_mm_h": 0.0,
        "Infil_max_mm_h": 3.0,
        "n_sugerido": 0.015,
        "n_min": 0.011,
        "n_max": 0.020,
    },
    {
        "Classe": "Superfícies semi-impermeáveis",
        "Exemplos": "Ruas não pavimentadas, estradas vicinais, caminhos de terra e estacionamentos de terra",
        "Infil_sugerida_mm_h": 6.0,
        "Infil_min_mm_h": 2.0,
        "Infil_max_mm_h": 12.0,
        "n_sugerido": 0.035,
        "n_min": 0.020,
        "n_max": 0.060,
    },
    {
        "Classe": "Solo exposto",
        "Exemplos": "Terrenos baldios, taludes expostos e áreas com remoção de vegetação",
        "Infil_sugerida_mm_h": 8.0,
        "Infil_min_mm_h": 2.0,
        "Infil_max_mm_h": 18.0,
        "n_sugerido": 0.040,
        "n_min": 0.020,
        "n_max": 0.080,
    },
    {
        "Classe": "Cobertura vegetal arbórea",
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
        "Exemplos": "Campos naturais, áreas de grama e capim natural e outras áreas verdes não urbanizadas",
        "Infil_sugerida_mm_h": 22.0,
        "Infil_min_mm_h": 10.0,
        "Infil_max_mm_h": 35.0,
        "n_sugerido": 0.25,
        "n_min": 0.16,
        "n_max": 0.35,
    },
    {
        "Classe": "Área verde urbana",
        "Exemplos": "Quintais residenciais, jardins, praças com vegetação, canteiros urbanos, áreas verdes de escolas e condomínios",
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
        "Classe": "Corpos d'água",
        "Exemplos": "Rios, açudes, lagos e canais abertos",
        "Infil_sugerida_mm_h": 0.0,
        "Infil_min_mm_h": 0.0,
        "Infil_max_mm_h": 0.5,
        "n_sugerido": 0.030,
        "n_min": 0.015,
        "n_max": 0.060,
    },
    {
        "Classe": "Infraestrutura urbana linear",
        "Exemplos": "Ferrovias, pátios ferroviários, corredores de serviço e faixas de dutos",
        "Infil_sugerida_mm_h": 4.0,
        "Infil_min_mm_h": 0.5,
        "Infil_max_mm_h": 12.0,
        "n_sugerido": 0.030,
        "n_min": 0.015,
        "n_max": 0.060,
    },
    {
        "Classe": "Superfícies drenantes artificiais",
        "Exemplos": "Piso intertravado drenante, pavimento permeável e valas/trincheiras de infiltração",
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
        "Notas": "Superfícies bem acabadas, canalizações urbanas típicas",
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
        "Tipo_revestimento": "Terra limpa (sem vegetação)",
        "n_sugerido": 0.025,
        "n_min": 0.020,
        "n_max": 0.030,
        "Notas": "Canais de terra compactada",
    },
    {
        "Tipo_revestimento": "Terra com vegetação",
        "n_sugerido": 0.038,
        "n_min": 0.030,
        "n_max": 0.045,
        "Notas": "Leitos com capim ou vegetação",
    },
    {
        "Tipo_revestimento": "Leito natural (rio / canal não revestido)",
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


def passos_integracao_validos(intervalo_registro_s: int) -> list[int]:
    ir = int(intervalo_registro_s)
    return [p for p in PASSOS_INTEGRACAO_PERMITIDOS if ir % p == 0]


def converter_precipitacao_para_taxa_m_s(
    valor: float,
    unidade: str,
    intervalo_registro_s: float,
) -> float:
    """Converte registro de chuva em taxa SI (m/s)."""
    v = float(valor)
    if not np.isfinite(v) or v <= 0:
        return 0.0
    if unidade == UNIDADE_CHUVA_ACUMULADA:
        dt_r = max(float(intervalo_registro_s), 1e-12)
        return v / (1000.0 * dt_r)
    return v / 3600000.0


def extrair_valores_chuva_df(chuva_df: pd.DataFrame, unidade: str) -> np.ndarray:
    """Extrai serie de registros. Legado: coluna P_mm_h = intensidade mm/h."""
    if unidade == UNIDADE_CHUVA_ACUMULADA and "P_mm" in chuva_df.columns:
        col = "P_mm"
    elif "P_mm_h" in chuva_df.columns:
        col = "P_mm_h"
    elif "P_mm" in chuva_df.columns:
        col = "P_mm"
    else:
        raise ValueError("Tabela de chuva sem coluna `P_mm_h` ou `P_mm`.")
    return pd.to_numeric(chuva_df[col], errors="coerce").astype(float).to_numpy()


def metricas_precipitacao(
    valores: np.ndarray,
    unidade: str,
    intervalo_registro_s: float,
) -> dict[str, float]:
    """Metricas do evento a partir dos registros (t=0 nao contribui volume)."""
    vals = np.asarray(valores, dtype=float)
    dt_r = float(intervalo_registro_s)
    if len(vals) <= 1 or dt_r <= 0:
        return {"P_acum_mm": 0.0, "I_max_mm_h": 0.0, "Duracao_evento_min": 0.0}
    serie = np.clip(vals[1:], 0.0, None)
    if unidade == UNIDADE_CHUVA_ACUMULADA:
        p_acum = float(np.nansum(serie))
        i_max = float(np.nanmax(serie) * 3600.0 / dt_r) if len(serie) else 0.0
    else:
        p_acum = float(np.nansum(serie * dt_r / 3600.0))
        i_max = float(np.nanmax(serie)) if len(serie) else 0.0
    if not np.isfinite(i_max):
        i_max = 0.0
    duracao_min = (len(vals) - 1) * dt_r / 60.0
    return {"P_acum_mm": p_acum, "I_max_mm_h": i_max, "Duracao_evento_min": duracao_min}


def taxa_chuva_no_passo(
    t_end_s: float,
    chuva_registros: np.ndarray,
    intervalo_registro_s: float,
    unidade: str,
    tempo_chuva_s: float,
) -> float:
    """
    Intensidade constante no intervalo de registro.
    O registro no instante k*dt_r representa a chuva ocorrida em ((k-1)*dt_r, k*dt_r].
    """
    if t_end_s <= 0 or t_end_s > tempo_chuva_s + 1e-9:
        return 0.0
    dt_r = float(intervalo_registro_s)
    if dt_r <= 0:
        return 0.0
    k = int(math.ceil(t_end_s / dt_r - 1e-12))
    if k < 1 or k >= len(chuva_registros):
        return 0.0
    return converter_precipitacao_para_taxa_m_s(chuva_registros[k], unidade, dt_r)


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
    intervalo_registro_s: int | None = None,
    dt_integracao_s: int | None = None,
    unidade_chuva: str = UNIDADE_CHUVA_INTENSIDADE,
    tempo_recessao_min: float = 0.0,
    modo_mhu: str = MODO_MHU_1_1,
) -> dict:
    start_hhmm = st.session_state.get("hora_inicio_evento", "12:00")
    end_hhmm = st.session_state.get("hora_fim_evento", "12:40")
    dt_int = int(dt_integracao_s if dt_integracao_s is not None else dt_seg)
    dt_reg = int(intervalo_registro_s if intervalo_registro_s is not None else dt_seg)
    return {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "titulo": titulo.strip() if titulo.strip() else f"Simulação {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "params": {
            # dt_seg mantido = passo de integracao (compatibilidade com saves antigos)
            "dt_seg": dt_int,
            "dt_integracao_s": dt_int,
            "intervalo_registro_s": dt_reg,
            "duracao_min": int(duracao_min),
            "tempo_recessao_min": float(tempo_recessao_min),
            "unidade_chuva": str(unidade_chuva),
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
            "modo_mhu": str(modo_mhu),
            "hora_inicio_evento": str(start_hhmm),
            "hora_fim_evento": str(end_hhmm),
        },
        "ac_df": ac_df.to_dict(orient="records"),
        "us_df": us_df.to_dict(orient="records"),
        "chuva_df": chuva_df.to_dict(orient="records"),
    }


def aplicar_payload_em_session(payload: dict) -> None:
    p = payload.get("params", {})
    dt_legado = int(p.get("dt_seg", 600))
    st.session_state["intervalo_registro_s"] = int(p.get("intervalo_registro_s", dt_legado))
    st.session_state["dt_integracao_s"] = int(p.get("dt_integracao_s", dt_legado))
    st.session_state["dt_seg"] = int(st.session_state["dt_integracao_s"])
    st.session_state["duracao_min"] = int(p.get("duracao_min", 40))
    st.session_state["tempo_recessao_min"] = float(p.get("tempo_recessao_min", 0.0))
    # Simulacoes antigas: registros P_mm_h sao intensidades em mm/h
    st.session_state["unidade_chuva"] = str(p.get("unidade_chuva", UNIDADE_CHUVA_INTENSIDADE))
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
    st.session_state["modo_mhu"] = str(p.get("modo_mhu", MODO_MHU_1_1))
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
    intervalo_registro_s: int | None = None,
    unidade_chuva: str = UNIDADE_CHUVA_INTENSIDADE,
    tempo_recessao_min: float = 0.0,
) -> list[str]:
    erros = []
    dt_int = int(dt_seg)
    dt_reg = int(intervalo_registro_s if intervalo_registro_s is not None else dt_seg)
    if dt_reg <= 0:
        erros.append("`Intervalo de registro da chuva (s)` deve ser maior que zero.")
    if dt_int <= 0:
        erros.append("`Passo de integracao (s)` deve ser maior que zero.")
    if dt_reg > 0 and dt_int > 0 and dt_reg % dt_int != 0:
        erros.append(
            "`Passo de integracao` deve ser divisor exato do `Intervalo de registro da chuva`."
        )
    if dt_int > 0 and dt_int not in PASSOS_INTEGRACAO_PERMITIDOS:
        erros.append(
            f"`Passo de integracao` deve ser um de: {', '.join(str(x) for x in PASSOS_INTEGRACAO_PERMITIDOS)}."
        )
    if duracao_min <= 0:
        erros.append("`Duração da chuva (min)` deve ser maior que zero.")
    if tempo_recessao_min < 0:
        erros.append("`Tempo de recessao (min)` nao pode ser negativo.")
    if dt_int > 0 and tempo_recessao_min > 0:
        rec_s = float(tempo_recessao_min) * 60.0
        if abs(rec_s / dt_int - round(rec_s / dt_int)) > 1e-9:
            erros.append("`Tempo de recessao` deve ser multiplo do passo de integracao.")
    if dt_reg > 0 and duracao_min > 0:
        chuva_s = float(duracao_min) * 60.0
        if abs(chuva_s / dt_reg - round(chuva_s / dt_reg)) > 1e-9:
            erros.append("`Duracao da chuva` deve ser multipla do intervalo de registro.")
    if n_ac <= 0:
        erros.append("`Número de ACs` deve ser maior que zero.")
    if exutorio_id <= 0:
        erros.append("`ID da AC de exutório` deve ser maior que zero.")
    if exutorio_id > n_ac:
        erros.append("`ID da AC de exutório` deve estar dentro do intervalo de ACs informadas.")
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
    col_p = "P_mm" if unidade_chuva == UNIDADE_CHUVA_ACUMULADA and "P_mm" in chuva_df.columns else None
    if col_p is None:
        col_p = "P_mm_h" if "P_mm_h" in chuva_df.columns else ("P_mm" if "P_mm" in chuva_df.columns else None)
    if chuva_df.empty or col_p is None:
        erros.append("Tabela de chuva esta vazia.")
    elif pd.to_numeric(chuva_df[col_p], errors="coerce").isna().any():
        erros.append(f"Preencha todos os valores de `{col_p}` na tabela de chuva.")
    return erros


def montar_tempo_evento_hhmm(n_steps: int, dt_seg: int, hora_inicio: str) -> list[str]:
    h, m = [int(x) for x in hora_inicio.split(":")]
    t0 = datetime(2000, 1, 1, h, m)
    return [(t0 + timedelta(seconds=i * dt_seg)).strftime("%H:%M") for i in range(n_steps)]


def parse_upstream_ids(text: str, *, strict: bool = False) -> list[int]:
    """
    Interpreta `ACs_montante_ids`.
    `0`, vazio, nan ou None = sem montante.
    Com strict=True, tokens invalidos geram ValueError (nao sao ignorados).
    """
    if text is None:
        return []
    raw = str(text).strip()
    if raw.lower() in {"", "0", "nan", "none"}:
        return []
    ids: list[int] = []
    for part in raw.split(";"):
        p = part.strip()
        if p == "":
            continue
        if p.lower() in {"0", "nan", "none"}:
            continue
        if p.isdigit() or (p.startswith("-") and p[1:].isdigit()):
            ids.append(int(p))
            continue
        # Aceita "1.0" tipico de planilha
        try:
            val = float(p.replace(",", "."))
            if val.is_integer():
                ids.append(int(val))
                continue
        except Exception:
            pass
        if strict:
            raise ValueError(f"Token invalido em `ACs_montante_ids`: '{p}'. Use inteiros separados por `;`.")
    return ids


def validar_e_preparar_rede_ac(
    ac_df: pd.DataFrame,
    exutorio_id: int,
) -> tuple[pd.DataFrame, dict]:
    """
    Valida rede convergente de ACs e devolve DataFrame ordenado (montante→jusante)
    mais metadados da topologia.

    Regras: cada AC (exceto o exutorio) possui exatamente um destino a jusante;
    o exutorio nao possui destino; nao ha bifurcacao da mesma vazao para duas ACs.
    """
    if ac_df is None or ac_df.empty:
        raise ValueError("Tabela de ACs vazia: informe ao menos uma area de contribuicao.")

    ac_work = ac_df.copy()
    if "ID_AC" not in ac_work.columns or "ACs_montante_ids" not in ac_work.columns:
        raise ValueError("Tabela de ACs deve conter as colunas `ID_AC` e `ACs_montante_ids`.")

    ac_work["ID_AC"] = pd.to_numeric(ac_work["ID_AC"], errors="coerce")
    if ac_work["ID_AC"].isna().any():
        raise ValueError("Existem valores nao numericos em `ID_AC`. Corrija os IDs das ACs.")
    ac_work["ID_AC"] = ac_work["ID_AC"].astype(int)
    ac_work = ac_work.reset_index(drop=True)

    ac_ids = ac_work["ID_AC"].tolist()
    # IDs duplicados
    vistos: dict[int, int] = {}
    duplicados = []
    for i, ac_id in enumerate(ac_ids):
        if ac_id in vistos:
            duplicados.append(ac_id)
        else:
            vistos[ac_id] = i
    if duplicados:
        duniq = sorted(set(duplicados))
        raise ValueError(
            f"IDs de AC duplicados na tabela: {duniq}. Cada `ID_AC` deve ser unico."
        )

    id_set = set(ac_ids)
    try:
        exutorio_id = int(exutorio_id)
    except Exception as exc:
        raise ValueError(f"Exutorio invalido: `{exutorio_id}` nao e um inteiro.") from exc
    if exutorio_id not in id_set:
        raise ValueError(
            f"Exutorio invalido: AC {exutorio_id} nao existe na tabela de ACs "
            f"(IDs cadastrados: {sorted(id_set)}). Nenhum exutorio substituto foi assumido."
        )

    upstream_of: dict[int, list[int]] = {ac_id: [] for ac_id in ac_ids}
    erros: list[str] = []

    for _, row in ac_work.iterrows():
        ac_id = int(row["ID_AC"])
        try:
            ups_raw = parse_upstream_ids(row["ACs_montante_ids"], strict=True)
        except ValueError as exc:
            erros.append(f"AC {ac_id}: {exc}")
            continue

        # Montantes repetidos na mesma lista
        if len(ups_raw) != len(set(ups_raw)):
            reps = sorted({u for u in ups_raw if ups_raw.count(u) > 1})
            erros.append(
                f"AC {ac_id}: IDs de montante repetidos em `ACs_montante_ids`: {reps}."
            )

        ups_unique: list[int] = []
        for u in ups_raw:
            if u == ac_id:
                erros.append(f"AC {ac_id}: referencia a si mesma em `ACs_montante_ids`.")
                continue
            if u not in id_set:
                erros.append(
                    f"AC {ac_id}: ID de montante inexistente `{u}` "
                    f"(IDs validos: {sorted(id_set)})."
                )
                continue
            if u not in ups_unique:
                ups_unique.append(u)
        upstream_of[ac_id] = ups_unique

    # Destinos a jusante (rede convergente: no maximo um por AC)
    downstream_of: dict[int, list[int]] = {ac_id: [] for ac_id in ac_ids}
    for ds_id, ups in upstream_of.items():
        for up_id in ups:
            downstream_of[up_id].append(ds_id)

    for ac_id, destinos in downstream_of.items():
        dest_u = sorted(set(destinos))
        if len(destinos) != len(dest_u):
            erros.append(
                f"AC {ac_id}: destino a jusante duplicado na montagem da rede "
                f"(destinos brutos={destinos})."
            )
        if len(dest_u) > 1:
            erros.append(
                f"AC {ac_id}: possui mais de um destino a jusante {dest_u}. "
                f"Nesta versao a rede deve ser convergente (uma unica transferencia de vazao por AC). "
                f"A mesma vazao nao pode ser integralmente enviada a duas ACs diferentes."
            )
        if ac_id == exutorio_id and dest_u:
            erros.append(
                f"Exutorio AC {exutorio_id}: nao pode ter destino a jusante {dest_u}."
            )
        if ac_id != exutorio_id and len(dest_u) == 0:
            erros.append(
                f"AC {ac_id}: nao possui destino a jusante e nao e o exutorio. "
                f"Conecte-a (como montante) a exatamente uma AC a jusante ate o exutorio {exutorio_id}."
            )

    # Ciclos via ordenacao topologica (Kahn)
    indeg = {ac_id: len(upstream_of[ac_id]) for ac_id in ac_ids}
    fila = deque(sorted([ac_id for ac_id in ac_ids if indeg[ac_id] == 0]))
    ordem_ids: list[int] = []
    while fila:
        atual = fila.popleft()
        ordem_ids.append(atual)
        for ds_id in sorted(downstream_of[atual]):
            indeg[ds_id] -= 1
            if indeg[ds_id] == 0:
                fila.append(ds_id)
    if len(ordem_ids) != len(ac_ids):
        em_ciclo = sorted(set(ac_ids) - set(ordem_ids))
        erros.append(
            f"Ciclo na rede de drenagem envolvendo as ACs {em_ciclo}. "
            f"A estrutura deve ser aciclica (montante→jusante)."
        )

    # Conectividade ao exutorio (caminhando de jusante para montante)
    alcancadas: set[int] = set()
    pilha = [exutorio_id]
    while pilha:
        cur = pilha.pop()
        if cur in alcancadas:
            continue
        alcancadas.add(cur)
        pilha.extend(upstream_of.get(cur, []))
    desconectadas = sorted(set(ac_ids) - alcancadas)
    if desconectadas:
        erros.append(
            f"ACs desconectadas do exutorio {exutorio_id}: {desconectadas}. "
            f"Toda AC deve contribuir ao exutorio sem ramificacao divergente."
        )

    # Duplicacao de volumes: cada AC nao-exutorio aparece em exatamente um receptor
    aparicoes: dict[int, list[int]] = {ac_id: [] for ac_id in ac_ids}
    for ds_id, ups in upstream_of.items():
        for u in ups:
            aparicoes[u].append(ds_id)
    for ac_id, receptores in aparicoes.items():
        if ac_id == exutorio_id:
            continue
        if len(receptores) > 1:
            erros.append(
                f"Duplicacao de volume: AC {ac_id} transfere integralmente para multiplas ACs {sorted(receptores)}."
            )

    if erros:
        # Mensagens distintas, preservando ordem
        raise ValueError("Inconsistencias na conectividade das ACs:\n- " + "\n- ".join(erros))

    idx_by_id = {ac_id: i for i, ac_id in enumerate(ac_ids)}
    ordem_idx = [idx_by_id[ac_id] for ac_id in ordem_ids]
    ac_ord = ac_work.iloc[ordem_idx].reset_index(drop=True)

    downstream_unico = {
        ac_id: (downstream_of[ac_id][0] if downstream_of[ac_id] else None) for ac_id in ac_ids
    }
    meta = {
        "upstream_of": upstream_of,
        "downstream_of": downstream_unico,
        "ordem_ids": ordem_ids,
        "exutorio_id": exutorio_id,
        "n_ac": len(ac_ids),
        "todas_contribuem": len(desconectadas) == 0 and len(alcancadas) == len(ac_ids),
    }
    return ac_ord, meta


def ordenar_ac_topologicamente(ac_df: pd.DataFrame, exutorio_id: int | None = None) -> pd.DataFrame:
    """
    Ordena ACs montante→jusante.
    Se `exutorio_id` for informado, aplica validacao completa da rede convergente.
    Sem exutorio, ainda rejeita ciclos, auto-referencia, IDs inexistentes/repetidos e bifurcacoes.
    """
    ac_work = ac_df.copy()
    ac_work["ID_AC"] = pd.to_numeric(ac_work["ID_AC"], errors="coerce")
    if ac_work["ID_AC"].isna().any():
        raise ValueError("Existem valores nao numericos em `ID_AC`.")
    ac_work["ID_AC"] = ac_work["ID_AC"].astype(int)

    if exutorio_id is None:
        # Usa um exutorio candidato: unico no com grau de saida 0, se existir
        ups_tmp = {}
        for _, row in ac_work.iterrows():
            ups_tmp[int(row["ID_AC"])] = parse_upstream_ids(row["ACs_montante_ids"], strict=True)
        ds_count: dict[int, int] = {i: 0 for i in ups_tmp}
        for ds, ups in ups_tmp.items():
            for u in ups:
                if u in ds_count:
                    ds_count[u] += 1
        candidatos = [i for i, c in ds_count.items() if c == 0]
        if len(candidatos) != 1:
            raise ValueError(
                "Informe `exutorio_id` explicitamente. Nao foi possivel inferir um unico exutorio "
                f"(candidatos sem destino a jusante: {sorted(candidatos)})."
            )
        exutorio_id = candidatos[0]

    ac_ord, _meta = validar_e_preparar_rede_ac(ac_work, int(exutorio_id))
    return ac_ord


def fig_nivel_com_hietograma(df_saida: pd.DataFrame) -> go.Figure:
    """
    Hidrograma de nível no canal com hietograma de precipitação no mesmo gráfico,
    em eixos distintos (nível à esquerda; precipitação à direita, invertido).
    Apenas apresentação visual — mesmos dados de entrada/saída.
    """
    try:
        from ui_pages import enhance_fig_nivel

        return enhance_fig_nivel(df_saida)
    except Exception:
        pass
    from plot_theme import COLOR_PREC, COLOR_SIM, apply_mhu_layout, annotate_peak

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
            name="Nível no canal (m)",
            mode="lines",
            line=dict(color=COLOR_SIM, width=2.5),
            yaxis="y",
            hovertemplate="Nível: %{y:.4f} m<extra></extra>",
        )
    )
    p_max = float(pd.to_numeric(df_saida["P_mm_h"], errors="coerce").max() or 0.0)
    apply_mhu_layout(fig, title="Hidrograma de nível e hietograma de precipitação")
    fig.update_layout(
        xaxis=dict(title="Horário", type="category"),
        yaxis=dict(title="Nível no canal (m)", side="left", showgrid=True, zeroline=True),
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


def fig_rede_conectividade_ac(meta: dict, titulo: str | None = None) -> go.Figure:
    """Figura interativa Plotly da rede montante→jusante."""
    upstream_of: dict[int, list[int]] = meta["upstream_of"]
    exutorio_id = int(meta["exutorio_id"])
    ordem = list(meta["ordem_ids"])

    # Niveis: distancia topologica desde as fontes
    nivel: dict[int, int] = {}
    for ac_id in ordem:
        ups = upstream_of.get(ac_id, [])
        nivel[ac_id] = 0 if not ups else 1 + max(nivel[u] for u in ups)

    por_nivel: dict[int, list[int]] = {}
    for ac_id, nv in nivel.items():
        por_nivel.setdefault(nv, []).append(ac_id)

    pos: dict[int, tuple[float, float]] = {}
    for nv, ids_nv in sorted(por_nivel.items()):
        ids_sorted = sorted(ids_nv)
        k = len(ids_sorted)
        for i, ac_id in enumerate(ids_sorted):
            x = nv
            y = i - (k - 1) / 2.0
            pos[ac_id] = (float(x), float(y))

    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    for ds_id, ups in upstream_of.items():
        for up_id in ups:
            x0, y0 = pos[up_id]
            x1, y1 = pos[ds_id]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

    node_x = [pos[i][0] for i in ordem]
    node_y = [pos[i][1] for i in ordem]
    cores = ["#d62728" if i == exutorio_id else "#1f77b4" for i in ordem]
    textos = [
        f"AC {i}" + (" (exutorio)" if i == exutorio_id else "")
        + (f"<br>Montantes: {upstream_of[i]}" if upstream_of[i] else "<br>Montantes: —")
        for i in ordem
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line=dict(width=1.5, color="#7f7f7f"),
            hoverinfo="none",
            name="Conexao",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=[str(i) for i in ordem],
            textposition="top center",
            marker=dict(size=22, color=cores, line=dict(width=1, color="#222")),
            hovertext=textos,
            hoverinfo="text",
            name="AC",
        )
    )
    fig.update_layout(
        title=titulo
        or (
            f"Rede de conectividade das ACs (exutorio={exutorio_id}) — "
            "transferência no mesmo passo = aproximação de reservatórios conectados"
        ),
        xaxis=dict(title="Direção montante → jusante (nível topológico)", showgrid=False, zeroline=False),
        yaxis=dict(title="", showgrid=False, zeroline=False, showticklabels=False),
        showlegend=False,
        margin=dict(l=40, r=20, t=60, b=40),
        height=max(320, 60 * max(1, max(len(v) for v in por_nivel.values()))),
    )
    return fig


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


def validar_parametros_superficie_ac(
    area_m2: float,
    comprimento_m: float,
    n_eq: float,
    declividade: float,
    ac_id: int | None = None,
) -> None:
    """Rejeita parametros fisicos invalidos (nao substitui por minimos silenciosos)."""
    prefixo = f"AC {ac_id}: " if ac_id is not None else ""
    checks = [
        ("Area_m2", area_m2, True),
        ("L_m", comprimento_m, True),
        ("n_eq", n_eq, True),
        ("S_m_m", declividade, True),
    ]
    for nome, valor, exige_positivo in checks:
        v = float(valor)
        if not np.isfinite(v):
            raise ValueError(f"{prefixo}`{nome}` deve ser finito (recebido: {valor}).")
        if exige_positivo and v <= 0:
            raise ValueError(f"{prefixo}`{nome}` deve ser > 0 (recebido: {valor}).")


def manning_vazao_superficie(
    volume_m3: float,
    area_m2: float,
    comprimento_m: float,
    n_eq: float,
    declividade: float,
) -> float:
    """
    Manning em plano inclinado:
      q = (1/n) * h^(5/3) * sqrt(S)
      Q = W * q,  W = A/L,  h = V/A
    """
    v = float(volume_m3)
    if v <= 0.0:
        return 0.0
    w = area_m2 / comprimento_m
    h = v / area_m2
    return (w / n_eq) * (h ** (5.0 / 3.0)) * math.sqrt(declividade)


def manning_dQ_dV_superficie(
    volume_m3: float,
    area_m2: float,
    comprimento_m: float,
    n_eq: float,
    declividade: float,
) -> float:
    """Derivada dQ/dV para polimento Newton (V>0)."""
    v = float(volume_m3)
    if v <= 0.0:
        return 0.0
    # Q = C * V^(5/3), C = (W/n)*sqrt(S) / A^(5/3)
    w = area_m2 / comprimento_m
    c = (w / n_eq) * math.sqrt(declividade) / (area_m2 ** (5.0 / 3.0))
    return c * (5.0 / 3.0) * (v ** (2.0 / 3.0))


def solve_surface_storage_implicit(
    v_disponivel: float,
    dt: float,
    area_m2: float,
    comprimento_m: float,
    n_eq: float,
    declividade: float,
    tol_abs: float = 1e-12,
    tol_rel: float = 1e-10,
    max_iter_bissection: int = 80,
    max_iter_newton: int = 8,
    ac_id: int | None = None,
) -> dict[str, float | bool | int]:
    """
    Euler implicito volumetrico conservativo:
      V_novo + dt * Q(V_novo) = V_disponivel
    com Q de Manning em plano inclinado.

    Resolve por bissecao em [0, V_disponivel] e polimento Newton opcional.
    A vazao reportada e consistente com o volume transferido:
      Q_out = (V_disponivel - V_novo) / dt
    """
    validar_parametros_superficie_ac(area_m2, comprimento_m, n_eq, declividade, ac_id=ac_id)
    dt = float(dt)
    if not np.isfinite(dt) or dt <= 0:
        raise ValueError(f"Passo de integracao `dt` deve ser > 0 (recebido: {dt}).")
    if not np.isfinite(v_disponivel):
        raise ValueError(f"V_disponivel deve ser finito (recebido: {v_disponivel}).")
    if not np.isfinite(tol_abs) or tol_abs < 0:
        raise ValueError("`tol_abs` invalida.")
    if not np.isfinite(tol_rel) or tol_rel < 0:
        raise ValueError("`tol_rel` invalida.")

    v_disp = max(float(v_disponivel), 0.0)
    if v_disp == 0.0:
        return {
            "v_novo": 0.0,
            "h_novo": 0.0,
            "q_out": 0.0,
            "v_escoado": 0.0,
            "residuo": 0.0,
            "convergiu": True,
            "n_iter": 0,
        }

    def residuo(v: float) -> float:
        return float(v + dt * manning_vazao_superficie(v, area_m2, comprimento_m, n_eq, declividade) - v_disp)

    # g(0) = -v_disp <= 0; g(v_disp) = dt*Q(v_disp) >= 0
    lo, hi = 0.0, v_disp
    g_lo, g_hi = residuo(lo), residuo(hi)
    if g_hi < 0:
        # Numericamente Q~0: todo volume permanece armazenado
        v_star = v_disp
        n_iter = 0
        convergiu = True
    else:
        v_star = 0.5 * (lo + hi)
        n_iter = 0
        convergiu = False
        escala = max(v_disp, 1.0)
        for n_iter in range(1, max_iter_bissection + 1):
            v_star = 0.5 * (lo + hi)
            g_mid = residuo(v_star)
            if abs(g_mid) <= tol_abs or abs(g_mid) <= tol_rel * escala:
                convergiu = True
                break
            if (hi - lo) <= max(tol_abs, tol_rel * escala):
                convergiu = True
                break
            if g_mid > 0.0:
                hi = v_star
                g_hi = g_mid
            else:
                lo = v_star
                g_lo = g_mid

        # Polimento Newton (complementar); mantem bissecao como garantia
        v_n = float(v_star)
        for _ in range(max_iter_newton):
            q = manning_vazao_superficie(v_n, area_m2, comprimento_m, n_eq, declividade)
            g = v_n + dt * q - v_disp
            if abs(g) <= tol_abs or abs(g) <= tol_rel * escala:
                v_star = v_n
                convergiu = True
                break
            dq = manning_dQ_dV_superficie(v_n, area_m2, comprimento_m, n_eq, declividade)
            dg = 1.0 + dt * dq
            if abs(dg) < 1e-30:
                break
            v_n = v_n - g / dg
            if v_n < 0.0 or v_n > v_disp:
                break
            v_star = v_n

    v_novo = min(max(float(v_star), 0.0), v_disp)
    v_escoado = v_disp - v_novo
    if v_escoado < 0.0:
        v_escoado = 0.0
        v_novo = v_disp
    q_out = v_escoado / dt
    h_novo = v_novo / area_m2
    res = float(v_novo + dt * manning_vazao_superficie(v_novo, area_m2, comprimento_m, n_eq, declividade) - v_disp)

    if not convergiu and abs(res) > max(tol_abs, tol_rel * max(v_disp, 1.0)):
        raise RuntimeError(
            f"Solver superficial nao convergiu (AC={ac_id}, residuo={res:.3e}, "
            f"V_disp={v_disp:.6g}, dt={dt})."
        )

    return {
        "v_novo": float(v_novo),
        "h_novo": float(h_novo),
        "q_out": float(q_out),
        "v_escoado": float(v_escoado),
        "residuo": float(res),
        "convergiu": bool(convergiu or abs(res) <= max(tol_abs, tol_rel * max(v_disp, 1.0))),
        "n_iter": int(n_iter),
    }


def solve_surface_depth_implicit(
    h_prev: float,
    dt: float,
    input_rate_m_s: float,
    alpha_m_2_3_s: float,
    max_iter: int = 25,
    tol: float = 1e-9,
) -> float:
    """
    Compatibilidade legada (formulação em lamina).
    Preferir `solve_surface_storage_implicit` no nucleo atual.
    """
    h_prev = float(h_prev)
    dt = float(dt)
    if not np.isfinite(h_prev) or h_prev < 0:
        raise ValueError("`h_prev` deve ser finito e >= 0.")
    if not np.isfinite(dt) or dt <= 0:
        raise ValueError("`dt` deve ser > 0.")
    if not np.isfinite(input_rate_m_s):
        raise ValueError("`input_rate_m_s` deve ser finito.")
    if not np.isfinite(alpha_m_2_3_s) or alpha_m_2_3_s < 0:
        raise ValueError("`alpha_m_2_3_s` deve ser finito e >= 0.")
    if alpha_m_2_3_s == 0.0:
        return max(0.0, h_prev + dt * input_rate_m_s)

    # Equivalente volumetrico unitario (A=1, W=alpha*n/sqrt(S) implícito via alpha)
    # Mantem Newton+bisseção em h: h + dt*alpha*h^(5/3) = h_prev + dt*input
    rhs = h_prev + dt * input_rate_m_s
    if rhs <= 0:
        return 0.0
    lo, hi = 0.0, rhs
    h = 0.5 * (lo + hi)
    for _ in range(max(max_iter, 40)):
        g = h + dt * alpha_m_2_3_s * (h ** (5.0 / 3.0) if h > 0 else 0.0) - rhs
        if abs(g) <= tol or abs(g) <= 1e-10 * max(abs(rhs), 1.0):
            break
        if g > 0:
            hi = h
        else:
            lo = h
        h = 0.5 * (lo + hi)
    return max(0.0, min(h, rhs))


def run_simulation(
    dt: float,
    chuva_registros: np.ndarray | None = None,
    ac_df: pd.DataFrame | None = None,
    exutorio_id: int = 1,
    b_canal: float = 1.0,
    s_canal: float = 0.001,
    n_canal: float = 0.02,
    nivel_base: float = 0.0,
    intervalo_registro_s: float | None = None,
    unidade_chuva: str = UNIDADE_CHUVA_INTENSIDADE,
    tempo_recessao_s: float = 0.0,
    usar_horton: bool = False,
    horton_k_h_inv: float = 2.5,
    horton_f0_multiplicador: float = 1.0,
    chuva_mmh: np.ndarray | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Simula o evento com:
    - t=0 apenas como condicao inicial (sem avanco do balanco);
    - intensidade constante dentro de cada intervalo de registro;
    - registro no fim do intervalo = chuva do intervalo anterior;
    - passo interno `dt` independente do intervalo de registro;
    - periodo opcional de recessao com P=0 apos o fim da chuva;
    - infiltracao por balanco volumetrico (lamina + precipitacao + montante).

    Compatibilidade: `chuva_mmh` legado e interpretado como intensidade (mm/h).
    """
    if ac_df is None:
        raise ValueError("ac_df e obrigatorio.")
    if chuva_registros is None:
        if chuva_mmh is None:
            raise ValueError("Informe chuva_registros ou chuva_mmh.")
        chuva_registros = np.asarray(chuva_mmh, dtype=float)
        unidade_chuva = UNIDADE_CHUVA_INTENSIDADE
    else:
        chuva_registros = np.asarray(chuva_registros, dtype=float)

    dt = float(dt)
    if dt <= 0:
        raise ValueError("Passo de integracao deve ser maior que zero.")
    dt_reg = float(intervalo_registro_s if intervalo_registro_s is not None else dt)
    if dt_reg <= 0:
        raise ValueError("Intervalo de registro da chuva deve ser maior que zero.")
    if abs(dt_reg / dt - round(dt_reg / dt)) > 1e-9:
        raise ValueError("Passo de integracao deve dividir exatamente o intervalo de registro.")

    n_reg = len(chuva_registros)
    tempo_chuva_s = max(n_reg - 1, 0) * dt_reg
    tempo_recessao_s = max(float(tempo_recessao_s), 0.0)
    tempo_total_s = tempo_chuva_s + tempo_recessao_s
    n_intervals = int(round(tempo_total_s / dt))
    if abs(n_intervals * dt - tempo_total_s) > 1e-6:
        n_intervals = int(math.ceil(tempo_total_s / dt - 1e-12))
    n_steps = n_intervals + 1
    tempo_s = np.arange(n_steps, dtype=float) * dt

    # Taxa de precipitacao em cada instante de saida (t=0 -> 0; demais = taxa do intervalo que termina em t*dt)
    chuva_ms = np.zeros(n_steps, dtype=float)
    for t in range(1, n_steps):
        chuva_ms[t] = taxa_chuva_no_passo(
            t_end_s=float(tempo_s[t]),
            chuva_registros=chuva_registros,
            intervalo_registro_s=dt_reg,
            unidade=unidade_chuva,
            tempo_chuva_s=tempo_chuva_s,
        )
    chuva_mmh_eq = chuva_ms * 3600000.0

    ac_df, rede_meta = validar_e_preparar_rede_ac(ac_df, int(exutorio_id))
    n_ac = len(ac_df)
    ac_ids = ac_df["ID_AC"].tolist()
    id_to_idx = {ac_id: i for i, ac_id in enumerate(ac_ids)}
    upstream_of = rede_meta["upstream_of"]
    exutorio_id = int(rede_meta["exutorio_id"])

    # Validacao explicita de parametros de superficie (sem clamps silenciosos)
    for _, row in ac_df.iterrows():
        ac_id_v = int(row["ID_AC"])
        validar_parametros_superficie_ac(
            area_m2=float(row["Area_m2"]),
            comprimento_m=float(row["L_m"]),
            n_eq=float(row["n_eq"]),
            declividade=float(row["S_m_m"]),
            ac_id=ac_id_v,
        )
        h0_v = float(row["h0_m"])
        if not np.isfinite(h0_v) or h0_v < 0:
            raise ValueError(f"AC {ac_id_v}: `h0_m` deve ser finito e >= 0 (recebido: {row['h0_m']}).")
        infil_v = float(row["Infiltracao_eq_mm_h"])
        if not np.isfinite(infil_v) or infil_v < 0:
            raise ValueError(
                f"AC {ac_id_v}: `Infiltracao_eq_mm_h` deve ser finito e >= 0 (recebido: {row['Infiltracao_eq_mm_h']})."
            )
    for nome, valor in [
        ("B_canal", b_canal),
        ("S_canal", s_canal),
        ("n_canal", n_canal),
    ]:
        if not np.isfinite(float(valor)) or float(valor) <= 0:
            raise ValueError(f"`{nome}` deve ser finito e > 0 (recebido: {valor}).")
    if not np.isfinite(float(nivel_base)):
        raise ValueError(f"`nivel_base` deve ser finito (recebido: {nivel_base}).")

    h = np.zeros((n_steps, n_ac), dtype=float)
    q_out = np.zeros((n_steps, n_ac), dtype=float)
    q_in = np.zeros((n_steps, n_ac), dtype=float)
    i_excesso = np.zeros((n_steps, n_ac), dtype=float)
    infil_cap = np.zeros((n_steps, n_ac), dtype=float)
    infil_real = np.zeros((n_steps, n_ac), dtype=float)
    vol_inf = np.zeros((n_steps, n_ac), dtype=float)
    vol_inf_acum = np.zeros((n_steps, n_ac), dtype=float)
    vol_escoado = np.zeros((n_steps, n_ac), dtype=float)
    residuo_impl = np.zeros((n_steps, n_ac), dtype=float)
    t_umido_s = np.zeros(n_ac, dtype=float)

    # t = 0: somente condicoes iniciais (sem balanco hidrico)
    for j, row in ac_df.iterrows():
        h[0, j] = float(row["h0_m"])

    for j, row in ac_df.iterrows():
        area = float(row["Area_m2"])
        comp = float(row["L_m"])
        n_eq = float(row["n_eq"])
        decliv = float(row["S_m_m"])
        h0 = h[0, j]
        ac_id0 = int(row["ID_AC"])
        qin0 = 0.0
        for up_id in upstream_of[ac_id0]:
            qin0 += q_out[0, id_to_idx[up_id]]
        q_in[0, j] = qin0
        q_out[0, j] = manning_vazao_superficie(h0 * area, area, comp, n_eq, decliv)
        i_excesso[0, j] = 0.0
        infil_fc0 = float(row["Infiltracao_eq_mm_h"]) / 3600000.0
        if usar_horton:
            f0_0 = infil_fc0 * max(float(horton_f0_multiplicador), 1.0)
            infil_cap[0, j] = max(f0_0, infil_fc0)
        else:
            infil_cap[0, j] = infil_fc0
        infil_real[0, j] = 0.0
        vol_inf[0, j] = 0.0
        vol_inf_acum[0, j] = 0.0
        vol_escoado[0, j] = 0.0
        residuo_impl[0, j] = 0.0

    for t in range(1, n_steps):
        p_ms = float(chuva_ms[t])
        if p_ms < 0.0:
            raise ValueError(f"Taxa de precipitacao negativa no passo {t}: {p_ms}")
        for j, row in ac_df.iterrows():
            ac_id = int(row["ID_AC"])
            area = float(row["Area_m2"])
            comp = float(row["L_m"])
            n_eq = float(row["n_eq"])
            infil_fc_mmh = float(row["Infiltracao_eq_mm_h"])
            decliv = float(row["S_m_m"])

            h_prev = float(h[t - 1, j])
            if h_prev < 0.0:
                raise RuntimeError(f"AC {ac_id}: armazenamento negativo detectado em t={t-1}.")

            # Vazao a montante no mesmo passo (ordem topologica; cada montante uma unica vez)
            qin_t = 0.0
            for up_id in upstream_of[ac_id]:
                qin_t += q_out[t, id_to_idx[up_id]]
            if qin_t < 0.0:
                raise RuntimeError(f"AC {ac_id}: Q_in negativo no passo {t}.")
            q_in[t, j] = qin_t

            # Capacidade de infiltracao f (m/s): constante ou Horton
            infil_fc_ms = infil_fc_mmh / 3600000.0
            if usar_horton:
                t_umido_h = t_umido_s[j] / 3600.0
                infil_f0_ms = infil_fc_ms * max(float(horton_f0_multiplicador), 1.0)
                if infil_f0_ms < infil_fc_ms:
                    infil_f0_ms = infil_fc_ms
                f_ms = infil_fc_ms + (infil_f0_ms - infil_fc_ms) * math.exp(
                    -max(float(horton_k_h_inv), 0.0) * t_umido_h
                )
            else:
                f_ms = infil_fc_ms
            if f_ms < 0.0:
                raise RuntimeError(f"AC {ac_id}: capacidade de infiltracao negativa.")
            infil_cap[t, j] = f_ms

            # Balanco volumetrico ate a infiltracao
            v_anterior = h_prev * area
            v_precipitacao = p_ms * area * dt
            v_montante = qin_t * dt
            v_bruto = v_anterior + v_precipitacao + v_montante
            if v_bruto < 0.0:
                raise RuntimeError(f"AC {ac_id}: volume bruto negativo antes da infiltracao.")
            v_infiltracao = min(v_bruto, f_ms * area * dt)
            if v_infiltracao < 0.0:
                v_infiltracao = 0.0
            v_apos_inf = v_bruto - v_infiltracao
            if v_apos_inf < 0.0:
                v_apos_inf = 0.0

            vol_inf[t, j] = v_infiltracao
            vol_inf_acum[t, j] = vol_inf_acum[t - 1, j] + v_infiltracao
            infil_rate = v_infiltracao / (area * dt)
            infil_real[t, j] = infil_rate
            i_excesso[t, j] = max(0.0, p_ms + qin_t / area - infil_rate)

            if usar_horton and v_bruto > 0.0 and f_ms > 0.0:
                t_umido_s[j] += dt

            # Propagacao: V_novo + dt*Q(V_novo) = V_disponivel (apos infiltracao)
            sol = solve_surface_storage_implicit(
                v_disponivel=v_apos_inf,
                dt=dt,
                area_m2=area,
                comprimento_m=comp,
                n_eq=n_eq,
                declividade=decliv,
                ac_id=ac_id,
            )
            h[t, j] = float(sol["h_novo"])
            q_out[t, j] = float(sol["q_out"])
            vol_escoado[t, j] = float(sol["v_escoado"])
            residuo_impl[t, j] = float(sol["residuo"])

        # Conservacao de transferencia no passo: soma Q_in = soma Q_out das ACs com destino
        soma_qin = float(np.sum(q_in[t, :]))
        soma_qout_transf = 0.0
        for ac_k in ac_ids:
            if rede_meta["downstream_of"][ac_k] is not None:
                soma_qout_transf += float(q_out[t, id_to_idx[ac_k]])
        if abs(soma_qin - soma_qout_transf) > 1e-9 * max(1.0, abs(soma_qout_transf)):
            raise RuntimeError(
                f"Duplicacao/perda de volume transferido no passo {t}: "
                f"soma(Q_in)={soma_qin:.6g} != soma(Q_out com destino)={soma_qout_transf:.6g}."
            )

    if exutorio_id not in id_to_idx:
        raise ValueError(
            f"Exutorio invalido: AC {exutorio_id} ausente apos ordenacao. "
            "Nenhum exutorio substituto foi assumido."
        )

    q_ex = q_out[:, id_to_idx[exutorio_id]]
    nivel = solve_channel_depth(q_ex, b_canal, s_canal, n_canal, n_iter=5)
    cota = nivel + nivel_base
    j_ex = id_to_idx[exutorio_id]

    df_saida = pd.DataFrame(
        {
            "Passo": np.arange(n_steps),
            "Tempo_s": tempo_s,
            "P_mm_h": chuva_mmh_eq,
            "P_m_s": chuva_ms,
            "Q_ex_m3_s": q_ex,
            "Nivel_m": nivel,
            "Cota_abs_m": cota,
            "Infiltracao_cap_m_s": infil_cap[:, j_ex],
            "Infiltracao_real_m_s": infil_real[:, j_ex],
            "Volume_infiltrado_m3": vol_inf[:, j_ex],
            "Volume_infiltrado_acum_m3": vol_inf_acum[:, j_ex],
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
                "Infiltracao_cap_m_s": infil_cap[:, j],
                "Infiltracao_real_m_s": infil_real[:, j],
                "Volume_infiltrado_m3": vol_inf[:, j],
                "Volume_infiltrado_acum_m3": vol_inf_acum[:, j],
                "Volume_escoado_m3": vol_escoado[:, j],
                "Residuo_implicito_m3": residuo_impl[:, j],
                "Q_in_m3_s": q_in[:, j],
                "Q_out_m3_s": q_out[:, j],
                "h_m": h[:, j],
            }
        )
        registros.append(df_ac)
    df_ac_detalhe = pd.concat(registros, ignore_index=True)
    df_saida = df_saida.copy()
    df_saida["Modo_hidrologico"] = MODO_MHU_1_1
    df_ac_detalhe = df_ac_detalhe.copy()
    df_ac_detalhe["Modo_hidrologico"] = MODO_MHU_1_1
    return df_saida, df_ac_detalhe


def executar_simulacao_mhu(
    *,
    modo: str,
    dt: float,
    chuva_registros: np.ndarray,
    ac_df: pd.DataFrame,
    us_df: pd.DataFrame | None = None,
    exutorio_id: int,
    b_canal: float,
    s_canal: float,
    n_canal: float,
    nivel_base: float,
    intervalo_registro_s: float | None = None,
    unidade_chuva: str = UNIDADE_CHUVA_INTENSIDADE,
    tempo_recessao_s: float = 0.0,
    usar_horton: bool = False,
    horton_k_h_inv: float = 2.5,
    horton_f0_multiplicador: float = 1.0,
    estrategia_montante: str = "proporcional_area",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    """
    Despacha MHU 1.1 (equivalente) ou MHU 2.0 (por classe US).
    Retorna (df_saida, df_ac_detalhe, df_us_detalhe|None).
    """
    if modo == MODO_MHU_2_0:
        if us_df is None or us_df.empty:
            raise ValueError("O Modo MHU 2.0 exige tabela de unidades de uso do solo (US).")
        from mhu_modo2 import run_simulation_por_classe

        return run_simulation_por_classe(
            dt=dt,
            chuva_registros=chuva_registros,
            ac_df=ac_df,
            us_df=us_df,
            exutorio_id=exutorio_id,
            b_canal=b_canal,
            s_canal=s_canal,
            n_canal=n_canal,
            nivel_base=nivel_base,
            intervalo_registro_s=intervalo_registro_s,
            unidade_chuva=unidade_chuva,
            tempo_recessao_s=tempo_recessao_s,
            usar_horton=usar_horton,
            horton_k_h_inv=horton_k_h_inv,
            horton_f0_multiplicador=horton_f0_multiplicador,
            estrategia_montante=estrategia_montante,
            validar_e_preparar_rede_ac=validar_e_preparar_rede_ac,
            taxa_chuva_no_passo=taxa_chuva_no_passo,
            solve_surface_storage_implicit=solve_surface_storage_implicit,
            manning_vazao_superficie=manning_vazao_superficie,
            solve_channel_depth=solve_channel_depth,
            UNIDADE_CHUVA_INTENSIDADE=UNIDADE_CHUVA_INTENSIDADE,
        )

    df_s, df_ac = run_simulation(
        dt=dt,
        chuva_registros=chuva_registros,
        ac_df=ac_df,
        exutorio_id=exutorio_id,
        b_canal=b_canal,
        s_canal=s_canal,
        n_canal=n_canal,
        nivel_base=nivel_base,
        intervalo_registro_s=intervalo_registro_s,
        unidade_chuva=unidade_chuva,
        tempo_recessao_s=tempo_recessao_s,
        usar_horton=usar_horton,
        horton_k_h_inv=horton_k_h_inv,
        horton_f0_multiplicador=horton_f0_multiplicador,
    )
    return df_s, df_ac, None


def comparar_mhu_1_1_e_2_0(
    *,
    dt: float,
    chuva_registros: np.ndarray,
    ac_df: pd.DataFrame,
    us_df: pd.DataFrame,
    exutorio_id: int,
    b_canal: float,
    s_canal: float,
    n_canal: float,
    nivel_base: float,
    intervalo_registro_s: float,
    unidade_chuva: str,
    tempo_recessao_s: float,
    usar_horton: bool,
    horton_k_h_inv: float,
    horton_f0_multiplicador: float,
) -> dict:
    """Executa ambos os modos com os mesmos dados e resume diferenças."""
    kwargs = dict(
        dt=dt,
        chuva_registros=chuva_registros,
        ac_df=ac_df,
        us_df=us_df,
        exutorio_id=exutorio_id,
        b_canal=b_canal,
        s_canal=s_canal,
        n_canal=n_canal,
        nivel_base=nivel_base,
        intervalo_registro_s=intervalo_registro_s,
        unidade_chuva=unidade_chuva,
        tempo_recessao_s=tempo_recessao_s,
        usar_horton=usar_horton,
        horton_k_h_inv=horton_k_h_inv,
        horton_f0_multiplicador=horton_f0_multiplicador,
    )
    s1, ac1, _ = executar_simulacao_mhu(modo=MODO_MHU_1_1, **kwargs)
    s2, ac2, us2 = executar_simulacao_mhu(modo=MODO_MHU_2_0, **kwargs)
    cmp = pd.DataFrame(
        [
            {
                "Indicador": "Q_pico_m3_s",
                "MHU_1.1": float(s1["Q_ex_m3_s"].max()),
                "MHU_2.0": float(s2["Q_ex_m3_s"].max()),
            },
            {
                "Indicador": "Nivel_pico_m",
                "MHU_1.1": float(s1["Nivel_m"].max()),
                "MHU_2.0": float(s2["Nivel_m"].max()),
            },
            {
                "Indicador": "Volume_exutorio_m3",
                "MHU_1.1": float((s1["Q_ex_m3_s"].iloc[1:] * dt).sum()) if len(s1) > 1 else 0.0,
                "MHU_2.0": float((s2["Q_ex_m3_s"].iloc[1:] * dt).sum()) if len(s2) > 1 else 0.0,
            },
            {
                "Indicador": "Volume_infiltrado_total_m3",
                "MHU_1.1": float(ac1.loc[ac1["Passo"] > 0, "Volume_infiltrado_m3"].sum()),
                "MHU_2.0": float(ac2.loc[ac2["Passo"] > 0, "Volume_infiltrado_m3"].sum()),
            },
        ]
    )
    cmp["Diferenca"] = cmp["MHU_2.0"] - cmp["MHU_1.1"]
    cmp["Diferenca_pct"] = np.where(
        np.abs(cmp["MHU_1.1"]) > 1e-15,
        100.0 * cmp["Diferenca"] / cmp["MHU_1.1"],
        np.nan,
    )
    return {
        "resumo": cmp,
        "df_saida_1_1": s1,
        "df_saida_2_0": s2,
        "df_ac_1_1": ac1,
        "df_ac_2_0": ac2,
        "df_us_2_0": us2,
    }


def diagnosticar_balanco_hidrico(
    df_saida: pd.DataFrame,
    df_ac_detalhe: pd.DataFrame,
    ac_df: pd.DataFrame,
    exutorio_id: int,
    dt: float,
    tempo_chuva_s: float,
    tol_fechamento_m3: float = TOL_BALANCO_HIDRICO_M3_DEFAULT,
) -> dict:
    """
    Diagnostico do balanco hidrico por AC/passo e para a bacia.

    Erro_AC = V_ini + V_prec + V_mont - V_inf - V_saida - V_fin
    Erro_bacia = V_ini + V_prec - V_inf - V_exutorio - V_fin
    (transferencias internas entre ACs nao entram no balanco global.)

    A tolerancia de fechamento e apenas criterio NUMERICO; nao valida a fisica do modelo.
    """
    if df_saida is None or df_ac_detalhe is None or ac_df is None:
        raise ValueError("Resultados de simulacao incompletos para o balanco hidrico.")
    dt = float(dt)
    if dt <= 0:
        raise ValueError("`dt` deve ser > 0 para o balanco hidrico.")
    tol = float(tol_fechamento_m3)
    if not np.isfinite(tol) or tol < 0:
        raise ValueError("`tol_fechamento_m3` deve ser finita e >= 0.")

    ac_work = ac_df.copy()
    ac_work["ID_AC"] = pd.to_numeric(ac_work["ID_AC"], errors="coerce").astype(int)
    ac_work["Area_m2"] = pd.to_numeric(ac_work["Area_m2"], errors="coerce").astype(float)
    area_by_id = {int(r["ID_AC"]): float(r["Area_m2"]) for _, r in ac_work.iterrows()}
    area_total = float(sum(area_by_id.values()))
    if area_total <= 0:
        raise ValueError("Area total da bacia deve ser > 0.")

    df_s = df_saida.copy()
    df_s["Passo"] = pd.to_numeric(df_s["Passo"], errors="coerce").astype(int)
    df_s["Tempo_s"] = pd.to_numeric(df_s["Tempo_s"], errors="coerce").astype(float)
    df_s["P_m_s"] = pd.to_numeric(df_s["P_m_s"], errors="coerce").astype(float)
    df_s["Q_ex_m3_s"] = pd.to_numeric(df_s["Q_ex_m3_s"], errors="coerce").astype(float)
    p_by_passo = df_s.set_index("Passo")["P_m_s"].to_dict()
    qex_by_passo = df_s.set_index("Passo")["Q_ex_m3_s"].to_dict()
    tempo_by_passo = df_s.set_index("Passo")["Tempo_s"].to_dict()

    df_ac = df_ac_detalhe.copy()
    df_ac["Passo"] = pd.to_numeric(df_ac["Passo"], errors="coerce").astype(int)
    df_ac["ID_AC"] = pd.to_numeric(df_ac["ID_AC"], errors="coerce").astype(int)
    df_ac["h_m"] = pd.to_numeric(df_ac["h_m"], errors="coerce").astype(float)
    df_ac["Q_in_m3_s"] = pd.to_numeric(df_ac["Q_in_m3_s"], errors="coerce").astype(float)
    df_ac["Q_out_m3_s"] = pd.to_numeric(df_ac["Q_out_m3_s"], errors="coerce").astype(float)
    if "Volume_infiltrado_m3" in df_ac.columns:
        df_ac["Volume_infiltrado_m3"] = pd.to_numeric(df_ac["Volume_infiltrado_m3"], errors="coerce").astype(float)
    else:
        df_ac["Volume_infiltrado_m3"] = 0.0
    if "Volume_escoado_m3" in df_ac.columns:
        df_ac["Volume_escoado_m3"] = pd.to_numeric(df_ac["Volume_escoado_m3"], errors="coerce").astype(float)
    else:
        df_ac["Volume_escoado_m3"] = df_ac["Q_out_m3_s"] * dt

    h_lookup = {(int(r["ID_AC"]), int(r["Passo"])): float(r["h_m"]) for _, r in df_ac.iterrows()}
    passos = sorted(df_ac["Passo"].unique())
    tempo_chuva_s = max(float(tempo_chuva_s), 0.0)

    rows_passo = []
    for _, row in df_ac.iterrows():
        passo = int(row["Passo"])
        ac_id = int(row["ID_AC"])
        area = area_by_id.get(ac_id)
        if area is None:
            raise ValueError(f"AC {ac_id} presente nos resultados mas ausente em ac_df.")
        tempo_s = float(tempo_by_passo.get(passo, row.get("Tempo_s", passo * dt)))
        periodo = "chuva" if tempo_s <= tempo_chuva_s + 1e-9 else "recessao"
        if passo == 0:
            v_ini = area * float(row["h_m"])
            rows_passo.append(
                {
                    "Passo": passo,
                    "Tempo_s": tempo_s,
                    "Periodo": "inicial",
                    "ID_AC": ac_id,
                    "Area_m2": area,
                    "V_inicial_m3": v_ini,
                    "V_precipitacao_m3": 0.0,
                    "V_montante_m3": 0.0,
                    "V_infiltracao_m3": 0.0,
                    "V_saida_m3": 0.0,
                    "V_final_m3": v_ini,
                    "Erro_AC_m3": 0.0,
                    "Fecha_tol": True,
                }
            )
            continue

        h_prev = h_lookup.get((ac_id, passo - 1))
        if h_prev is None:
            raise ValueError(f"Falta h no passo {passo - 1} para AC {ac_id}.")
        v_ini = area * h_prev
        v_fin = area * float(row["h_m"])
        p_ms = float(p_by_passo.get(passo, 0.0))
        v_prec = max(p_ms, 0.0) * area * dt
        v_mont = max(float(row["Q_in_m3_s"]), 0.0) * dt
        v_inf = max(float(row["Volume_infiltrado_m3"]), 0.0)
        v_sai = max(float(row["Volume_escoado_m3"]), 0.0)
        erro = v_ini + v_prec + v_mont - v_inf - v_sai - v_fin
        rows_passo.append(
            {
                "Passo": passo,
                "Tempo_s": tempo_s,
                "Periodo": periodo,
                "ID_AC": ac_id,
                "Area_m2": area,
                "V_inicial_m3": v_ini,
                "V_precipitacao_m3": v_prec,
                "V_montante_m3": v_mont,
                "V_infiltracao_m3": v_inf,
                "V_saida_m3": v_sai,
                "V_final_m3": v_fin,
                "Erro_AC_m3": erro,
                "Fecha_tol": abs(erro) <= tol,
            }
        )

    df_passos = pd.DataFrame(rows_passo)

    def _resumo_ac(df_src: pd.DataFrame, label: str) -> pd.DataFrame:
        regs = []
        ativos = df_src[df_src["Passo"] > 0]
        for ac_id, area in area_by_id.items():
            sub = ativos[ativos["ID_AC"] == ac_id]
            # V_inicial do periodo = armazenamento no inicio do primeiro passo ativo do recorte
            if sub.empty:
                v0 = area * h_lookup.get((ac_id, 0), 0.0)
                vf = v0
                v_prec = v_mont = v_inf = v_sai = 0.0
                erro_sum = 0.0
            else:
                p0 = int(sub["Passo"].min())
                p1 = int(sub["Passo"].max())
                v0 = area * h_lookup.get((ac_id, p0 - 1), h_lookup.get((ac_id, 0), 0.0))
                vf = area * h_lookup.get((ac_id, p1), 0.0)
                v_prec = float(sub["V_precipitacao_m3"].sum())
                v_mont = float(sub["V_montante_m3"].sum())
                v_inf = float(sub["V_infiltracao_m3"].sum())
                v_sai = float(sub["V_saida_m3"].sum())
                erro_sum = float(sub["Erro_AC_m3"].sum())
            erro_periodo = v0 + v_prec + v_mont - v_inf - v_sai - vf
            regs.append(
                {
                    "Periodo": label,
                    "ID_AC": ac_id,
                    "Area_m2": area,
                    "V_inicial_m3": v0,
                    "V_precipitacao_m3": v_prec,
                    "V_montante_m3": v_mont,
                    "V_infiltracao_m3": v_inf,
                    "V_saida_m3": v_sai,
                    "V_final_m3": vf,
                    "Erro_AC_m3": erro_periodo,
                    "Erro_AC_soma_passos_m3": erro_sum,
                    "Fecha_tol": abs(erro_periodo) <= tol,
                }
            )
        return pd.DataFrame(regs)

    def _balanco_bacia(df_src: pd.DataFrame, label: str) -> dict:
        ativos = df_src[df_src["Passo"] > 0]
        if ativos.empty:
            v_ini = float(
                sum(area_by_id[a] * h_lookup.get((a, 0), 0.0) for a in area_by_id)
            )
            return {
                "Periodo": label,
                "V_inicial_m3": v_ini,
                "V_precipitacao_m3": 0.0,
                "V_infiltracao_m3": 0.0,
                "V_exutorio_m3": 0.0,
                "V_final_m3": v_ini,
                "Erro_bacia_m3": 0.0,
                "Erro_abs_m3": 0.0,
                "Erro_rel_pct": 0.0,
                "Coef_escoamento": float("nan"),
                "Pct_infiltrado": float("nan"),
                "Pct_armazenado": float("nan"),
                "Lamina_escoamento_mm": 0.0,
                "Lamina_infiltrada_mm": 0.0,
                "Volume_acum_exutorio_m3": 0.0,
                "Fecha_tol": True,
                "Tol_m3": tol,
            }

        p0 = int(ativos["Passo"].min())
        p1 = int(ativos["Passo"].max())
        v_ini = float(sum(area_by_id[a] * h_lookup.get((a, p0 - 1), 0.0) for a in area_by_id))
        v_fin = float(sum(area_by_id[a] * h_lookup.get((a, p1), 0.0) for a in area_by_id))
        # Precipitacao e infiltracao: somar por AC (sem contar montante)
        v_prec = float(ativos["V_precipitacao_m3"].sum())
        v_inf = float(ativos["V_infiltracao_m3"].sum())
        # Volume no exutorio: integrar Q_ex nos passos do periodo (sem transferencias internas)
        passos_periodo = sorted(ativos["Passo"].unique())
        v_ex = float(sum(max(qex_by_passo.get(p, 0.0), 0.0) * dt for p in passos_periodo))
        erro = v_ini + v_prec - v_inf - v_ex - v_fin
        escala = max(abs(v_prec), abs(v_ini), abs(v_fin), abs(v_ex), abs(v_inf), 1.0)
        erro_rel = 100.0 * erro / escala
        coef = (v_ex / v_prec) if abs(v_prec) > 1e-15 else float("nan")
        pct_inf = (100.0 * v_inf / v_prec) if abs(v_prec) > 1e-15 else float("nan")
        pct_arm = (100.0 * (v_fin - v_ini) / v_prec) if abs(v_prec) > 1e-15 else float("nan")
        return {
            "Periodo": label,
            "V_inicial_m3": v_ini,
            "V_precipitacao_m3": v_prec,
            "V_infiltracao_m3": v_inf,
            "V_exutorio_m3": v_ex,
            "V_final_m3": v_fin,
            "Erro_bacia_m3": erro,
            "Erro_abs_m3": abs(erro),
            "Erro_rel_pct": erro_rel,
            "Coef_escoamento": coef,
            "Pct_infiltrado": pct_inf,
            "Pct_armazenado": pct_arm,
            "Lamina_escoamento_mm": 1000.0 * v_ex / area_total,
            "Lamina_infiltrada_mm": 1000.0 * v_inf / area_total,
            "Volume_acum_exutorio_m3": v_ex,
            "Fecha_tol": abs(erro) <= tol,
            "Tol_m3": tol,
        }

    # Periodos: so chuva (Tempo_s <= tempo_chuva) e horizonte completo (chuva+recessao)
    df_chuva = df_passos[df_passos["Periodo"].isin(["inicial", "chuva"])].copy()
    # Inclui passo 0 sempre; passos de chuva; exclui recessao
    df_chuva = df_passos[(df_passos["Passo"] == 0) | (df_passos["Periodo"] == "chuva")].copy()
    df_completo = df_passos.copy()

    resumo_ac_chuva = _resumo_ac(df_chuva, "evento_chuva")
    resumo_ac_completo = _resumo_ac(df_completo, "chuva_mais_recessao")
    df_resumo_ac = pd.concat([resumo_ac_chuva, resumo_ac_completo], ignore_index=True)

    bacia_chuva = _balanco_bacia(df_chuva, "evento_chuva")
    bacia_completo = _balanco_bacia(df_completo, "chuva_mais_recessao")
    df_bacia = pd.DataFrame([bacia_chuva, bacia_completo])

    # Series acumuladas (horizonte completo) para graficos
    ativos_full = df_passos[df_passos["Passo"] > 0].copy()
    if ativos_full.empty:
        df_acum = pd.DataFrame(
            columns=[
                "Passo",
                "Tempo_s",
                "V_prec_acum_m3",
                "V_inf_acum_m3",
                "V_exutorio_acum_m3",
                "V_arm_bacia_m3",
            ]
        )
    else:
        # Agregar por passo
        prec_passo = ativos_full.groupby("Passo", as_index=False)["V_precipitacao_m3"].sum()
        inf_passo = ativos_full.groupby("Passo", as_index=False)["V_infiltracao_m3"].sum()
        prec_passo = prec_passo.merge(inf_passo, on="Passo", how="outer").fillna(0.0)
        prec_passo["Tempo_s"] = prec_passo["Passo"].map(tempo_by_passo)
        prec_passo = prec_passo.sort_values("Passo")
        prec_passo["V_prec_acum_m3"] = prec_passo["V_precipitacao_m3"].cumsum()
        prec_passo["V_inf_acum_m3"] = prec_passo["V_infiltracao_m3"].cumsum()
        prec_passo["V_exutorio_acum_m3"] = [
            sum(max(qex_by_passo.get(p, 0.0), 0.0) * dt for p in prec_passo["Passo"] if p <= passo)
            for passo in prec_passo["Passo"]
        ]
        arm = []
        for passo in prec_passo["Passo"]:
            arm.append(float(sum(area_by_id[a] * h_lookup.get((a, int(passo)), 0.0) for a in area_by_id)))
        prec_passo["V_arm_bacia_m3"] = arm
        df_acum = prec_passo[
            [
                "Passo",
                "Tempo_s",
                "V_prec_acum_m3",
                "V_inf_acum_m3",
                "V_exutorio_acum_m3",
                "V_arm_bacia_m3",
            ]
        ].copy()

    # Distribuicao percentual (completo e chuva) sobre precipitacao
    dist_rows = []
    for b in (bacia_chuva, bacia_completo):
        vp = b["V_precipitacao_m3"]
        base = abs(vp) if abs(vp) > 1e-15 else float("nan")
        dist_rows.append(
            {
                "Periodo": b["Periodo"],
                "Componente": "Infiltracao",
                "Volume_m3": b["V_infiltracao_m3"],
                "Percentual": 100.0 * b["V_infiltracao_m3"] / base if np.isfinite(base) else float("nan"),
            }
        )
        dist_rows.append(
            {
                "Periodo": b["Periodo"],
                "Componente": "Exutorio",
                "Volume_m3": b["V_exutorio_m3"],
                "Percentual": 100.0 * b["V_exutorio_m3"] / base if np.isfinite(base) else float("nan"),
            }
        )
        darm = b["V_final_m3"] - b["V_inicial_m3"]
        dist_rows.append(
            {
                "Periodo": b["Periodo"],
                "Componente": "Variacao_armazenamento",
                "Volume_m3": darm,
                "Percentual": 100.0 * darm / base if np.isfinite(base) else float("nan"),
            }
        )
        dist_rows.append(
            {
                "Periodo": b["Periodo"],
                "Componente": "Residuo_numerico",
                "Volume_m3": b["Erro_bacia_m3"],
                "Percentual": 100.0 * b["Erro_bacia_m3"] / base if np.isfinite(base) else float("nan"),
            }
        )
    df_distribuicao = pd.DataFrame(dist_rows)

    return {
        "df_passos": df_passos,
        "df_resumo_ac": df_resumo_ac,
        "df_bacia": df_bacia,
        "df_acumulados": df_acum,
        "df_distribuicao": df_distribuicao,
        "tol_m3": tol,
        "area_total_m2": area_total,
        "exutorio_id": int(exutorio_id),
        "tempo_chuva_s": tempo_chuva_s,
        "fecha_ok": bool(df_bacia["Fecha_tol"].all() and df_passos["Fecha_tol"].all()),
    }


def montar_excel_resultados(
    df_saida: pd.DataFrame,
    df_ac_detalhe: pd.DataFrame,
    balanco: dict | None = None,
    df_us_detalhe: pd.DataFrame | None = None,
    df_comparacao: pd.DataFrame | None = None,
) -> bytes:
    """Empacota saidas da simulacao e do diagnostico de balanco em Excel."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_saida.to_excel(writer, index=False, sheet_name="Exutorio")
        df_ac_detalhe.to_excel(writer, index=False, sheet_name="Detalhe_AC")
        if df_us_detalhe is not None and not df_us_detalhe.empty:
            df_us_detalhe.to_excel(writer, index=False, sheet_name="Detalhe_US")
        if df_comparacao is not None and not df_comparacao.empty:
            df_comparacao.to_excel(writer, index=False, sheet_name="Comparacao_1_1_x_2_0")
        if balanco is not None:
            balanco["df_passos"].to_excel(writer, index=False, sheet_name="Balanco_passos")
            balanco["df_resumo_ac"].to_excel(writer, index=False, sheet_name="Balanco_AC")
            balanco["df_bacia"].to_excel(writer, index=False, sheet_name="Balanco_bacia")
            balanco["df_acumulados"].to_excel(writer, index=False, sheet_name="Balanco_acumulados")
            balanco["df_distribuicao"].to_excel(writer, index=False, sheet_name="Balanco_distribuicao")
            pd.DataFrame(
                [
                    {
                        "Tol_fechamento_m3": balanco["tol_m3"],
                        "Nota": (
                            "Tolerancia de fechamento NUMERICO do balanco hidrico. "
                            "Nao constitui validacao fisica do modelo."
                        ),
                        "Fecha_ok": balanco["fecha_ok"],
                        "Area_total_m2": balanco["area_total_m2"],
                        "Exutorio_id": balanco["exutorio_id"],
                        "Tempo_chuva_s": balanco["tempo_chuva_s"],
                    }
                ]
            ).to_excel(writer, index=False, sheet_name="Balanco_meta")
    return output.getvalue()


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
    intervalo_registro_s: float | None = None,
    unidade_chuva: str = UNIDADE_CHUVA_INTENSIDADE,
    tempo_recessao_s: float = 0.0,
) -> pd.DataFrame:
    if df_obs is None or df_obs.empty:
        return pd.DataFrame()

    obs_base = df_obs[["Tempo_s", "Nivel_obs_m"]].copy()
    obs_base["Tempo_s"] = pd.to_numeric(obs_base["Tempo_s"], errors="coerce")
    obs_base["Nivel_obs_m"] = pd.to_numeric(obs_base["Nivel_obs_m"], errors="coerce")
    obs_base = obs_base.dropna(subset=["Tempo_s", "Nivel_obs_m"]).drop_duplicates(subset=["Tempo_s"])
    if len(obs_base) < 2:
        return pd.DataFrame()

    dt_reg = float(intervalo_registro_s if intervalo_registro_s is not None else dt_seg)
    registros = []
    for k_h in k_vals:
        for f0fc in f0fc_vals:
            df_saida_k, _ = run_simulation(
                dt=float(dt_seg),
                chuva_registros=chuva_mmh,
                ac_df=ac_df,
                exutorio_id=int(exutorio_id),
                b_canal=float(b_canal),
                s_canal=float(s_canal),
                n_canal=float(n_canal),
                nivel_base=float(nivel_base),
                intervalo_registro_s=dt_reg,
                unidade_chuva=unidade_chuva,
                tempo_recessao_s=float(tempo_recessao_s),
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


def _run_streamlit_ui() -> None:
    """UI Streamlit — só no entrypoint (evita reexecução ao importar app)."""
    st.set_page_config(
        page_title="MHU — Modelo Hidrológico Urbano",
        page_icon="💧",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    try:
        from plot_theme import register_mhu_plotly_theme
        from ui_components import inject_mhu_styles

        register_mhu_plotly_theme()
        inject_mhu_styles()
    except Exception:
        pass

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

    # Compatibilidade: nomes antigos de página → novos
    _LEGACY_PAGE_MAP = {
        "Simulação": "Nova simulação",
        "Balanço Hídrico": "Balanço hídrico",
        "Sugestão de calibração": "Calibração",
        "Descrição das variáveis": "Glossário de variáveis",
    }
    if st.session_state.get("pagina_menu") in _LEGACY_PAGE_MAP:
        st.session_state["pagina_menu"] = _LEGACY_PAGE_MAP[st.session_state["pagina_menu"]]

    if st.session_state.get("pending_page") is not None:
        dest = st.session_state["pending_page"]
        dest = _LEGACY_PAGE_MAP.get(dest, dest)
        st.session_state["pagina_menu"] = dest
        from ui_components import PAGE_ICONS

        st.session_state["pagina_menu_label"] = f"{PAGE_ICONS.get(dest, '•')}  {dest}"
        st.session_state["pending_page"] = None

    from ui_components import render_sidebar_nav

    pagina = render_sidebar_nav(default="Visão geral")

    if pagina == "Visão geral":
        from ui_pages import render_visao_geral

        render_visao_geral()

    elif pagina == "Resultados":
        from ui_pages import render_resultados

        render_resultados()

    elif pagina == "Metodologia":
        from ui_pages import render_metodologia

        render_metodologia()

    elif pagina == "Diagnóstico numérico":
        from ui_pages import render_diagnostico_numerico

        render_diagnostico_numerico()

    elif pagina == "Balanço hídrico":
        from ui_components import page_header

        page_header(
            "Balanço hídrico",
            "Diagnóstico de fechamento numérico de massa. "
            "Não confunda com validação física do modelo (ver Validação).",
        )
        st.session_state.setdefault("tol_balanco_m3", float(TOL_BALANCO_HIDRICO_M3_DEFAULT))
        tol_ui = st.number_input(
            "Tolerância de fechamento numérico (m³)",
            min_value=0.0,
            format="%.6e",
            key="tol_balanco_m3",
            help="Critério numérico |Erro| ≤ tol. Padrão 1e-6 m³. Não é validação física.",
        )

        df_s = st.session_state.get("df_saida_validacao")
        df_ac = st.session_state.get("df_ac_detalhe")
        ac_ref = st.session_state.get("ac_df_loaded")
        meta_sim = st.session_state.get("sim_meta_balanco")
        if df_s is None or df_ac is None or ac_ref is None or meta_sim is None:
            st.warning(
                "Nenhuma simulação disponível. Vá em **Nova simulação**, rode o modelo e volte a esta aba."
            )
        else:
            try:
                from plot_theme import COLOR_INFIL, COLOR_PREC, COLOR_Q, HYDRO, TEAL, ALERT, apply_mhu_layout
                from ui_components import chart_container, metric_cards

                bal = diagnosticar_balanco_hidrico(
                    df_saida=df_s,
                    df_ac_detalhe=df_ac,
                    ac_df=ac_ref,
                    exutorio_id=int(meta_sim["exutorio_id"]),
                    dt=float(meta_sim["dt"]),
                    tempo_chuva_s=float(meta_sim["tempo_chuva_s"]),
                    tol_fechamento_m3=float(tol_ui),
                )
                st.session_state["balanco_hidrico"] = bal
                df_bacia = bal["df_bacia"]
                row_ev = df_bacia[df_bacia["Periodo"] == "evento_chuva"].iloc[0]
                row_full = df_bacia[df_bacia["Periodo"] == "chuva_mais_recessao"].iloc[0]

                st.info(
                    f"Tolerância configurada: **{tol_ui:.3e} m³**. "
                    f"Fechamento numérico global: "
                    f"{'OK' if bal['fecha_ok'] else 'FORA DA TOLERÂNCIA'}."
                )

                st.subheader("Indicadores — evento de chuva")
                metric_cards(
                    [
                        {"label": "Erro abs.", "value": f"{row_ev['Erro_abs_m3']:.4e}", "unit": "m³"},
                        {"label": "Erro rel.", "value": f"{row_ev['Erro_rel_pct']:.4e}", "unit": "%"},
                        {
                            "label": "Coef. escoamento",
                            "value": f"{row_ev['Coef_escoamento']:.4f}" if np.isfinite(row_ev["Coef_escoamento"]) else "—",
                        },
                        {"label": "Vol. exutório", "value": f"{row_ev['Volume_acum_exutorio_m3']:.4f}", "unit": "m³"},
                        {
                            "label": "% infiltrado",
                            "value": f"{row_ev['Pct_infiltrado']:.2f}" if np.isfinite(row_ev["Pct_infiltrado"]) else "—",
                        },
                        {
                            "label": "% armazenado",
                            "value": f"{row_ev['Pct_armazenado']:.2f}" if np.isfinite(row_ev["Pct_armazenado"]) else "—",
                        },
                        {"label": "Lâmina escoamento", "value": f"{row_ev['Lamina_escoamento_mm']:.3f}", "unit": "mm"},
                        {"label": "Lâmina infiltrada", "value": f"{row_ev['Lamina_infiltrada_mm']:.3f}", "unit": "mm"},
                    ]
                )

                st.subheader("Indicadores — chuva + recessão")
                metric_cards(
                    [
                        {"label": "Erro abs.", "value": f"{row_full['Erro_abs_m3']:.4e}", "unit": "m³"},
                        {"label": "Erro rel.", "value": f"{row_full['Erro_rel_pct']:.4e}", "unit": "%"},
                        {
                            "label": "Coef. escoamento",
                            "value": f"{row_full['Coef_escoamento']:.4f}" if np.isfinite(row_full["Coef_escoamento"]) else "—",
                        },
                        {"label": "Vol. exutório", "value": f"{row_full['Volume_acum_exutorio_m3']:.4f}", "unit": "m³"},
                        {
                            "label": "% infiltrado",
                            "value": f"{row_full['Pct_infiltrado']:.2f}" if np.isfinite(row_full["Pct_infiltrado"]) else "—",
                        },
                        {
                            "label": "% armazenado",
                            "value": f"{row_full['Pct_armazenado']:.2f}" if np.isfinite(row_full["Pct_armazenado"]) else "—",
                        },
                        {"label": "Lâmina escoamento", "value": f"{row_full['Lamina_escoamento_mm']:.3f}", "unit": "mm"},
                        {"label": "Lâmina infiltrada", "value": f"{row_full['Lamina_infiltrada_mm']:.3f}", "unit": "mm"},
                    ]
                )

                # Sankey da distribuição (chuva + recessão) — apenas visual
                try:
                    v_prec = max(float(row_full["V_precipitacao_m3"]), 0.0)
                    v_inf = max(float(row_full["V_infiltracao_m3"]), 0.0)
                    v_ex = max(float(row_full["V_exutorio_m3"]), 0.0)
                    v_arm = max(float(row_full["V_final_m3"]) - float(row_full["V_inicial_m3"]), 0.0)
                    v_res = abs(float(row_full["Erro_bacia_m3"]))
                    fig_sankey = go.Figure(
                        data=[
                            go.Sankey(
                                node=dict(
                                    label=["Precipitação", "Infiltração", "Exutório", "Δ Armazenamento", "Resíduo |ε|"],
                                    color=[COLOR_PREC, COLOR_INFIL, COLOR_Q, TEAL, ALERT],
                                ),
                                link=dict(
                                    source=[0, 0, 0, 0],
                                    target=[1, 2, 3, 4],
                                    value=[v_inf, v_ex, v_arm, max(v_res, 1e-12)],
                                    color=[
                                        "rgba(38,166,154,0.35)",
                                        "rgba(23,107,135,0.35)",
                                        "rgba(16,59,83,0.25)",
                                        "rgba(217,119,54,0.35)",
                                    ],
                                ),
                            )
                        ]
                    )
                    apply_mhu_layout(fig_sankey, title="Distribuição volumétrica (chuva + recessão)", height=380)
                    chart_container(fig_sankey, filename="sankey_balanco", key="sankey_balanco")
                except Exception:
                    pass

                st.subheader("Volumes acumulados (bacia)")
                df_acum = bal["df_acumulados"]
                if not df_acum.empty:
                    fig_acum = go.Figure()
                    fig_acum.add_trace(
                        go.Scatter(
                            x=df_acum["Tempo_s"],
                            y=df_acum["V_prec_acum_m3"],
                            name="Precipitação acum.",
                            mode="lines",
                            line=dict(color=COLOR_PREC, width=2.2),
                        )
                    )
                    fig_acum.add_trace(
                        go.Scatter(
                            x=df_acum["Tempo_s"],
                            y=df_acum["V_inf_acum_m3"],
                            name="Infiltração acum.",
                            mode="lines",
                            line=dict(color=COLOR_INFIL, width=2.2),
                        )
                    )
                    fig_acum.add_trace(
                        go.Scatter(
                            x=df_acum["Tempo_s"],
                            y=df_acum["V_exutorio_acum_m3"],
                            name="Exutório acum.",
                            mode="lines",
                            line=dict(color=COLOR_Q, width=2.2),
                        )
                    )
                    fig_acum.add_trace(
                        go.Scatter(
                            x=df_acum["Tempo_s"],
                            y=df_acum["V_arm_bacia_m3"],
                            name="Armazenamento bacia",
                            mode="lines",
                            line=dict(color=HYDRO, width=2.2),
                        )
                    )
                    if float(meta_sim["tempo_chuva_s"]) > 0:
                        fig_acum.add_vline(
                            x=float(meta_sim["tempo_chuva_s"]),
                            line_dash="dash",
                            line_color="#888",
                            annotation_text="Fim da chuva",
                        )
                    apply_mhu_layout(fig_acum, title="Volumes acumulados na bacia")
                    fig_acum.update_layout(xaxis_title="Tempo (s)", yaxis_title="Volume (m³)")
                    chart_container(fig_acum, filename="balanco_acumulados", key="fig_bal_acum")

                st.subheader("Distribuição percentual dos componentes")
                fig_dist = px.bar(
                    bal["df_distribuicao"],
                    x="Componente",
                    y="Percentual",
                    color="Periodo",
                    barmode="group",
                    title="Percentuais em relação à precipitação do período",
                    color_discrete_sequence=[HYDRO, TEAL],
                )
                apply_mhu_layout(fig_dist)
                chart_container(fig_dist, filename="balanco_distribuicao", key="fig_bal_dist")

                st.subheader("Balanço da bacia")
                st.dataframe(bal["df_bacia"], use_container_width=True, hide_index=True)

                st.subheader("Resumo por AC")
                st.dataframe(bal["df_resumo_ac"], use_container_width=True, hide_index=True)

                st.subheader("Tabelas individuais por AC (passos)")
                ids_ac = sorted(bal["df_passos"]["ID_AC"].unique())
                ac_sel = st.selectbox("Selecionar AC", options=ids_ac, key="balanco_ac_sel")
                st.dataframe(
                    bal["df_passos"][bal["df_passos"]["ID_AC"] == ac_sel].reset_index(drop=True),
                    use_container_width=True,
                    hide_index=True,
                )

                st.download_button(
                    "Baixar Excel (simulação + balanço)",
                    data=montar_excel_resultados(df_s, df_ac, bal),
                    file_name="resultado_balanco_hidrico.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_balanco_excel",
                )
            except Exception as exc_bal:
                st.error(f"Erro no diagnóstico de balanço: {exc_bal}")

    elif pagina == "Comparação MHU 1.1 × 2.0":
        from ui_components import page_header

        page_header("Comparação MHU 1.1 × MHU 2.0")
        st.markdown(
            """
    O **MHU 2.0 (Modo 2)** processa cada classe de uso do solo com armazenamento, infiltração e
    vazão próprios. Isso é uma **mudança de concepção matemática**, não uma correção de programação
    do MHU 1.1 (parâmetros equivalentes por AC).

    Ambos os modos usam os **mesmos dados de entrada** (AC, US, chuva, canal, Δt). A distribuição
    da vazão de montante entre classes no Modo 2 segue a hipótese experimental de **mistura homogênea**
    (proporcional à área).
            """
        )
        ac_ref = st.session_state.get("ac_df_loaded")
        us_ref = st.session_state.get("us_df_loaded")
        chuva_ref = st.session_state.get("chuva_df_loaded")
        meta = st.session_state.get("sim_meta_balanco")
        if (
            not isinstance(ac_ref, pd.DataFrame)
            or ac_ref.empty
            or not isinstance(us_ref, pd.DataFrame)
            or us_ref.empty
            or not isinstance(chuva_ref, pd.DataFrame)
            or chuva_ref.empty
            or meta is None
        ):
            st.warning(
                "Carregue ou rode uma simulação na aba **Simulação** (com tabela US preenchida) "
                "para habilitar a comparação com os mesmos dados de entrada."
            )
        else:
            from mhu_modo2 import verificar_consistencia_areas_us, normalizar_areas_us_proporcional

            df_areas = verificar_consistencia_areas_us(ac_ref, us_ref)
            st.subheader("Consistência de áreas (AC × soma das US)")
            st.dataframe(df_areas, use_container_width=True, hide_index=True)
            inconsistentes = df_areas[~df_areas["Consistente"]]
            us_cmp = us_ref.copy()
            if not inconsistentes.empty:
                st.error(
                    "Há diferença entre a área da AC e a soma das áreas das classes US. "
                    "Erro absoluto e percentual estão na tabela acima. Corrija as áreas ou autorize "
                    "a normalização proporcional (não é feita silenciosamente)."
                )
                autorizar = st.checkbox(
                    "Autorizo normalização proporcional das áreas US para a comparação",
                    key="cmp_autorizar_norm_areas",
                )
                if autorizar:
                    us_cmp = normalizar_areas_us_proporcional(ac_ref, us_ref)
                    st.info("Áreas US normalizadas proporcionalmente para esta comparação.")
                else:
                    st.stop()

            if st.button("Executar comparação 1.1 × 2.0", type="primary", key="btn_comparar_mhu"):
                try:
                    unidade = str(meta.get("unidade_chuva", st.session_state.get("unidade_chuva", UNIDADE_CHUVA_INTENSIDADE)))
                    chuva_regs = extrair_valores_chuva_df(chuva_ref, unidade)
                    ac_m1 = ac_ref.copy()
                    if bool(st.session_state.get("usar_us_para_eq", True)):
                        ac_m1 = calcular_parametros_equivalentes_por_us(ac_m1, us_cmp)
                    resultado = comparar_mhu_1_1_e_2_0(
                        dt=float(meta["dt"]),
                        chuva_registros=chuva_regs,
                        ac_df=ac_m1,
                        us_df=us_cmp,
                        exutorio_id=int(meta["exutorio_id"]),
                        b_canal=float(st.session_state.get("b_canal", 4.0)),
                        s_canal=float(st.session_state.get("s_canal", 0.004)),
                        n_canal=float(st.session_state.get("n_canal", 0.018)),
                        nivel_base=float(st.session_state.get("nivel_base", 0.2)),
                        intervalo_registro_s=float(meta.get("intervalo_registro_s", meta["dt"])),
                        unidade_chuva=unidade,
                        tempo_recessao_s=float(meta.get("tempo_recessao_s", 0.0)),
                        usar_horton=bool(st.session_state.get("usar_horton", False)),
                        horton_k_h_inv=float(st.session_state.get("horton_k_h_inv", 2.5)),
                        horton_f0_multiplicador=float(st.session_state.get("horton_f0_multiplicador", 1.0)),
                    )
                    st.session_state["cmp_mhu"] = resultado
                    st.success("Comparação concluída.")
                except Exception as exc_cmp:
                    st.error(f"Erro na comparação: {exc_cmp}")

            cmp_store = st.session_state.get("cmp_mhu")
            if isinstance(cmp_store, dict) and "resumo" in cmp_store:
                st.subheader("Resumo de indicadores")
                st.dataframe(cmp_store["resumo"], use_container_width=True, hide_index=True)
                s1 = cmp_store["df_saida_1_1"].copy()
                s2 = cmp_store["df_saida_2_0"].copy()
                from plot_theme import COLOR_MHU11, COLOR_MHU20, apply_mhu_layout
                from ui_components import chart_container

                fig_cmp = go.Figure()
                fig_cmp.add_trace(
                    go.Scatter(
                        x=s1["Tempo_s"],
                        y=s1["Q_ex_m3_s"],
                        name="Q_ex MHU 1.1",
                        mode="lines",
                        line=dict(color=COLOR_MHU11, width=2.4),
                        hovertemplate="MHU 1.1: %{y:.4f} m³/s<extra></extra>",
                    )
                )
                fig_cmp.add_trace(
                    go.Scatter(
                        x=s2["Tempo_s"],
                        y=s2["Q_ex_m3_s"],
                        name="Q_ex MHU 2.0",
                        mode="lines",
                        line=dict(color=COLOR_MHU20, width=2.4, dash="dash"),
                        hovertemplate="MHU 2.0: %{y:.4f} m³/s<extra></extra>",
                    )
                )
                apply_mhu_layout(fig_cmp, title="Hidrograma no exutório — mesmos dados de entrada")
                fig_cmp.update_layout(xaxis_title="Tempo (s)", yaxis_title="Vazão (m³/s)")
                chart_container(fig_cmp, filename="comparacao_q", key="cmp_q")
                fig_n = go.Figure()
                fig_n.add_trace(
                    go.Scatter(
                        x=s1["Tempo_s"],
                        y=s1["Nivel_m"],
                        name="Nível MHU 1.1",
                        mode="lines",
                        line=dict(color=COLOR_MHU11, width=2.4),
                    )
                )
                fig_n.add_trace(
                    go.Scatter(
                        x=s2["Tempo_s"],
                        y=s2["Nivel_m"],
                        name="Nível MHU 2.0",
                        mode="lines",
                        line=dict(color=COLOR_MHU20, width=2.4, dash="dash"),
                    )
                )
                apply_mhu_layout(fig_n, title="Nível no canal — MHU 1.1 × 2.0")
                fig_n.update_layout(xaxis_title="Tempo (s)", yaxis_title="Nível (m)")
                chart_container(fig_n, filename="comparacao_nivel", key="cmp_n")
                st.download_button(
                    "Baixar Excel da comparação",
                    data=montar_excel_resultados(
                        cmp_store["df_saida_2_0"],
                        cmp_store["df_ac_2_0"],
                        df_us_detalhe=cmp_store.get("df_us_2_0"),
                        df_comparacao=cmp_store["resumo"],
                    ),
                    file_name="comparacao_mhu_1_1_x_2_0.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_cmp_mhu",
                )

    elif pagina == "Calibração":
        from ui_components import page_header

        page_header(
            "Calibração",
            "Valores de referência para infiltração (mm/h) e Manning (n) na superfície (US) e n do canal. "
            "Ordens de magnitude para eventos urbanos — calibre com dados locais e validação.",
        )
        st.info(
            "Use estas tabelas como **ponto de partida** na aba **Simulação** (campos US e `n_canal`). "
            "Ajuste dentro das faixas conforme solo, declividade, estado de conservação e comparação com observações."
        )

        st.subheader("Uso e ocupação do solo (superfície — plano inclinado)")
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
    **Referências usadas para sugerir faixas (valores iniciais de calibração):**

    - **Chow, V. T. (1959)** — *Open-Channel Hydraulics* (faixas clássicas de `n` de Manning para canais e superfícies).
    - **USDA-SCS / NRCS** — manuais hidrológicos e parâmetros de infiltração para diferentes coberturas e condições de solo.
    - **Tucci, C. E. M.** (drenagem urbana, edições diversas) — comportamento hidrológico em bacias urbanas brasileiras e uso de parâmetros de superfície.
    - **Akan, A. O. & Houghtalen, R. J.** — *Urban Hydrology, Hydraulics, and Stormwater Quality* (parâmetros típicos em drenagem urbana).

    **Nota técnica:** estes valores são **pontos de partida** para evento único; devem ser ajustados por calibração local (chuva-vazão/nível observado), considerando compactação, saturação antecedente, declividade, cobertura vegetal e estado de conservação das superfícies/canais.
            """
        )

    elif pagina == "Instruções":
        from ui_components import page_header

        page_header("Instruções de uso")
        st.markdown(
            """
    ### Fluxo recomendado

    1. **Configuração** (barra lateral): escolha o **modo hidrológico** (MHU 1.1 equivalente ou MHU 2.0 por classe), o **intervalo de registro da chuva**, o **passo de integração**, a **duração da chuva**, o **tempo de recessão** e a **unidade** (mm ou mm/h).
    2. **Parâmetros do canal**: largura, declividade, Manning e nível de base (cota opcional).
    3. **Áreas de contribuição (AC)**: informe geometria, declividade, montantes (`ACs_montante_ids` com IDs separados por `;`) e lâmina inicial `h0_m`. A rede deve ser **convergente**: cada AC (exceto o exutório) tem um único destino a jusante; o grafo interativo ajuda a conferir.
    4. **Unidades de uso do solo (US)**: preencha áreas e parâmetros por classe.
       - **Modo 1 (MHU 1.1)**: com a opção automática, `Infiltracao_eq_mm_h` e `n_eq` são médias ponderadas pela área.
       - **Modo 2 (MHU 2.0)**: cada classe evolui com A, n, f, V, h e Q próprios; a vazão da AC é Σ Q_ij. Não se calcula média de Manning. A soma das áreas das classes deve fechar com a área da AC (diferenças exigem correção ou autorização explícita de normalização).
    5. **Chuva**: edite a tabela de registros. O instante `t = 0` é apenas condição inicial. Cada valor no **fim** de um intervalo representa a precipitação do intervalo anterior.
    6. Clique em **Rodar simulação**. No Modo 2, visualize também resultados por classe US.
    7. Aba **Comparação MHU 1.1 × 2.0**: rode ambos os modos com os mesmos dados e compare hidrogramas/indicadores.
    8. Aba **Balanço Hídrico**: fechamento numérico de massa (não é validação física).
    9. Aba **Validação** / **Sugestão de calibração**: níveis observados e faixas de parâmetros.

    ### Observações

    - O **MHU 2.0** é experimental e representa **mudança de concepção matemática**, não apenas correção de código.
    - No Modo 2, a vazão de montante entre classes usa hipótese experimental de **mistura homogênea** (proporcional à área), com código preparado para outras estratégias.
    - O intervalo dos registros de precipitação é independente do passo interno de integração.
    - Simulações antigas com coluna `P_mm_h` são interpretadas como **intensidade em mm/h**.
    - Infiltração volumétrica + Euler implícito + rede convergente preservados em ambos os modos.
    - Snapshot congelado do MHU 1.1 em `snapshots/MHU_1.1/`.
            """
        )

    elif pagina == "Glossário de variáveis":
        from ui_components import page_header

        page_header("Glossário de variáveis", "Tabela de referência alinhada à metodologia do modelo.")
        st.dataframe(
            pd.DataFrame(GLOSSARIO_ROWS),
            use_container_width=True,
            hide_index=True,
        )

    elif pagina == "Simulações salvas":
        from ui_components import page_header

        page_header("Simulações salvas", "Carregue, exclua e reutilize simulações anteriores.")

        store = st.session_state.get("sim_store", {"last_id": None, "items": []})
        items = store.get("items", [])
        if not items:
            st.info("Nenhuma simulação salva ainda. Salve uma simulação na aba **Simulação**.")
        else:
            for item in sorted(items, key=lambda x: x.get("created_at", ""), reverse=True):
                titulo = item.get("titulo", "Sem título")
                created = item.get("created_at", "")
                with st.container(border=True):
                    st.markdown(f"**{titulo}**")
                    st.caption(f"Criada em: {created}")
                    c1, c2 = st.columns(2)
                    if c1.button("Usar nesta simulação", key=f"load_{item.get('id')}"):
                        aplicar_payload_em_session(item)
                        st.session_state["sim_store"]["last_id"] = item.get("id")
                        salvar_simulacoes_salvas(st.session_state["sim_store"])
                        st.session_state["pending_page"] = "Simulação"
                        st.rerun()
                    if c2.button("Excluir", key=f"del_{item.get('id')}"):
                        st.session_state["sim_store"]["items"] = [
                            x for x in st.session_state["sim_store"]["items"] if x.get("id") != item.get("id")
                        ]
                        if st.session_state["sim_store"].get("last_id") == item.get("id"):
                            st.session_state["sim_store"]["last_id"] = None
                        salvar_simulacoes_salvas(st.session_state["sim_store"])
                        st.rerun()

    elif pagina == "Validação":
        from ui_components import page_header

        page_header(
            "Validação: nível observado vs simulado",
            "Compare níveis medidos em campo com a série simulada no exutório. "
            "Indicadores elevados não classificam automaticamente o modelo como validado.",
        )

        df_sim = st.session_state.get("df_saida_validacao")
        if df_sim is None:
            st.warning(
                "Nenhuma simulação disponível. Vá em **Nova simulação**, preencha os dados e clique em **Rodar simulação**."
            )
        else:
            st.info(
                f"Série simulada carregada: **{len(df_sim)}** passos. "
                "Unidade de nível: metros (mesma referência do modelo)."
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
                            "Nível observado (m)",
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
                            st.success(f"Importados {len(df_up)} pontos; alinhados por Tempo_s à grade da simulação.")
                    except Exception as exc:
                        st.error(f"Erro ao ler CSV: {exc}")

            df_obs = st.session_state.get("df_validacao_obs")
            if df_obs is not None and "Nivel_obs_m" in df_obs.columns and "Nivel_sim_m" in df_obs.columns:
                mask = df_obs["Nivel_obs_m"].notna()
                n_valid = int(mask.sum())
                calibracao_habilitada = n_valid >= 2

                if not calibracao_habilitada:
                    st.warning("Informe pelo menos **2** valores de nível observado para calcular métricas e habilitar a calibração.")
                else:
                    obs = df_obs.loc[mask, "Nivel_obs_m"].astype(float).values
                    sim = df_obs.loc[mask, "Nivel_sim_m"].astype(float).values

                    nse = nash_sutcliffe_efficiency(obs, sim)
                    r2 = r2_pearson(obs, sim)
                    err_rmse = rmse(obs, sim)
                    err_mae = mae(obs, sim)
                    vb = vies_medio(obs, sim)

                    from ui_components import metric_cards, chart_container
                    from plot_theme import COLOR_OBS, COLOR_SIM, apply_mhu_layout, annotate_peak

                    metric_cards(
                        [
                            {"label": "NSE (Nash-Sutcliffe)", "value": f"{nse:.4f}"},
                            {"label": "R² (Pearson)", "value": f"{r2:.4f}"},
                            {"label": "RMSE", "value": f"{err_rmse:.4f}", "unit": "m"},
                            {"label": "MAE", "value": f"{err_mae:.4f}", "unit": "m"},
                            {"label": "Viés médio (sim − obs)", "value": f"{vb:.4f}", "unit": "m"},
                        ]
                    )
                    st.caption(
                        "Viés médio: média de (simulado − observado) nos passos com observação. "
                        "Indicadores elevados **não** classificam automaticamente o modelo como validado."
                    )

                    df_cmp = df_obs.loc[mask, ["Tempo_s", "Nivel_obs_m", "Nivel_sim_m"]].copy()
                    fig_val = go.Figure()
                    fig_val.add_trace(
                        go.Scatter(
                            x=df_cmp["Tempo_s"],
                            y=df_cmp["Nivel_sim_m"],
                            name="Nível simulado",
                            mode="lines",
                            line=dict(color=COLOR_SIM, width=2.4),
                            hovertemplate="Sim: %{y:.4f} m<extra></extra>",
                        )
                    )
                    fig_val.add_trace(
                        go.Scatter(
                            x=df_cmp["Tempo_s"],
                            y=df_cmp["Nivel_obs_m"],
                            name="Nível observado",
                            mode="markers+lines",
                            line=dict(color=COLOR_OBS, width=1.5, dash="dot"),
                            marker=dict(size=7, color=COLOR_OBS),
                            hovertemplate="Obs: %{y:.4f} m<extra></extra>",
                        )
                    )
                    apply_mhu_layout(fig_val, title="Nível observado vs simulado")
                    chart_container(fig_val, filename="validacao_nivel", key="fig_val_nivel")

                    pico_obs = float(np.nanmax(obs))
                    pico_sim = float(np.nanmax(sim))
                    fig_picos = go.Figure(
                        data=[
                            go.Bar(
                                x=["Observado", "Simulado"],
                                y=[pico_obs, pico_sim],
                                marker_color=[COLOR_OBS, COLOR_SIM],
                                text=[f"{pico_obs:.3f} m", f"{pico_sim:.3f} m"],
                                textposition="outside",
                                hovertemplate="%{x}: %{y:.4f} m<extra></extra>",
                            )
                        ]
                    )
                    apply_mhu_layout(fig_picos, title="Comparação dos picos de nível", height=360)
                    chart_container(fig_picos, filename="validacao_picos", key="fig_val_picos")
                    st.subheader("Tabela detalhada de comparação")
                    st.dataframe(df_cmp.reset_index(drop=True), use_container_width=True, hide_index=True)

                st.divider()
                st.subheader("Calibração automática (grade Horton)")
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
                    "Rodar calibração automática",
                    key="btn_calibracao_horton",
                    disabled=not calibracao_habilitada,
                    help="Disponível após informar pelo menos 2 níveis observados válidos.",
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
                                st.error("Dados de simulação não encontrados. Rode a simulação novamente antes de calibrar.")
                            else:
                                ac_cal = ac_loaded.copy()
                                ac_cal["ID_AC"] = pd.to_numeric(ac_cal["ID_AC"], errors="coerce").astype(int)
                                for col in ["Area_m2", "L_m", "S_m_m", "h0_m", "Infiltracao_eq_mm_h", "n_eq"]:
                                    ac_cal[col] = pd.to_numeric(ac_cal[col], errors="coerce").astype(float)

                                unidade_cal = str(
                                    st.session_state.get("unidade_chuva", UNIDADE_CHUVA_INTENSIDADE)
                                )
                                chuva_cal = extrair_valores_chuva_df(chuva_loaded, unidade_cal)
                                dt_int_cal = float(
                                    st.session_state.get(
                                        "dt_integracao_s", st.session_state.get("dt_seg", 600)
                                    )
                                )
                                dt_reg_cal = float(
                                    st.session_state.get(
                                        "intervalo_registro_s", st.session_state.get("dt_seg", 600)
                                    )
                                )
                                rec_cal_s = float(st.session_state.get("tempo_recessao_min", 0.0)) * 60.0
                                df_rank = calibrar_horton_em_grade(
                                    df_obs=df_obs,
                                    dt_seg=dt_int_cal,
                                    chuva_mmh=chuva_cal,
                                    ac_df=ac_cal,
                                    exutorio_id=int(st.session_state.get("exutorio_id", int(ac_cal["ID_AC"].max()))),
                                    b_canal=float(st.session_state.get("b_canal", 4.0)),
                                    s_canal=float(st.session_state.get("s_canal", 0.004)),
                                    n_canal=float(st.session_state.get("n_canal", 0.018)),
                                    nivel_base=float(st.session_state.get("nivel_base", 0.2)),
                                    k_vals=k_vals,
                                    f0fc_vals=f_vals,
                                    intervalo_registro_s=dt_reg_cal,
                                    unidade_chuva=unidade_cal,
                                    tempo_recessao_s=rec_cal_s,
                                )
                                if df_rank.empty:
                                    st.error("Não foi possível calibrar: sem pontos observados suficientes após alinhamento por Tempo_s.")
                                else:
                                    st.session_state["df_calibracao_horton"] = df_rank
                                    st.success(
                                        f"Calibração concluída com {len(df_rank)} combinações válidas."
                                    )
                    except Exception as exc:
                        st.error(f"Erro na calibração automática: {exc}")

                df_rank = st.session_state.get("df_calibracao_horton")
                if isinstance(df_rank, pd.DataFrame) and not df_rank.empty:
                    st.markdown("**Melhor combinação encontrada**")
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
                            unidade_ap = str(
                                st.session_state.get("unidade_chuva", UNIDADE_CHUVA_INTENSIDADE)
                            )
                            chuva_ap = extrair_valores_chuva_df(
                                st.session_state.get("chuva_df_loaded"), unidade_ap
                            )
                            dt_int_ap = float(
                                st.session_state.get(
                                    "dt_integracao_s", st.session_state.get("dt_seg", 600)
                                )
                            )
                            dt_reg_ap = float(
                                st.session_state.get(
                                    "intervalo_registro_s", st.session_state.get("dt_seg", 600)
                                )
                            )
                            rec_ap_s = float(st.session_state.get("tempo_recessao_min", 0.0)) * 60.0
                            df_saida_best, _ = run_simulation(
                                dt=dt_int_ap,
                                chuva_registros=chuva_ap,
                                ac_df=ac_ap,
                                exutorio_id=int(st.session_state.get("exutorio_id", int(ac_ap["ID_AC"].max()))),
                                b_canal=float(st.session_state.get("b_canal", 4.0)),
                                s_canal=float(st.session_state.get("s_canal", 0.004)),
                                n_canal=float(st.session_state.get("n_canal", 0.018)),
                                nivel_base=float(st.session_state.get("nivel_base", 0.2)),
                                intervalo_registro_s=dt_reg_ap,
                                unidade_chuva=unidade_ap,
                                tempo_recessao_s=rec_ap_s,
                                usar_horton=True,
                                horton_k_h_inv=float(best["k_h_inv"]),
                                horton_f0_multiplicador=float(best["f0_fc"]),
                            )
                            st.session_state["df_saida_validacao"] = df_saida_best.copy()
                            st.session_state["df_validacao_obs"] = montar_df_validacao(
                                df_saida_best, st.session_state.get("df_validacao_obs")
                            )
                            st.success(
                                "Melhor conjunto aplicado. Série simulada da validação foi atualizada com os novos parâmetros."
                            )
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Erro ao aplicar melhor conjunto: {exc}")

                if calibracao_habilitada:
                    st.subheader("Gráfico comparativo")
                    fig = go.Figure()
                    fig.add_trace(
                        go.Scatter(
                            x=df_obs["Tempo_s"],
                            y=df_obs["Nivel_sim_m"],
                            name="Nível simulado",
                            mode="lines",
                            line=dict(color="#1f77b4", width=2),
                        )
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=df_obs.loc[mask, "Tempo_s"],
                            y=obs,
                            name="Nível observado",
                            mode="markers+lines",
                            line=dict(color="#d62728", dash="dot"),
                            marker=dict(size=8),
                        )
                    )
                    fig.update_layout(
                        title="Nível no canal: observado vs simulado",
                        xaxis_title="Tempo (s)",
                        yaxis_title="Nível (m)",
                        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    st.subheader("Tabela de comparação (passos com observação)")
                    st.dataframe(
                        df_obs.loc[mask].reset_index(drop=True),
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.divider()
                st.subheader("Calibração automática (grade Horton)")
                st.caption(
                    "Preencha dados observados na grade ou via CSV para habilitar a calibração automática."
                )
                st.button(
                    "Rodar calibração automática",
                    key="btn_calibracao_horton_sem_dados",
                    disabled=True,
                    help="Disponível após informar pelo menos 2 níveis observados válidos.",
                )

    elif pagina == "Nova simulação":
        from ui_components import page_header

        page_header(
            "Nova simulação",
            "MHU 1.1 preservado (Modo 1) · MHU 2.0 experimental (Modo 2, por classe de uso do solo).",
        )

        # Defaults (ou ultimo salvo carregado)
        st.session_state.setdefault("dt_seg", 600)
        st.session_state.setdefault("intervalo_registro_s", int(st.session_state.get("dt_seg", 600)))
        st.session_state.setdefault("dt_integracao_s", int(st.session_state.get("dt_seg", 600)))
        st.session_state.setdefault("duracao_min", 40)
        st.session_state.setdefault("tempo_recessao_min", 0.0)
        st.session_state.setdefault("unidade_chuva", UNIDADE_CHUVA_INTENSIDADE)
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
        st.session_state.setdefault("modo_mhu", MODO_MHU_1_1)
        st.session_state.setdefault("titulo_salvar", "")
        st.session_state.setdefault("hora_inicio_evento", "12:00")
        st.session_state.setdefault("hora_fim_evento", "12:40")
        st.session_state.setdefault("_clear_sim_requested", False)
        st.session_state.setdefault("_show_clear_notice", False)
        st.session_state.setdefault("autorizar_norm_areas_us", False)

        if st.session_state.get("_clear_sim_requested"):
            st.session_state["ac_df_loaded"] = pd.DataFrame(
                columns=["ID_AC", "Area_m2", "L_m", "S_m_m", "ACs_montante_ids", "h0_m", "Infiltracao_eq_mm_h", "n_eq"]
            )
            st.session_state["us_df_loaded"] = pd.DataFrame(
                columns=["ID_AC", "ID_US", "Classe_US", "Area_US_m2", "Infiltracao_US_mm_h", "n_US"]
            )
            st.session_state["chuva_df_loaded"] = pd.DataFrame(columns=["Passo", "Tempo_s", "P_mm_h", "P_mm"])
            st.session_state["titulo_salvar"] = ""
            st.session_state["hora_inicio_evento"] = "12:00"
            st.session_state["hora_fim_evento"] = "12:40"
            st.session_state["tempo_recessao_min"] = 0.0
            st.session_state["unidade_chuva"] = UNIDADE_CHUVA_INTENSIDADE
            # Limpa estado interno dos widgets antes de renderizar novamente.
            st.session_state.pop("editor_ac", None)
            st.session_state.pop("editor_us", None)
            st.session_state.pop("editor_chuva", None)
            st.session_state["_clear_sim_requested"] = False
            st.session_state["_show_clear_notice"] = True

        if st.session_state.get("_show_clear_notice"):
            st.info("Campos da simulação limpos. Preencha novamente para iniciar do zero.")
            st.session_state["_show_clear_notice"] = False

        from ui_components import chart_container, fig_canal_secao, info_card

        tab_evt, tab_canal, tab_ac, tab_us, tab_chuva, tab_run = st.tabs(
            [
                "1. Evento",
                "2. Canal",
                "3. Áreas de contribuição",
                "4. Uso do solo",
                "5. Precipitação",
                "6. Revisão e execução",
            ]
        )

        with tab_evt:
            info_card(
                "Configuração do evento",
                "Defina formulação hidrológica, discretização temporal e opções de infiltração. "
                "Os valores permanecem em session_state ao navegar entre as etapas.",
            )
            modo_mhu = st.radio(
                "Formulação hidrológica",
                options=[MODO_MHU_1_1, MODO_MHU_2_0],
                format_func=lambda m: (
                    "Modo 1 — MHU 1.1 (parâmetros equivalentes por AC)"
                    if m == MODO_MHU_1_1
                    else "Modo 2 — MHU 2.0 (processamento por classe US)"
                ),
                key="modo_mhu",
                horizontal=True,
                help=(
                    "Modo 1 preserva o MHU 1.1. Modo 2 é experimental: cada classe US tem "
                    "armazenamento, infiltração e vazão próprios (mudança de concepção matemática)."
                ),
            )
            if modo_mhu == MODO_MHU_2_0:
                st.caption(
                    "MHU 2.0: Q_i = Σ Q_ij · W_ij = A_ij/L_i · hipótese experimental de mistura "
                    "homogênea para Q de montante (proporcional à área)."
                )
            c_a, c_b, c_c = st.columns(3)
            with c_a:
                intervalo_registro_s = st.number_input(
                    "Intervalo de registro da chuva (s)",
                    min_value=5,
                    step=5,
                    key="intervalo_registro_s",
                    help="Espaçamento temporal dos registros de precipitação (ex.: 600 s).",
                )
            opcoes_dt = passos_integracao_validos(int(intervalo_registro_s))
            with c_b:
                if not opcoes_dt:
                    st.error(
                        "Nenhum passo de integração permitido divide o intervalo de registro. "
                        f"Use um intervalo múltiplo de: {', '.join(str(x) for x in PASSOS_INTEGRACAO_PERMITIDOS)}."
                    )
                    dt_integracao_s = int(intervalo_registro_s)
                else:
                    atual_dt = int(st.session_state.get("dt_integracao_s", opcoes_dt[0]))
                    if atual_dt not in opcoes_dt:
                        st.session_state["dt_integracao_s"] = opcoes_dt[0]
                    dt_integracao_s = st.selectbox(
                        "Passo de integração numérica (s)",
                        options=opcoes_dt,
                        key="dt_integracao_s",
                        help="Passo interno do modelo; deve dividir o intervalo de registro.",
                    )
            st.session_state["dt_seg"] = int(dt_integracao_s)
            dt_seg = int(dt_integracao_s)
            with c_c:
                duracao_min = st.number_input("Duração da chuva (min)", min_value=5, step=5, key="duracao_min")
            c_d, c_e = st.columns(2)
            with c_d:
                tempo_recessao_min = st.number_input(
                    "Tempo de recessão após a chuva (min)",
                    min_value=0.0,
                    step=5.0,
                    key="tempo_recessao_min",
                    help="Período adicional com precipitação zero para avaliar a recessão.",
                )
            with c_e:
                unidade_chuva = st.radio(
                    "Unidade da precipitação",
                    options=[UNIDADE_CHUVA_INTENSIDADE, UNIDADE_CHUVA_ACUMULADA],
                    format_func=lambda u: (
                        "Intensidade (mm/h)" if u == UNIDADE_CHUVA_INTENSIDADE else "Acumulado por intervalo (mm)"
                    ),
                    key="unidade_chuva",
                    horizontal=True,
                )
            usar_horton = st.checkbox("Usar infiltração variável (Horton)", key="usar_horton")
            if usar_horton:
                st.caption("Modo avançado de infiltração para calibração.")
                h1, h2 = st.columns(2)
                horton_k_h_inv = h1.number_input("k de Horton (1/h)", min_value=0.0, step=0.1, key="horton_k_h_inv")
                horton_f0_multiplicador = h2.number_input(
                    "f0/fc de Horton", min_value=1.0, step=0.1, key="horton_f0_multiplicador"
                )
            else:
                st.caption("Modo metodologia: infiltração constante por US/AC.")
                horton_k_h_inv = float(st.session_state.get("horton_k_h_inv", 2.5))
                horton_f0_multiplicador = float(st.session_state.get("horton_f0_multiplicador", 1.0))

            n_registros = int(round((duracao_min * 60) / float(intervalo_registro_s))) + 1
            if abs((n_registros - 1) * float(intervalo_registro_s) - duracao_min * 60) > 1e-6:
                n_registros = int(math.ceil((duracao_min * 60) / float(intervalo_registro_s))) + 1
            tempo_chuva_s = (n_registros - 1) * float(intervalo_registro_s)
            tempo_total_s = tempo_chuva_s + float(tempo_recessao_min) * 60.0
            n_passos_int = int(round(tempo_total_s / float(dt_integracao_s))) + 1
            m_a, m_b, m_c = st.columns(3)
            m_a.metric("Registros de chuva", f"{n_registros} (inclui t=0)")
            m_b.metric("Passos de integração", f"{n_passos_int} (inclui CI)")
            m_c.metric("Horizonte total", f"{tempo_total_s/60:.1f} min")
            st.caption(
                "t=0 = condições iniciais. Cada registro no fim do intervalo representa a chuva do intervalo anterior."
            )

        with tab_canal:
            info_card(
                "Parâmetros hidráulicos do canal",
                "Seção retangular no exutório. O esquema abaixo é apenas visual e usa o nível da última simulação, se houver.",
            )
            col1, col2, col3, col4 = st.columns(4)
            b_canal = col1.number_input("B_canal (m)", min_value=0.1, key="b_canal")
            s_canal = col2.number_input("S_canal (m/m)", min_value=0.0001, format="%.4f", key="s_canal")
            n_canal = col3.number_input("n_canal", min_value=0.001, format="%.3f", key="n_canal")
            nivel_base = col4.number_input("Nível base (m)", format="%.3f", key="nivel_base")
            _df_prev = st.session_state.get("df_saida_validacao")
            _y_prev = float(_df_prev["Nivel_m"].max()) if isinstance(_df_prev, pd.DataFrame) and not _df_prev.empty else 0.0
            chart_container(
                fig_canal_secao(float(b_canal), nivel_m=_y_prev, nivel_base=float(nivel_base)),
                filename="secao_canal",
                key="fig_secao_canal",
            )

        with tab_ac:
            st.caption(
                "Rede convergente: cada AC (exceto o exutório) deve ter um único destino a jusante. "
                "A transferência de vazão entre ACs no mesmo passo interno é uma aproximação de "
                "reservatórios conectados, não uma hidráulica explícita dos canais de ligação."
            )
            n1, n2 = st.columns(2)
            n_ac = n1.number_input("Número de ACs", min_value=1, max_value=20, step=1, key="n_ac")
            exutorio_id = n2.number_input("ID da AC de exutório", min_value=1, max_value=20, step=1, key="exutorio_id")

            # Padrao convergente: ACs 1..n-1 → exutorio n (sem bifurcacao da mesma vazao)
            exut_padrao = int(n_ac)
            rows_ac_default = []
            for idx in range(1, int(n_ac) + 1):
                if idx == 1:
                    area, L, S, infil, n_eq = 85000.0, 350.0, 0.015, 12.0, 0.12
                elif idx == 2:
                    area, L, S, infil, n_eq = 92000.0, 420.0, 0.012, 10.0, 0.10
                elif idx == 3:
                    area, L, S, infil, n_eq = 130000.0, 500.0, 0.010, 8.0, 0.09
                else:
                    area, L, S, infil, n_eq = 100000.0, 400.0, 0.01, 10.0, 0.1
                if idx == exut_padrao:
                    montantes = ";".join(str(i) for i in range(1, exut_padrao)) if exut_padrao > 1 else "0"
                else:
                    montantes = "0"
                rows_ac_default.append(
                    {
                        "ID_AC": idx,
                        "Area_m2": area,
                        "L_m": L,
                        "S_m_m": S,
                        "ACs_montante_ids": montantes,
                        "h0_m": 0.0,
                        "Infiltracao_eq_mm_h": infil,
                        "n_eq": n_eq,
                    }
                )
            default_ac = pd.DataFrame(rows_ac_default)
            ac_df_edit = default_ac.copy()
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

            try:
                _ac_ord_ui, rede_ui = validar_e_preparar_rede_ac(ac_df, int(exutorio_id))
                st.success(
                    f"Rede válida: {rede_ui['n_ac']} ACs contribuem ao exutório {rede_ui['exutorio_id']} "
                    f"sem bifurcação de vazão (ordenação montante→jusante: {rede_ui['ordem_ids']})."
                )
                from plot_theme import apply_mhu_layout
                from ui_components import chart_container as _cc

                _fig_rede = fig_rede_conectividade_ac(rede_ui)
                apply_mhu_layout(_fig_rede, title="Rede de ACs")
                _cc(_fig_rede, filename="rede_acs", key="fig_rede_acs")
            except Exception as exc_rede:
                st.error(str(exc_rede))

        with tab_us:
            if modo_mhu == MODO_MHU_1_1:
                usar_us_para_eq = st.checkbox(
                    "Calcular Infiltracao_eq_mm_h e n_eq automaticamente a partir das US",
                    key="usar_us_para_eq",
                )
            else:
                usar_us_para_eq = False
                st.info(
                    "Modo 2 (MHU 2.0): cada classe US tem área, Manning, infiltração, armazenamento, "
                    "lâmina e vazão próprios. **Não** se calcula média aritmética de Manning. "
                    "A vazão da AC é a soma das vazões das classes."
                )
            classes_padrao = ["Superfície impermeável", "Gramado", "Vegetação arbórea"]
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

            from mhu_modo2 import verificar_consistencia_areas_us, normalizar_areas_us_proporcional

            df_areas_check = verificar_consistencia_areas_us(ac_df, us_df)
            st.subheader("Consistência de áreas (AC × soma das US)")
            st.dataframe(df_areas_check, use_container_width=True, hide_index=True)
            areas_ok = bool(df_areas_check["Consistente"].all()) if not df_areas_check.empty else False
            us_df_run = us_df.copy()
            if areas_ok:
                st.success("Soma das áreas das classes US coincide com a área de cada AC.")
            elif modo_mhu == MODO_MHU_2_0:
                st.error(
                    "Diferença entre área da AC e soma das classes US. "
                    "No Modo 2, corrija as áreas ou autorize explicitamente a normalização proporcional. "
                    "Não há normalização silenciosa."
                )
                autorizar_norm = st.checkbox(
                    "Autorizo normalização proporcional das áreas US à área da AC",
                    key="autorizar_norm_areas_us",
                )
                if autorizar_norm:
                    us_df_run = normalizar_areas_us_proporcional(ac_df, us_df)
                    st.warning("Áreas US serão normalizadas proporcionalmente nesta execução.")
                    st.dataframe(
                        verificar_consistencia_areas_us(ac_df, us_df_run),
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.warning(
                    "Há diferença entre área da AC e soma das US (ver erros abs./%). "
                    "No Modo 1 isso afeta apenas a ponderação dos equivalentes; no Modo 2 seria bloqueante."
                )

            if modo_mhu == MODO_MHU_1_1 and usar_us_para_eq:
                ac_preview = calcular_parametros_equivalentes_por_us(ac_df, us_df_run)
                st.caption("Parâmetros equivalentes calculados por US (ponderados pela área da AC) — apenas Modo 1.")
                st.dataframe(
                    ac_preview[["ID_AC", "Infiltracao_eq_mm_h", "n_eq"]],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                ac_preview = ac_df.copy()
                if modo_mhu == MODO_MHU_2_0:
                    if "Infiltracao_eq_mm_h" not in ac_preview.columns:
                        ac_preview["Infiltracao_eq_mm_h"] = 0.0
                    if "n_eq" not in ac_preview.columns:
                        ac_preview["n_eq"] = 0.1

        with tab_chuva:
            st.caption(
                "Unidade definida na etapa Evento. O valor no fim de cada intervalo de registro "
                "representa a precipitação ocorrida no intervalo anterior. Em t=0 não há avanço do balanço."
            )
            c_t1, c_t2 = st.columns(2)
            hora_inicio_str = c_t1.text_input("Horário de início do evento (HH:MM)", key="hora_inicio_evento")
            hora_fim_str = c_t2.text_input("Horário de término do evento (HH:MM)", key="hora_fim_evento")
            horario_ok = True
            try:
                inicio_h, inicio_m = [int(x) for x in hora_inicio_str.split(":")]
                fim_h, fim_m = [int(x) for x in hora_fim_str.split(":")]
                t_ini = datetime(2000, 1, 1, inicio_h, inicio_m)
                t_fim = datetime(2000, 1, 1, fim_h, fim_m)
                if t_fim < t_ini:
                    t_fim = t_fim + timedelta(days=1)
                duracao_horario_min = int((t_fim - t_ini).total_seconds() / 60)
                duracao_modelo_min = int(tempo_chuva_s / 60)
                if duracao_horario_min != duracao_modelo_min:
                    st.warning(
                        f"Duração por horário ({duracao_horario_min} min) difere da duração da chuva no modelo "
                        f"({duracao_modelo_min} min). O eixo será discretizado pelo passo de integração a partir do início."
                    )
            except Exception:
                horario_ok = False
                st.error("Formato de horário inválido. Use HH:MM, ex.: 12:00.")

            tempo_vec = np.arange(n_registros) * float(intervalo_registro_s)
            col_chuva = "P_mm" if unidade_chuva == UNIDADE_CHUVA_ACUMULADA else "P_mm_h"
            default_chuva = np.zeros(n_registros)
            if n_registros >= 5:
                if unidade_chuva == UNIDADE_CHUVA_ACUMULADA:
                    default_chuva[1:5] = np.array([18, 42, 25, 8], dtype=float) * float(intervalo_registro_s) / 3600.0
                else:
                    default_chuva[1:5] = [18, 42, 25, 8]
            chuva_df = pd.DataFrame(
                {"Passo": np.arange(n_registros), "Tempo_s": tempo_vec, col_chuva: default_chuva}
            )
            if st.session_state.get("_editor_chuva_unidade") != unidade_chuva:
                st.session_state.pop("editor_chuva", None)
                st.session_state["_editor_chuva_unidade"] = unidade_chuva
            if st.session_state.get("_editor_chuva_nreg") != n_registros:
                st.session_state.pop("editor_chuva", None)
                st.session_state["_editor_chuva_nreg"] = n_registros
            if st.session_state.get("_editor_chuva_dtreg") != int(intervalo_registro_s):
                st.session_state.pop("editor_chuva", None)
                st.session_state["_editor_chuva_dtreg"] = int(intervalo_registro_s)

            chuva_loaded = st.session_state.get("chuva_df_loaded")
            if isinstance(chuva_loaded, pd.DataFrame) and not chuva_loaded.empty:
                chuva_loaded = chuva_loaded.copy()
                src_col = None
                if col_chuva in chuva_loaded.columns:
                    src_col = col_chuva
                elif "P_mm_h" in chuva_loaded.columns:
                    src_col = "P_mm_h"
                elif "P_mm" in chuva_loaded.columns:
                    src_col = "P_mm"
                if src_col is not None:
                    chuva_df[col_chuva] = np.nan
                    n_copy = min(len(chuva_df), len(chuva_loaded))
                    vals_src = pd.to_numeric(chuva_loaded.iloc[:n_copy][src_col], errors="coerce").to_numpy()
                    if src_col != col_chuva and src_col == "P_mm_h" and col_chuva == "P_mm":
                        vals_src = vals_src * float(intervalo_registro_s) / 3600.0
                    elif src_col != col_chuva and src_col == "P_mm" and col_chuva == "P_mm_h":
                        vals_src = vals_src * 3600.0 / max(float(intervalo_registro_s), 1e-12)
                    chuva_df.loc[: n_copy - 1, col_chuva] = vals_src
            chuva_df_edit = st.data_editor(
                chuva_df,
                num_rows="fixed",
                use_container_width=True,
                hide_index=True,
                disabled=["Passo", "Tempo_s"],
                key="editor_chuva",
            )

            try:
                vals_ui = extrair_valores_chuva_df(chuva_df_edit, unidade_chuva)
                met_p = metricas_precipitacao(vals_ui, unidade_chuva, float(intervalo_registro_s))
                m1, m2, m3 = st.columns(3)
                m1.metric("Precipitação acumulada total (mm)", f"{met_p['P_acum_mm']:.2f}")
                m2.metric("Intensidade máxima (mm/h)", f"{met_p['I_max_mm_h']:.2f}")
                m3.metric("Duração do evento (min)", f"{met_p['Duracao_evento_min']:.1f}")
                if float(tempo_recessao_min) > 0:
                    st.caption(
                        f"Recessão configurada: {float(tempo_recessao_min):.1f} min com P=0 após o fim da chuva "
                        f"(horizonte total de simulação: {tempo_total_s / 60.0:.1f} min)."
                    )
            except Exception:
                pass

        with tab_run:
            info_card(
                "Revisão e execução",
                "Confira o resumo, salve a configuração e execute o modelo. "
                "A lógica hidrológica permanece inalterada.",
            )
            st.markdown(
                f"""
                - **Modo:** `{modo_mhu}`
                - **Δt registro / integração:** {int(intervalo_registro_s)} s / {int(dt_integracao_s)} s
                - **Duração chuva / recessão:** {int(duracao_min)} min / {float(tempo_recessao_min):.0f} min
                - **ACs / exutório:** {int(n_ac)} / {int(exutorio_id)}
                - **Canal:** B={float(b_canal):.2f} m · S={float(s_canal):.4f} · n={float(n_canal):.3f}
                """
            )
            st.text_input("Título da simulação para salvar", key="titulo_salvar", placeholder="Ex.: Evento 12/03/2026")
            g1, g2 = st.columns(2)
            if g1.button("Salvar simulação"):
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
                    us_df=us_df_run,
                    chuva_df=chuva_df_edit,
                    intervalo_registro_s=int(intervalo_registro_s),
                    dt_integracao_s=int(dt_integracao_s),
                    unidade_chuva=str(unidade_chuva),
                    tempo_recessao_min=float(tempo_recessao_min),
                    modo_mhu=str(modo_mhu),
                )
                store = st.session_state.get("sim_store", {"last_id": None, "items": []})
                store["items"] = [x for x in store.get("items", []) if x.get("id") != payload["id"]]
                store["items"].append(payload)
                store["last_id"] = payload["id"]
                st.session_state["sim_store"] = store
                salvar_simulacoes_salvas(store)
                st.success("Simulação salva com sucesso.")

            if g2.button("Limpar simulação"):
                st.session_state["_clear_sim_requested"] = True
                st.rerun()

            if st.button("Rodar simulação", type="primary"):
                try:
                    if not horario_ok:
                        st.error("Corrija os horários de início/fim antes de rodar a simulação.")
                        st.stop()
                    if (
                        modo_mhu == MODO_MHU_2_0
                        and not areas_ok
                        and not bool(st.session_state.get("autorizar_norm_areas_us", False))
                    ):
                        st.error(
                            "Modo 2: áreas US inconsistentes com as ACs. Corrija os valores ou autorize "
                            "a normalização proporcional antes de rodar."
                        )
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
                        us_df=us_df_run,
                        chuva_df=chuva_df_edit,
                        intervalo_registro_s=int(intervalo_registro_s),
                        unidade_chuva=str(unidade_chuva),
                        tempo_recessao_min=float(tempo_recessao_min),
                    )
                    if erros:
                        st.error("A simulação não pode rodar. Corrija os campos obrigatórios:")
                        for e in erros:
                            st.markdown(f"- {e}")
                        st.stop()

                    chuva_regs = extrair_valores_chuva_df(chuva_df_edit, str(unidade_chuva))
                    ac_df = ac_preview.copy()
                    ac_df["ID_AC"] = ac_df["ID_AC"].astype(int)
                    for col in ["Area_m2", "L_m", "S_m_m", "h0_m", "Infiltracao_eq_mm_h", "n_eq"]:
                        if col in ac_df.columns:
                            ac_df[col] = ac_df[col].astype(float)

                    df_saida, df_ac_detalhe, df_us_detalhe = executar_simulacao_mhu(
                        modo=str(modo_mhu),
                        dt=float(dt_integracao_s),
                        chuva_registros=chuva_regs,
                        ac_df=ac_df,
                        us_df=us_df_run,
                        exutorio_id=int(exutorio_id),
                        b_canal=float(b_canal),
                        s_canal=float(s_canal),
                        n_canal=float(n_canal),
                        nivel_base=float(nivel_base),
                        intervalo_registro_s=float(intervalo_registro_s),
                        unidade_chuva=str(unidade_chuva),
                        tempo_recessao_s=float(tempo_recessao_min) * 60.0,
                        usar_horton=bool(usar_horton),
                        horton_k_h_inv=float(horton_k_h_inv),
                        horton_f0_multiplicador=float(horton_f0_multiplicador),
                        estrategia_montante="proporcional_area",
                    )

                    tempo_chuva_s_run = max(len(chuva_regs) - 1, 0) * float(intervalo_registro_s)
                    st.session_state["df_saida_validacao"] = df_saida.copy()
                    st.session_state["df_ac_detalhe"] = df_ac_detalhe.copy()
                    st.session_state["df_us_detalhe"] = (
                        df_us_detalhe.copy() if df_us_detalhe is not None else None
                    )
                    st.session_state["df_validacao_obs"] = montar_df_validacao(
                        df_saida, st.session_state.get("df_validacao_obs")
                    )
                    st.session_state["ac_df_loaded"] = ac_df.copy()
                    st.session_state["us_df_loaded"] = us_df_run.copy()
                    st.session_state["chuva_df_loaded"] = chuva_df_edit.copy()
                    st.session_state["sim_meta_balanco"] = {
                        "dt": float(dt_integracao_s),
                        "tempo_chuva_s": float(tempo_chuva_s_run),
                        "tempo_recessao_s": float(tempo_recessao_min) * 60.0,
                        "exutorio_id": int(exutorio_id),
                        "intervalo_registro_s": float(intervalo_registro_s),
                        "unidade_chuva": str(unidade_chuva),
                        "modo_mhu": str(modo_mhu),
                    }

                    rotulo_modo = (
                        "MHU 1.1 (equivalente)" if modo_mhu == MODO_MHU_1_1 else "MHU 2.0 (por classe US)"
                    )
                    st.success(f"Simulação concluída — {rotulo_modo}.")
                    met_run = metricas_precipitacao(
                        chuva_regs, str(unidade_chuva), float(intervalo_registro_s)
                    )
                    r1, r2, r3 = st.columns(3)
                    r1.metric("Precipitação acumulada total (mm)", f"{met_run['P_acum_mm']:.2f}")
                    r2.metric("Intensidade máxima (mm/h)", f"{met_run['I_max_mm_h']:.2f}")
                    r3.metric("Duração do evento (min)", f"{met_run['Duracao_evento_min']:.1f}")

                    tempo_hhmm = montar_tempo_evento_hhmm(len(df_saida), int(dt_integracao_s), hora_inicio_str)
                    df_saida = df_saida.copy()
                    df_saida["Tempo_hhmm"] = tempo_hhmm
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Pico de vazão (m³/s)", f"{df_saida['Q_ex_m3_s'].max():.4f}")
                    c2.metric("Pico de nível (m)", f"{df_saida['Nivel_m'].max():.4f}")
                    c3.metric("Horário do pico", f"{df_saida.loc[df_saida['Nivel_m'].idxmax(), 'Tempo_hhmm']}")

                    st.plotly_chart(fig_nivel_com_hietograma(df_saida), use_container_width=True)

                    fig_q = px.line(df_saida, x="Tempo_hhmm", y="Q_ex_m3_s", title="Hidrograma de vazão no exutório")
                    fig_q.update_layout(xaxis_title="Horário", yaxis_title="Vazão (m³/s)")
                    st.plotly_chart(fig_q, use_container_width=True)

                    st.subheader("Saída - exutório")
                    st.dataframe(df_saida, use_container_width=True, hide_index=True)

                    st.subheader("Saída detalhada por AC")
                    ids_ac_out = sorted(df_ac_detalhe["ID_AC"].unique())
                    ac_out_sel = st.selectbox("Filtrar AC", options=["Todas"] + list(ids_ac_out), key="out_ac_sel")
                    if ac_out_sel == "Todas":
                        st.dataframe(df_ac_detalhe, use_container_width=True, hide_index=True)
                    else:
                        st.dataframe(
                            df_ac_detalhe[df_ac_detalhe["ID_AC"] == ac_out_sel].reset_index(drop=True),
                            use_container_width=True,
                            hide_index=True,
                        )

                    if df_us_detalhe is not None and not df_us_detalhe.empty:
                        st.subheader("Saída detalhada por classe de uso do solo (US)")
                        st.caption(
                            "Cada classe possui h, Q_out, infiltração e volumes próprios. "
                            "Estratégia de montante: mistura homogênea proporcional à área (experimental)."
                        )
                        ids_us_ac = sorted(df_us_detalhe["ID_AC"].unique())
                        us_ac_sel = st.selectbox("AC (detalhe US)", options=ids_us_ac, key="out_us_ac_sel")
                        df_us_ac = df_us_detalhe[df_us_detalhe["ID_AC"] == us_ac_sel]
                        ids_us = sorted(df_us_ac["ID_US"].unique())
                        us_sel = st.selectbox("Classe US", options=["Todas"] + list(ids_us), key="out_us_sel")
                        if us_sel == "Todas":
                            st.dataframe(df_us_ac.reset_index(drop=True), use_container_width=True, hide_index=True)
                            fig_us = px.line(
                                df_us_ac,
                                x="Tempo_s",
                                y="Q_out_m3_s",
                                color="Classe_US",
                                title=f"Vazão por classe US — AC {us_ac_sel}",
                            )
                            fig_us.update_layout(xaxis_title="Tempo (s)", yaxis_title="Q_out (m³/s)")
                            st.plotly_chart(fig_us, use_container_width=True)
                        else:
                            st.dataframe(
                                df_us_ac[df_us_ac["ID_US"] == us_sel].reset_index(drop=True),
                                use_container_width=True,
                                hide_index=True,
                            )

                    tol_xlsx = float(st.session_state.get("tol_balanco_m3", TOL_BALANCO_HIDRICO_M3_DEFAULT))
                    bal_xlsx = diagnosticar_balanco_hidrico(
                        df_saida=df_saida,
                        df_ac_detalhe=df_ac_detalhe,
                        ac_df=ac_df,
                        exutorio_id=int(exutorio_id),
                        dt=float(dt_integracao_s),
                        tempo_chuva_s=float(tempo_chuva_s_run),
                        tol_fechamento_m3=tol_xlsx,
                    )
                    st.session_state["balanco_hidrico"] = bal_xlsx
                    st.download_button(
                        "Baixar resultados em Excel",
                        data=montar_excel_resultados(
                            df_saida, df_ac_detalhe, bal_xlsx, df_us_detalhe=df_us_detalhe
                        ),
                        file_name="resultado_modelo_hidrologico.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                except Exception as exc:
                    st.error(f"Erro na simulação: {exc}")



# Entrypoint Streamlit: `streamlit run app.py` define __name__ == "__main__".
# Quando ui_pages/testes fazem `import app`, a UI não é renderizada de novo.
if __name__ == "__main__":
    _run_streamlit_ui()
