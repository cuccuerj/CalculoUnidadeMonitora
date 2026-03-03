import streamlit as st
import pandas as pd
import pdfplumber
import re
import numpy as np
import urllib.request
import base64
import io
from datetime import date
from scipy.interpolate import RegularGridInterpolator
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, Image as RLImage
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DE PÁGINA E CSS
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Verificação de UM · Radioterapia",
    page_icon="☢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

/* ── Base ── */
html, body, [class*="css"], .stApp {
    font-family: 'IBM Plex Sans', sans-serif !important;
    background: #0d1117 !important;
    color: #e6edf3 !important;
}

/* ── Layout principal ── */
.block-container {
    padding: 1.5rem 2.5rem 3rem !important;
    max-width: 1440px !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #161b22 !important;
    border-right: 1px solid #21262d !important;
}
[data-testid="stSidebar"] * { color: #c9d1d9 !important; }
[data-testid="stSidebar"] .stMarkdown h3 {
    color: #8b949e !important;
    font-size: 0.65rem !important;
    letter-spacing: 1.8px !important;
    text-transform: uppercase !important;
    margin: 20px 0 8px !important;
    font-weight: 600 !important;
}
[data-testid="stSidebar"] .stMarkdown h3::after {
    content: ''; display: block;
    height: 1px; background: #21262d;
    margin-top: 6px;
}

/* ── Cabeçalho principal ── */
.app-header {
    background: linear-gradient(135deg, #161b22 0%, #0d1f2d 100%);
    border: 1px solid #21262d;
    border-top: 3px solid #00c896;
    border-radius: 12px;
    padding: 26px 32px 22px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 18px;
}
.app-header-icon {
    width: 52px; height: 52px;
    background: rgba(0,200,150,0.1);
    border: 1px solid rgba(0,200,150,0.25);
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.6rem; flex-shrink: 0;
}
.app-header-text h1 {
    color: #f0f6fc; font-size: 1.45rem; font-weight: 700;
    margin: 0 0 4px; letter-spacing: -0.4px;
}
.app-header-text p { color: #8b949e; font-size: 0.83rem; margin: 0; }
.app-header-right { margin-left: auto; text-align: right; }
.app-badge {
    display: inline-block;
    background: rgba(0,200,150,0.1);
    border: 1px solid rgba(0,200,150,0.3);
    color: #00c896;
    padding: 3px 11px; border-radius: 20px;
    font-size: 0.7rem; font-weight: 700;
    letter-spacing: 0.8px; text-transform: uppercase;
    margin-bottom: 4px;
}
.app-header-right small { color: #484f58; font-size: 0.72rem; display: block; }

/* ── Step labels ── */
.step-label {
    display: flex; align-items: center; gap: 10px;
    margin: 22px 0 10px;
}
.step-num {
    width: 26px; height: 26px; border-radius: 50%;
    background: rgba(0,200,150,0.12);
    border: 1px solid rgba(0,200,150,0.3);
    color: #00c896; font-size: 0.75rem; font-weight: 700;
    display: inline-flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.step-title {
    color: #c9d1d9; font-size: 0.9rem; font-weight: 600;
}
.step-line { flex: 1; height: 1px; background: #21262d; }

/* ── Inputs ── */
.stNumberInput input, .stTextInput input,
.stTextArea textarea, .stDateInput input {
    background: #0d1117 !important;
    border: 1px solid #30363d !important;
    color: #e6edf3 !important;
    border-radius: 6px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.88rem !important;
}
.stNumberInput input:focus, .stTextInput input:focus {
    border-color: #00c896 !important;
    box-shadow: 0 0 0 3px rgba(0,200,150,0.08) !important;
}
label, .stLabel { color: #8b949e !important; font-size: 0.8rem !important; font-weight: 500 !important; }

/* ── Radio ── */
.stRadio label { color: #c9d1d9 !important; font-size: 0.85rem !important; }
.stRadio [data-baseweb="radio"] input:checked + div { border-color: #00c896 !important; }

/* ── Expander ── */
[data-testid="stExpander"] {
    background: #161b22 !important;
    border: 1px solid #21262d !important;
    border-radius: 8px !important;
    margin-bottom: 4px !important;
}
[data-testid="stExpander"] summary {
    color: #c9d1d9 !important;
    font-size: 0.88rem !important;
    font-weight: 600 !important;
    padding: 12px 16px !important;
}

/* ── Botões ── */
.stButton > button {
    border-radius: 7px !important;
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    transition: all 0.18s !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #00c896, #00a37a) !important;
    color: #fff !important; border: none !important;
    padding: 0.5rem 1.6rem !important;
}
.stButton > button[kind="primary"]:hover { opacity: 0.88 !important; transform: translateY(-1px) !important; }
.stButton > button:not([kind="primary"]) {
    background: #21262d !important;
    color: #c9d1d9 !important;
    border: 1px solid #30363d !important;
}
.stButton > button:not([kind="primary"]):hover { border-color: #00c896 !important; color: #00c896 !important; }

/* ── Download button ── */
[data-testid="stDownloadButton"] button {
    background: linear-gradient(135deg, #00c896, #00a37a) !important;
    color: #fff !important; border: none !important;
    border-radius: 7px !important; font-weight: 700 !important;
    font-size: 0.9rem !important; padding: 0.55rem 1.8rem !important;
    width: 100% !important;
}

/* ── Métricas ── */
[data-testid="metric-container"] {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 14px 18px !important;
}
[data-testid="metric-container"] label { color: #8b949e !important; font-size: 0.72rem !important; letter-spacing: 0.5px; text-transform: uppercase; }
[data-testid="metric-container"] [data-testid="metric-value"] {
    color: #e6edf3 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 1.8rem !important;
    font-weight: 600 !important;
}

/* ── Alerts ── */
.stInfo    { background: rgba(0,128,255,0.06) !important; border-left: 3px solid #388bfd !important; color: #79c0ff !important; border-radius: 6px !important; }
.stSuccess { background: rgba(0,200,150,0.06) !important; border-left: 3px solid #00c896 !important; color: #00c896   !important; border-radius: 6px !important; }
.stWarning { background: rgba(255,170,0,0.06) !important; border-left: 3px solid #d29922 !important; color: #d29922   !important; border-radius: 6px !important; }
.stError   { background: rgba(255,80,80,0.06)  !important; border-left: 3px solid #f85149 !important; color: #f85149   !important; border-radius: 6px !important; }

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: #161b22 !important;
    border: 1px dashed #30363d !important;
    border-radius: 8px !important;
}
[data-testid="stFileUploader"]:hover { border-color: #00c896 !important; }

/* ── Data editor ── */
[data-testid="stDataEditor"] {
    border: 1px solid #21262d !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}

/* ── Tabela de resultados custom ── */
.res-table-wrap {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    overflow: hidden;
    margin: 12px 0 20px;
}
.res-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.83rem;
}
.res-table thead tr { background: #0d1f2d; }
.res-table th {
    color: #8b949e;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 11px 14px;
    text-align: center;
    border-bottom: 1px solid #21262d;
    white-space: nowrap;
}
.res-table th:first-child { text-align: left; }
.res-table td {
    padding: 10px 14px;
    border-bottom: 1px solid #161b22;
    color: #c9d1d9;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.8rem;
    text-align: center;
    background: #0d1117;
}
.res-table td:first-child {
    text-align: left;
    font-family: 'IBM Plex Sans', sans-serif;
    font-weight: 600;
    color: #e6edf3;
    background: #0d1117;
}
.res-table tr:hover td { background: #161b22 !important; }
.td-um-calc { color: #00c896 !important; font-size: 0.95rem !important; font-weight: 700 !important; }
.td-um-ecl  { color: #79c0ff !important; }
.badge-ok   { background: rgba(0,200,150,0.12); color: #00c896; border: 1px solid rgba(0,200,150,0.3); border-radius: 4px; padding: 2px 8px; font-weight: 700; font-size: 0.75rem; }
.badge-warn { background: rgba(210,153,34,0.12); color: #d29922; border: 1px solid rgba(210,153,34,0.3); border-radius: 4px; padding: 2px 8px; font-weight: 700; font-size: 0.75rem; }
.badge-err  { background: rgba(248,81,73,0.12);  color: #f85149; border: 1px solid rgba(248,81,73,0.3);  border-radius: 4px; padding: 2px 8px; font-weight: 700; font-size: 0.75rem; }

/* ── Panel de preview ── */
.preview-panel {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 24px;
    margin-top: 16px;
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

SAD = 100.0

# ══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES DE CÁLCULO (mantidas do código original)
# ══════════════════════════════════════════════════════════════════════════════

def calcular_eqsq(x, y):
    if x <= 0 or y <= 0:
        return 0.0
    return (4 * x * y) / (2 * (x + y))

def calcular_fator_distancia(ssd, prof, dmax, sad=SAD):
    if ssd <= 0:
        return 0.0
    return ((sad + dmax) / (prof + ssd)) ** 2

def extrair_dados_rt(pdf_file):
    dados_campos = {}
    with pdfplumber.open(pdf_file) as pdf:
        texto_completo = ""
        for page in pdf.pages:
            texto_completo += (page.extract_text() or "") + "\n"

    match_plano = re.search(r"(?:Plano|Plan):\s*(.+)", texto_completo, re.IGNORECASE)
    nome_plano = match_plano.group(1).strip() if match_plano else pdf_file.name

    campos_encontrados = sorted(list(set(re.findall(r'Campo (\d+)', texto_completo))))

    for c in campos_encontrados:
        dados_campos[c] = {
            "Plano": nome_plano, "Campo": f"Campo {c}",
            "X": 0.0, "Y": 0.0, "Fsx (cm)": 0.0, "Fsy (cm)": 0.0,
            "FILTRO": "Nenhum", "UM (Eclipse)": 0.0, "DOSE (cGy)": 0.0,
            "SSD": 0.0, "Prof.": 0.0, "Prof. Ef.": 0.0,
        }

    def buscar_valor(chave, campo_num, texto):
        padrao = rf"{chave}.*?Campo {campo_num}\s+([\d.]+)"
        match = re.search(padrao, texto, re.DOTALL | re.IGNORECASE)
        return float(match.group(1)) if match else 0.0

    for c in campos_encontrados:
        dados_campos[c]["X"]            = buscar_valor("Tamanho do Campo Aberto X", c, texto_completo)
        dados_campos[c]["Y"]            = buscar_valor("Tamanho do Campo Aberto Y", c, texto_completo)
        dados_campos[c]["UM (Eclipse)"] = buscar_valor("MU", c, texto_completo)
        dados_campos[c]["DOSE (cGy)"]   = buscar_valor("Dose", c, texto_completo)
        dados_campos[c]["SSD"]          = buscar_valor("SSD", c, texto_completo)
        dados_campos[c]["Prof."]        = buscar_valor("Profundidade", c, texto_completo)
        dados_campos[c]["Prof. Ef."]    = buscar_valor("Profundidade Efetiva", c, texto_completo)
        match_f = re.search(rf"Filtro.*?Campo {c}\s+(.*?)\n", texto_completo, re.DOTALL | re.IGNORECASE)
        if match_f:
            f = match_f.group(1).strip()
            dados_campos[c]["FILTRO"] = "Nenhum" if (not f or f == "-") else f

    padrao_fs = r"(?:fluência total|total fluence).{0,100}?fsx\s*=\s*([\d.]+)\s*mm(?:.{0,50}?fsy\s*=\s*([\d.]+)\s*mm)?"
    matches_fs = re.findall(padrao_fs, texto_completo, re.IGNORECASE | re.DOTALL)
    for i, c in enumerate(campos_encontrados):
        if i < len(matches_fs):
            dados_campos[c]["Fsx (cm)"] = float(matches_fs[i][0]) / 10.0
            dados_campos[c]["Fsy (cm)"] = float(matches_fs[i][1] or matches_fs[i][0]) / 10.0

    return pd.DataFrame(dados_campos.values())

@st.cache_data
def carregar_tabelas_maquina(conteudo_texto):
    linhas = conteudo_texto.split('\n')
    campos, sc, sp, profundidades, tmr_matriz = [], [], [], [], []

    for linha in linhas:
        partes = linha.strip().split('\t')
        if len(partes) < 2:
            partes = linha.strip().split()
        if not partes or len(partes) < 2:
            continue
        rotulo = partes[0].strip().lower()
        try:
            valores = [float(v.replace(',', '.')) for v in partes[1:] if v.strip()]
        except ValueError:
            continue
        if rotulo == 'campo':   campos = valores
        elif rotulo == 'sc':    sc = valores
        elif rotulo == 'sp':    sp = valores
        else:
            try:
                profundidades.append(float(rotulo.replace(',', '.')))
                tmr_matriz.append(valores)
            except ValueError:
                pass

    tmr_array  = np.array(tmr_matriz)
    prof_array = np.array(profundidades)
    dmax_auto  = 1.5
    if tmr_array.size > 0:
        idx = np.argmax(tmr_array[:, tmr_array.shape[1] // 2])
        dmax_auto = prof_array[idx]

    return np.array(campos), np.array(sc), np.array(sp), prof_array, tmr_array, dmax_auto


# ══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DE PDF
# ══════════════════════════════════════════════════════════════════════════════

def gerar_pdf(df_res, nome_paciente, id_paciente, nome_plano,
              data_calc, logo_bytes=None, instituicao=""):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2.5*cm)

    styles = getSampleStyleSheet()
    VERDE  = colors.HexColor("#00c896")
    AZUL_E = colors.HexColor("#0a1a3a")
    CINZA  = colors.HexColor("#555555")

    s_tit   = ParagraphStyle("tit",  parent=styles["Normal"], fontSize=14, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=3)
    s_sub   = ParagraphStyle("sub",  parent=styles["Normal"], fontSize=9,  alignment=TA_CENTER, spaceAfter=12, textColor=CINZA)
    s_sec   = ParagraphStyle("sec",  parent=styles["Normal"], fontSize=10, fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4)
    s_inst  = ParagraphStyle("inst", parent=styles["Normal"], fontSize=10, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=3)
    s_aviso = ParagraphStyle("av",   parent=styles["Normal"], fontSize=7.5, textColor=CINZA, alignment=TA_CENTER, spaceBefore=12)

    story = []

    # Cabeçalho
    if logo_bytes:
        try:
            story.append(RLImage(io.BytesIO(logo_bytes), width=4*cm, height=1.6*cm, kind='proportional'))
            story.append(Spacer(1, 4))
        except Exception:
            pass

    if instituicao:
        story.append(Paragraph(instituicao, s_inst))

    story.append(Paragraph("Ficha de Verificacao Independente de Unidades Monitor", s_tit))
    story.append(Paragraph("Radioterapia &nbsp;·&nbsp; Clinac 6 MV &nbsp;·&nbsp; SAD = 100 cm", s_sub))
    story.append(HRFlowable(width="100%", thickness=2.5, color=VERDE))
    story.append(Spacer(1, 10))

    # Dados do paciente
    story.append(Paragraph("Identificacao do Paciente", s_sec))
    t_pac = Table([
        ["Paciente:",    nome_paciente or "—",              "ID / Prontuario:", id_paciente or "—"],
        ["Plano:",       nome_plano    or "—",              "Data do Calculo:", data_calc.strftime("%d/%m/%Y")],
    ], colWidths=[3*cm, 7.5*cm, 3.5*cm, 3.5*cm])
    t_pac.setStyle(TableStyle([
        ("FONTNAME",      (0,0),(0,-1), "Helvetica-Bold"),
        ("FONTNAME",      (2,0),(2,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 9),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
    ]))
    story.append(t_pac)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#DDDDDD")))

    # Tabela de resultados
    story.append(Paragraph("Resultados do Calculo Independente", s_sec))

    header = [["Campo", "Dose\n(cGy)", "Sc", "Sp", "TMR", "ISQF",
               "F.Filtro", "UM\nCalc.", "UM\nEclipse", "Desvio\n(%)"]]
    rows = []
    for _, r in df_res.iterrows():
        d = r.get("Desvio (%)", 0)
        rows.append([
            str(r.get("Campo", "")),
            f"{r.get('DOSE (cGy)', 0):.1f}",
            f"{r.get('Sc', 0):.4f}",
            f"{r.get('Sp', 0):.4f}",
            f"{r.get('TMR', 0):.4f}",
            f"{r.get('ISQF', 0):.4f}",
            f"{r.get('Fator Filtro', 1.0):.3f}",
            f"{r.get('UM Calculada', 0):.1f}",
            f"{r.get('UM (Eclipse)', 0):.0f}",
            f"{d:+.1f}%",
        ])

    cw = [2.7*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm]
    t_res = Table(header + rows, colWidths=cw, repeatRows=1)

    cmd = [
        ("BACKGROUND",    (0,0),  (-1,0),  AZUL_E),
        ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),  (-1,-1), 7.5),
        ("ALIGN",         (0,0),  (-1,-1), "CENTER"),
        ("ALIGN",         (0,1),  (0,-1),  "LEFT"),
        ("FONTNAME",      (-3,1), (-2,-1), "Helvetica-Bold"),
        ("GRID",          (0,0),  (-1,-1), 0.4, colors.HexColor("#CCCCCC")),
        ("TOPPADDING",    (0,0),  (-1,-1), 4),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 4),
        *[("BACKGROUND",  (0,i),  (-1,i),  colors.HexColor("#F0F8FF"))
          for i in range(2, len(rows)+1, 2)],
    ]
    # Cor do desvio por linha
    for i, r in enumerate(df_res.itertuples(), start=1):
        d = getattr(r, "Desvio ___", getattr(r, "_10", 0))
        try:
            d = float(df_res.iloc[i-1]["Desvio (%)"])
        except Exception:
            d = 0
        if abs(d) <= 2:
            cmd.append(("TEXTCOLOR", (-1, i), (-1, i), colors.HexColor("#006644")))
        elif abs(d) <= 5:
            cmd.append(("TEXTCOLOR", (-1, i), (-1, i), colors.HexColor("#7d5a00")))
        else:
            cmd.append(("TEXTCOLOR", (-1, i), (-1, i), colors.HexColor("#9e1c1c")))
            cmd.append(("FONTNAME",  (-1, i), (-1, i), "Helvetica-Bold"))

    t_res.setStyle(TableStyle(cmd))
    story.append(t_res)

    # Legenda
    story.append(Spacer(1, 8))
    leg = Table([[
        Paragraph("<font color='#006644'>■ Desvio ≤ 2%  —  Aprovado</font>",
                  ParagraphStyle("l1", parent=styles["Normal"], fontSize=8)),
        Paragraph("<font color='#7d5a00'>■ Desvio 2–5%  —  Atencao</font>",
                  ParagraphStyle("l2", parent=styles["Normal"], fontSize=8)),
        Paragraph("<font color='#9e1c1c'>■ Desvio > 5%  —  Revisar</font>",
                  ParagraphStyle("l3", parent=styles["Normal"], fontSize=8)),
    ]], colWidths=[5.6*cm]*3)
    leg.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#F8F8F8")),
        ("BOX",           (0,0),(-1,-1), 0.4, colors.HexColor("#CCCCCC")),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("ALIGN",         (0,0),(-1,-1), "CENTER"),
    ]))
    story.append(leg)

    # Rodapé
    story.append(Spacer(1, 18))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#DDDDDD")))
    story.append(Paragraph(
        "Ferramenta de apoio a verificacao independente. "
        "Deve ser conferido e assinado pelo fisico medico responsavel antes do uso clinico.",
        s_aviso))

    t_ass = Table([[
        "Calculado por: _______________________",
        "Data: ___/___/______",
        "Verificado por: _______________________",
    ]], colWidths=[6.5*cm, 4*cm, 7*cm])
    t_ass.setStyle(TableStyle([
        ("FONTSIZE",      (0,0),(-1,-1), 8),
        ("TOPPADDING",    (0,0),(-1,-1), 16),
        ("ALIGN",         (1,0),(1,0),   "CENTER"),
        ("TEXTCOLOR",     (0,0),(-1,-1), colors.HexColor("#444444")),
    ]))
    story.append(t_ass)
    doc.build(story)
    buffer.seek(0)
    return buffer


# ══════════════════════════════════════════════════════════════════════════════
# PREVIEW HTML
# ══════════════════════════════════════════════════════════════════════════════

def gerar_preview_html(df_res, nome_paciente, id_paciente, nome_plano,
                        data_calc, logo_b64=None, instituicao=""):
    logo_html = ""
    if logo_b64:
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height:52px;object-fit:contain;margin-bottom:8px;display:block;margin-left:auto;margin-right:auto;">'

    inst_html = f'<div style="font-weight:700;font-size:12px;color:#111;margin-bottom:2px;text-align:center;">{instituicao}</div>' if instituicao else ""

    rows_html = ""
    for _, r in df_res.iterrows():
        d = r.get("Desvio (%)", 0)
        if abs(d) <= 2:
            badge = f'<span style="background:#d1fae5;color:#065f46;border-radius:4px;padding:2px 9px;font-weight:700;font-size:11px;font-family:monospace;">{d:+.1f}%</span>'
        elif abs(d) <= 5:
            badge = f'<span style="background:#fef3c7;color:#92400e;border-radius:4px;padding:2px 9px;font-weight:700;font-size:11px;font-family:monospace;">{d:+.1f}%</span>'
        else:
            badge = f'<span style="background:#fee2e2;color:#991b1b;border-radius:4px;padding:2px 9px;font-weight:700;font-size:11px;font-family:monospace;">{d:+.1f}%</span>'

        rows_html += f"""
        <tr>
          <td style="font-weight:600;color:#0a1a3a;text-align:left;">{r.get('Campo','')}</td>
          <td>{r.get('DOSE (cGy)', 0):.1f}</td>
          <td>{r.get('Sc', 0):.4f}</td>
          <td>{r.get('Sp', 0):.4f}</td>
          <td>{r.get('TMR', 0):.4f}</td>
          <td>{r.get('ISQF', 0):.4f}</td>
          <td>{r.get('Fator Filtro', 1.0):.3f}</td>
          <td style="font-weight:800;color:#059669;font-size:15px;">{r.get('UM Calculada', 0):.1f}</td>
          <td style="color:#2563eb;">{r.get('UM (Eclipse)', 0):.0f}</td>
          <td>{badge}</td>
        </tr>"""

    th_style = "background:#0a1a3a;color:#fff;padding:9px 12px;font-size:10px;letter-spacing:0.8px;text-transform:uppercase;text-align:center;font-weight:700;white-space:nowrap;"
    td_style = "padding:10px 12px;text-align:center;border-bottom:1px solid #f1f5f9;font-family:'Courier New',monospace;font-size:12px;color:#334155;"

    return f"""
    <div style="background:#ffffff;font-family:-apple-system,Helvetica,Arial,sans-serif;
                padding:36px 40px;border-radius:10px;max-width:900px;margin:0 auto;
                box-shadow:0 4px 24px rgba(0,0,0,0.1);">

      {logo_html}
      {inst_html}
      <div style="text-align:center;margin-bottom:20px;">
        <div style="font-size:17px;font-weight:800;color:#0a1a3a;margin-bottom:4px;letter-spacing:-0.3px;">
          Ficha de Verificação Independente de Unidades Monitor
        </div>
        <div style="font-size:11px;color:#94a3b8;margin-bottom:14px;">
          Radioterapia &nbsp;·&nbsp; Clinac 6 MV &nbsp;·&nbsp; SAD = 100 cm
        </div>
        <div style="height:3px;border-radius:2px;background:linear-gradient(90deg,#0080ff,#00c896);"></div>
      </div>

      <table style="width:100%;font-size:12px;margin-bottom:18px;border-collapse:collapse;">
        <tr>
          <td style="color:#64748b;font-weight:600;padding:3px 0;width:16%;">Paciente:</td>
          <td style="color:#0a1a3a;font-weight:500;padding:3px 0;width:38%;">{nome_paciente or "—"}</td>
          <td style="color:#64748b;font-weight:600;padding:3px 0;width:20%;">ID / Prontuário:</td>
          <td style="color:#0a1a3a;font-weight:500;padding:3px 0;">{id_paciente or "—"}</td>
        </tr>
        <tr>
          <td style="color:#64748b;font-weight:600;padding:3px 0;">Plano:</td>
          <td style="color:#0a1a3a;font-weight:500;padding:3px 0;">{nome_plano or "—"}</td>
          <td style="color:#64748b;font-weight:600;padding:3px 0;">Data:</td>
          <td style="color:#0a1a3a;font-weight:500;padding:3px 0;">{data_calc.strftime("%d/%m/%Y")}</td>
        </tr>
      </table>

      <div style="height:1px;background:#e2e8f0;margin-bottom:16px;"></div>

      <div style="font-size:10px;font-weight:700;color:#64748b;letter-spacing:1.2px;
                  text-transform:uppercase;margin-bottom:10px;">
        Resultados do Cálculo Independente
      </div>

      <table style="width:100%;border-collapse:collapse;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.06);">
        <thead>
          <tr>
            {"".join(f'<th style="{th_style}">{h}</th>' for h in
              ["Campo","Dose (cGy)","Sc","Sp","TMR","ISQF","F.Filtro","UM Calc.","UM Eclipse","Desvio"])}
          </tr>
        </thead>
        <tbody>
          {"".join(f'<tr style="background:{"#f8fafc" if i%2==0 else "#fff"};">{row.replace("padding:10px 12px", "padding:10px 12px")}</tr>' for i, row in enumerate(rows_html.split("</tr>")[:-1]))}
        </tbody>
      </table>
      <style>tbody td {{ {td_style} }}</style>

      <div style="display:flex;gap:10px;margin-top:14px;flex-wrap:wrap;">
        <span style="background:#d1fae5;color:#065f46;border-radius:5px;padding:4px 12px;font-size:11px;font-weight:600;">✓ ≤ 2%  Aprovado</span>
        <span style="background:#fef3c7;color:#92400e;border-radius:5px;padding:4px 12px;font-size:11px;font-weight:600;">⚠ 2–5%  Atenção</span>
        <span style="background:#fee2e2;color:#991b1b;border-radius:5px;padding:4px 12px;font-size:11px;font-weight:600;">✗ &gt;5%  Revisar</span>
      </div>

      <div style="margin-top:28px;padding-top:14px;border-top:1px solid #e2e8f0;
                  display:flex;justify-content:space-between;font-size:10px;color:#94a3b8;">
        <span>Calculado por: _______________________</span>
        <span>Data: ___/___/______</span>
        <span>Verificado por: _______________________</span>
      </div>
      <div style="margin-top:10px;text-align:center;font-size:9px;color:#cbd5e1;">
        Ferramenta de apoio à verificação independente. Deve ser conferido e assinado pelo físico médico responsável.
      </div>
    </div>"""


# ══════════════════════════════════════════════════════════════════════════════
# INTERFACE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <div class="app-header-icon">☢️</div>
  <div class="app-header-text">
    <h1>Verificação de Unidades Monitor</h1>
    <p>Segunda verificação independente de cálculo 3D &nbsp;·&nbsp; Clinac 6 MV &nbsp;·&nbsp; SAD 100 cm</p>
  </div>
  <div class="app-header-right">
    <div class="app-badge">Clínico · v2.0</div>
    <small>Radioterapia</small>
  </div>
</div>
""", unsafe_allow_html=True)


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙ Máquina")
    dose_ref = st.number_input("Taxa de Dose (cGy/UM)", value=1.000, step=0.01, format="%.3f")

    st.markdown("### 🏥 Instituição")
    instituicao = st.text_input("Nome", placeholder="Ex.: Hospital Universitário...")
    logo_file = st.file_uploader("Logotipo (PNG/JPG)", type=["png","jpg","jpeg"],
                                  help="Exibido no cabeçalho da ficha PDF e na pré-visualização.")
    logo_bytes = logo_file.read() if logo_file else None
    logo_b64   = base64.b64encode(logo_bytes).decode() if logo_bytes else None

    st.markdown("### 📋 Dados do Paciente")
    nome_paciente = st.text_input("Nome do Paciente", placeholder="Nome completo")
    id_paciente   = st.text_input("ID / Prontuário",  placeholder="Ex.: 1803851")
    data_calc     = st.date_input("Data do Cálculo", value=date.today())

    st.markdown("### 🔬 Filtros / Bandejas")
    df_filtros_default = pd.DataFrame([
        {"Nome do Filtro": "Nenhum",           "Fator": 1.000},
        {"Nome do Filtro": "EDW",              "Fator": 1.000},
        {"Nome do Filtro": "Bandeja Acrílico", "Fator": 0.970},
    ])
    df_filtros_edit = st.data_editor(df_filtros_default, num_rows="dynamic", hide_index=True)
    dict_filtros = dict(zip(df_filtros_edit["Nome do Filtro"], df_filtros_edit["Fator"]))


# ── PASSO 1: DADOS DA MÁQUINA ──────────────────────────────────────────────────
st.markdown("""
<div class="step-label">
  <div class="step-num">1</div>
  <div class="step-title">Dados da Máquina — Sc, Sp, TMR</div>
  <div class="step-line"></div>
</div>""", unsafe_allow_html=True)

with st.expander("Configurar fonte dos dados dosimétricos", expanded=False):
    fonte = st.radio("Fonte:", ("Repositório GitHub (padrão)", "Upload de arquivo TXT"), horizontal=True)
    conteudo_maquina = None

    if fonte == "Repositório GitHub (padrão)":
        url = "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/refs/heads/main/clinac_fac_tmr.txt"
        st.info(f"🔗 `{url}`")
        try:
            with urllib.request.urlopen(url) as r:
                conteudo_maquina = r.read().decode("utf-8")
            st.success("Tabelas carregadas do GitHub.")
        except Exception:
            st.warning("Sem conexão ao GitHub. Use o upload manual.")
    else:
        arq = st.file_uploader("Arquivo TXT da máquina", type=["txt"])
        if arq:
            conteudo_maquina = arq.getvalue().decode("utf-8")
            st.success("Arquivo carregado.")

    # Persiste no session state para não precisar do expander aberto
    if conteudo_maquina:
        st.session_state["conteudo_maquina"] = conteudo_maquina

conteudo_maquina = st.session_state.get("conteudo_maquina")


# ── PASSO 2: PARÂMETROS DO PLANO ──────────────────────────────────────────────
st.markdown("""
<div class="step-label">
  <div class="step-num">2</div>
  <div class="step-title">Parâmetros do Plano</div>
  <div class="step-line"></div>
</div>""", unsafe_allow_html=True)

metodo = st.radio("Entrada de dados:", ("Extrair do PDF (Eclipse)", "Manual"), horizontal=True)

colunas_padrao = ["Plano","Campo","X","Y","Fsx (cm)","Fsy (cm)","FILTRO","UM (Eclipse)","DOSE (cGy)","SSD","Prof.","Prof. Ef."]
df_paciente = pd.DataFrame(columns=colunas_padrao)
nome_plano = ""

if metodo == "Extrair do PDF (Eclipse)":
    pdfs = st.file_uploader("PDF(s) do Eclipse", type=["pdf"], accept_multiple_files=True)
    if pdfs:
        with st.spinner("Extraindo parâmetros..."):
            df_paciente = pd.concat([extrair_dados_rt(p) for p in pdfs], ignore_index=True)
        nome_plano = df_paciente["Plano"].iloc[0] if not df_paciente.empty else ""
        st.success(f"✅ {len(df_paciente)} campo(s) extraído(s) — **{nome_plano}**")
else:
    df_paciente = pd.DataFrame([{
        "Plano":"Plano Manual","Campo":"Campo 1","X":10.0,"Y":10.0,
        "Fsx (cm)":10.0,"Fsy (cm)":10.0,"FILTRO":"Nenhum",
        "UM (Eclipse)":100.0,"DOSE (cGy)":100.0,
        "SSD":100.0,"Prof.":5.0,"Prof. Ef.":5.0,
    }])
    nome_plano = "Plano Manual"

if not df_paciente.empty:
    st.markdown('<div style="font-size:0.72rem;color:#8b949e;font-weight:600;letter-spacing:1px;text-transform:uppercase;margin:12px 0 6px;">Tabela de parâmetros — editável</div>', unsafe_allow_html=True)
    df_edit = st.data_editor(df_paciente, num_rows="dynamic", use_container_width=True)


# ── PASSO 3: CÁLCULO ──────────────────────────────────────────────────────────
if not df_paciente.empty and conteudo_maquina:

    campos_m, sc_m, sp_m, prof_m, tmr_m, dmax = carregar_tabelas_maquina(conteudo_maquina)
    interp_tmr = RegularGridInterpolator((prof_m, campos_m), tmr_m, bounds_error=False, fill_value=None)

    st.markdown("""
    <div class="step-label">
      <div class="step-num">3</div>
      <div class="step-title">Resultados</div>
      <div class="step-line"></div>
    </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="background:#161b22;border:1px solid #21262d;border-left:3px solid #00c896;
                border-radius:6px;padding:10px 16px;margin-bottom:16px;font-size:0.83rem;
                color:#8b949e;">
      <b style="color:#e6edf3;">d<sub>max</sub> = {dmax} cm</b>
      &nbsp;·&nbsp; Detectado automaticamente do pico da matriz TMR
    </div>""", unsafe_allow_html=True)

    # Calcula todos os campos
    resultados = []
    for _, row in df_edit.iterrows():
        eqsq_c = calcular_eqsq(row["X"], row["Y"])
        eqsq_f = calcular_eqsq(row["Fsx (cm)"], row["Fsy (cm)"])
        isqf   = calcular_fator_distancia(row["SSD"], row["Prof."], dmax=dmax)
        sc_v   = np.interp(eqsq_c, campos_m, sc_m)
        sp_v   = np.interp(eqsq_f, campos_m, sp_m)
        tmr_v  = float(interp_tmr((row["Prof. Ef."], eqsq_f))) if row["Prof. Ef."] > 0 and eqsq_f > 0 else 0.0
        ff     = dict_filtros.get(row["FILTRO"], 1.0)
        denom  = dose_ref * sc_v * sp_v * tmr_v * isqf * ff
        um_c   = row["DOSE (cGy)"] / denom if denom > 0 else 0.0
        dev    = ((um_c - row["UM (Eclipse)"]) / row["UM (Eclipse)"]) * 100 if row["UM (Eclipse)"] > 0 else 0.0
        resultados.append({
            "Plano": row["Plano"], "Campo": row["Campo"],
            "DOSE (cGy)": row["DOSE (cGy)"],
            "Sc": round(sc_v,4), "Sp": round(sp_v,4), "TMR": round(tmr_v,4),
            "ISQF": round(isqf,4), "Fator Filtro": ff,
            "UM Calculada": round(um_c,1), "UM (Eclipse)": row["UM (Eclipse)"],
            "Desvio (%)": round(dev,2),
        })

    df_res = pd.DataFrame(resultados)

    # Métricas resumo
    tot = len(df_res)
    ok  = int((df_res["Desvio (%)"].abs() <= 2).sum())
    av  = int(((df_res["Desvio (%)"].abs() > 2) & (df_res["Desvio (%)"].abs() <= 5)).sum())
    er  = int((df_res["Desvio (%)"].abs() > 5).sum())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Campos calculados", tot)
    m2.metric("✅ Aprovados ≤ 2%", ok)
    m3.metric("⚠️ Atenção 2–5%",  av)
    m4.metric("❌ Revisar > 5%",   er)

    # Tabela de resultados com design customizado
    rows_table = ""
    for _, r in df_res.iterrows():
        d = r["Desvio (%)"]
        if abs(d) <= 2:
            badge = f'<span class="badge-ok">{d:+.1f}%</span>'
        elif abs(d) <= 5:
            badge = f'<span class="badge-warn">{d:+.1f}%</span>'
        else:
            badge = f'<span class="badge-err">{d:+.1f}%</span>'

        rows_table += f"""
        <tr>
          <td class="td-campo">{r['Campo']}</td>
          <td>{r['DOSE (cGy)']:.1f}</td>
          <td>{r['Sc']:.4f}</td>
          <td>{r['Sp']:.4f}</td>
          <td>{r['TMR']:.4f}</td>
          <td>{r['ISQF']:.4f}</td>
          <td>{r['Fator Filtro']:.3f}</td>
          <td class="td-um-calc">{r['UM Calculada']:.1f}</td>
          <td class="td-um-ecl">{r['UM (Eclipse)']:.0f}</td>
          <td>{badge}</td>
        </tr>"""

    st.markdown(f"""
    <div class="res-table-wrap">
      <table class="res-table">
        <thead>
          <tr>
            <th style="text-align:left;">Campo</th>
            <th>Dose (cGy)</th><th>Sc</th><th>Sp</th><th>TMR</th>
            <th>ISQF</th><th>F.Filtro</th>
            <th>UM Calc.</th><th>UM Eclipse</th><th>Desvio</th>
          </tr>
        </thead>
        <tbody>{rows_table}</tbody>
      </table>
    </div>""", unsafe_allow_html=True)

    st.caption("Desvios < 5% são esperados para campos abertos. Cunhas dinâmicas, heterogeneidades e campos pequenos podem gerar desvios maiores em relação ao AAA/Acuros.")


    # ── PASSO 4: EXPORTAR ──────────────────────────────────────────────────────
    st.markdown("""
    <div class="step-label">
      <div class="step-num">4</div>
      <div class="step-title">Exportar Ficha</div>
      <div class="step-line"></div>
    </div>""", unsafe_allow_html=True)

    c_prev, c_gen = st.columns(2)

    with c_prev:
        if st.button("👁  Pré-visualizar ficha", use_container_width=True):
            st.session_state["show_preview"] = not st.session_state.get("show_preview", False)

    with c_gen:
        if st.button("📄  Gerar PDF", type="primary", use_container_width=True):
            if not nome_paciente.strip():
                st.warning("Preencha o nome do paciente na barra lateral antes de gerar o PDF.")
            else:
                pdf_buf  = gerar_pdf(df_res, nome_paciente, id_paciente,
                                     nome_plano, data_calc, logo_bytes, instituicao)
                nome_arq = f"verificacao_mu_{id_paciente or 'paciente'}_{data_calc.strftime('%Y%m%d')}.pdf"
                st.download_button(
                    label="⬇️  Baixar PDF",
                    data=pdf_buf, file_name=nome_arq,
                    mime="application/pdf", type="primary",
                    use_container_width=True,
                )

    # Pré-visualização inline
    if st.session_state.get("show_preview"):
        st.markdown('<div class="preview-panel">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.72rem;color:#8b949e;font-weight:600;letter-spacing:1px;text-transform:uppercase;margin-bottom:14px;">Pré-visualização da Ficha</div>', unsafe_allow_html=True)

        html_prev = gerar_preview_html(
            df_res, nome_paciente, id_paciente, nome_plano,
            data_calc, logo_b64, instituicao
        )
        st.components.v1.html(
            f'<div style="background:#f1f5f9;padding:24px;min-height:600px;">{html_prev}</div>',
            height=680, scrolling=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

elif not conteudo_maquina and not df_paciente.empty:
    st.info("Abra a seção **Passo 1** e carregue os dados dosimétricos da máquina para calcular.")
