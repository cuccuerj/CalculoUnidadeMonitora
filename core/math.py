import re
import numpy as np
import pandas as pd
import streamlit as st
from scipy.interpolate import RegularGridInterpolator

SAD = 100.0

# ══════════════════════════════════════════════════════════════════════════════
# TABELA DE FATORES EDW (Enhanced Dynamic Wedge)
# ══════════════════════════════════════════════════════════════════════════════
# Indexada por tamanho de campo Y (cm) × ângulo de cunha.
# Valores IN e OUT são idênticos para o fator de output.
# Fonte: dados comissionados da UNIQUE (GSTT).

_EDW_Y_SIZES = np.array([
    0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5,
    5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0,
])

_EDW_ANGLES = [0, 10, 15, 20, 25, 30, 45, 60]

_EDW_FACTORS = np.array([
    [1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 0.9577],
    [1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 0.9854, 0.9295],
    [1.0000, 1.0000, 1.0000, 1.0000, 0.9995, 0.9929, 0.9620, 0.9013],
    [1.0000, 1.0000, 0.9978, 0.9921, 0.9841, 0.9753, 0.9387, 0.8730],
    [1.0000, 0.9841, 0.9750, 0.9700, 0.9607, 0.9500, 0.9202, 0.8700],
    [1.0000, 0.9800, 0.9700, 0.9600, 0.9504, 0.9400, 0.8972, 0.8350],
    [1.0000, 0.9750, 0.9650, 0.9500, 0.9361, 0.9200, 0.8706, 0.7950],
    [1.0000, 0.9700, 0.9550, 0.9350, 0.9202, 0.9050, 0.8438, 0.7580],
    [1.0000, 0.9650, 0.9450, 0.9300, 0.9085, 0.8900, 0.8210, 0.7250],
    [1.0000, 0.9600, 0.9350, 0.9150, 0.8936, 0.8700, 0.7960, 0.6930],
    [1.0000, 0.9500, 0.9250, 0.9000, 0.8759, 0.8500, 0.7689, 0.6600],
    [1.0000, 0.9450, 0.9200, 0.8900, 0.8656, 0.8400, 0.7493, 0.6350],
    [1.0000, 0.9350, 0.9050, 0.8750, 0.8472, 0.8200, 0.7233, 0.6030],
    [1.0000, 0.9300, 0.8950, 0.8650, 0.8334, 0.8000, 0.7018, 0.5780],
    [1.0000, 0.9200, 0.8850, 0.8500, 0.8183, 0.7850, 0.6793, 0.5500],
    [1.0000, 0.9200, 0.8800, 0.8450, 0.8079, 0.7750, 0.6616, 0.5300],
    [1.0000, 0.9050, 0.8650, 0.8250, 0.7858, 0.7500, 0.6348, 0.5030],
    [1.0000, 0.8950, 0.8500, 0.8100, 0.7692, 0.7300, 0.6131, 0.4800],
    [1.0000, 0.8850, 0.8350, 0.7950, 0.7516, 0.7100, 0.496, 0.4580],
    [1.0000, 0.8650, 0.8150, 0.7600, 0.7287, 0.6850, 0.4965, 0.4350],
    [1.0000, 0.8550, 0.8000, 0.7550, 0.7107, 0.6700, 0.497, 0.4130],
])

# Mapa ângulo -> índice da coluna
_EDW_ANGLE_IDX = {a: i for i, a in enumerate(_EDW_ANGLES)}


def obter_fator_edw(filtro_nome: str, y_campo: float) -> float | None:
    """
    Retorna o fator EDW interpolado para o ângulo e tamanho de campo Y.

    Parâmetros
    ----------
    filtro_nome : str
        Nome do filtro, ex: "EDW45OUT", "EDW30IN", "EDW60OUT".
    y_campo : float
        Tamanho do campo Y em cm (jaw Y1 + Y2).

    Retorna
    -------
    float ou None
        Fator EDW interpolado. None se o filtro não for EDW.
    """
    m = re.match(r"EDW(\d+)", filtro_nome, re.IGNORECASE)
    if not m:
        return None

    angulo = int(m.group(1))
    if angulo not in _EDW_ANGLE_IDX:
        return None

    col = _EDW_ANGLE_IDX[angulo]

    # Interpolar na dimensão Y, clampando nos limites da tabela
    y_clamp = np.clip(y_campo, _EDW_Y_SIZES[0], _EDW_Y_SIZES[-1])
    return float(np.interp(y_clamp, _EDW_Y_SIZES, _EDW_FACTORS[:, col]))


