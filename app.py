import streamlit as st
import pandas as pd
import urllib.request
from datetime import date

# Importação dos seus módulos
from core.pdf_parser import extrair_dados_rt
from core.math import carregar_tabelas_maquina, processar_calculos_tabela
from utils.report_gen import gerar_pdf_transposto

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO MINIMALISTA
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Verificação de UM", layout="wide")

if "nome_paciente" not in st.session_state: st.session_state["nome_paciente"] = ""
if "id_paciente" not in st.session_state: st.session_state["id_paciente"] = ""

st.title("Verificação Independente de UM")
st.markdown("Sistema de conferência paramétrica para radioterapia 3D.")
st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# BARRA LATERAL (Apenas Configurações Fixas)
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.subheader("Configurações do Serviço")
    instituicao = st.text_input("Instituição (Opcional)")
    dose_ref = st.number_input("Fator de Calibração (cGy/UM)", value=1.000, step=0.01, format="%.3f")
    
    st.markdown("---")
    st.caption("Fatores de Bandeja/Filtro")
    df_filtros_default = pd.DataFrame([
        {"Filtro": "Nenhum", "Fator": 1.000},
        {"Filtro": "EDW", "Fator": 1.000},
        {"Filtro": "Acrílico", "Fator": 0.970},
    ])
    df_filtros_edit = st.data_editor(df_filtros_default, num_rows="dynamic", hide_index=True, use_container_width=True)
    dict_filtros = dict(zip(df_filtros_edit["Filtro"], df_filtros_edit["Fator"]))

# ══════════════════════════════════════════════════════════════════════════════
# PASSO 1: DADOS DO EQUIPAMENTO
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("1. Base de Dados do Acelerador")
col_fonte, col_status = st.columns([1, 2])

with col_fonte:
    fonte = st.selectbox("Selecione a Tabela:", ["Usar dados do CL2100", "Fazer upload de TXT manual"])

if fonte == "Usar padrão do sistema (GitHub)":
    url = "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/refs/heads/main/clinac_fac_tmr.txt"
    try:
        with urllib.request.urlopen(url) as r:
            st.session_state["conteudo_maquina"] = r.read().decode("utf-8")
        with col_status:
            st.info("Tabela padrão carregada e pronta para uso.")
    except Exception:
        st.error("Erro na ligação. Insira o ficheiro manualmente.")
else:
    arq = st.file_uploader("Selecione o ficheiro TXT do equipamento", type=["txt"])
    if arq:
        st.session_state["conteudo_maquina"] = arq.getvalue().decode("utf-8")

conteudo_maquina = st.session_state.get("conteudo_maquina")

# ══════════════════════════════════════════════════════════════════════════════
# PASSO 2: DADOS DO PLANEAMENTO
# ══════════════════════════════════════════════════════════════════════════════
st.write("") # Espaçamento
st.subheader("2. Extração do Planeamento (TPS)")

pdf_file = st.file_uploader("Importar relatório do Eclipse (PDF)", type=["pdf"])

df_paciente = pd.DataFrame()
nome_plano = ""

if pdf_file:
    with st.spinner("A processar documento..."):
        dados = extrair_dados_rt(pdf_file)
        df_paciente = dados["df"]
        st.session_state["nome_paciente"] = dados["nome"]
        st.session_state["id_paciente"] = dados["id"]
        nome_plano = df_paciente["Plano"].iloc[0] if not df_paciente.empty else ""

# Se o PDF foi lido, mostramos os campos para confirmar e a tabela para edição
if not df_paciente.empty:
    c1, c2, c3 = st.columns(3)
    nome_paciente = c1.text_input("Paciente", value=st.session_state["nome_paciente"])
    id_paciente = c2.text_input("ID / Processo", value=st.session_state["id_paciente"])
    data_calc = c3.date_input("Data da Avaliação", value=date.today())

    st.caption("Revise os parâmetros extraídos do PDF. Edite se necessário:")
    df_edit = st.data_editor(df_paciente, num_rows="dynamic", use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════════
    # PASSO 3: CÁLCULO E RESULTADOS
    # ══════════════════════════════════════════════════════════════════════════════
    st.write("")
    st.subheader("3. Resultados da Conferência")
    
    if st.button("Calcular Parâmetros e Gerar Relatório", type="primary", use_container_width=True):
        if not conteudo_maquina:
            st.error("Por favor, carregue os dados do equipamento no Passo 1.")
        else:
            # Processamento Matemático
            campos_m, sc_m, sp_m, prof_m, tmr_m, dmax = carregar_tabelas_maquina(conteudo_maquina)
            df_res = processar_calculos_tabela(df_edit, campos_m, sc_m, sp_m, prof_m, tmr_m, dmax, dose_ref, dict_filtros)
            
            # Exibir Tabela Rodada no Ecrã
            st.dataframe(df_res.copy().set_index("Campo").T, use_container_width=True)
            
            # Gerar o PDF Transposto
            pdf_buf = gerar_pdf_transposto(
                df_res, nome_paciente, id_paciente, nome_plano, data_calc, dose_ref, instituicao=instituicao
            )
            
            nome_arq = f"verificacao_{id_paciente or 'paciente'}.pdf"
            st.download_button(
                label="Descarregar Relatório PDF",
                data=pdf_buf.getvalue(),
                file_name=nome_arq,
                mime="application/pdf",
                type="primary"
            )
