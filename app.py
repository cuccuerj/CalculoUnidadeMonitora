import streamlit as st
import pandas as pd
import urllib.request
import base64
from datetime import date

# Importando os nossos próprios ficheiros (módulos)
from core.pdf_parser import extrair_dados_rt
from core.math import carregar_tabelas_maquina, processar_calculos_tabela
from utils.report_gen import gerar_pdf_transposto

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DE PÁGINA E ESTADO
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Verificação de UM · Radioterapia", page_icon="☢️", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1 { color: #005088; }
    h2, h3 { color: #1e293b; }
</style>
""", unsafe_allow_html=True)

if "nome_paciente" not in st.session_state: st.session_state["nome_paciente"] = ""
if "id_paciente" not in st.session_state: st.session_state["id_paciente"] = ""

st.title("☢️ Verificação Independente de UM (3D)")
st.write("Sistema de conferência com Relatório Paramétrico Transposto.")
st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# BARRA LATERAL (Definições)
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.header("⚙️ Configurações Gerais")
    dose_ref = st.number_input("Fator de Calibração (cGy/UM)", value=1.000, step=0.01, format="%.3f")
    
    st.subheader("Filtros Dinâmicos / Bandejas")
    df_filtros_default = pd.DataFrame([
        {"Nome do Filtro": "Nenhum", "Fator": 1.000},
        {"Nome do Filtro": "EDW", "Fator": 1.000},
        {"Nome do Filtro": "Bandeja Acrílico", "Fator": 0.970},
    ])
    df_filtros_edit = st.data_editor(df_filtros_default, num_rows="dynamic", hide_index=True)
    dict_filtros = dict(zip(df_filtros_edit["Nome do Filtro"], df_filtros_edit["Fator"]))

    st.subheader("🏥 Instituição (Opcional)")
    instituicao = st.text_input("Nome da Clínica/Hospital")
    logo_file = st.file_uploader("Logotipo (Imagem)", type=["png","jpg","jpeg"])
    logo_bytes = logo_file.read() if logo_file else None

# ══════════════════════════════════════════════════════════════════════════════
# FLUXO PRINCIPAL (Ecrãs)
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs(["1. Máquina (Sc, Sp, TMR)", "2. Dados do Paciente", "3. Cálculos e Relatório"])

with tab1:
    st.subheader("Carregar Tabela da Máquina")
    fonte = st.radio("Selecione a fonte dos dados:", ("Usar padrão do GitHub", "Fazer upload do TXT manual"))
    
    if fonte == "Usar padrão do GitHub":
        url = "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/refs/heads/main/clinac_fac_tmr.txt"
        try:
            with urllib.request.urlopen(url) as r:
                st.session_state["conteudo_maquina"] = r.read().decode("utf-8")
            st.success("Tabelas da máquina carregadas com sucesso!")
        except Exception:
            st.error("Erro ao ligar ao GitHub. Faça o upload manual.")
    else:
        arq = st.file_uploader("Ficheiro TXT", type=["txt"])
        if arq:
            st.session_state["conteudo_maquina"] = arq.getvalue().decode("utf-8")
            st.success("Ficheiro TXT processado!")

conteudo_maquina = st.session_state.get("conteudo_maquina")

with tab2:
    st.subheader("Extrair Planeamento")
    metodo = st.radio("Método:", ("Upload PDF do Eclipse", "Digitação Manual"), horizontal=True)
    df_paciente = pd.DataFrame()
    nome_plano = "Plano Manual"

    if metodo == "Upload PDF do Eclipse":
        pdfs = st.file_uploader("Selecione o(s) relatório(s) em PDF", type=["pdf"], accept_multiple_files=True)
        if pdfs:
            with st.spinner("A ler informações do paciente..."):
                dfs_extraidos = []
                for p in pdfs:
                    dados = extrair_dados_rt(p)
                    dfs_extraidos.append(dados["df"])
                    if dados["nome"]: st.session_state["nome_paciente"] = dados["nome"]
                    if dados["id"]: st.session_state["id_paciente"] = dados["id"]
                    
                df_paciente = pd.concat(dfs_extraidos, ignore_index=True)
                nome_plano = df_paciente["Plano"].iloc[0] if not df_paciente.empty else ""
    else:
        df_paciente = pd.DataFrame([{
            "Plano": "Manual", "Campo": "Campo 1", "Aparelho": "Clinac", "Energia": "6X",
            "X": 10.0, "Y": 10.0, "Fsx (cm)": 10.0, "Fsy (cm)": 10.0, 
            "FILTRO": "Nenhum", "OAR": 1.000, "UM (Eclipse)": 100.0, "DOSE (cGy)": 100.0, 
            "SSD": 100.0, "Prof.": 5.0, "Prof. Ef.": 5.0
        }])

    if not df_paciente.empty:
        col_nome, col_id, col_data = st.columns(3)
        nome_paciente = col_nome.text_input("Nome do Paciente", value=st.session_state["nome_paciente"])
        id_paciente = col_id.text_input("ID/Processo", value=st.session_state["id_paciente"])
        data_calc = col_data.date_input("Data do Cálculo", value=date.today())

        st.caption("Verifique e edite os parâmetros extraídos abaixo:")
        df_edit = st.data_editor(df_paciente, num_rows="dynamic", use_container_width=True)

with tab3:
    if not conteudo_maquina:
        st.warning("⚠️ Volte ao Separador 1 e carregue os dados da máquina primeiro.")
    elif df_paciente.empty:
        st.warning("⚠️ Volte ao Separador 2 e extraia os dados do planeamento.")
    else:
        # Chama as funções dos outros ficheiros!
        campos_m, sc_m, sp_m, prof_m, tmr_m, dmax = carregar_tabelas_maquina(conteudo_maquina)
        
        df_res = processar_calculos_tabela(df_edit, campos_m, sc_m, sp_m, prof_m, tmr_m, dmax, dose_ref, dict_filtros)

        st.success("Cálculo processado com sucesso! Veja a tabela detalhada abaixo e o PDF gerado.")

        st.subheader("Visualização no Ecrã (Rodar Tabela)")
        st.dataframe(df_res.copy().set_index("Campo").T, use_container_width=True)

        st.divider()
        st.subheader("📄 Relatório PDF Oficial")
        
        pdf_buf = gerar_pdf_transposto(df_res, nome_paciente, id_paciente, nome_plano, data_calc, dose_ref, logo_bytes=logo_bytes, instituicao=instituicao)
        
        col_btn, col_prev = st.columns([1, 4])
        with col_btn:
            nome_arq = f"verificacao_{id_paciente or 'paciente'}.pdf"
            st.download_button("⬇️ Descarregar PDF", data=pdf_buf.getvalue(), file_name=nome_arq, mime="application/pdf", type="primary", use_container_width=True)
            
        with col_prev:
            with st.expander("Pré-visualizar PDF", expanded=True):
                b64_pdf = base64.b64encode(pdf_buf.getvalue()).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="600" style="border: none; border-radius: 8px;"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
