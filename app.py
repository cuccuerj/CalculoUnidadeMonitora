import streamlit as st
import pandas as pd
import pdfplumber
import re

# --- CONFIGURAÇÕES FÍSICAS PADRÃO ---
DMAX = 1.5 # Profundidade de dose máxima para 6X (Ajustar se a energia mudar)
SAD = 100.0 # Distância Fonte-Eixo padrão da máquina

# --- FUNÇÕES DE APOIO ---
def calcular_eqsq(x, y):
    """Calcula o Lado do Campo Quadrado Equivalente."""
    if x <= 0 or y <= 0:
        return 0.0
    return (4 * x * y) / (2 * (x + y))

def calcular_fator_distancia(ssd,prof, dmax=DMAX, sad=SAD):
    """Calcula o ISQF: ((SAD + dmax) / (ssd + prof))^2"""
    if ssd <= 0:
        return 0.0
    return ((SAD + dmax) / (ssd + prof)) ** 2

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
            "Plano": nome_plano,
            "Campo": f"Campo {c}", 
            "X": 0.0, 
            "Y": 0.0, 
            "Fsx (cm)": 0.0, 
            "Fsy (cm)": 0.0, 
            "FILTRO": "-", 
            "UM (Eclipse)": 0.0, 
            "DOSE": 0.0, 
            "SSD": 0.0, 
            "Prof.": 0.0, 
            "Prof. Ef.": 0.0
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

caminho_arquivo_maquina = None
if fonte_dados_maquina == "Usar dados padrão (GitHub)":
    url_github = "COLOQUE_AQUI_O_LINK_RAW_DO_SEU_GITHUB" 
    st.info("A usar a base de dados padrão da clínica alojada no GitHub.")
    caminho_arquivo_maquina = url_github
elif fonte_dados_maquina == "Fazer upload de ficheiro TXT":
    arquivo_upload = st.file_uploader("Faça o upload do ficheiro TXT (Sc, Sp e TMR)", type=["txt"])
    if arquivo_upload is not None:
        st.success("Ficheiro da máquina carregado com sucesso!")
        caminho_arquivo_maquina = arquivo_upload

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

# --- CÁLCULOS INTERMEDIÁRIOS AUTOMÁTICOS ---
if not df_paciente.empty:
    st.subheader("Parâmetros do Planeamento e Cálculos Intermédios")
    st.write("Reveja os dados. Os valores de EqSq e ISQF são calculados automaticamente.")
    
    # 1. Permite edição pelo utilizador
    df_editado = st.data_editor(df_paciente, num_rows="dynamic", use_container_width=True)
    
    # 2. Faz os cálculos baseados na tabela editada
    # Usamos st.container() apenas para organizar visualmente
    with st.container(border=True):
        st.markdown("**Variáveis Calculadas para a Equação:**")
        
        # Cria cópia para não mexer na tabela original de edição
        df_calculos = df_editado.copy()
        
        # Aplica as fórmulas que você solicitou
        df_calculos['EqSq Colimador (Sc)'] = df_calculos.apply(lambda row: calcular_eqsq(row['X'], row['Y']), axis=1).round(2)
        df_calculos['EqSq Fantoma (Sp/TMR)'] = df_calculos.apply(lambda row: calcular_eqsq(row['Fsx (cm)'], row['Fsy (cm)']), axis=1).round(2)
        df_calculos['Fator Distância (ISQF)'] = df_calculos.apply(lambda row: calcular_fator_distancia(row['SSD']),row['Prof.']), axis=1).round(4)
        
        # Mostra apenas as colunas que importam para os próximos passos
        colunas_mostrar = ['Plano', 'Campo', 'EqSq Colimador (Sc)', 'EqSq Fantoma (Sp/TMR)', 'Prof. Ef.', 'Fator Distância (ISQF)', 'DOSE']
        st.dataframe(df_calculos[colunas_mostrar], use_container_width=True, hide_index=True)

    st.info("Passo 5: Agora vamos usar estes valores de EqSq e Prof. Ef. para interpolar o Sc, Sp e TMR no seu ficheiro TXT!")
