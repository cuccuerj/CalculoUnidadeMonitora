import streamlit as st
import pandas as pd
from core.pdf_parser import extrair_dados_rt
from core.math import carregar_tabelas_maquina, calcular_fatores
from utils.report_gen import gerar_pdf_transposto

# 1. Configuração de Tela (Fica no topo)
st.set_page_config(page_title="Verificação de UM", layout="wide")
st.title("☢️ Verificação Independente de UM")

# 2. Lógica da Interface
tab1, tab2, tab3 = st.tabs(["Máquina", "Paciente", "Relatório"])

with tab2:
    pdf_file = st.file_uploader("Upload do Eclipse")
    if pdf_file:
        # Olha como fica limpo: você chama a função de outro arquivo!
        dados = extrair_dados_rt(pdf_file) 
        df_edit = st.data_editor(dados['df'])

with tab3:
    if st.button("Calcular e Gerar PDF"):
         # Cálculos e geração em arquivos separados
         resultados = calcular_fatores(df_edit) 
         pdf = gerar_pdf_transposto(resultados)
         st.download_button("Baixar", pdf, "relatorio.pdf")
