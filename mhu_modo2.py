# -*- coding: utf-8 -*-
"""
MHU 2.0 — processamento hidrológico individual por classe de uso do solo (US).

IMPORTANTE (concepção matemática):
O Modo 2 NÃO é apenas uma correção de programação do MHU 1.1. Trata-se de uma
mudança na formulação: em vez de parâmetros equivalentes por AC (média ponderada),
cada classe US evolui com armazenamento, infiltração e vazão próprios. A vazão da
AC é a soma das vazões das classes. A distribuição da vazão de montante entre
classes é, nesta versão experimental, proporcional à área (hipótese de mistura
homogênea), com interface preparada para outras estratégias futuras.
"""

from __future__ import annotations

import math
from typing import Callable

import numpy as np
import pandas as pd

# Estratégias de distribuição de Q_in entre classes (extensível)
ESTRATEGIA_MONTANTE_AREA = "proporcional_area"


def distribuir_montante_entre_classes(
    q_in_m3_s: float,
    areas_m2: np.ndarray,
    estrategia: str = ESTRATEGIA_MONTANTE_AREA,
) -> np.ndarray:
    """
    Distribui a vazão recebida de montante entre classes da mesma AC.

    Hipótese experimental atual (`proporcional_area`): mistura homogênea —
    cada classe recebe Q_in * (A_j / sum A).
    """
    q_in = float(q_in_m3_s)
    areas = np.asarray(areas_m2, dtype=float)
    if areas.ndim != 1 or len(areas) == 0:
        raise ValueError("areas_m2 deve ser um vetor 1D não vazio.")
    if np.any(~np.isfinite(areas)) or np.any(areas < 0):
        raise ValueError("Áreas das classes devem ser finitas e >= 0.")
    if q_in < 0:
        raise ValueError("Q_in negativo não é permitido.")

    if estrategia == ESTRATEGIA_MONTANTE_AREA:
        total = float(np.sum(areas))
        if total <= 0:
            return np.zeros_like(areas)
        return q_in * (areas / total)

    raise ValueError(
        f"Estratégia de distribuição de montante desconhecida: '{estrategia}'. "
        f"Disponível nesta versão: '{ESTRATEGIA_MONTANTE_AREA}'."
    )


# Registro para extensão futura
ESTRATEGIAS_DISTRIBUICAO_MONTANTE: dict[str, Callable[..., np.ndarray]] = {
    ESTRATEGIA_MONTANTE_AREA: distribuir_montante_entre_classes,
}


def verificar_consistencia_areas_us(
    ac_df: pd.DataFrame,
    us_df: pd.DataFrame,
    tol_rel: float = 1e-6,
) -> pd.DataFrame:
    """
    Compara Area_m2 da AC com a soma das Area_US_m2.
    Retorna DataFrame com erro absoluto (m²) e percentual.
    Não normaliza.
    """
    ac = ac_df.copy()
    us = us_df.copy()
    ac["ID_AC"] = pd.to_numeric(ac["ID_AC"], errors="coerce").astype(int)
    ac["Area_m2"] = pd.to_numeric(ac["Area_m2"], errors="coerce").astype(float)
    us["ID_AC"] = pd.to_numeric(us["ID_AC"], errors="coerce")
    us["Area_US_m2"] = pd.to_numeric(us["Area_US_m2"], errors="coerce")
    us = us.dropna(subset=["ID_AC", "Area_US_m2"])
    us["ID_AC"] = us["ID_AC"].astype(int)

    rows = []
    for _, row in ac.iterrows():
        ac_id = int(row["ID_AC"])
        a_ac = float(row["Area_m2"])
        a_us = float(us.loc[us["ID_AC"] == ac_id, "Area_US_m2"].sum()) if not us.empty else 0.0
        erro_abs = a_us - a_ac
        erro_pct = 100.0 * erro_abs / a_ac if abs(a_ac) > 1e-15 else float("nan")
        ok = abs(erro_abs) <= max(tol_rel * abs(a_ac), 1e-6)
        rows.append(
            {
                "ID_AC": ac_id,
                "Area_AC_m2": a_ac,
                "Soma_US_m2": a_us,
                "Erro_abs_m2": erro_abs,
                "Erro_pct": erro_pct,
                "Consistente": ok,
            }
        )
    return pd.DataFrame(rows)


