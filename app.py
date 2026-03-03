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
from reportlab.lib.pagesizes import A4, landscape
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

if "nome_paciente" not in st.session_state: st.session_state["nome_paciente"] = ""
if "id_paciente" not in st.session_state: st.session_state["id_paciente"] = ""

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

    # Extração de Paciente e Plano
    match_nome = re.search(r"Nome do Paciente:\s*(.+)", texto_completo, re.IGNORECASE)
    nome_pac = match_nome.group(1).strip() if match_nome else ""

    match_id = re.search(r"(?:Matricula|ID|Patient ID):\s*(.+)", texto_completo, re.IGNORECASE)
    id_pac = match_id.group(1).strip() if match_id else ""

    match_plano = re.search(r"(?:Plano|Plan):\s*(.+)", texto_completo, re.IGNORECASE)
    nome_plano = match_plano.group(1).strip() if match_plano else pdf_file.name

    # Extração de Aparelho e Energia
    aparelho = "Clinac"
    energia = "6X"
    match_machine = re.search(r"Treatment unit:\s*([^,]+),\s*energy:\s*(.+)", texto_completo, re.IGNORECASE)
    if match_machine:
        aparelho = match_machine.group(1).strip()
        energia = match_machine.group(2).strip()

    campos_encontrados = sorted(list(set(re.findall(r'Campo (\d+)', texto_completo))))

    for c in campos_encontrados:
        dados_campos[c] = {
            "Plano": nome_plano, "Campo": f"Campo {c}", "Aparelho": aparelho, "Energia": energia,
            "X": 0.0, "Y": 0.0, "Fsx (cm)": 0.0, "Fsy (cm)": 0.0,
            "FILTRO": "Nenhum", "OAR": 1.000, "UM (Eclipse)": 0.0, "DOSE (cGy)": 0.0,
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

    return {"df": pd.DataFrame(dados_campos.values()), "nome": nome_pac, "id": id_pac}

@st.cache_data
def carregar_tabelas_maquina(conteudo_texto):
    linhas = conteudo_texto.split('\n')
    campos, sc, sp, profundidades, tmr_matriz = [], [], [], [], []

    for linha in linhas:
        partes = linha.strip().split('\t')
        if len(partes) < 2: partes = linha.strip().split()
        if not partes or len(partes) < 2: continue
            
        rotulo = partes[0].strip().lower()
        try: valores = [float(v.replace(',', '.')) for v in partes[1:] if v.strip()]
        except ValueError: continue
            
        if rotulo == 'campo':   campos = valores
        elif rotulo == 'sc':    sc = valores
        elif rotulo == 'sp':    sp = valores
        else:
            try:
                profundidades.append(float(rotulo.replace(',', '.')))
                tmr_matriz.append(valores)
            except ValueError: pass

    tmr_array  = np.array(tmr_matriz)
    prof_array = np.array(profundidades)
    dmax_auto  = 1.5
    if tmr_array.size > 0:
        idx = np.argmax(tmr_array[:, tmr_array.shape[1] // 2])
        dmax_auto = prof_array[idx]

    return np.array(campos), np.array(sc), np.array(sp), prof_array, tmr_array, dmax_auto

# ══════════════════════════════════════════════════════════════════════════════
# GERAÇÃO DE PDF (OTIMIZADO PARA CABER NUMA ÚNICA FOLHA A4)
# ══════════════════════════════════════════════════════════════════════════════
def gerar_pdf_transposto(df_res, nome_paciente, id_paciente, nome_plano, data_calc, dose_ref, logo_bytes=None, instituicao=""):
    buffer = io.BytesIO()
    # Margens reduzidas para maximizar o espaço útil
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=1.2*cm, rightMargin=1.2*cm, topMargin=1.2*cm, bottomMargin=1.2*cm)

    styles = getSampleStyleSheet()
    VERDE = colors.HexColor("#00c896")
    AZUL = colors.HexColor("#005088")
    
    s_tit  = ParagraphStyle("tit", parent=styles["Normal"], fontSize=14, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=2, textColor=AZUL)
    s_sub  = ParagraphStyle("sub", parent=styles["Normal"], fontSize=9, alignment=TA_CENTER, spaceAfter=8, textColor=colors.gray)
    s_sec  = ParagraphStyle("sec", parent=styles["Normal"], fontSize=11, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4, textColor=AZUL)
    
    story = []

    # Logo e Instituição
    if logo_bytes:
        try:
            story.append(RLImage(io.BytesIO(logo_bytes), width=4*cm, height=1.6*cm, kind='proportional'))
            story.append(Spacer(1, 4))
        except: pass
    
    if instituicao:
        story.append(Paragraph(instituicao, ParagraphStyle("inst", parent=styles["Normal"], fontSize=10, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4)))

    story.append(Paragraph("Verificação da Unidade Monitora", s_tit))
    #story.append(Paragraph("Relatório Paramétrico Completo", s_sub))
    story.append(HRFlowable(width="100%", thickness=1.5, color=AZUL))

    # Dados do Paciente (Otimizado verticalmente)
    #story.append(Paragraph("Identificação", s_sec))
    t_pac = Table([
        ["Paciente:", nome_paciente or "N/A", "Prontuário:", id_paciente or "N/A", "Data do Cálculo:", data_calc.strftime("%d/%m/%Y")],
        ["Plano:", nome_plano or "N/A", "", "", "", ""]
    ], colWidths=[2.2*cm, 9*cm, 2.2*cm, 5*cm, 3.2*cm, 4*cm])
    t_pac.setStyle(TableStyle([
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTNAME", (4,0), (4,-1), "Helvetica-Bold"),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 2),
    ]))
    story.append(t_pac)
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))

    #story.append(Paragraph("Tabela Dosimétrica (Transposta)", s_sec))

    # Mapeamento exato dos nomes solicitados
    parametros = [
        ("Aparelho", lambda r: str(r["Aparelho"])),
        ("Energia (MV)", lambda r: str(r["Energia"])),
        ("Tamanho do Campo x (cm)", lambda r: f"{r['X']:.1f}"),
        ("Tamanho do Campo y (cm)", lambda r: f"{r['Y']:.1f}"),
        ("Campo Equivalente (cm)", lambda r: f"{r['EqSq Colimador']:.2f}"),
        ("Campo Colimado (cm)", lambda r: f"{r['EqSq Fantoma']:.2f}"),
        ("Distância Fonte Superfície (cm)", lambda r: f"{r['SSD']:.1f}"),
        ("Distância Fonte Isocentro (cm)", lambda r: f"{SAD:.1f}"),
        ("Dose (cGy)", lambda r: f"{r['DOSE (cGy)']:.1f}"),
        ("Profundidade (cm)", lambda r: f"{r['Prof.']:.2f}"),
        ("Profundidade Efetiva (cm)", lambda r: f"{r['Prof. Ef.']:.2f}"),
        ("TPR/TMR", lambda r: f"{r['TMR']:.4f}"),
        ("Fator de Calibração (UM/cGy)", lambda r: f"{dose_ref:.3f}"),
        ("Sc", lambda r: f"{r['Sc']:.4f}"),
        ("Sp", lambda r: f"{r['Sp']:.4f}"),
        ("Fator Filtro Dinâmico", lambda r: f"{r['Fator Filtro']:.3f}"),
        ("Fator OAR", lambda r: f"{r['OAR']:.3f}"),
        ("Fator Distância", lambda r: f"{r['ISQF']:.4f}"),
        ("UM Calculada Manualmente", lambda r: f"{r['UM Calculada']:.1f}"),
        ("UM Calculada pelo Eclipse", lambda r: f"{r['UM (Eclipse)']:.0f}"),
        ("Concordância cálculo/Eclipse (%)", lambda r: f"{r['Desvio_num']:+.2f}%")
    ]

    # Construindo as linhas da tabela
    header = ["Parâmetro"] + [str(r["Campo"]) for _, r in df_res.iterrows()]
    data = [header]
    
    for nome_param, func in parametros:
        linha = [nome_param] + [func(row) for _, row in df_res.iterrows()]
        data.append(linha)

    # Cálculo da largura adaptativa precisa
    largura_total_util = 27.3 * cm # A4 Landscape 29.7cm - 2.4cm (Margens)
    largura_param = 6.5 * cm
    num_campos = max(1, len(df_res))
    largura_campo = (largura_total_util - largura_param) / num_campos
    
    t_res = Table(data, colWidths=[largura_param] + [largura_campo]*num_campos, repeatRows=1)
    
    estilo_tabela = [
        ("BACKGROUND", (0,0), (-1,0), AZUL), # Cabeçalho
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("ALIGN", (0,0), (0,-1), "LEFT"), # Coluna de parâmetros à esquerda
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"), # Parâmetros em negrito
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("FONTSIZE", (0,0), (-1,-1), 7.5), # Tamanho de letra compactado
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3)
    ]
    
    # Linhas zebradas para facilitar a leitura
    for i in range(1, len(data)):
        if i % 2 == 0:
            estilo_tabela.append(("BACKGROUND", (0,i), (-1,i), colors.whitesmoke))

    # Coloração da última linha (Concordância/Desvio)
    idx_desvio = len(data) - 1
    for col_idx, r in enumerate(df_res.itertuples(), start=1):
        d = float(r.Desvio_num)
        if abs(d) <= 2: estilo_tabela.append(("TEXTCOLOR", (col_idx, idx_desvio), (col_idx, idx_desvio), colors.green))
        elif abs(d) <= 5: estilo_tabela.append(("TEXTCOLOR", (col_idx, idx_desvio), (col_idx, idx_desvio), colors.darkgoldenrod))
        else: 
            estilo_tabela.append(("TEXTCOLOR", (col_idx, idx_desvio), (col_idx, idx_desvio), colors.red))
            estilo_tabela.append(("FONTNAME", (col_idx, idx_desvio), (col_idx, idx_desvio), "Helvetica-Bold"))
            
    t_res.setStyle(TableStyle(estilo_tabela))
    story.append(t_res)

    # Assinaturas no final (Otimizado)
    story.append(Spacer(1, 12))
    t_ass = Table([
        ["___________________________________", "", "___________________________________"],
        ["Físico Médico Responsável", "", "Data da Revisão"]
    ], colWidths=[7.0*cm, 5*cm, 7.0*cm])
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
st.write("Sistema de conferência com Relatório Paramétrico Transposto.")
st.divider()

