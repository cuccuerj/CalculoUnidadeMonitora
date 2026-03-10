
import numpy as np
import pandas as pd
import streamlit as st
from scipy.interpolate import RegularGridInterpolator

SAD = 100.0

def calcular_eqsq(x, y):
    if x <= 0 or y <= 0: return 0.0
    return (4 * x * y) / (2 * (x + y))

def calcular_fator_distancia(ssd, prof, dmax, sad=SAD):
    if ssd <= 0: return 0.0
    return ((sad + dmax) / (prof + ssd)) ** 2

@st.cache_data
def carregar_tabelas_maquina(conteudo_texto):
    linhas = conteudo_texto.split('\n')
    campos, sc, sp, profundidades, tmr_matriz = [], [], [], [], []

    for linha in linhas:
        partes = linha.strip().split('\t')
        if len(partes) < 2: partes = linha.strip().split()
        if not partes or len(partes) < 2: continue
            
        rotulo = partes[0].strip().lower()
        try: valores = [float(v.replace(',', '.')) for v in partes[1:] if v.strip()]
        except ValueError: continue
            
        if rotulo == 'campo':   campos = valores
        elif rotulo == 'sc':    sc = valores
        elif rotulo == 'sp':    sp = valores
        else:
            try:
                profundidades.append(float(rotulo.replace(',', '.')))
                tmr_matriz.append(valores)
            except ValueError: pass

    tmr_array  = np.array(tmr_matriz)
    prof_array = np.array(profundidades)
    dmax_auto  = 1.5
    if tmr_array.size > 0:
        idx = np.argmax(tmr_array[:, tmr_array.shape[1] // 2])
        dmax_auto = prof_array[idx]

    return np.array(campos), np.array(sc), np.array(sp), prof_array, tmr_array, dmax_auto

def processar_calculos_tabela(df_edit, campos_m, sc_m, sp_m, prof_m, tmr_m, dmax, dose_ref, dict_filtros):
    """Esta função faz o loop pesado por todos os campos e retorna o DataFrame final"""
    interp_tmr = RegularGridInterpolator((prof_m, campos_m), tmr_m, bounds_error=False, fill_value=None)
    resultados = []
    
    for _, row in df_edit.iterrows():
        eqsq_c = calcular_eqsq(row["X"], row["Y"])
        eqsq_f = calcular_eqsq(row["Fsx (cm)"], row["Fsy (cm)"])
        isqf   = calcular_fator_distancia(row["SSD"], row["Prof."], dmax=dmax)
        sc_v   = np.interp(eqsq_c, campos_m, sc_m)
        sp_v   = np.interp(eqsq_f, campos_m, sp_m)
        tmr_v  = float(interp_tmr((row["Prof. Ef."], eqsq_f))) if row["Prof. Ef."] > 0 and eqsq_f > 0 else 0.0
        ff     = dict_filtros.get(row["FILTRO"], 1.0)
        oar    = row.get("OAR", 1.0)
        
        denom  = dose_ref * sc_v * sp_v * tmr_v * isqf * ff * oar
        um_c   = row["DOSE (cGy)"] / denom if denom > 0 else 0.0
        dev    = ((um_c - row["UM (Eclipse)"]) / row["UM (Eclipse)"]) * 100 if row["UM (Eclipse)"] > 0 else 0.0
        
        resultados.append({
            "Campo": row["Campo"], "Aparelho": row["Aparelho"], "Energia": row["Energia"],
            "X": row["X"], "Y": row["Y"], "EqSq Colimador": eqsq_c, "EqSq Fantoma": eqsq_f,
            "SSD": row["SSD"], "DOSE (cGy)": row["DOSE (cGy)"], "Prof.": row["Prof."], "Prof. Ef.": row["Prof. Ef."],
            "Sc": sc_v, "Sp": sp_v, "TMR": tmr_v, "ISQF": isqf,
            "Fator Filtro": ff, "OAR": oar, "UM Calculada": um_c, "UM (Eclipse)": row["UM (Eclipse)"],
            "Desvio_num": dev 
        })
    return pd.DataFrame(resultados)
