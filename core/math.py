import re
import numpy as np
import pandas as pd
import streamlit as st
from scipy.interpolate import RegularGridInterpolator

SAD = 100.0

# ══════════════════════════════════════════════════════════════════════════════
# TABELAS DE FATORES EDW (Enhanced Dynamic Wedge)
# ══════════════════════════════════════════════════════════════════════════════
# Indexadas por jaw individual (Y1 ou Y2) em cm × ângulo de cunha.
# IN e OUT usam a mesma tabela de fatores, mas jaws diferentes:
#   EDW OUT → interpola com Y1
#   EDW IN  → interpola com Y2
# Tabelas separadas para 6MV e 10MV.

_EDW_JAW_SIZES = np.array([
    0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5,
    5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0,
])

_EDW_ANGLES = [10, 15, 20, 25, 30, 45, 60]

# ── 6MV ──
_EDW_FACTORS_6MV = np.array([
    # EDW10   EDW15   EDW20   EDW25   EDW30   EDW45   EDW60
    [1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 0.9577],  # 0
    [1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 0.9854, 0.9295],  # 0.5
    [1.0000, 1.0000, 1.0000, 0.9995, 0.9929, 0.9620, 0.9013],  # 1
    [1.0000, 0.9978, 0.9921, 0.9841, 0.9753, 0.9387, 0.8730],  # 1.5
    [0.9841, 0.9750, 0.9700, 0.9607, 0.9500, 0.9202, 0.8700],  # 2
    [0.9800, 0.9700, 0.9600, 0.9504, 0.9400, 0.8972, 0.8350],  # 2.5
    [0.9750, 0.9650, 0.9500, 0.9361, 0.9200, 0.8706, 0.7950],  # 3
    [0.9700, 0.9550, 0.9350, 0.9202, 0.9050, 0.8438, 0.7580],  # 3.5
    [0.9650, 0.9450, 0.9300, 0.9085, 0.8900, 0.8210, 0.7250],  # 4
    [0.9600, 0.9350, 0.9150, 0.8936, 0.8700, 0.7960, 0.6930],  # 4.5
    [0.9500, 0.9250, 0.9000, 0.8759, 0.8500, 0.7689, 0.6600],  # 5
    [0.9450, 0.9200, 0.8900, 0.8656, 0.8400, 0.7493, 0.6350],  # 5.5
    [0.9350, 0.9050, 0.8750, 0.8472, 0.8200, 0.7233, 0.6030],  # 6
    [0.9300, 0.8950, 0.8650, 0.8334, 0.8000, 0.7018, 0.5780],  # 6.5
    [0.9200, 0.8850, 0.8500, 0.8183, 0.7850, 0.6793, 0.5500],  # 7
    [0.9200, 0.8800, 0.8450, 0.8079, 0.7750, 0.6616, 0.5300],  # 7.5
    [0.9050, 0.8650, 0.8250, 0.7858, 0.7500, 0.6348, 0.5030],  # 8
    [0.8950, 0.8500, 0.8100, 0.7692, 0.7300, 0.6131, 0.4800],  # 8.5
    [0.8850, 0.8350, 0.7950, 0.7516, 0.7100, 0.5910, 0.4580],  # 9
    [0.8650, 0.8150, 0.7600, 0.7287, 0.6850, 0.5655, 0.4350],  # 9.5
    [0.8550, 0.8000, 0.7550, 0.7107, 0.6700, 0.5444, 0.4130],  # 10
])

