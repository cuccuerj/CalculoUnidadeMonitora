import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import urllib.request
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
# GERAR PDF + PREVIEW HTML
# ══════════════════════════════════════════════════════════════════════════════
pdf_buf = gerar_pdf_transposto(
    df_res, nome_paciente, id_paciente, nome_plano, data_calc, dose_ref, instituicao=instituicao
)
pdf_bytes = pdf_buf.getvalue()

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

# ── Preview HTML do relatório ──
preview_html = []
preview_html.append("""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #fff; }
  .card { border:1px solid #e2e8f0; border-radius:10px; overflow:hidden; box-shadow:0 2px 12px rgba(0,0,0,0.04); }
  .header { padding:16px 20px 12px; border-bottom:2px solid #00c896; text-align:center; }
  .header h1 { font-size:15px; font-weight:700; color:#005088; margin:0 0 4px; }
  .header p { font-size:11px; color:#718096; }
  .info { padding:10px 20px; font-size:12px; color:#4a5568; display:flex; gap:24px; flex-wrap:wrap; border-bottom:1px solid #f0f0f0; }
  .info b { color:#2d3748; }
  table { width:100%; border-collapse:collapse; }
  th { text-align:center; padding:6px 8px; font-size:11px; color:#fff; background:#005088; white-space:nowrap; }
  th:first-child { text-align:left; padding:6px 10px; font-size:12px; }
  td { padding:5px 8px; font-size:12px; text-align:center; color:#4a5568; }
  td:first-child { text-align:left; padding:5px 10px; font-weight:600; color:#2d3748; white-space:nowrap; }
  tr:nth-child(odd) td { background:#f8fafc; }
  tr:nth-child(even) td { background:#fff; }
  .dev-ok { color:#22543d; font-weight:700; }
  .dev-warn { color:#744210; font-weight:700; }
  .dev-fail { color:#c53030; font-weight:700; }
  .footer { padding:12px 20px; border-top:1px solid #f0f0f0; display:flex; justify-content:space-around; color:#a0aec0; font-size:11px; text-align:center; }
</style></head><body><div class="card">""")

# Header
inst_line = f'<p style="font-size:13px;font-weight:700;color:#005088;margin:0 0 2px;">{instituicao}</p>' if instituicao else ''
preview_html.append(f"""
<div class="header">
  {inst_line}
  <h1>Verificação Independente de Unidades Monitor</h1>
  <p>Fator de Calibração: {dose_ref:.3f} cGy/UM &nbsp;|&nbsp; SAD: 100.0 cm</p>
</div>""")

# Patient info
preview_html.append(f"""
<div class="info">
  <span><b>Paciente:</b> {nome_paciente or 'N/A'}</span>
  <span><b>ID:</b> {id_paciente or 'N/A'}</span>
  <span><b>Plano:</b> {nome_plano or 'N/A'}</span>
  <span><b>Data:</b> {data_calc.strftime('%d/%m/%Y')}</span>
</div>""")

# Table
campos = list(df_res["Campo"])
header_ths = '<th>Parâmetro</th>'
for c in campos:
    header_ths += f'<th>{c}</th>'

parametros_preview = [
    ("Aparelho",            "Aparelho",       "s"),
    ("Energia",             "Energia",        "s"),
    ("Campo X (cm)",        "X",              ".1f"),
    ("Campo Y (cm)",        "Y",              ".1f"),
    ("Eq. Colimador (cm)",  "EqSq Colimador", ".2f"),
    ("Eq. Fantoma (cm)",    "EqSq Fantoma",   ".2f"),
    ("SSD (cm)",            "SSD",            ".1f"),
    ("Dose (cGy)",          "DOSE (cGy)",     ".1f"),
    ("Profundidade (cm)",   "Prof.",          ".2f"),
    ("Prof. Efetiva (cm)",  "Prof. Ef.",      ".2f"),
    ("TMR",                 "TMR",            ".4f"),
    ("Sc",                  "Sc",             ".4f"),
    ("Sp",                  "Sp",             ".4f"),
    ("Fator Filtro",        "Fator Filtro",   ".3f"),
    ("OAR",                 "OAR",            ".3f"),
    ("Fator Distância",     "ISQF",           ".4f"),
    ("UM Calculada",        "UM Calculada",   ".1f"),
    ("UM Eclipse",          "UM (Eclipse)",   ".0f"),
    ("Desvio (%)",          "Desvio_num",     "+.2f"),
]

rows_str = ""
for label, col, fmt in parametros_preview:
    tds = f"<td>{label}</td>"
    for _, r in df_res.iterrows():
        val = r[col]
        if fmt == "s":
            cell = str(val)
            css_class = ""
        else:
            cell = f"{val:{fmt}}"
            css_class = ""
            if col == "Desvio_num":
                cell += "%"
                d = abs(float(val))
                if d <= 2:
                    css_class = ' class="dev-ok"'
                elif d <= 5:
                    css_class = ' class="dev-warn"'
                else:
                    css_class = ' class="dev-fail"'
        tds += f"<td{css_class}>{cell}</td>"
    rows_str += f"<tr>{tds}</tr>\n"

preview_html.append(f"""
<div style="overflow-x:auto;">
  <table>
    <thead><tr>{header_ths}</tr></thead>
    <tbody>{rows_str}</tbody>
  </table>
</div>""")

# Footer
preview_html.append("""
<div class="footer">
  <span>___________________________<br><small>Físico Médico Responsável</small></span>
  <span>___________________________<br><small>Data da Revisão</small></span>
</div>
</div></body></html>""")

full_html = "\n".join(preview_html)

# Calcular altura aproximada: header(80) + info(40) + rows(~26 cada) + footer(50) + margens
preview_height = 80 + 40 + len(parametros_preview) * 26 + 50 + 40
components.html(full_html, height=preview_height, scrolling=True)

st.caption("Preview do relatório · O PDF oficial para impressão está no botão acima.")