# --- BARRA LATERAL ---
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

# --- FLUXO PRINCIPAL ---
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
            st.error("Erro ao conectar no GitHub. Faça o upload manual.")
    else:
        arq = st.file_uploader("Arquivo TXT", type=["txt"])
        if arq:
            st.session_state["conteudo_maquina"] = arq.getvalue().decode("utf-8")
            st.success("Arquivo TXT processado!")

conteudo_maquina = st.session_state.get("conteudo_maquina")

with tab2:
    st.subheader("Extrair Planejamento")
    metodo = st.radio("Método:", ("Upload PDF do Eclipse", "Digitação Manual"), horizontal=True)

    df_paciente = pd.DataFrame()
    nome_plano = "Plano Manual"

    if metodo == "Upload PDF do Eclipse":
        pdfs = st.file_uploader("Selecione o(s) relatório(s) em PDF", type=["pdf"], accept_multiple_files=True)
        if pdfs:
            with st.spinner("Lendo informações do paciente..."):
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
        id_paciente = col_id.text_input("ID/Prontuário", value=st.session_state["id_paciente"])
        data_calc = col_data.date_input("Data do Cálculo", value=date.today())

        st.caption("Verifique e edite os parâmetros extraídos abaixo (inclusive OAR, Aparelho e Energia):")
        df_edit = st.data_editor(df_paciente, num_rows="dynamic", use_container_width=True)