# ── 10MV ──
_EDW_FACTORS_10MV = np.array([
    # EDW10   EDW15   EDW20   EDW25   EDW30   EDW45   EDW60
    [1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 0.9711],  # 0
    [1.0000, 1.0000, 1.0000, 1.0000, 1.0000, 0.9909, 0.9453],  # 0.5
    [1.0000, 1.0000, 1.0000, 1.0000, 0.9950, 0.9706, 0.9196],  # 1
    [1.0000, 0.9962, 0.9948, 0.9880, 0.9804, 0.9503, 0.8938],  # 1.5
    [0.9940, 0.9840, 0.9820, 0.9740, 0.9650, 0.9380, 0.8920],  # 2
    [0.9890, 0.9790, 0.9720, 0.9620, 0.9490, 0.9150, 0.8580],  # 2.5
    [0.9840, 0.9710, 0.9620, 0.9480, 0.9380, 0.8910, 0.8220],  # 3
    [0.9790, 0.9650, 0.9540, 0.9390, 0.9240, 0.8700, 0.7920],  # 3.5
    [0.9730, 0.9560, 0.9430, 0.9250, 0.9060, 0.8460, 0.7580],  # 4
    [0.9680, 0.9490, 0.9330, 0.9130, 0.8930, 0.8260, 0.7300],  # 4.5
    [0.9630, 0.9400, 0.9220, 0.9010, 0.8790, 0.8050, 0.7020],  # 5
    [0.9570, 0.9320, 0.9110, 0.8890, 0.8640, 0.7830, 0.6730],  # 5.5
    [0.9510, 0.9240, 0.9010, 0.8760, 0.8500, 0.7630, 0.6480],  # 6
    [0.9450, 0.9150, 0.8900, 0.8620, 0.8340, 0.7430, 0.6240],  # 6.5
    [0.9390, 0.9080, 0.8800, 0.8520, 0.8200, 0.7220, 0.6010],  # 7
    [0.9360, 0.9010, 0.8710, 0.8410, 0.8080, 0.7060, 0.5780],  # 7.5
    [0.9250, 0.8890, 0.8570, 0.8240, 0.7890, 0.6840, 0.5550],  # 8
    [0.9200, 0.8830, 0.8480, 0.8130, 0.7770, 0.6670, 0.5350],  # 8.5
    [0.9140, 0.8740, 0.8370, 0.7990, 0.7610, 0.6480, 0.5150],  # 9
    [0.9070, 0.8640, 0.8250, 0.7850, 0.7460, 0.6300, 0.4950],  # 9.5
    [0.9000, 0.8550, 0.8130, 0.7720, 0.7320, 0.6130, 0.4770],  # 10
])

_EDW_ANGLE_IDX = {a: i for i, a in enumerate(_EDW_ANGLES)}


def obter_fator_edw(filtro_nome: str, jaw_y1: float, jaw_y2: float, energia: str = "6X") -> float | None:
    """
    Retorna o fator EDW interpolado.

    Parâmetros
    ----------
    filtro_nome : str
        Nome do filtro (ex: "EDW45OUT", "EDW30IN").
    jaw_y1 : float
        Posição da jaw Y1 em cm.
    jaw_y2 : float
        Posição da jaw Y2 em cm.
    energia : str
        Energia do feixe ("6X", "10X", etc.). Seleciona a tabela correta.

    Retorna
    -------
    float ou None se não for EDW.

    Lógica:
        EDW OUT → interpola com jaw Y1
        EDW IN  → interpola com jaw Y2
        Energia com "10" → tabela 10MV, senão → tabela 6MV
    """
    m = re.match(r"EDW(\d+)(IN|OUT)", filtro_nome, re.IGNORECASE)
    if not m:
        return None

    angulo = int(m.group(1))
    direcao = m.group(2).upper()

    if angulo not in _EDW_ANGLE_IDX:
        return None

    col = _EDW_ANGLE_IDX[angulo]
    jaw = jaw_y1 if direcao == "OUT" else jaw_y2

    # Selecionar tabela pela energia
    if "10" in str(energia).upper():
        tabela = _EDW_FACTORS_10MV
    else:
        tabela = _EDW_FACTORS_6MV

    jaw_clamp = np.clip(jaw, _EDW_JAW_SIZES[0], _EDW_JAW_SIZES[-1])
    return float(np.interp(jaw_clamp, _EDW_JAW_SIZES, tabela[:, col]))


# ══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES DE CÁLCULO
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
    Cálculo de UM para todos os campos.

    Fator de filtro:
      - EDW: calculado automaticamente da tabela comissionada,
        usando jaw Y1 (OUT) ou Y2 (IN) e a energia do campo.
      - Outros (Acrílico, bandeja): usa dict_filtros da sidebar.
      - Sem filtro: 1.0.
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
        jaw_y1 = row.get("Jaw Y1", 0.0)
        jaw_y2 = row.get("Jaw Y2", 0.0)
        energia = row.get("Energia", "6X")
        ff_edw = obter_fator_edw(filtro_nome, jaw_y1, jaw_y2, energia)
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
