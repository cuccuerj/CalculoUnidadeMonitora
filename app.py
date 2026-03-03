import streamlit as st
import pandas as pd
import pdfplumber
import re
import numpy as np
import urllib.request
from scipy.interpolate import RegularGridInterpolator

# --- CONFIGURAÇÕES FÍSICAS PADRÃO ---
DMAX = 1.5 # Profundidade de dose máxima para 6X (Ajustar se a energia mudar)
SAD = 100.0 # Distância Fonte-Eixo padrão da máquina

# --- FUNÇÕES DE APOIO MATEMÁTICO ---
def calcular_eqsq(x, y):
    if x <= 0 or y <= 0:
        return 0.0
    return (4 * x * y) / (2 * (x + y))

def calcular_fator_distancia(ssd, dmax=DMAX, sad=SAD):
    if ssd <= 0:
        return 0.0
    return ((ssd + dmax) / sad) ** 2

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
            "DOSE": 0.0, "SSD": 0.0, "Prof.": 0.0, "Prof. Ef.": 0.0
        }

    def buscar_valor(chave, campo_num, texto):
        padrao = rf"{chave}.*?Campo {campo_num}\s+([\d.]+)"
        match = re.search(padrao, texto, re.DOTALL | re.IGNORECASE)
        return float(match.group(1)) if match else 0.0

    for c in campos_encontrados:
        dados_campos[c]["X"] = buscar_valor("Tamanho do Campo Aberto X", c, texto_completo)
        dados_campos[c]["Y"] = buscar_valor("Tamanho do Campo Aberto Y", c, texto_completo)
        dados_campos[c]["UM (Eclipse)"] = buscar_valor("MU", c, texto_completo)
        dados_campos[c]["DOSE"] = buscar_valor("Dose", c, texto_completo)
        dados_campos[c]["SSD"] = buscar_valor("SSD", c, texto_completo)
        dados_campos[c]["Prof."] = buscar_valor("Profundidade", c, texto_completo)
        dados_campos[c]["Prof. Ef."] = buscar_valor("Profundidade Efetiva", c, texto_completo)
        
        padrao_filtro = rf"Filtro.*?Campo {c}\s+(.*?)\n"
        match_f = re.search(padrao_filtro, texto_completo, re.DOTALL | re.IGNORECASE)
        if match_f:
            dados_campos[c]["FILTRO"] = match_f.group(1).strip()

    padrao_fs = r"(?:fluência total|total fluence).{0,100}?fsx\s*=\s*([\d.]+)\s*mm(?:.{0,50}?fsy\s*=\s*([\d.]+)\s*mm)?"
    matches_fs = re.findall(padrao_fs, texto_completo, re.IGNORECASE | re.DOTALL)
    
    for i, c in enumerate(campos_encontrados):
        if i < len(matches_fs):
            fsx_mm = matches_fs[i][0]
            fsy_mm = matches_fs[i][1] if matches_fs[i][1] else fsx_mm 
            dados_campos[c]["Fsx (cm)"] = float(fsx_mm) / 10.0
            dados_campos[c]["Fsy (cm)"] = float(fsy_mm) / 10.0

    return pd.DataFrame(dados_campos.values())

# --- FUNÇÃO PARA LER O FICHEIRO DA MÁQUINA ---
@st.cache_data # Memoriza os dados para não ter de ler o ficheiro sempre que clica num botão
def carregar_tabelas_maquina(conteudo_texto):
    linhas = conteudo_texto.split('\n')
    campos = []
    sc = []
    sp = []
    profundidades = []
    tmr_matriz = []
    
    for linha in linhas:
        # Divide por Tabulação ou por Espaços
        partes = linha.strip().split('\t')
        if len(partes) < 2:
            partes = linha.strip().split()
            
        if not partes or len(partes) < 2:
            continue
            
        rotulo = partes[0].strip().lower()
        try:
            # Substitui vírgulas por pontos caso existam
            valores = [float(v.replace(',', '.')) for v in partes[1:] if v.strip() != '']
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
                prof = float(rotulo.replace(',', '.'))
                profundidades.append(prof)
                tmr_matriz.append(valores)
            except ValueError:
                pass
                
    return np.array(campos), np.array(sc), np.array(sp), np.array(profundidades), np.array(tmr_matriz)


# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Calculadora de UM - 3D", layout="wide")

st.title("Calculadora de Unidades Monitoras (3D)")
st.write("Ferramenta para conferência de cálculo de UM.")

# 1. Secção de Dados da Máquina
st.header("1. Dados da Máquina (Fatores e TMR)")
fonte_dados_maquina = st.radio(
    "Como deseja carregar os dados da máquina (Sc, Sp, TMR)?",
    ("Usar dados padrão (GitHub)", "Fazer upload de ficheiro TXT")
)

conteudo_maquina = None

if fonte_dados_maquina == "Usar dados padrão (GitHub)":
    url_github = "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/refs/heads/main/clinac_fac_tmr.txt" 
    st.info("A usar a base de dados padrão da clínica")
    try:
        # Se o utilizador não tiver mudado a URL ainda, não tentamos descarregar
        if url_github.startswith("http"):
            with urllib.request.urlopen(url_github) as response:
                conteudo_maquina = response.read().decode('utf-8')
    except Exception as e:
        st.warning("Aguardando ligação ao GitHub. Cole o link RAW no código.")
        
elif fonte_dados_maquina == "Fazer upload de ficheiro TXT":
    arquivo_upload = st.file_uploader("Faça o upload do ficheiro TXT (Sc, Sp e TMR)", type=["txt"])
    if arquivo_upload is not None:
        conteudo_maquina = arquivo_upload.getvalue().decode('utf-8')
        st.success("Ficheiro da máquina carregado com sucesso!")

st.divider()

# 2. Secção de Dados do Doente
st.header("2. Dados do Doente e Planeamento")

metodo_entrada = st.radio(
    "Como deseja inserir os parâmetros dos campos do doente?",
    ("Extrair de PDF do Planeamento", "Inserção Manual")
)

colunas_padrao = ["Plano", "Campo", "X", "Y", "Fsx (cm)", "Fsy (cm)", "FILTRO", "UM (Eclipse)", "DOSE", "SSD", "Prof.", "Prof. Ef."]
df_paciente = pd.DataFrame(columns=colunas_padrao)

if metodo_entrada == "Extrair de PDF do Planeamento":
    arquivos_pdf = st.file_uploader("Faça o upload dos relatórios do plano (PDF)", type=["pdf"], accept_multiple_files=True)
    if arquivos_pdf:
        with st.spinner('A ler e a extrair dados dos PDFs...'):
            lista_tabelas = []
            for pdf in arquivos_pdf:
                try:
                    df_temp = extrair_dados_rt(pdf)
                    lista_tabelas.append(df_temp)
                except Exception as e:
                    st.error(f"Erro ao ler o PDF {pdf.name}. Detalhe: {e}")
            if lista_tabelas:
                df_paciente = pd.concat(lista_tabelas, ignore_index=True)
                st.success(f"Dados extraídos com sucesso de {len(arquivos_pdf)} ficheiro(s)!")
        
elif metodo_entrada == "Inserção Manual":
    df_paciente = pd.DataFrame([{
        "Plano": "Plano Manual", "Campo": "Campo 1", "X": 10.0, "Y": 10.0, "Fsx (cm)": 10.0, "Fsy (cm)": 10.0, 
        "FILTRO": "-", "UM (Eclipse)": 100.0, "DOSE": 100.0, "SSD": 100.0, "Prof.": 5.0, "Prof. Ef.": 5.0
    }])

