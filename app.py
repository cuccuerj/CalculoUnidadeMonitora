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

    # Regex para encontrar os números dos campos presentes (Ex: Campo 6, Campo 7...)
    campos_encontrados = sorted(list(set(re.findall(r'Campo (\d+)', texto_completo))))
    
    # Inicializa o dicionário para cada campo com as novas colunas Fsx e Fsy
    for c in campos_encontrados:
        dados_campos[c] = {
            "Campo": f"Campo {c}", 
            "X (cm)": 0.0, 
            "Y (cm)": 0.0, 
            "Fsx (cm)": 0.0, 
            "Fsy (cm)": 0.0, 
            "FILTRO": "-", 
            "UM": 0.0, 
            "DOSE (cGy)": 0.0, 
            "SSD (cm)": 0.0, 
            "Prof. (cm)": 0.0, 
            "Prof. Ef. (cm)": 0.0
        }

    # Função auxiliar para buscar valores numéricos básicos na tabela inicial do PDF
    def buscar_valor(chave, campo_num, texto):
        padrao = rf"{chave}.*?Campo {campo_num}\s+([\d.]+)"
        match = re.search(padrao, texto, re.DOTALL | re.IGNORECASE)
        return float(match.group(1)) if match else 0.0

    # 1. Extração dos dados da tabela principal do relatório
    for c in campos_encontrados:
        dados_campos[c]["X"] = buscar_valor("Tamanho do Campo Aberto X", c, texto_completo)
        dados_campos[c]["Y"] = buscar_valor("Tamanho do Campo Aberto Y", c, texto_completo)
        dados_campos[c]["UM"] = buscar_valor("MU", c, texto_completo)
        dados_campos[c]["DOSE"] = buscar_valor("Dose", c, texto_completo)
        dados_campos[c]["SSD"] = buscar_valor("SSD", c, texto_completo)
        dados_campos[c]["Prof."] = buscar_valor("Profundidade", c, texto_completo)
        dados_campos[c]["Prof. Ef."] = buscar_valor("Profundidade Efetiva", c, texto_completo)
        
        # O filtro requer um cuidado especial pois pode ser texto ou "-"
        padrao_filtro = rf"Filtro.*?Campo {c}\s+(.*?)\n"
        match_f = re.search(padrao_filtro, texto_completo, re.DOTALL | re.IGNORECASE)
        if match_f:
            dados_campos[c]["FILTRO"] = match_f.group(1).strip()

    # 2. Extração específica do fsx e fsy (Ignorando o CBSF e aceitando PT/EN)
    # A regra busca "fluência total" ou "total fluence" e pega os valores de fsx e fsy em "mm"
    padrao_fs = r"(?:fluência total|total fluence).{0,100}?fsx\s*=\s*([\d.]+)\s*mm(?:.{0,50}?fsy\s*=\s*([\d.]+)\s*mm)?"
    matches_fs = re.findall(padrao_fs, texto_completo, re.IGNORECASE | re.DOTALL)
    
    # O Eclipse geralmente lista essas informações na mesma ordem dos campos
    for i, c in enumerate(campos_encontrados):
        if i < len(matches_fs):
            fsx_mm = matches_fs[i][0]
            # Se por acaso o fsy não vier escrito, assume o valor do fsx
            fsy_mm = matches_fs[i][1] if matches_fs[i][1] else fsx_mm 
            
            # Converte de mm para cm dividindo por 10
            dados_campos[c]["Fsx (cm)"] = float(fsx_mm) / 10.0
            dados_campos[c]["Fsy (cm)"] = float(fsy_mm) / 10.0

    return pd.DataFrame(dados_campos.values())

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Calculadora de UM - 3D", layout="wide")

st.title("Calculadora de Unidades Monitoras (3D)")
st.write("Ferramenta para conferência de cálculo de UM.")

# 1. Seção de Dados da Máquina
st.header("1. Dados da Máquina (Fatores e TMR)")
fonte_dados_maquina = st.radio(
    "Como deseja carregar os dados da máquina (Sc, Sp, TMR)?",
    ("Usar dados padrão (GitHub)", "Fazer upload de arquivo TXT")
)

caminho_arquivo_maquina = None
if fonte_dados_maquina == "Usar dados padrão (GitHub)":
    url_github = "COLOQUE_AQUI_O_LINK_RAW_DO_SEU_GITHUB" 
    st.info("Usando o banco de dados padrão da clínica hospedado no GitHub.")
    caminho_arquivo_maquina = url_github
elif fonte_dados_maquina == "Fazer upload de arquivo TXT":
    arquivo_upload = st.file_uploader("Faça o upload do arquivo TXT (Sc, Sp e TMR)", type=["txt"])
    if arquivo_upload is not None:
        st.success("Arquivo da máquina carregado com sucesso!")
        caminho_arquivo_maquina = arquivo_upload

st.divider()

# 2. Seção de Dados do Paciente
st.header("2. Dados do Paciente e Planejamento")

metodo_entrada = st.radio(
    "Como deseja inserir os parâmetros dos campos do paciente?",
    ("Extrair de PDF do Planejamento", "Inserção Manual")
)

# Colunas na ordem que você pediu, mais as novas do Campo Efetivo
colunas_padrao = ["Campo", "X", "Y", "Fsx (cm)", "Fsy (cm)", "FILTRO", "UM", "DOSE", "SSD", "Prof.", "Prof. Ef."]
df_paciente = pd.DataFrame(columns=colunas_padrao)

if metodo_entrada == "Extrair de PDF do Planejamento":
    arquivo_pdf = st.file_uploader("Faça o upload do relatório do plano (PDF)", type=["pdf"])
    if arquivo_pdf:
        with st.spinner('Lendo e extraindo dados do PDF...'):
            try:
                df_paciente = extrair_dados_rt(arquivo_pdf)
                st.success("Dados extraídos com sucesso!")
            except Exception as e:
                st.error(f"Erro ao ler o PDF. Verifique se o formato é suportado. Detalhe: {e}")
        
elif metodo_entrada == "Inserção Manual":
    # Adiciona uma linha inicial para o usuário digitar
    df_paciente = pd.DataFrame([{
        "Campo": "Campo 1", "X": 10.0, "Y": 10.0, "Fsx (cm)": 10.0, "Fsy (cm)": 10.0, 
        "FILTRO": "-", "UM": 100.0, "DOSE": 100.0, "SSD": 100.0, "Prof.": 5.0, "Prof. Ef.": 5.0
    }])

st.subheader("Tabela de Parâmetros")
st.write("Verifique os dados extraídos. Você pode clicar nas células para **editar** qualquer valor incorreto ou arredondar os centímetros.")

# Tabela interativa
df_editado = st.data_editor(df_paciente, num_rows="dynamic", use_container_width=True)

st.info("No próximo passo (Passo 4), vamos conectar os valores desta tabela para calcular automaticamente os valores equivalentes de Campo Quadrado (EqSq) e iniciar a interpolação do TMR e Fatores de Espalhamento.")