def normalizar_areas_us_proporcional(ac_df: pd.DataFrame, us_df: pd.DataFrame) -> pd.DataFrame:
    """Normalização proporcional explícita (somente se o usuário autorizar)."""
    us_out = us_df.copy()
    us_out["ID_AC"] = pd.to_numeric(us_out["ID_AC"], errors="coerce")
    us_out["Area_US_m2"] = pd.to_numeric(us_out["Area_US_m2"], errors="coerce")
    ac = ac_df.copy()
    ac["ID_AC"] = pd.to_numeric(ac["ID_AC"], errors="coerce").astype(int)
    ac["Area_m2"] = pd.to_numeric(ac["Area_m2"], errors="coerce").astype(float)

    for _, row in ac.iterrows():
        ac_id = int(row["ID_AC"])
        a_ac = float(row["Area_m2"])
        mask = us_out["ID_AC"].astype(int) == ac_id
        soma = float(us_out.loc[mask, "Area_US_m2"].sum())
        if soma <= 0 or a_ac <= 0:
            continue
        us_out.loc[mask, "Area_US_m2"] = us_out.loc[mask, "Area_US_m2"] * (a_ac / soma)
    return us_out


def run_simulation_por_classe(
    dt: float,
    chuva_registros: np.ndarray,
    ac_df: pd.DataFrame,
    us_df: pd.DataFrame,
    exutorio_id: int,
    b_canal: float,
    s_canal: float,
    n_canal: float,
    nivel_base: float,
    intervalo_registro_s: float | None = None,
    unidade_chuva: str = "mm/h",
    tempo_recessao_s: float = 0.0,
    usar_horton: bool = False,
    horton_k_h_inv: float = 2.5,
    horton_f0_multiplicador: float = 1.0,
    estrategia_montante: str = ESTRATEGIA_MONTANTE_AREA,
    # injetados de app para evitar import circular de Streamlit
    *,
    validar_e_preparar_rede_ac,
    taxa_chuva_no_passo,
    solve_surface_storage_implicit,
    manning_vazao_superficie,
    solve_channel_depth,
    UNIDADE_CHUVA_INTENSIDADE: str = "mm/h",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    MHU 2.0: cada classe US tem V, h, f, n e Q próprios.
    Q_i = sum_j Q_ij; infiltração da AC = sum_j V_inf_ij.
    Não usa média aritmética de Manning.
    """
    dt = float(dt)
    if dt <= 0:
        raise ValueError("Passo de integração deve ser > 0.")

    ac_ord, rede = validar_e_preparar_rede_ac(ac_df, int(exutorio_id))
    upstream_of = rede["upstream_of"]
    exutorio_id = int(rede["exutorio_id"])
    ac_ids = ac_ord["ID_AC"].astype(int).tolist()
    id_to_idx = {ac_id: i for i, ac_id in enumerate(ac_ids)}
    n_ac = len(ac_ids)

    # Validação física AC
    for _, row in ac_ord.iterrows():
        ac_id = int(row["ID_AC"])
        for nome, val in [("Area_m2", row["Area_m2"]), ("L_m", row["L_m"]), ("S_m_m", row["S_m_m"])]:
            v = float(val)
            if not np.isfinite(v) or v <= 0:
                raise ValueError(f"AC {ac_id}: `{nome}` deve ser > 0.")
        if float(row["h0_m"]) < 0 or not np.isfinite(float(row["h0_m"])):
            raise ValueError(f"AC {ac_id}: `h0_m` deve ser >= 0.")

    for nome, valor in [("B_canal", b_canal), ("S_canal", s_canal), ("n_canal", n_canal)]:
        if not np.isfinite(float(valor)) or float(valor) <= 0:
            raise ValueError(f"`{nome}` deve ser > 0.")

    us = us_df.copy()
    for col in ["ID_AC", "ID_US", "Area_US_m2", "Infiltracao_US_mm_h", "n_US"]:
        if col not in us.columns:
            raise ValueError(f"Tabela US sem coluna obrigatória `{col}`.")
    us["ID_AC"] = pd.to_numeric(us["ID_AC"], errors="coerce")
    us["ID_US"] = pd.to_numeric(us["ID_US"], errors="coerce")
    us["Area_US_m2"] = pd.to_numeric(us["Area_US_m2"], errors="coerce")
    us["Infiltracao_US_mm_h"] = pd.to_numeric(us["Infiltracao_US_mm_h"], errors="coerce")
    us["n_US"] = pd.to_numeric(us["n_US"], errors="coerce")
    us = us.dropna(subset=["ID_AC", "ID_US", "Area_US_m2", "Infiltracao_US_mm_h", "n_US"])
    us["ID_AC"] = us["ID_AC"].astype(int)
    us["ID_US"] = us["ID_US"].astype(int)
    if us.empty:
        raise ValueError("Tabela US vazia: o Modo 2 exige classes de uso do solo.")

    # Índices planos de classes (na ordem das ACs topológicas)
    classes: list[dict] = []
    classes_por_ac: dict[int, list[int]] = {ac_id: [] for ac_id in ac_ids}
    for ac_id in ac_ids:
        sub = us[us["ID_AC"] == ac_id]
        if sub.empty:
            raise ValueError(f"AC {ac_id}: nenhuma classe US associada (obrigatório no Modo 2).")
        row_ac = ac_ord.loc[ac_ord["ID_AC"] == ac_id].iloc[0]
        L_i = float(row_ac["L_m"])
        S_i = float(row_ac["S_m_m"])
        h0 = float(row_ac["h0_m"])
        for _, urow in sub.iterrows():
            a_j = float(urow["Area_US_m2"])
            n_j = float(urow["n_US"])
            f_j = float(urow["Infiltracao_US_mm_h"])
            if a_j <= 0 or not np.isfinite(a_j):
                raise ValueError(f"AC {ac_id} / US {int(urow['ID_US'])}: Area_US_m2 deve ser > 0.")
            if n_j <= 0 or not np.isfinite(n_j):
                raise ValueError(f"AC {ac_id} / US {int(urow['ID_US'])}: n_US deve ser > 0.")
            if f_j < 0 or not np.isfinite(f_j):
                raise ValueError(f"AC {ac_id} / US {int(urow['ID_US'])}: Infiltracao_US_mm_h deve ser >= 0.")
            idx = len(classes)
            classes.append(
                {
                    "idx": idx,
                    "ID_AC": ac_id,
                    "ID_US": int(urow["ID_US"]),
                    "Classe_US": str(urow.get("Classe_US", "")),
                    "Area_m2": a_j,
                    "L_m": L_i,
                    "S_m_m": S_i,
                    "n": n_j,
                    "fc_mmh": f_j,
                    "h0_m": h0,
                }
            )
            classes_por_ac[ac_id].append(idx)

    n_cls = len(classes)
    chuva_registros = np.asarray(chuva_registros, dtype=float)
    dt_reg = float(intervalo_registro_s if intervalo_registro_s is not None else dt)
    if abs(dt_reg / dt - round(dt_reg / dt)) > 1e-9:
        raise ValueError("Passo de integração deve dividir o intervalo de registro.")
    n_reg = len(chuva_registros)
    tempo_chuva_s = max(n_reg - 1, 0) * dt_reg
    tempo_total_s = tempo_chuva_s + max(float(tempo_recessao_s), 0.0)
    n_intervals = int(round(tempo_total_s / dt))
    if abs(n_intervals * dt - tempo_total_s) > 1e-6:
        n_intervals = int(math.ceil(tempo_total_s / dt - 1e-12))
    n_steps = n_intervals + 1
    tempo_s = np.arange(n_steps, dtype=float) * dt

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

    # Estados por classe
    h_c = np.zeros((n_steps, n_cls), dtype=float)
    q_out_c = np.zeros((n_steps, n_cls), dtype=float)
    q_in_c = np.zeros((n_steps, n_cls), dtype=float)
    infil_cap_c = np.zeros((n_steps, n_cls), dtype=float)
    infil_real_c = np.zeros((n_steps, n_cls), dtype=float)
    vol_inf_c = np.zeros((n_steps, n_cls), dtype=float)
    vol_inf_acum_c = np.zeros((n_steps, n_cls), dtype=float)
    vol_esc_c = np.zeros((n_steps, n_cls), dtype=float)
    residuo_c = np.zeros((n_steps, n_cls), dtype=float)
    t_umido_c = np.zeros(n_cls, dtype=float)

    # Agregados por AC
    h_ac = np.zeros((n_steps, n_ac), dtype=float)
    q_out = np.zeros((n_steps, n_ac), dtype=float)
    q_in = np.zeros((n_steps, n_ac), dtype=float)
    i_excesso = np.zeros((n_steps, n_ac), dtype=float)
    infil_cap = np.zeros((n_steps, n_ac), dtype=float)
    infil_real = np.zeros((n_steps, n_ac), dtype=float)
    vol_inf = np.zeros((n_steps, n_ac), dtype=float)
    vol_inf_acum = np.zeros((n_steps, n_ac), dtype=float)
    vol_escoado = np.zeros((n_steps, n_ac), dtype=float)
    residuo_impl = np.zeros((n_steps, n_ac), dtype=float)

    # t=0 CI
    for c in classes:
        k = c["idx"]
        h_c[0, k] = c["h0_m"]
        q_out_c[0, k] = manning_vazao_superficie(
            c["h0_m"] * c["Area_m2"], c["Area_m2"], c["L_m"], c["n"], c["S_m_m"]
        )
        fc = c["fc_mmh"] / 3600000.0
        if usar_horton:
            infil_cap_c[0, k] = max(fc * max(float(horton_f0_multiplicador), 1.0), fc)
        else:
            infil_cap_c[0, k] = fc

    for ac_id in ac_ids:
        j = id_to_idx[ac_id]
        idxs = classes_por_ac[ac_id]
        area_ac = float(ac_ord.loc[ac_ord["ID_AC"] == ac_id, "Area_m2"].iloc[0])
        q_out[0, j] = float(np.sum(q_out_c[0, idxs]))
        v_tot = float(sum(h_c[0, k] * classes[k]["Area_m2"] for k in idxs))
        h_ac[0, j] = v_tot / area_ac if area_ac > 0 else 0.0
        # Q_in em t=0
        qin0 = 0.0
        for up in upstream_of[ac_id]:
            qin0 += q_out[0, id_to_idx[up]]
        q_in[0, j] = qin0
        areas_cls = np.array([classes[k]["Area_m2"] for k in idxs], dtype=float)
        q_parts = distribuir_montante_entre_classes(qin0, areas_cls, estrategia_montante)
        for m, k in enumerate(idxs):
            q_in_c[0, k] = float(q_parts[m])

    for t in range(1, n_steps):
        p_ms = float(chuva_ms[t])
        if p_ms < 0:
            raise ValueError(f"Precipitação negativa no passo {t}.")

        for ac_id in ac_ids:
            j = id_to_idx[ac_id]
            idxs = classes_por_ac[ac_id]
            area_ac = float(ac_ord.loc[ac_ord["ID_AC"] == ac_id, "Area_m2"].iloc[0])

            qin_t = 0.0
            for up in upstream_of[ac_id]:
                qin_t += q_out[t, id_to_idx[up]]
            q_in[t, j] = qin_t
            areas_cls = np.array([classes[k]["Area_m2"] for k in idxs], dtype=float)
            q_parts = distribuir_montante_entre_classes(qin_t, areas_cls, estrategia_montante)

            v_inf_ac = 0.0
            v_esc_ac = 0.0
            q_out_ac = 0.0
            v_arm_ac = 0.0
            res_ac = 0.0
            infil_cap_pond = 0.0
            infil_real_pond = 0.0

            for m, k in enumerate(idxs):
                c = classes[k]
                a_j = c["Area_m2"]
                q_in_c[t, k] = float(q_parts[m])
                h_prev = float(h_c[t - 1, k])

                fc_ms = c["fc_mmh"] / 3600000.0
                if usar_horton:
                    t_umido_h = t_umido_c[k] / 3600.0
                    f0 = fc_ms * max(float(horton_f0_multiplicador), 1.0)
                    if f0 < fc_ms:
                        f0 = fc_ms
                    f_ms = fc_ms + (f0 - fc_ms) * math.exp(-max(float(horton_k_h_inv), 0.0) * t_umido_h)
                else:
                    f_ms = fc_ms
                f_ms = max(f_ms, 0.0)
                infil_cap_c[t, k] = f_ms

                v_ant = h_prev * a_j
                v_prec = p_ms * a_j * dt
                v_mont = q_in_c[t, k] * dt
                v_bruto = v_ant + v_prec + v_mont
                v_inf = min(max(v_bruto, 0.0), f_ms * a_j * dt)
                v_apos = max(v_bruto - v_inf, 0.0)

                if usar_horton and v_bruto > 0 and f_ms > 0:
                    t_umido_c[k] += dt

                sol = solve_surface_storage_implicit(
                    v_disponivel=v_apos,
                    dt=dt,
                    area_m2=a_j,
                    comprimento_m=c["L_m"],
                    n_eq=c["n"],
                    declividade=c["S_m_m"],
                    ac_id=ac_id,
                )
                h_c[t, k] = float(sol["h_novo"])
                q_out_c[t, k] = float(sol["q_out"])
                vol_esc_c[t, k] = float(sol["v_escoado"])
                residuo_c[t, k] = float(sol["residuo"])
                vol_inf_c[t, k] = v_inf
                vol_inf_acum_c[t, k] = vol_inf_acum_c[t - 1, k] + v_inf
                infil_real_c[t, k] = v_inf / (a_j * dt) if dt > 0 else 0.0

                v_inf_ac += v_inf
                v_esc_ac += float(sol["v_escoado"])
                q_out_ac += float(sol["q_out"])
                v_arm_ac += float(sol["h_novo"]) * a_j
                res_ac += float(sol["residuo"])
                infil_cap_pond += f_ms * a_j
                infil_real_pond += (v_inf / (a_j * dt) if dt > 0 else 0.0) * a_j

            q_out[t, j] = q_out_ac
            h_ac[t, j] = v_arm_ac / area_ac if area_ac > 0 else 0.0
            vol_inf[t, j] = v_inf_ac
            vol_inf_acum[t, j] = vol_inf_acum[t - 1, j] + v_inf_ac
            vol_escoado[t, j] = v_esc_ac
            residuo_impl[t, j] = res_ac
            infil_cap[t, j] = infil_cap_pond / area_ac if area_ac > 0 else 0.0
            infil_real[t, j] = infil_real_pond / area_ac if area_ac > 0 else 0.0
            i_excesso[t, j] = max(0.0, p_ms + qin_t / area_ac - infil_real[t, j])

        # Conservação de transferência entre ACs
        soma_qin = float(np.sum(q_in[t, :]))
        soma_qout_transf = 0.0
        for ac_k in ac_ids:
            if rede["downstream_of"][ac_k] is not None:
                soma_qout_transf += float(q_out[t, id_to_idx[ac_k]])
        if abs(soma_qin - soma_qout_transf) > 1e-9 * max(1.0, abs(soma_qout_transf)):
            raise RuntimeError(
                f"Duplicação/perda de volume transferido no passo {t} (Modo 2): "
                f"soma(Q_in)={soma_qin:.6g} != soma(Q_out com destino)={soma_qout_transf:.6g}."
            )

    if exutorio_id not in id_to_idx:
        raise ValueError(f"Exutório inválido: AC {exutorio_id}.")

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
            "Modo_hidrologico": "MHU_2.0_por_classe",
        }
    )

    regs_ac = []
    for j, ac_id in enumerate(ac_ids):
        regs_ac.append(
            pd.DataFrame(
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
                    "h_m": h_ac[:, j],
                    "Modo_hidrologico": "MHU_2.0_por_classe",
                }
            )
        )
    df_ac_detalhe = pd.concat(regs_ac, ignore_index=True)

    regs_us = []
    for c in classes:
        k = c["idx"]
        regs_us.append(
            pd.DataFrame(
                {
                    "Passo": np.arange(n_steps),
                    "Tempo_s": tempo_s,
                    "ID_AC": c["ID_AC"],
                    "ID_US": c["ID_US"],
                    "Classe_US": c["Classe_US"],
                    "Area_US_m2": c["Area_m2"],
                    "n_US": c["n"],
                    "h_m": h_c[:, k],
                    "Q_in_m3_s": q_in_c[:, k],
                    "Q_out_m3_s": q_out_c[:, k],
                    "Infiltracao_cap_m_s": infil_cap_c[:, k],
                    "Infiltracao_real_m_s": infil_real_c[:, k],
                    "Volume_infiltrado_m3": vol_inf_c[:, k],
                    "Volume_infiltrado_acum_m3": vol_inf_acum_c[:, k],
                    "Volume_escoado_m3": vol_esc_c[:, k],
                    "Residuo_implicito_m3": residuo_c[:, k],
                    "Estrategia_montante": estrategia_montante,
                }
            )
        )
    df_us_detalhe = pd.concat(regs_us, ignore_index=True)
    return df_saida, df_ac_detalhe, df_us_detalhe