# --- CÁLCULOS INTERMÉDIOS E INTERPOLAÇÃO AUTOMÁTICA ---
if not df_paciente.empty:
    st.subheader("Parâmetros do Planeamento")
    df_editado = st.data_editor(df_paciente, num_rows="dynamic", use_container_width=True)
    
    with st.container(border=True):
        st.markdown("**Cálculos Intermédios e Fatores da Máquina:**")
        
        df_calculos = df_editado.copy()
        
        # 1. Aplica as fórmulas de EqSq e Distância
        df_calculos['EqSq Colimador'] = df_calculos.apply(lambda row: calcular_eqsq(row['X'], row['Y']), axis=1).round(2)
        df_calculos['EqSq Fantoma'] = df_calculos.apply(lambda row: calcular_eqsq(row['Fsx (cm)'], row['Fsy (cm)']), axis=1).round(2)
        df_calculos['Fator Distância (ISQF)'] = df_calculos.apply(lambda row: calcular_fator_distancia(row['SSD']), axis=1).round(4)
        
        # 2. Interpolação dos valores da Máquina
        if conteudo_maquina is not None:
            # Lê e prepara as matrizes do ficheiro TXT
            campos_maq, sc_maq, sp_maq, prof_maq, tmr_matriz_maq = carregar_tabelas_maquina(conteudo_maquina)
            
            # Prepara a função de interpolação bilinear (2D) para o TMR
            # bounds_error=False e fill_value=None permitem extrapolar ligeiramente se necessário
            interpolador_tmr = RegularGridInterpolator((prof_maq, campos_maq), tmr_matriz_maq, bounds_error=False, fill_value=None)
            
            sc_list = []
            sp_list = []
            tmr_list = []
            
            # Para cada campo (linha) da tabela do doente, buscamos o Sc, Sp e TMR
            for index, row in df_calculos.iterrows():
                # Interpolação 1D para Sc (baseado no EqSq Colimador)
                sc_interp = np.interp(row['EqSq Colimador'], campos_maq, sc_maq)
                
                # Interpolação 1D para Sp (baseado no EqSq Fantoma)
                sp_interp = np.interp(row['EqSq Fantoma'], campos_maq, sp_maq)
                
                # Interpolação 2D para TMR (Profundidade Efetiva, EqSq Fantoma)
                # Verifica se a profundidade efetiva é maior que 0 para calcular
                if row['Prof. Ef.'] > 0 and row['EqSq Fantoma'] > 0:
                    tmr_interp = float(interpolador_tmr((row['Prof. Ef.'], row['EqSq Fantoma'])))
                else:
                    tmr_interp = 0.0
                    
                sc_list.append(round(sc_interp, 4))
                sp_list.append(round(sp_interp, 4))
                tmr_list.append(round(tmr_interp, 4))
                
            # Adiciona as novas colunas à tabela
            df_calculos['Sc (Interpolado)'] = sc_list
            df_calculos['Sp (Interpolado)'] = sp_list
            df_calculos['TMR (Interpolado)'] = tmr_list
            
            # Mostra o resumo final dos fatores!
            colunas_mostrar = ['Plano', 'Campo', 'EqSq Colimador', 'EqSq Fantoma', 'Sc (Interpolado)', 'Sp (Interpolado)', 'TMR (Interpolado)', 'Fator Distância (ISQF)']
            st.dataframe(df_calculos[colunas_mostrar], use_container_width=True, hide_index=True)
            
            st.success("Passo 6: Todos os fatores foram extraídos e interpolados com sucesso! Falta apenas multiplicar tudo na equação final de UM.")
        else:
            # Caso o utilizador ainda não tenha feito upload do ficheiro TXT
            st.warning("⚠️ Faça o upload do ficheiro TXT da máquina (Passo 1) para o sistema interpolar o Sc, Sp e TMR.")
            colunas_mostrar_sem_maq = ['Plano', 'Campo', 'EqSq Colimador', 'EqSq Fantoma', 'Fator Distância (ISQF)']
            st.dataframe(df_calculos[colunas_mostrar_sem_maq], use_container_width=True, hide_index=True)