with tab3:
    if not conteudo_maquina:
        st.warning("⚠️ Volte à Aba 1 e carregue os dados da máquina primeiro.")
    elif df_paciente.empty:
        st.warning("⚠️ Volte à Aba 2 e extraia os dados do planejamento.")
    else:
        campos_m, sc_m, sp_m, prof_m, tmr_m, dmax = carregar_tabelas_maquina(conteudo_maquina)
        interp_tmr = RegularGridInterpolator((prof_m, campos_m), tmr_m, bounds_error=False, fill_value=None)

        resultados = []
        for _, row in df_edit.iterrows():
            eqsq_c = calcular_eqsq(row["X"], row["Y"])
            eqsq_f = calcular_eqsq(row["Fsx (cm)"], row["Fsy (cm)"])
            isqf   = calcular_fator_distancia(row["SSD"], row["Prof."], dmax=dmax)
            sc_v   = np.interp(eqsq_c, campos_m, sc_m)
            sp_v   = np.interp(eqsq_f, campos_m, sp_m)
            tmr_v  = float(interp_tmr((row["Prof. Ef."], eqsq_f))) if row["Prof. Ef."] > 0 and eqsq_f > 0 else 0.0
            ff     = dict_filtros.get(row["FILTRO"], 1.0)
            oar    = row.get("OAR", 1.0)
            
            denom  = dose_ref * sc_v * sp_v * tmr_v * isqf * ff * oar
            um_c   = row["DOSE (cGy)"] / denom if denom > 0 else 0.0
            dev    = ((um_c - row["UM (Eclipse)"]) / row["UM (Eclipse)"]) * 100 if row["UM (Eclipse)"] > 0 else 0.0
            
            # Dicionário com TODAS as informações requisitadas
            resultados.append({
                "Campo": row["Campo"],
                "Aparelho": row["Aparelho"],
                "Energia": row["Energia"],
                "X": row["X"], "Y": row["Y"],
                "EqSq Colimador": eqsq_c, "EqSq Fantoma": eqsq_f,
                "SSD": row["SSD"], "DOSE (cGy)": row["DOSE (cGy)"],
                "Prof.": row["Prof."], "Prof. Ef.": row["Prof. Ef."],
                "Sc": sc_v, "Sp": sp_v, "TMR": tmr_v, "ISQF": isqf,
                "Fator Filtro": ff, "OAR": oar,
                "UM Calculada": um_c, "UM (Eclipse)": row["UM (Eclipse)"],
                "Desvio_num": dev # Guardado como número para regras de cor
            })

        df_res = pd.DataFrame(resultados)

        st.success("Cálculo processado com sucesso! Veja a tabela detalhada abaixo e o PDF gerado.")

        # Tabela na tela (Também girada usando o recurso .T do Pandas!)
        st.subheader("Visualização na Tela (Girar Tabela)")
        df_display = df_res.copy().set_index("Campo").T
        st.dataframe(df_display, use_container_width=True)

        st.divider()
        st.subheader("📄 Relatório PDF Oficial")
        
        # O PDF agora é gerado na horizontal e transposto
        pdf_buf = gerar_pdf_transposto(df_res, nome_paciente, id_paciente, nome_plano, data_calc, dose_ref, logo_bytes, instituicao)
        
        col_btn, col_prev = st.columns([1, 4])
        with col_btn:
            nome_arq = f"verificacao_{id_paciente or 'paciente'}.pdf"
            st.download_button(
                label="⬇️ Baixar PDF",
                data=pdf_buf.getvalue(),
                file_name=nome_arq,
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
            
        with col_prev:
            with st.expander("Pré-visualizar PDF", expanded=True):
                b64_pdf = base64.b64encode(pdf_buf.getvalue()).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="600" style="border: none; border-radius: 8px;"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
