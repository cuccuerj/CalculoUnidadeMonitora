import streamlit as st
import pandas as pd
import urllib.request
from datetime import date

# Importação dos seus módulos
from core.pdf_parser import extrair_dados_rt
from core.math import carregar_tabelas_maquina, processar_calculos_tabela
from utils.report_gen import gerar_pdf_transposto
import urllib.request
import urllib.error

# ══════════════════════════════════════════════════════════════════════════════
# AUTO-DETEÇÃO DE MÁQUINA E ENERGIA
# ══════════════════════════════════════════════════════════════════════════════
def identificar_url_maquina(aparelho, energia):
    a = str(aparelho).upper()
    e = str(energia).upper()
    
    # Lógica de seleção
    if "UNIQUE" in a:
        return "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/main/unique_fac_tmr.txt"
    elif "2100" in a:
        if "10" in e:
            return "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/main/cl2100_10mv_fac_tmr.txt"
        else:
            return "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/main/cl2100_6mv_fac_tmr.txt"
            
    # Fallback (Padrão de segurança se o nome for estranho)
    return "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/main/cl2100_6mv_fac_tmr.txt"

# Função com CACHE para evitar bloqueio (Rate Limit) do GitHub
@st.cache_data(show_spinner=False, ttl=3600)
def obter_tabela_github(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as r:
        return r.read().decode("utf-8")


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
# PASSO 1: EXTRAÇÃO DO PLANEAMENTO (TPS)
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("1. Importar Relatório (Eclipse)")
pdf_file = st.file_uploader("Arraste o ficheiro PDF do planeamento aqui", type=["pdf"])

df_paciente = pd.DataFrame()
nome_plano = ""

if pdf_file:
    with st.spinner("A processar documento e a identificar equipamentos..."):
        dados = extrair_dados_rt(pdf_file)
        df_paciente = dados["df"]
        st.session_state["nome_paciente"] = dados["nome"]
        st.session_state["id_paciente"] = dados["id"]
        nome_plano = df_paciente["Plano"].iloc[0] if not df_paciente.empty else ""

if not df_paciente.empty:
    c1, c2, c3 = st.columns(3)
    nome_paciente = c1.text_input("Paciente", value=st.session_state["nome_paciente"])
    id_paciente = c2.text_input("ID / Processo", value=st.session_state["id_paciente"])
    data_calc = c3.date_input("Data da Avaliação", value=date.today())

    st.caption("Revise os parâmetros. A tabela TMR/Sc/Sp será selecionada automaticamente baseada na coluna Aparelho/Energia.")
    df_edit = st.data_editor(df_paciente, num_rows="dynamic", use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════════
    # PASSO 2: CÁLCULO INTELIGENTE E RESULTADOS
    # ══════════════════════════════════════════════════════════════════════════════
    st.write("")
    st.subheader("2. Resultados da Conferência")
    
    if st.button("Calcular Parâmetros e Gerar Relatório", type="primary", use_container_width=True):
        
        resultados_finais = []
        houve_erro = False
        
        with st.spinner("A transferir tabelas do equipamento e a calcular..."):
            # O sistema agora calcula campo a campo, buscando a tabela certa para cada um
            for index, row in df_edit.iterrows():
                url_maq = identificar_url_maquina(row["Aparelho"], row["Energia"])
                
                try:
                    # Vai buscar ao GitHub (ou à memória cache se já tiver transferido hoje)
                    texto_maq = obter_tabela_github(url_maq)
                    campos_m, sc_m, sp_m, prof_m, tmr_m, dmax = carregar_tabelas_maquina(texto_maq)
                    
                    # Cria um micro-dataframe só com esta linha para a função de matemática processar
                    df_linha = pd.DataFrame([row])
                    res_linha = processar_calculos_tabela(df_linha, campos_m, sc_m, sp_m, prof_m, tmr_m, dmax, dose_ref, dict_filtros)
                    resultados_finais.append(res_linha)
                    
                except Exception as e:
                    st.error(f"Erro ao carregar os dados para a máquina do {row['Campo']}. Verifique se a ligação à internet está ativa.")
                    houve_erro = True
                    break
        
        if not houve_erro and resultados_finais:
            # Junta todos os resultados de volta num único DataFrame
            df_res = pd.concat(resultados_finais, ignore_index=True)
            
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
