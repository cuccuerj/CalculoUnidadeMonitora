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
# CONFIGURAÇÃO DE PÁGINA
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Verificação de UM · Radioterapia",
    page_icon="☢️",
    layout="wide"
)

# Estilo mínimo apenas para alinhar componentes nativos
st.markdown("""
<style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1 { color: #005088; }
    h2, h3 { color: #1e293b; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES E ESTADOS
# ══════════════════════════════════════════════════════════════════════════════
SAD = 100.0

if "nome_paciente" not in st.session_state:
    st.session_state["nome_paciente"] = ""
if "id_paciente" not in st.session_state:
    st.session_state["id_paciente"] = ""

# ══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES DE CÁLCULO E EXTRAÇÃO
# ══════════════════════════════════════════════════════════════════════════════
def calcular_eqsq(x, y):
    if x <= 0 or y <= 0: return 0.0
    return (4 * x * y) / (2 * (x + y))

def calcular_fator_distancia(ssd, prof, dmax, sad=SAD):
    if ssd <= 0: return 0.0
    return ((sad + dmax) / (prof + ssd)) ** 2

def extrair_dados_rt(pdf_file):
    dados_campos = {}
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_completo += (page.extract_text() or "") + "\n"

    # Extração automática dos dados do Paciente
    match_nome = re.search(r"Nome do Paciente:\s*(.+)", texto_completo, re.IGNORECASE)
    nome_pac = match_nome.group(1).strip() if match_nome else ""

    match_id = re.search(r"(?:Matricula|ID|Patient ID):\s*(.+)", texto_completo, re.IGNORECASE)
    id_pac = match_id.group(1).strip() if match_id else ""

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

    df = pd.DataFrame(dados_campos.values())
    return {"df": df, "nome": nome_pac, "id": id_pac}

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
def gerar_pdf(df_res, nome_paciente, id_paciente, nome_plano, data_calc, logo_bytes=None, instituicao=""):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2.5*cm)

    styles = getSampleStyleSheet()
    VERDE = colors.HexColor("#00c896")
    AZUL = colors.HexColor("#005088")
    
    s_tit  = ParagraphStyle("tit", parent=styles["Normal"], fontSize=16, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=3, textColor=AZUL)
    s_sub  = ParagraphStyle("sub", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER, spaceAfter=15, textColor=colors.gray)
    s_sec  = ParagraphStyle("sec", parent=styles["Normal"], fontSize=12, fontName="Helvetica-Bold", spaceBefore=15, spaceAfter=6, textColor=AZUL)
    
    story = []

    # Logo e Instituição
    if logo_bytes:
        try:
            story.append(RLImage(io.BytesIO(logo_bytes), width=4*cm, height=1.6*cm, kind='proportional'))
            story.append(Spacer(1, 10))
        except: pass
    
    if instituicao:
        story.append(Paragraph(instituicao, ParagraphStyle("inst", parent=styles["Normal"], fontSize=11, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=5)))

    story.append(Paragraph("Verificação Independente de Unidades Monitor", s_tit))
    story.append(Paragraph("Radioterapia • Clinac 6 MV • SAD = 100 cm", s_sub))
    story.append(HRFlowable(width="100%", thickness=1.5, color=VERDE))

    # Dados do Paciente
    story.append(Paragraph("Identificação do Paciente", s_sec))
    t_pac = Table([
        ["Paciente:", nome_paciente or "N/A", "Prontuário:", id_paciente or "N/A"],
        ["Plano:", nome_plano or "N/A", "Data do Cálculo:", data_calc.strftime("%d/%m/%Y")]
    ], colWidths=[2.5*cm, 7.5*cm, 3*cm, 4*cm])
    t_pac.setStyle(TableStyle([
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(t_pac)
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))

    # Tabela de Resultados
    story.append(Paragraph("Resultados Dosimétricos", s_sec))
    header = [["Campo", "Dose\n(cGy)", "Sc", "Sp", "TMR", "ISQF", "F.Filtro", "UM\nCalc.", "UM\nEcl.", "Desvio"]]
    rows = []
    for _, r in df_res.iterrows():
        d = r.get("Desvio (%)", 0)
        rows.append([
            str(r.get("Campo", "")), f"{r.get('DOSE (cGy)', 0):.1f}",
            f"{r.get('Sc', 0):.4f}", f"{r.get('Sp', 0):.4f}", f"{r.get('TMR', 0):.4f}",
            f"{r.get('ISQF', 0):.4f}", f"{r.get('Fator Filtro', 1.0):.3f}",
            f"{r.get('UM Calculada', 0):.1f}", f"{r.get('UM (Eclipse)', 0):.0f}", f"{d:+.1f}%"
        ])

    cw = [2.5*cm, 1.6*cm, 1.4*cm, 1.4*cm, 1.4*cm, 1.4*cm, 1.6*cm, 1.8*cm, 1.8*cm, 1.8*cm]
    t_res = Table(header + rows, colWidths=cw, repeatRows=1)
    
    # Estilização da tabela de resultados
    estilo_tabela = [
        ("BACKGROUND", (0,0), (-1,0), AZUL),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 6)
    ]
    
    # Coloração de desvios no PDF
    for i, r in enumerate(df_res.itertuples(), start=1):
        try: d = float(df_res.iloc[i-1]["Desvio (%)"])
        except: d = 0
        if abs(d) <= 2: estilo_tabela.append(("TEXTCOLOR", (-1, i), (-1, i), colors.green))
        elif abs(d) <= 5: estilo_tabela.append(("TEXTCOLOR", (-1, i), (-1, i), colors.darkgoldenrod))
        else: 
            estilo_tabela.append(("TEXTCOLOR", (-1, i), (-1, i), colors.red))
            estilo_tabela.append(("FONTNAME", (-1, i), (-1, i), "Helvetica-Bold"))
            
    t_res.setStyle(TableStyle(estilo_tabela))
    story.append(t_res)

    # Assinaturas
    story.append(Spacer(1, 30))
    t_ass = Table([
        ["___________________________________", "", "___________________________________"],
        ["Físico Médico Responsável", "", "Data da Revisão"]
    ], colWidths=[7.5*cm, 2*cm, 7.5*cm])
    t_ass.setStyle(TableStyle([
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (-1,-1), colors.dimgrey)
    ]))
    story.append(t_ass)

    doc.build(story)
    buffer.seek(0)
    return buffer

# ══════════════════════════════════════════════════════════════════════════════
# INTERFACE PRINCIPAL (STREAMLIT)
# ══════════════════════════════════════════════════════════════════════════════

st.title("☢️ Verificação Independente de UM (3D)")
st.write("Sistema limpo e rápido para conferência de Unidades Monitoras do Eclipse.")
st.divider()

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configurações Gerais")
    dose_ref = st.number_input("Taxa de Dose (cGy/UM)", value=1.000, step=0.01, format="%.3f")
    
    st.subheader("Filtros / Bandejas")
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

# --- FLUXO PRINCIPAL ---
tab1, tab2, tab3 = st.tabs(["1. Máquina (Sc, Sp, TMR)", "2. Dados do Paciente", "3. Cálculos e Relatório"])

# ABA 1: MÁQUINA
with tab1:
    st.subheader("Carregar Tabela da Máquina")
    fonte = st.radio("Selecione a fonte dos dados:", ("Usar padrão do GitHub", "Fazer upload do TXT manual"))
    
    if fonte == "Usar padrão do GitHub":
        url = "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/refs/heads/main/clinac_fac_tmr.txt"
        try:
            with urllib.request.urlopen(url) as r:
                st.session_state["conteudo_maquina"] = r.read().decode("utf-8")
            st.success("Tabelas da máquina carregadas automaticamente com sucesso!")
        except Exception:
            st.error("Erro ao conectar no GitHub. Faça o upload manual.")
    else:
        arq = st.file_uploader("Arquivo TXT", type=["txt"])
        if arq:
            st.session_state["conteudo_maquina"] = arq.getvalue().decode("utf-8")
            st.success("Arquivo TXT processado!")

conteudo_maquina = st.session_state.get("conteudo_maquina")

# ABA 2: DADOS DO PACIENTE
with tab2:
    st.subheader("Extrair Planejamento")
    metodo = st.radio("Método:", ("Upload PDF do Eclipse", "Digitação Manual"), horizontal=True)

    df_paciente = pd.DataFrame()
    nome_plano = "Plano Manual"

    if metodo == "Upload PDF do Eclipse":
        pdfs = st.file_uploader("Selecione o(s) relatório(s) em PDF", type=["pdf"], accept_multiple_files=True)
        if pdfs:
            with st.spinner("Extraindo dados e lendo informações do paciente..."):
                dfs_extraidos = []
                for p in pdfs:
                    dados = extrair_dados_rt(p)
                    dfs_extraidos.append(dados["df"])
                    # Salva nome e ID se encontrar
                    if dados["nome"]: st.session_state["nome_paciente"] = dados["nome"]
                    if dados["id"]: st.session_state["id_paciente"] = dados["id"]
                    
                df_paciente = pd.concat(dfs_extraidos, ignore_index=True)
                nome_plano = df_paciente["Plano"].iloc[0] if not df_paciente.empty else ""
                
            st.success("Dados extraídos com sucesso!")
    else:
        df_paciente = pd.DataFrame([{
            "Plano": "Plano Manual", "Campo": "Campo 1", "X": 10.0, "Y": 10.0,
            "Fsx (cm)": 10.0, "Fsy (cm)": 10.0, "FILTRO": "Nenhum",
            "UM (Eclipse)": 100.0, "DOSE (cGy)": 100.0, "SSD": 100.0, "Prof.": 5.0, "Prof. Ef.": 5.0
        }])

    if not df_paciente.empty:
        # Mostra os dados do paciente capturados para conferência
        col_nome, col_id, col_data = st.columns(3)
        nome_paciente = col_nome.text_input("Nome do Paciente", value=st.session_state["nome_paciente"])
        id_paciente = col_id.text_input("ID/Prontuário", value=st.session_state["id_paciente"])
        data_calc = col_data.date_input("Data do Cálculo", value=date.today())

        st.caption("Verifique e edite os parâmetros da tabela abaixo, se necessário:")
        df_edit = st.data_editor(df_paciente, num_rows="dynamic", use_container_width=True)

# ABA 3: CÁLCULOS E RESULTADOS
with tab3:
    if not conteudo_maquina:
        st.warning("⚠️ Volte à Aba 1 e carregue os dados da máquina primeiro.")
    elif df_paciente.empty:
        st.warning("⚠️ Volte à Aba 2 e extraia os dados do planejamento.")
    else:
        campos_m, sc_m, sp_m, prof_m, tmr_m, dmax = carregar_tabelas_maquina(conteudo_maquina)
        interp_tmr = RegularGridInterpolator((prof_m, campos_m), tmr_m, bounds_error=False, fill_value=None)

        st.success(f"Cálculo processado com base no d_max = {dmax} cm")

        # Processamento matemático
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
                "Campo": row["Campo"], "DOSE (cGy)": row["DOSE (cGy)"],
                "Sc": sc_v, "Sp": sp_v, "TMR": tmr_v, "ISQF": isqf,
                "Fator Filtro": ff, "UM Calculada": um_c, "UM (Eclipse)": row["UM (Eclipse)"],
                "Desvio (%)": dev
            })

        df_res = pd.DataFrame(resultados)

        # Função de formatação nativa do Pandas Styler
        def highlight_desvio(val):
            try:
                if abs(val) <= 2.0: return 'color: #059669; font-weight: bold; background-color: #d1fae5;'
                elif abs(val) <= 5.0: return 'color: #d97706; font-weight: bold; background-color: #fef3c7;'
                else: return 'color: #dc2626; font-weight: bold; background-color: #fee2e2;'
            except: return ''

        # Formatação das casas decimais na exibição
        styled_df = df_res.style.format({
            "DOSE (cGy)": "{:.1f}", "Sc": "{:.4f}", "Sp": "{:.4f}", 
            "TMR": "{:.4f}", "ISQF": "{:.4f}", "Fator Filtro": "{:.3f}", 
            "UM Calculada": "{:.1f}", "UM (Eclipse)": "{:.0f}", "Desvio (%)": "{:+.2f}%"
        }).map(highlight_desvio, subset=["Desvio (%)"])

        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("📄 Exportar Ficha")
        
        pdf_buf = gerar_pdf(df_res, nome_paciente, id_paciente, nome_plano, data_calc, logo_bytes, instituicao)
        
        col_btn, col_prev = st.columns([1, 3])
        with col_btn:
            nome_arq = f"verificacao_{id_paciente or 'paciente'}.pdf"
            st.download_button(
                label="⬇️ Baixar Relatório (PDF)",
                data=pdf_buf.getvalue(),
                file_name=nome_arq,
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
            
        with col_prev:
            with st.expander("Pré-visualizar PDF gerado na tela", expanded=True):
                # Utiliza Iframe nativo para ler o próprio PDF gerado (Sem HTML Falso)
                b64_pdf = base64.b64encode(pdf_buf.getvalue()).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="600" style="border: none; border-radius: 8px;"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
