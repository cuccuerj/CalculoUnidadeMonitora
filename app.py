import streamlit as st
import pandas as pd
import pdfplumber
import re

# --- FUNÇÕES DE APOIO ---
def extrair_dados_rt(pdf_file):
    dados_campos = {}
    
    with pdfplumber.open(pdf_file) as pdf:
        texto_completo = ""
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"

    # Captura o Nome do Plano (Suporta PT e EN)
    padrao_plano = r"(?:Plano|Plan):\s*(.+)"
    match_plano = re.search(padrao_plano, texto_completo, re.IGNORECASE)
    nome_plano = match_plano.group(1).strip() if match_plano else pdf_file.name # Se não achar, usa o nome do ficheiro

    # Regex para encontrar os números dos campos presentes
    campos_encontrados = sorted(list(set(re.findall(r'Campo (\d+)', texto_completo))))
    
    # Inicializa o dicionário com a nova coluna "Plano"
    for c in campos_encontrados:
        dados_campos[c] = {
            "Plano": nome_plano,
            "Campo": f"Campo {c}", 
            "X": 0.0, 
            "Y": 0.0, 
            "Fsx (cm)": 0.0, 
            "Fsy (cm)": 0.0, 
            "FILTRO": "-", 
            "UM": 0.0, 
            "DOSE": 0.0, 
            "SSD": 0.0, 
            "Prof.": 0.0, 
            "Prof. Ef.": 0.0
        }

    def buscar_valor(chave, campo_num, texto):
        padrao = rf"{chave}.*?Campo {campo_num}\s+([\d.]+)"
        match = re.search(padrao, texto, re.DOTALL | re.IGNORECASE)
        return float(match.group(1)) if match else 0.0

    # 1. Extração dos dados da tabela principal
    for c in campos_encontrados:
        dados_campos[c]["X"] = buscar_valor("Tamanho do Campo Aberto X", c, texto_completo)
        dados_campos[c]["Y"] = buscar_valor("Tamanho do Campo Aberto Y", c, texto_completo)
        dados_campos[c]["UM"] = buscar_valor("MU", c, texto_completo)
        dados_campos[c]["DOSE"] = buscar_valor("Dose", c, texto_completo)
        dados_campos[c]["SSD"] = buscar_valor("SSD", c, texto_completo)
        dados_campos[c]["Prof."] = buscar_valor("Profundidade", c, texto_completo)
        dados_campos[c]["Prof. Ef."] = buscar_valor("Profundidade Efetiva", c, texto_completo)
        
        padrao_filtro = rf"Filtro.*?Campo {c}\s+(.*?)\n"
        match_f = re.search(padrao_filtro, texto_completo, re.DOTALL | re.IGNORECASE)
        if match_f:
            dados_campos[c]["FILTRO"] = match_f.group(1).strip()

    # 2. Extração específica do fsx e fsy
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

# Colunas atualizadas com a adição do "Plano" no início
colunas_padrao = ["Plano", "Campo", "X", "Y", "Fsx (cm)", "Fsy (cm)", "FILTRO", "UM", "DOSE", "SSD", "Prof.", "Prof. Ef."]
df_paciente = pd.DataFrame(columns=colunas_padrao)

if metodo_entrada == "Extrair de PDF do Planeamento":
    # MUDANÇA: accept_multiple_files=True permite selecionar vários PDFs ao mesmo tempo
    arquivos_pdf = st.file_uploader("Faça o upload dos relatórios do plano (PDF)", type=["pdf"], accept_multiple_files=True)
    
    if arquivos_pdf: # Se a lista não estiver vazia
        with st.spinner('A ler e a extrair dados dos PDFs...'):
            lista_tabelas = []
            for pdf in arquivos_pdf:
                try:
                    df_temp = extrair_dados_rt(pdf)
                    lista_tabelas.append(df_temp)
                except Exception as e:
                    st.error(f"Erro ao ler o PDF {pdf.name}. Detalhe: {e}")
            
            # Se conseguiu extrair de pelo menos um, junta todos numa tabela só
            if lista_tabelas:
                df_paciente = pd.concat(lista_tabelas, ignore_index=True)
                st.success(f"Dados extraídos com sucesso de {len(arquivos_pdf)} ficheiro(s)!")
        
elif metodo_entrada == "Inserção Manual":
    df_paciente = pd.DataFrame([{
        "Plano": "Plano Manual", "Campo": "Campo 1", "X": 10.0, "Y": 10.0, "Fsx (cm)": 10.0, "Fsy (cm)": 10.0, 
        "FILTRO": "-", "UM": 100.0, "DOSE": 100.0, "SSD": 100.0, "Prof.": 5.0, "Prof. Ef.": 5.0
    }])

st.subheader("Tabela de Parâmetros")
st.write("Verifique os dados extraídos. Pode clicar nas células para **editar** qualquer valor incorreto.")

df_editado = st.data_editor(df_paciente, num_rows="dynamic", use_container_width=True)

st.info("No próximo passo, faremos a aplicação ler o seu ficheiro TXT e ligá-lo a esta tabela!")
