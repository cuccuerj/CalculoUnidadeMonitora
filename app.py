import streamlit as st
import pandas as pd
import pdfplumber
import re
import numpy as np
import urllib.request
from scipy.interpolate import RegularGridInterpolator

# --- CONFIGURAÇÕES FÍSICAS PADRÃO ---
DMAX = 1.4 # Profundidade de dose máxima para 6X
SAD = 100.0 # Distância Fonte-Eixo padrão

# --- FUNÇÕES DE APOIO MATEMÁTICO ---
def calcular_eqsq(x, y):
    if x <= 0 or y <= 0:
        return 0.0
    return (4 * x * y) / (2 * (x + y))

def calcular_fator_distancia(ssd, prof, dmax=DMAX, sad=SAD):
    if ssd <= 0:
        return 0.0
    return ((sad + dmax) / (ssd + prof)) ** 2

def extrair_dados_rt(pdf_file):
    dados_campos = {}
    with pdfplumber.open(pdf_file) as pdf:
        texto_completo = ""
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"

    padrao_plano = r"(?:Plano|Plan):\s*(.+)"
    match_plano = re.search(padrao_plano, texto_completo, re.IGNORECASE)
    nome_plano = match_plano.group(1).strip() if match_plano else pdf_file.name

    campos_encontrados = sorted(list(set(re.findall(r'Campo (\d+)', texto_completo))))
    
    for c in campos_encontrados:
        dados_campos[c] = {
            "Plano": nome_plano, "Campo": f"Campo {c}", "X": 0.0, "Y": 0.0, 
            "Fsx (cm)": 0.0, "Fsy (cm)": 0.0, "FILTRO": "-", "UM (Eclipse)": 0.0, 
            "DOSE (cGy)": 0.0, "SSD": 0.0, "Prof.": 0.0, "Prof. Ef.": 0.0
        }

    def buscar_valor(chave, campo_num, texto):
        padrao = rf"{chave}.*?Campo {campo_num}\s+([\d.]+)"
        match = re.search(padrao, texto, re.DOTALL | re.IGNORECASE)
        return float(match.group(1)) if match else 0.0

    for c in campos_encontrados:
        dados_campos[c]["X"] = buscar_valor("Tamanho do Campo Aberto X", c, texto_completo)
        dados_campos[c]["Y"] = buscar_valor("Tamanho do Campo Aberto Y", c, texto_completo)
        dados_campos[c]["UM (Eclipse)"] = buscar_valor("MU", c, texto_completo)
        dados_campos[c]["DOSE (cGy)"] = buscar_valor("Dose", c, texto_completo)
        dados_campos[c]["SSD"] = buscar_valor("SSD", c, texto_completo)
        dados_campos[c]["Prof."] = buscar_valor("Profundidade", c, texto_completo)
        dados_campos[c]["Prof. Ef."] = buscar_valor("Profundidade Efetiva", c, texto_completo)
        
        padrao_filtro = rf"Filtro.*?Campo {c}\s+(.*?)\n"
        match_f = re.search(padrao_filtro, texto_completo, re.DOTALL | re.IGNORECASE)
        if match_f:
            filtro_encontrado = match_f.group(1).strip()
            # Limpa caso o filtro venha vazio ou apenas um traço
            if not filtro_encontrado or filtro_encontrado == "-":
                 dados_campos[c]["FILTRO"] = "Nenhum"
            else:
                 dados_campos[c]["FILTRO"] = filtro_encontrado

    padrao_fs = r"(?:fluência total|total fluence).{0,100}?fsx\s*=\s*([\d.]+)\s*mm(?:.{0,50}?fsy\s*=\s*([\d.]+)\s*mm)?"
    matches_fs = re.findall(padrao_fs, texto_completo, re.IGNORECASE | re.DOTALL)
    
    for i, c in enumerate(campos_encontrados):
        if i < len(matches_fs):
            fsx_mm = matches_fs[i][0]
            fsy_mm = matches_fs[i][1] if matches_fs[i][1] else fsx_mm 
            dados_campos[c]["Fsx (cm)"] = float(fsx_mm) / 10.0
            dados_campos[c]["Fsy (cm)"] = float(fsy_mm) / 10.0

    return pd.DataFrame(dados_campos.values())

