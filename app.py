import streamlit as st
import pandas as pd

# 1. Configuração inicial da página
st.set_page_config(page_title="Calculadora de UM - 3D", layout="wide")

st.title("Calculadora de Unidades Monitoras (3D)")
st.write("Ferramenta para conferência de cálculo de UM.")

# 2. Seção de Dados da Máquina
st.header("1. Dados da Máquina (Fatores e TMR)")

# Nova escolha: GitHub ou Upload manual
fonte_dados_maquina = st.radio(
    "Como deseja carregar os dados da máquina (Sc, Sp, TMR)?",
    ("Usar dados padrão (GitHub)", "Fazer upload de arquivo TXT")
)

# Variável que vai guardar o arquivo (ou o link) para lermos depois
caminho_arquivo_maquina = None

if fonte_dados_maquina == "Usar dados padrão (GitHub)":
    # ATENÇÃO: Você precisa colocar o link RAW do seu arquivo no GitHub aqui.
    # Exemplo: "https://raw.githubusercontent.com/seu-usuario/seu-repositorio/main/clinac_fac_tmr.txt"
    url_github = "COLOQUE_AQUI_O_LINK_RAW_DO_SEU_GITHUB" 
    
    st.info("Usando o banco de dados padrão da clínica hospedado no GitHub.")
    caminho_arquivo_maquina = url_github
    
elif fonte_dados_maquina == "Fazer upload de arquivo TXT":
    arquivo_upload = st.file_uploader("Faça o upload do arquivo TXT (Sc, Sp e TMR)", type=["txt"])
    
    if arquivo_upload is not None:
        st.success("Arquivo da máquina carregado com sucesso!")
        caminho_arquivo_maquina = arquivo_upload

st.divider()

# 3. Seção de Dados do Paciente
st.header("2. Dados do Paciente e Planejamento")

metodo_entrada = st.radio(
    "Como deseja inserir os parâmetros dos campos do paciente?",
    ("Inserção Manual", "Extrair de PDF do Planejamento")
)

arquivo_pdf = None

if metodo_entrada == "Extrair de PDF do Planejamento":
    arquivo_pdf = st.file_uploader("Faça o upload do relatório do plano (PDF)", type=["pdf"])
    if arquivo_pdf is not None:
        st.success("PDF carregado! (A extração será configurada nos próximos passos)")
        
elif metodo_entrada == "Inserção Manual":
    st.info("Aqui criaremos os campos para digitar SSD, Profundidade, Tamanho de Campo, Dose prescrita, etc.")
