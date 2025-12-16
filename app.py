# app.py
import streamlit as st
import pandas as pd
import requests
from io import StringIO

st.set_page_config(page_title="Calculadora de Unidade Monitora", layout="wide")

# Configuração dos aceleradores disponíveis no GitHub
ACELERADORES = {
    "Clinac 6MV": "https://raw.githubusercontent.com/seu-usuario/dosimetria/main/dados/clinac_6mv.txt",
    "Clinac 10MV": "https://raw.githubusercontent.com/seu-usuario/dosimetria/main/dados/clinac_10mv.txt",
    "Clinac 15MV": "https://raw.githubusercontent.com/seu-usuario/dosimetria/main/dados/clinac_15mv.txt",
    "TrueBeam 6FFF": "https://raw.githubusercontent.com/seu-usuario/dosimetria/main/dados/truebeam_6fff.txt",
}

def carregar_acelerador(url):
    """Carrega dados de um acelerador específico"""
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        conteudo = StringIO(response.text)
        linhas = conteudo.readlines()
        
        # Processamento
        campos_line = linhas[0].strip().split('\t')
        campos = [float(campo) for campo in campos_line[1:]]
        
        sc_line = linhas[1].strip().split('\t')
        sc = [float(val) for val in sc_line[1:]]
        
        sp_line = linhas[2].strip().split('\t')
        sp = [float(val) for val in sp_line[1:]]
        
        tmr_data = {}
        for linha in linhas[3:]:
            if linha.strip():
                partes = linha.strip().split('\t')
                profundidade = float(partes[0])
                valores_tmr = [float(val) for val in partes[1:]]
                tmr_data[profundidade] = valores_tmr
        
        return campos, sc, sp, tmr_data
        
    except Exception as e:
        st.error(f"Erro ao carregar: {e}")
        return None

# Interface
st.title("🏥 Sistema de Cálculo de Unidade Monitora")
st.markdown("---")

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("Configuração")
    
    # Selecionar acelerador
    acelerador_selecionado = st.selectbox(
        "Selecione o acelerador:",
        options=list(ACELERADORES.keys())
    )
    
    # Botão para carregar
    if st.button("🔄 Carregar Dados", type="primary"):
        with st.spinner(f"Carregando {acelerador_selecionado}..."):
            url = ACELERADORES[acelerador_selecionado]
            campos, sc_vals, sp_vals, tmr_data = carregar_acelerador(url)
            
            if campos:
                # Armazenar na sessão do Streamlit
                st.session_state['dados'] = {
                    'campos': campos,
                    'sc': sc_vals,
                    'sp': sp_vals,
                    'tmr': tmr_data,
                    'acelerador': acelerador_selecionado
                }
                st.success(f"Dados de {acelerador_selecionado} carregados!")

with col2:
    if 'dados' in st.session_state:
        dados = st.session_state['dados']
        st.subheader(f"Acelerador: {dados['acelerador']}")
        
        # Sua interface de cálculo aqui
        # ...