@st.cache_data
def carregar_tabelas_maquina(conteudo_texto):
    linhas = conteudo_texto.split('\n')
    campos, sc, sp, profundidades, tmr_matriz = [], [], [], [], []
    
    for linha in linhas:
        partes = linha.strip().split('\t')
        if len(partes) < 2:
            partes = linha.strip().split()
            
        if not partes or len(partes) < 2: continue
            
        rotulo = partes[0].strip().lower()
        try:
            valores = [float(v.replace(',', '.')) for v in partes[1:] if v.strip() != '']
        except ValueError: continue 
            
        if rotulo == 'campo': campos = valores
        elif rotulo == 'sc': sc = valores
        elif rotulo == 'sp': sp = valores
        else:
            try:
                profundidades.append(float(rotulo.replace(',', '.')))
                tmr_matriz.append(valores)
            except ValueError: pass
                
    return np.array(campos), np.array(sc), np.array(sp), np.array(profundidades), np.array(tmr_matriz)


# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Calculadora de UM - 3D", layout="wide")

st.title("🎯 Calculadora de Unidades Monitoras (3D)")
st.write("Sistema de conferência independente de cálculo de UM.")

# --- BARRA LATERAL (CONFIGURAÇÕES GERAIS) ---
with st.sidebar:
    st.header("⚙️ Configurações da Máquina")
    dose_ref = st.number_input("Taxa de Dose Nominal (cGy/UM)", value=1.000, step=0.01, format="%.3f")
    dmax_user = st.number_input("Profundidade d_max (cm)", value=1.5, step=0.1)
    
    st.divider()
    st.subheader("Fatores de Transmissão (Filtros/Bandejas)")
    st.write("Se o campo tiver um filtro, indique o fator (Ex: 0.98). Caso contrário, será usado 1.0.")
    # Um pequeno dicionário editável para o utilizador adicionar os seus filtros
    df_filtros_padrao = pd.DataFrame([
        {"Nome do Filtro": "Nenhum", "Fator": 1.000},
        {"Nome do Filtro": "EDW", "Fator": 1.000}, # Cunhas dinâmicas geralmente já estão na fluência
        {"Nome do Filtro": "Bandeja Acrílico", "Fator": 0.970}
    ])
    df_filtros_editado = st.data_editor(df_filtros_padrao, num_rows="dynamic", hide_index=True)
    
    # Transforma a tabela editada num dicionário para fácil acesso { "Nome": Fator }
    dict_filtros = dict(zip(df_filtros_editado["Nome do Filtro"], df_filtros_editado["Fator"]))

# 1. Secção de Dados da Máquina
with st.expander("1. Dados da Máquina (Fatores e TMR)", expanded=False):
    fonte_dados_maquina = st.radio(
        "Como deseja carregar os dados da máquina (Sc, Sp, TMR)?",
        ("Usar dados padrão (GitHub)", "Fazer upload de ficheiro TXT")
    )

    conteudo_maquina = None
    if fonte_dados_maquina == "Usar dados padrão (GitHub)":
        url_github = "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/refs/heads/main/clinac_fac_tmr.txt" 
        st.info("A usar a base de dados padrão da clínica alojada no GitHub.")
        try:
            if url_github.startswith("http"):
                with urllib.request.urlopen(url_github) as response:
                    conteudo_maquina = response.read().decode('utf-8')
        except Exception:
            st.warning("Aguardando ligação ao GitHub. Cole o link RAW no código.")
            
    elif fonte_dados_maquina == "Fazer upload de ficheiro TXT":
        arquivo_upload = st.file_uploader("Faça o upload do ficheiro TXT", type=["txt"])
        if arquivo_upload is not None:
            conteudo_maquina = arquivo_upload.getvalue().decode('utf-8')
            st.success("Ficheiro da máquina carregado!")

# 2. Secção de Dados do Doente
st.header("2. Dados do Doente e Planeamento")

metodo_entrada = st.radio("Método de entrada dos parâmetros:", ("Extrair de PDF do Planeamento", "Inserção Manual"), horizontal=True)

colunas_padrao = ["Plano", "Campo", "X", "Y", "Fsx (cm)", "Fsy (cm)", "FILTRO", "UM (Eclipse)", "DOSE (cGy)", "SSD", "Prof.", "Prof. Ef."]
df_paciente = pd.DataFrame(columns=colunas_padrao)

if metodo_entrada == "Extrair de PDF do Planeamento":
    arquivos_pdf = st.file_uploader("Faça o upload dos relatórios do plano (PDF)", type=["pdf"], accept_multiple_files=True)
    if arquivos_pdf:
        with st.spinner('A extrair dados...'):
            lista_tabelas = [extrair_dados_rt(pdf) for pdf in arquivos_pdf]
            if lista_tabelas:
                df_paciente = pd.concat(lista_tabelas, ignore_index=True)
        