# ══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES DE CÁLCULO EXISTENTES
# ══════════════════════════════════════════════════════════════════════════════
def calcular_eqsq(x, y):
    if x <= 0 or y <= 0:
        return 0.0
    return (4 * x * y) / (2 * (x + y))


def calcular_fator_distancia(ssd, prof, dmax, sad=SAD):
    if ssd <= 0:
        return 0.0
    return ((sad + dmax) / (prof + ssd)) ** 2


@st.cache_data
def carregar_tabelas_maquina(conteudo_texto):
    linhas = conteudo_texto.split('\n')
    campos, sc, sp, profundidades, tmr_matriz = [], [], [], [], []
    for linha in linhas:
        partes = linha.strip().split('\t')
        if len(partes) < 2:
            partes = linha.strip().split()
        if not partes or len(partes) < 2:
            continue

        rotulo = partes[0].strip().lower()
        try:
            valores = [float(v.replace(',', '.')) for v in partes[1:] if v.strip()]
        except ValueError:
            continue

        if rotulo == 'campo':
            campos = valores
        elif rotulo == 'sc':
            sc = valores
        elif rotulo == 'sp':
            sp = valores
        else:
            try:
                profundidades.append(float(rotulo.replace(',', '.')))
                tmr_matriz.append(valores)
            except ValueError:
                pass

    tmr_array = np.array(tmr_matriz)
    prof_array = np.array(profundidades)
    dmax_auto = 1.5
    if tmr_array.size > 0:
        idx = np.argmax(tmr_array[:, tmr_array.shape[1] // 2])
        dmax_auto = prof_array[idx]
    return np.array(campos), np.array(sc), np.array(sp), prof_array, tmr_array, dmax_auto


def processar_calculos_tabela(df_edit, campos_m, sc_m, sp_m, prof_m, tmr_m, dmax, dose_ref, dict_filtros):
    """
    Loop de cálculo por todos os campos. Retorna DataFrame com resultados.

    Para filtros EDW, o fator é calculado automaticamente a partir da tabela
    comissionada (ângulo × tamanho Y). Para outros filtros (Acrílico, etc.),
    usa o dict_filtros da sidebar.
    """
    interp_tmr = RegularGridInterpolator(
        (prof_m, campos_m), tmr_m, bounds_error=False, fill_value=None
    )
    resultados = []

    for _, row in df_edit.iterrows():
        eqsq_c = calcular_eqsq(row["X"], row["Y"])
        eqsq_f = calcular_eqsq(row["Fsx (cm)"], row["Fsy (cm)"])
        isqf = calcular_fator_distancia(row["SSD"], row["Prof."], dmax=dmax)
        sc_v = np.interp(eqsq_c, campos_m, sc_m)
        sp_v = np.interp(eqsq_f, campos_m, sp_m)
        tmr_v = (
            float(interp_tmr((row["Prof. Ef."], eqsq_f)))
            if row["Prof. Ef."] > 0 and eqsq_f > 0
            else 0.0
        )

        # ── Fator de filtro ──
        filtro_nome = row["FILTRO"]
        ff_edw = obter_fator_edw(filtro_nome, row["Y"])
        if ff_edw is not None:
            ff = ff_edw
        else:
            ff = dict_filtros.get(filtro_nome, 1.0)

        oar = row.get("OAR", 1.0)

        denom = dose_ref * sc_v * sp_v * tmr_v * isqf * ff * oar
        um_c = row["DOSE (cGy)"] / denom if denom > 0 else 0.0
        dev = (
            ((um_c - row["UM (Eclipse)"]) / row["UM (Eclipse)"]) * 100
            if row["UM (Eclipse)"] > 0
            else 0.0
        )

        resultados.append({
            "Campo": row["Campo"],
            "Aparelho": row["Aparelho"],
            "Energia": row["Energia"],
            "X": row["X"],
            "Y": row["Y"],
            "EqSq Colimador": eqsq_c,
            "EqSq Fantoma": eqsq_f,
            "SSD": row["SSD"],
            "DOSE (cGy)": row["DOSE (cGy)"],
            "Prof.": row["Prof."],
            "Prof. Ef.": row["Prof. Ef."],
            "Sc": sc_v,
            "Sp": sp_v,
            "TMR": tmr_v,
            "ISQF": isqf,
            "Fator Filtro": ff,
            "OAR": oar,
            "UM Calculada": um_c,
            "UM (Eclipse)": row["UM (Eclipse)"],
            "Desvio_num": dev,
        })
    return pd.DataFrame(resultados)
