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
    
    # Inicializa o dicionário para cada campo
    for c in campos_encontrados:
        dados_campos[c] = {"Campo": f"Campo {c}", "X": 0.0, "Y": 0.0, "FILTRO": "-", "UM": 0.0, "DOSE": 0.0, "SSD": 0.0, "Prof.": 0.0, "Prof. Ef.": 0.0}

    # Função auxiliar para buscar valores numéricos após uma chave e o nome do campo
    def buscar_valor(chave, campo_num, texto):
        # Procura a seção da chave (ex: SSD) e depois o valor específico do campo
        padrao = rf"{chave}.*?Campo {campo_num}\s+([\d.]+)"
        match = re.search(padrao, texto, re.DOTALL | re.IGNORECASE)
        return float(match.group(1)) if match else 0.0

    for c in campos_encontrados:
        dados_campos[c]["X"] = buscar_valor("Tamanho do Campo Aberto X", c, texto_completo)
        dados_campos[c]["Y"] = buscar_valor("Tamanho do Campo Aberto Y", c, texto_completo)
        dados_campos[c]["UM"] = buscar_valor("MU", c, texto_completo)
        dados_campos[c]["DOSE"] = buscar_valor("Dose", c, texto_completo)
        dados_campos[c]["SSD"] = buscar_valor("SSD", c, texto_completo)
        dados_campos[c]["Prof."] = buscar_valor("Profundidade", c, texto_completo)
        dados_campos[c]["Prof. Ef."] = buscar_valor("Profundidade Efetiva", c, texto_completo)
        
        # Filtro (Tratamento especial pois pode ser texto ou "-")
        padrao_filtro = rf"Filtro.*?Campo {c}\s+(.*?)\n"
        match_f = re.search(padrao_filtro, texto_completo, re.DOTALL | re.IGNORECASE)
        if match_f:
            dados_campos[c]["FILTRO"] = match_f.group(1).strip()

    return pd.DataFrame(dados_campos.values())

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Calculadora de UM - 3D", layout="wide")

# (Seção da Máquina omitida aqui para focar no PDF, mas deve continuar no seu código)

st.header("Dados do Paciente e Planejamento")
metodo_entrada = st.radio("Método de entrada:", ("Manual", "PDF"))

# Criamos um DataFrame vazio inicial
df_paciente = pd.DataFrame(columns=["Campo", "X", "Y", "FILTRO", "UM", "DOSE", "SSD", "Prof.", "Prof. Ef."])

if metodo_entrada == "PDF":
    arquivo_pdf = st.file_uploader("Upload do relatório", type=["pdf"])
    if arquivo_pdf:
        with st.spinner('Extraindo dados do PDF...'):
            df_paciente = extrair_dados_rt(arquivo_pdf)
        st.success("Dados extraídos!")

elif metodo_entrada == "Manual":
    # Adiciona uma linha vazia para começar
    df_paciente = pd.DataFrame([{"Campo": "Campo 1", "X": 10.0, "Y": 10.0, "FILTRO": "-", "UM": 100, "DOSE": 100, "SSD": 100, "Prof.": 5.0, "Prof. Ef.": 5.0}])

st.subheader("Tabela de Parâmetros (Confira e edite se necessário)")
# O data_editor permite que o usuário mude os valores na hora!
df_editado = st.data_editor(df_paciente, num_rows="dynamic", use_container_width=True)

st.info("No próximo passo, usaremos os dados desta tabela acima para buscar Sc, Sp e TMR nos arquivos da máquina.")
