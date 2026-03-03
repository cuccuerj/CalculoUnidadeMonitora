import streamlit as st
import pandas as pd

# 1. Configuração inicial da página
st.set_page_config(page_title="Calculadora de UM - 3D", layout="wide")

st.title("Calculadora de Unidades Monitoras (3D)")
st.write("Ferramenta para conferência de cálculo de UM.")

# 2. Seção de Dados da Máquina
st.header("1. Dados da Máquina (Fatores e TMR)")
arquivo_txt = st.file_uploader("Faça o upload do arquivo TXT (Sc, Sp e TMR)", type=["txt"])

if arquivo_txt is not None:
    st.success("Arquivo da máquina carregado com sucesso! (A leitura dos dados será feita no próximo passo)")

st.divider()

# 3. Seção de Dados do Paciente
st.header("2. Dados do Paciente e Planejamento")

# Botões de rádio para o usuário escolher o método de entrada
metodo_entrada = st.radio(
    "Como deseja inserir os parâmetros dos campos?",
    ("Inserção Manual", "Extrair de PDF do Planejamento")
)

arquivo_pdf = None

if metodo_entrada == "Extrair de PDF do Planejamento":
    arquivo_pdf = st.file_uploader("Faça o upload do relatório do plano (PDF)", type=["pdf"])
    if arquivo_pdf is not None:
        st.success("PDF carregado! (A extração será configurada nos próximos passos)")
        
elif metodo_entrada == "Inserção Manual":
    st.info("Aqui criaremos os campos para digitar SSD, Profundidade, Tamanho de Campo, etc.")