elif metodo_entrada == "Inserção Manual":
    df_paciente = pd.DataFrame([{
        "Plano": "Plano Manual", "Campo": "Campo 1", "X": 10.0, "Y": 10.0, "Fsx (cm)": 10.0, "Fsy (cm)": 10.0, 
        "FILTRO": "Nenhum", "UM (Eclipse)": 100.0, "DOSE (cGy)": 100.0, "SSD": 100.0, "Prof.": 5.0, "Prof. Ef.": 5.0
    }])

# --- CÁLCULO FINAL ---
if not df_paciente.empty:
    st.subheader("Tabela de Extração (Editável)")
    df_editado = st.data_editor(df_paciente, num_rows="dynamic", use_container_width=True)
    
    st.subheader("3. Resultado: Cálculo Independente de Unidades Monitoras")
    
    if conteudo_maquina is not None:
        campos_maq, sc_maq, sp_maq, prof_maq, tmr_matriz_maq = carregar_tabelas_maquina(conteudo_maquina)
        interpolador_tmr = RegularGridInterpolator((prof_maq, campos_maq), tmr_matriz_maq, bounds_error=False, fill_value=None)
        
        resultados = []
        
        for index, row in df_editado.iterrows():
            # 1. Cálculos de EqSq e ISQF
            eqsq_c = calcular_eqsq(row['X'], row['Y'])
            eqsq_f = calcular_eqsq(row['Fsx (cm)'], row['Fsy (cm)'])
            isqf = calcular_fator_distancia(row['SSD'], row['Prof.'], dmax=dmax_user)
            
            # 2. Interpolações
            sc_val = np.interp(eqsq_c, campos_maq, sc_maq)
            sp_val = np.interp(eqsq_f, campos_maq, sp_maq)
            tmr_val = float(interpolador_tmr((row['Prof. Ef.'], eqsq_f))) if row['Prof. Ef.'] > 0 and eqsq_f > 0 else 0.0
            
            # 3. Fator de Filtro (Busca no dicionário lateral)
            nome_filtro = row['FILTRO']
            fator_filtro = dict_filtros.get(nome_filtro, 1.0) # Se o filtro não existir na lista, usa 1.0
            
            # 4. A GRANDE EQUAÇÃO DE UM
            denominador = dose_ref * sc_val * sp_val * tmr_val * isqf * fator_filtro
            
            if denominador > 0:
                um_calc = row['DOSE (cGy)'] / denominador
                # Calcula o desvio percentual entre o Eclipse e a nossa Calculadora
                if row['UM (Eclipse)'] > 0:
                    diferenca = ((um_calc - row['UM (Eclipse)']) / row['UM (Eclipse)']) * 100
                else:
                    diferenca = 0.0
            else:
                um_calc = 0.0
                diferenca = 0.0
                
            resultados.append({
                "Plano": row['Plano'],
                "Campo": row['Campo'],
                "UM Calculada": round(um_calc, 1),
                "UM (Eclipse)": row['UM (Eclipse)'],
                "Desvio (%)": round(diferenca, 2),
                "Sc": round(sc_val, 3),
                "Sp": round(sp_val, 3),
                "TMR": round(tmr_val, 3),
                "ISQF": round(isqf, 3),
                "Fator Filtro": fator_filtro
            })
            
        df_resultados = pd.DataFrame(resultados)
        
        # Função para pintar a coluna de desvio (Verde < 2%, Amarelo < 5%, Vermelho > 5%)
        def colorir_desvio(val):
            try:
                if abs(val) <= 2.0: return 'background-color: #d4edda; color: #155724'
                elif abs(val) <= 5.0: return 'background-color: #fff3cd; color: #856404'
                else: return 'background-color: #f8d7da; color: #721c24'
            except:
                return ''

        # Mostra a tabela de resultados com cores!
        st.dataframe(df_resultados.style.map(colorir_desvio, subset=['Desvio (%)']), use_container_width=True, hide_index=True)
        
        st.caption("Aviso: Esta é uma ferramenta de apoio de segunda verificação. Fatores como dispersão no colimador (Off-axis), cunhas dinâmicas complexas ou heterogeneidades acentuadas podem gerar desvios esperados (normalmente < 5%) em relação a algoritmos avançados como o AAA/Acuros.")
        
    else:
        st.error("Por favor, carregue o ficheiro TXT da máquina para realizar o cálculo final.")
