import streamlit as st
import pandas as pd
import urllib.request
import base64
from datetime import date

from core.pdf_parser import extrair_dados_rt
from core.math import carregar_tabelas_maquina, processar_calculos_tabela
from utils.report_gen import gerar_pdf_transposto

# ══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ══════════════════════════════════════════════════════════════════════════════
def identificar_url_maquina(aparelho, energia):
    a = str(aparelho).upper()
    e = str(energia).upper()
    if "UNIQUE" in a:
        return "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/main/unique_fac_tmr.txt"
    elif "2100" in a:
        if "10" in e:
            return "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/main/cl2100_10mv_fac_tmr.txt"
        else:
            return "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/main/cl2100_6mv_fac_tmr.txt"
    return "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/main/cl2100_6mv_fac_tmr.txt"

@st.cache_data(show_spinner=False, ttl=3600)
def obter_tabela_github(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as r:
        return r.read().decode("utf-8")

def calcular_todos_campos(df_edit, dose_ref, dict_filtros):
    """Calcula todos os campos e retorna (df_resultado, erro_msg)."""
    resultados = []
    for _, row in df_edit.iterrows():
        url_maq = identificar_url_maquina(row["Aparelho"], row["Energia"])
        try:
            texto_maq = obter_tabela_github(url_maq)
            campos_m, sc_m, sp_m, prof_m, tmr_m, dmax = carregar_tabelas_maquina(texto_maq)
            df_linha = pd.DataFrame([row])
            res = processar_calculos_tabela(df_linha, campos_m, sc_m, sp_m, prof_m, tmr_m, dmax, dose_ref, dict_filtros)
            resultados.append(res)
        except Exception as e:
            return None, f"Erro no campo {row['Campo']}: {e}"
    if resultados:
        return pd.concat(resultados, ignore_index=True), None
    return None, "Nenhum resultado calculado."

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DA PÁGINA
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Verificação de UM",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ──
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');

    .block-container { max-width: 1100px; padding-top: 2rem; }

    .app-header {
        text-align: center;
        padding: 1.2rem 0 0.3rem;
    }
    .app-header h1 {
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 1.5rem;
        color: #1a365d;
        margin-bottom: 0.2rem;
        letter-spacing: -0.02em;
    }
    .app-header p {
        font-family: 'DM Sans', sans-serif;
        color: #718096;
        font-size: 0.85rem;
        margin: 0;
    }

    .info-strip {
        background: linear-gradient(135deg, #ebf4ff 0%, #f0f7ff 100%);
        border: 1px solid #bee3f8;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        font-family: 'DM Sans', sans-serif;
    }
    .info-strip .label {
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #4a5568;
        font-weight: 500;
    }
    .info-strip .value {
        font-size: 0.92rem;
        color: #1a365d;
        font-weight: 700;
    }

    .result-ok   { display:inline-block; background:#c6f6d5; color:#22543d; padding:0.12rem 0.55rem; border-radius:99px; font-size:0.76rem; font-weight:600; }
    .result-warn { display:inline-block; background:#fefcbf; color:#744210; padding:0.12rem 0.55rem; border-radius:99px; font-size:0.76rem; font-weight:600; }
    .result-fail { display:inline-block; background:#fed7d7; color:#742a2a; padding:0.12rem 0.55rem; border-radius:99px; font-size:0.76rem; font-weight:600; }

    .pdf-frame {
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0,0,0,0.06);
        margin: 0.8rem 0;
    }
    .pdf-frame iframe {
        border: none;
        width: 100%;
        height: 700px;
    }

    .soft-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, #e2e8f0 20%, #e2e8f0 80%, transparent);
        margin: 0.8rem 0;
    }

    section[data-testid="stSidebar"] { background: #f7fafc; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — Configurações avançadas (colapsado por padrão)
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("#### ⚙️ Configurações")
    instituicao = st.text_input("Instituição", value="", placeholder="Opcional")
    dose_ref = st.number_input("Fator de Calibração (cGy/UM)", value=1.000, step=0.01, format="%.3f")
    mu_threshold = st.number_input("Limiar mínimo de UM", value=50, min_value=0, step=10,
        help="Campos com UM abaixo deste valor são descartados.")
    st.markdown("---")
    st.caption("Fatores de Bandeja / Filtro")
    df_filtros_default = pd.DataFrame([
        {"Filtro": "Nenhum", "Fator": 1.000},
        {"Filtro": "EDW", "Fator": 1.000},
        {"Filtro": "Acrílico", "Fator": 0.970},
    ])
    df_filtros_edit = st.data_editor(df_filtros_default, num_rows="dynamic", hide_index=True, use_container_width=True)
    dict_filtros = dict(zip(df_filtros_edit["Filtro"], df_filtros_edit["Fator"]))

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="app-header">
    <h1>🔬 Verificação Independente de Unidades Monitor</h1>
    <p>Importe o relatório do Eclipse · Cálculo automático · Preview do relatório</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="soft-divider"></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# UPLOAD
# ══════════════════════════════════════════════════════════════════════════════
pdf_files = st.file_uploader(
    "Arraste o(s) relatório(s) PDF do Eclipse",
    type=["pdf"],
    accept_multiple_files=True,
)

if not pdf_files:
    st.markdown("""
    <div style="text-align:center; padding: 3rem 1rem; color: #a0aec0;">
        <p style="font-size: 2.2rem; margin-bottom: 0.4rem;">📄</p>
        <p style="font-family: 'DM Sans', sans-serif; font-size: 0.92rem;">
            Arraste um ou mais PDFs do Eclipse acima para começar
        </p>
        <p style="font-family: 'DM Sans', sans-serif; font-size: 0.76rem; color: #cbd5e0;">
            Configurações avançadas na barra lateral (☰)
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# PROCESSAMENTO AUTOMÁTICO
# ══════════════════════════════════════════════════════════════════════════════
with st.spinner("Extraindo dados e calculando..."):
    dfs_extraidos = []
    nome_paciente, id_paciente, nome_plano = "", "", ""

    for pdf_file in pdf_files:
        dados = extrair_dados_rt(pdf_file, mu_threshold=mu_threshold)
        if not dados["df"].empty:
            dfs_extraidos.append(dados["df"])
        if dados["nome"]: nome_paciente = dados["nome"]
        if dados["id"]: id_paciente = dados["id"]

    if not dfs_extraidos:
        st.error(f"Nenhum campo com UM ≥ {mu_threshold} encontrado. Verifique o PDF ou ajuste o limiar na barra lateral.")
        st.stop()

    df_paciente = pd.concat(dfs_extraidos, ignore_index=True)
    planos_unicos = [str(p) for p in df_paciente["Plano"].unique() if p]
    nome_plano = " + ".join(planos_unicos) if planos_unicos else "Plano"

    # Desambiguar nomes duplicados
    contagem = df_paciente["Campo"].value_counts()
    for idx in df_paciente.index:
        if df_paciente.loc[idx, "Campo"] in contagem[contagem > 1].index:
            pl = df_paciente.loc[idx, "Plano"]
            df_paciente.loc[idx, "Campo"] = f"{df_paciente.loc[idx, 'Campo']} ({pl})"
    sufixos = df_paciente.groupby("Campo").cumcount()
    df_paciente["Campo"] = df_paciente["Campo"].astype(str) + sufixos.apply(lambda x: f" #{x+1}" if x > 0 else "")

    data_calc = date.today()
    df_res, erro = calcular_todos_campos(df_paciente, dose_ref, dict_filtros)

if erro:
    st.error(erro)
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# RESUMO (info strip compacto)
# ══════════════════════════════════════════════════════════════════════════════
num_campos = len(df_res)
desvios = df_res["Desvio_num"].abs()
max_desvio = desvios.max()

cols = st.columns([2.2, 1.5, 1.2, 1.5])
with cols[0]:
    st.markdown(f"""<div class="info-strip">
        <span class="label">Paciente</span><br>
        <span class="value">{nome_paciente or 'N/A'}</span>
        <span style="color:#a0aec0; font-size:0.78rem; margin-left:0.6rem;">ID {id_paciente or '—'}</span>
    </div>""", unsafe_allow_html=True)
with cols[1]:
    st.markdown(f"""<div class="info-strip">
        <span class="label">Plano</span><br>
        <span class="value">{nome_plano}</span>
    </div>""", unsafe_allow_html=True)
with cols[2]:
    st.markdown(f"""<div class="info-strip">
        <span class="label">Campos</span><br>
        <span class="value">{num_campos}</span>
    </div>""", unsafe_allow_html=True)
with cols[3]:
    if max_desvio <= 3.0:
        badge = '<span class="result-ok">✓ OK</span>'
    elif max_desvio <= 5.0:
        badge = '<span class="result-warn">⚠ Atenção</span>'
    else:
        badge = '<span class="result-fail">✗ Fora</span>'
    st.markdown(f"""<div class="info-strip">
        <span class="label">Concordância</span><br>
        {badge}
        <span style="font-size:0.76rem; color:#718096; margin-left:0.3rem;">máx {max_desvio:.1f}%</span>
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TABELA DE PARÂMETROS (colapsada)
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("📊 Ver parâmetros calculados", expanded=False):
    st.dataframe(df_res.copy().set_index("Campo").T, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# GERAR PDF + PREVIEW
# ══════════════════════════════════════════════════════════════════════════════
pdf_buf = gerar_pdf_transposto(
    df_res, nome_paciente, id_paciente, nome_plano, data_calc, dose_ref, instituicao=instituicao
)
pdf_bytes = pdf_buf.getvalue()
b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

st.markdown('<div class="soft-divider"></div>', unsafe_allow_html=True)

nome_arq = f"verificacao_{id_paciente or 'paciente'}.pdf"
st.download_button(
    label="⬇️  Descarregar Relatório PDF",
    data=pdf_bytes,
    file_name=nome_arq,
    mime="application/pdf",
    type="primary",
    use_container_width=True,
)

# Preview embutido
st.markdown(f"""
<div class="pdf-frame">
    <iframe src="data:application/pdf;base64,{b64_pdf}" type="application/pdf"></iframe>
</div>
""", unsafe_allow_html=True)

st.caption("Se o preview não aparecer no seu navegador, use o botão acima para descarregar.")
