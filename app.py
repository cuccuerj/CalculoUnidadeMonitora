import streamlit as st
import numpy as np
from pathlib import Path
from datetime import date
import io, re

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER


# ══════════════════════════════════════════════════════════════════════════════
# 1. DADOS DOSIMÉTRICOS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data
def carregar_dados(caminho="clinac_fac_tmr.txt"):
    caminho = Path(caminho)
    if not caminho.exists():
        st.error(f"Arquivo não encontrado: `{caminho}`")
        st.stop()
    linhas = caminho.read_text(encoding="utf-8").strip().splitlines()
    campos  = [float(v) for v in linhas[0].split("\t")[1:]]
    sc_vals = [float(v) for v in linhas[1].split("\t")[1:]]
    sp_vals = [float(v) for v in linhas[2].split("\t")[1:]]
    profundidades, tmr_data = [], []
    for linha in linhas[4:]:
        partes = linha.split("\t")
        if not partes[0].strip():
            continue
        profundidades.append(float(partes[0]))
        tmr_data.append([float(v) for v in partes[1:]])
    return (
        np.array(campos), np.array(sc_vals), np.array(sp_vals),
        np.array(profundidades), np.array(tmr_data),
    )


# ══════════════════════════════════════════════════════════════════════════════
# 2. PARSER DO PDF DO ECLIPSE
# ══════════════════════════════════════════════════════════════════════════════

def parse_eclipse_pdf(pdf_bytes):
    """
    Lê um PDF de planejamento do Eclipse (Varian) e extrai:
    nome, id, e por campo: dose, SSD, profundidade efetiva, tamanho X e Y.
    Retorna dict com 'nome', 'id', 'campos' (lista).
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    texto  = "\n".join(page.extract_text() or "" for page in reader.pages)

    resultado = {}

    # Nome e matrícula
    m = re.search(r'Nome do Paciente:\s*(.+)', texto)
    resultado["nome"] = m.group(1).strip() if m else ""
    m = re.search(r'Matricula:\s*(\S+)', texto)
    resultado["id"]   = m.group(1).strip() if m else ""

    # Campos detectados pela linha de energia
    campos_nomes = re.findall(r'^(Campo \d+)\s+6X', texto, re.MULTILINE)
    if not campos_nomes:
        return None  # PDF não reconhecido

    def extrair_secao(label):
        """Extrai {campo: float} de uma seção com quebra simples de linha."""
        padrao = rf'{re.escape(label)}\n((?:Campo \d+.*\n?)+)'
        m = re.search(padrao, texto)
        vals = {}
        if m:
            for linha in m.group(1).splitlines():
                lm = re.match(r'(Campo \d+)\s+([\d.]+)', linha.strip())
                if lm:
                    vals[lm.group(1)] = float(lm.group(2))
        return vals

    def extrair_multipage(label):
        """Para seções que quebram entre páginas (ex: Profundidade Efetiva)."""
        idx = texto.find(label)
        if idx == -1:
            return {}
        vals = {}
        for linha in texto[idx:].splitlines()[1:]:
            lm = re.match(r'(Campo \d+)\s+([\d.]+)', linha.strip())
            if lm:
                vals[lm.group(1)] = float(lm.group(2))
            elif linha.strip() and not linha.strip().startswith("Campo") and vals:
                break
        return vals

    sx   = extrair_secao("Tamanho do Campo Aberto X")
    sy   = extrair_secao("Tamanho do Campo Aberto Y")
    dose = extrair_secao("Dose")
    ssd  = extrair_secao("SSD")
    prof = extrair_multipage("Profundidade Efetiva")

    campos_lista = []
    avisos = []
    for cn in campos_nomes:
        x = sx.get(cn); y = sy.get(cn)
        d = dose.get(cn); s = ssd.get(cn); p = prof.get(cn)
        if None in (x, y, d, s, p):
            avisos.append(f"{cn}: dados incompletos — preenchido parcialmente.")
            continue

        leq  = round(2*x*y / (x+y), 2)    # campo equivalente retangular
        lc   = round(np.sqrt(x*y), 2)      # campo colimador equivalente para Sc
        dist = round(s + p, 1)             # distância foco-ponto = SSD + prof_efetiva

        campos_lista.append({
            "nome": cn, "dose": d, "lc": lc, "leq": leq,
            "prof": p, "dist": dist,
        })

    resultado["campos"] = campos_lista
    resultado["avisos"] = avisos
    return resultado


# ══════════════════════════════════════════════════════════════════════════════
# 3. CÁLCULO DE MU
# ══════════════════════════════════════════════════════════════════════════════

def get_sc(campos, sc_vals, campo):
    return float(np.interp(campo, campos, sc_vals))

def get_sp(campos, sp_vals, campo):
    return float(np.interp(campo, campos, sp_vals))

def get_tmr(campos, profundidades, tmr_data, prof, campo):
    col_interp = np.array([
        np.interp(prof, profundidades, tmr_data[:, j])
        for j in range(len(campos))
    ])
    return float(np.interp(campo, campos, col_interp))

def calcular_mu(campos, sc_vals, sp_vals, profundidades, tmr_data,
                dose_cgy, campo_col, campo_eq, prof, dist, sad_ref=100.0, dr=1.0):
    sc  = get_sc(campos, sc_vals, campo_col)
    sp  = get_sp(campos, sp_vals, campo_eq)
    tmr = get_tmr(campos, profundidades, tmr_data, prof, campo_eq)
    fd  = (sad_ref / dist) ** 2
    denom = dr * sc * sp * tmr * fd
    mu = dose_cgy / denom
    return {
        "mu": mu, "sc": sc, "sp": sp, "tmr": tmr, "fd": fd,
        "denom": denom, "dose": dose_cgy, "dr": dr,
        "campo_col": campo_col, "campo_eq": campo_eq,
        "prof": prof, "dist": dist,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. GERAÇÃO DE PDF
# ══════════════════════════════════════════════════════════════════════════════

def gerar_pdf(nome_paciente, id_paciente, data_calculo, campos_lista, sad_ref):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2.5*cm,
    )

    styles = getSampleStyleSheet()
    AZUL = colors.HexColor("#1a73e8")
    s_titulo  = ParagraphStyle("titulo",  parent=styles["Normal"], fontSize=15, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=2)
    s_subtit  = ParagraphStyle("subtit",  parent=styles["Normal"], fontSize=9,  alignment=TA_CENTER, spaceAfter=10, textColor=colors.HexColor("#555555"))
    s_secao   = ParagraphStyle("secao",   parent=styles["Normal"], fontSize=11, fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4)
    s_formula = ParagraphStyle("formula", parent=styles["Normal"], fontSize=8.5, fontName="Courier", backColor=colors.HexColor("#F5F5F5"), leftIndent=8, rightIndent=8, spaceBefore=3, spaceAfter=3)
    s_label   = ParagraphStyle("label",   parent=styles["Normal"], fontSize=9,  fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=2)
    s_aviso   = ParagraphStyle("aviso",   parent=styles["Normal"], fontSize=7.5, textColor=colors.HexColor("#888888"), alignment=TA_CENTER, spaceBefore=12)

    story = []

    # Cabeçalho
    story.append(Paragraph("Ficha de Calculo Manual de Unidades Monitor", s_titulo))
    story.append(Paragraph("Radioterapia &nbsp;·&nbsp; Clinac 6 MV &nbsp;·&nbsp; Tecnica SAD", s_subtit))
    story.append(HRFlowable(width="100%", thickness=2, color=AZUL))
    story.append(Spacer(1, 8))

    # Dados do paciente
    story.append(Paragraph("Dados do Paciente", s_secao))
    t_pac = Table([
        ["Nome:", nome_paciente or "—",    "ID / Prontuario:", id_paciente or "—"],
        ["Data do Calculo:", data_calculo.strftime("%d/%m/%Y"), "SAD de referencia:", f"{sad_ref:.0f} cm"],
    ], colWidths=[3.2*cm, 7.3*cm, 3.8*cm, 3.2*cm])
    t_pac.setStyle(TableStyle([
        ("FONTNAME",      (0,0),(0,-1), "Helvetica-Bold"),
        ("FONTNAME",      (2,0),(2,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 9),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
    ]))
    story.append(t_pac)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC")))

    # Tabela resumo
    story.append(Paragraph("Resumo dos Campos", s_secao))
    header = [["Campo", "Dose\n(cGy)", "Lc\n(cm)", "Leq\n(cm)", "Prof.\n(cm)", "Dist.\n(cm)", "Sc", "Sp", "TMR", "FD", "UM\ncalc.", "UM\nEclipse"]]
    linhas_tab = []
    for i, c in enumerate(campos_lista):
        r = c["resultado"]
        mu_eclipse = c.get("mu_eclipse", "—")
        mu_eclipse_str = f"{mu_eclipse:.0f}" if isinstance(mu_eclipse, (int, float)) else "—"
        linhas_tab.append([
            c["nome"] or f"Campo {i+1}",
            f"{r['dose']:.1f}", f"{r['campo_col']:.2f}", f"{r['campo_eq']:.2f}",
            f"{r['prof']:.1f}", f"{r['dist']:.1f}",
            f"{r['sc']:.4f}", f"{r['sp']:.4f}", f"{r['tmr']:.4f}",
            f"{r['fd']:.4f}", f"{r['mu']:.1f}", mu_eclipse_str,
        ])

    t_res = Table(header + linhas_tab,
                  colWidths=[2.2*cm,1.4*cm,1.2*cm,1.2*cm,1.2*cm,1.2*cm,1.5*cm,1.5*cm,1.5*cm,1.5*cm,1.3*cm,1.3*cm],
                  repeatRows=1)
    t_res.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (-1,0),  AZUL),
        ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),  (-1,0),  7),
        ("ALIGN",         (0,0),  (-1,-1), "CENTER"),
        ("ALIGN",         (0,1),  (0,-1),  "LEFT"),
        ("FONTSIZE",      (0,1),  (-1,-1), 7.5),
        ("FONTNAME",      (-2,1), (-1,-1), "Helvetica-Bold"),
        ("GRID",          (0,0),  (-1,-1), 0.4, colors.HexColor("#CCCCCC")),
        ("TOPPADDING",    (0,0),  (-1,-1), 3),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 3),
        *[("BACKGROUND",  (0,i),  (-1,i),  colors.HexColor("#EEF4FF"))
          for i in range(2, len(linhas_tab)+1, 2)],
    ]))
    story.append(t_res)

    # Detalhamento
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC")))
    story.append(Paragraph("Detalhamento dos Calculos", s_secao))

    for i, c in enumerate(campos_lista):
        r = c["resultado"]
        nome = c["nome"] or f"Campo {i+1}"
        mu_eclipse = c.get("mu_eclipse")
        diff_str = ""
        if isinstance(mu_eclipse, (int, float)):
            diff = r["mu"] - mu_eclipse
            diff_str = f"  |  Eclipse: {mu_eclipse:.0f} MU  |  Diferenca: {diff:+.1f} MU ({100*diff/mu_eclipse:+.1f}%)"
        story.append(Paragraph(f"Campo {i+1}: {nome}", s_label))
        story.append(Paragraph(
            f"UM = Dose / (DR x Sc x Sp x TMR x FD)\n"
            f"UM = {r['dose']:.1f} / ({r['dr']:.2f} x {r['sc']:.4f} x {r['sp']:.4f} x {r['tmr']:.4f} x {r['fd']:.4f})\n"
            f"UM = {r['dose']:.1f} / {r['denom']:.6f}  =  {r['mu']:.2f} MU{diff_str}",
            s_formula
        ))

    # Rodapé
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC")))
    story.append(Paragraph(
        "Ferramenta de auxilio ao calculo manual. Deve ser verificado e assinado pelo fisico medico responsavel antes do uso clinico.",
        s_aviso
    ))
    t_ass = Table(
        [["Calculado por: ______________________", "Data: ___/___/______", "Verificado por: ______________________"]],
        colWidths=[6.2*cm, 4*cm, 7.3*cm]
    )
    t_ass.setStyle(TableStyle([
        ("FONTSIZE",     (0,0),(-1,-1), 8),
        ("TOPPADDING",   (0,0),(-1,-1), 14),
        ("ALIGN",        (1,0),(1,0),   "CENTER"),
    ]))
    story.append(t_ass)

    doc.build(story)
    buffer.seek(0)
    return buffer


# ══════════════════════════════════════════════════════════════════════════════
# 5. INTERFACE
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="Cálculo de UM", page_icon="☢️", layout="wide")
st.title("☢️ Cálculo Manual de Unidades Monitor")

# Carrega dados dosimétricos
campos_arr, sc_arr, sp_arr, prof_arr, tmr_arr = carregar_dados("clinac_fac_tmr.txt")
SAD_REF = 100.0

st.caption(
    f"Clinac 6 MV · SAD = {SAD_REF:.0f} cm · "
    f"Campos: {campos_arr[0]:.0f}–{campos_arr[-1]:.0f} cm · "
    f"Profundidades: {prof_arr[0]:.1f}–{prof_arr[-1]:.1f} cm"
)

# ── Session state ──────────────────────────────────────────────────────────────
if "n_campos" not in st.session_state:
    st.session_state.n_campos = 1
if "prefill" not in st.session_state:
    st.session_state.prefill = {}   # {i: {nome, dose, lc, leq, prof, dist, mu_eclipse}}

# ── Importar PDF do Eclipse ────────────────────────────────────────────────────
st.subheader("Importar do Eclipse (opcional)")

with st.expander("📂 Carregar PDF do planejamento", expanded=True):
    pdf_file = st.file_uploader(
        "Selecione o PDF exportado do Eclipse",
        type=["pdf"],
        help="O app extrai automaticamente: nome, ID, dose, SSD, profundidade efetiva e tamanho de campo."
    )

    if pdf_file is not None:
        dados = parse_eclipse_pdf(pdf_file.read())

        if dados is None:
            st.error("PDF não reconhecido. Verifique se é um relatório do Eclipse com energia 6X.")
        else:
            if dados.get("avisos"):
                for av in dados["avisos"]:
                    st.warning(av)

            n = len(dados["campos"])
            st.success(f"✅ PDF lido: **{dados['nome']}** · Matrícula: **{dados['id']}** · {n} campo(s) detectado(s)")

            col_info, col_btn = st.columns([4, 1])
            with col_info:
                prev_rows = []
                for c in dados["campos"]:
                    prev_rows.append({
                        "Campo": c["nome"], "Dose (cGy)": c["dose"],
                        "Lc (cm)": c["lc"], "Leq (cm)": c["leq"],
                        "Prof. ef. (cm)": c["prof"], "Dist. (cm)": c["dist"],
                    })
                st.dataframe(prev_rows, use_container_width=True, hide_index=True)

            with col_btn:
                if st.button("⬇️ Preencher campos", type="primary", use_container_width=True):
                    st.session_state.n_campos = n
                    st.session_state.prefill  = {i: c for i, c in enumerate(dados["campos"])}
                    st.session_state["nome_pac"] = dados["nome"]
                    st.session_state["id_pac"]   = dados["id"]
                    st.rerun()

st.divider()

# ── Dados do paciente ──────────────────────────────────────────────────────────
st.subheader("Dados do Paciente")
cp1, cp2, cp3 = st.columns([3, 2, 2])
with cp1:
    nome_paciente = st.text_input("Nome do Paciente",
        value=st.session_state.get("nome_pac", ""),
        placeholder="Ex.: João da Silva")
with cp2:
    id_paciente = st.text_input("ID / Prontuário",
        value=st.session_state.get("id_pac", ""),
        placeholder="Ex.: 12345")
with cp3:
    data_calculo = st.date_input("Data do Cálculo", value=date.today())

st.divider()

# ── Campos de tratamento ───────────────────────────────────────────────────────
st.subheader("Campos de Tratamento")

resultados = []
pf = st.session_state.prefill   # atalho

for i in range(st.session_state.n_campos):
    p = pf.get(i, {})
    label = p.get("nome") or f"Campo {i+1}"

    with st.expander(label, expanded=True):
        cn, c1, c2, c3, c4, c5, c6 = st.columns([2, 1.4, 1.4, 1.4, 1.4, 1.5, 1.4])

        with cn:
            nome_campo = st.text_input("Nome", key=f"nome_{i}",
                value=p.get("nome", ""), placeholder="AP, PA, Lat D...")
        with c1:
            dose = st.number_input("Dose (cGy)", min_value=1.0, max_value=5000.0,
                value=float(p.get("dose", 200.0)), step=1.0, key=f"dose_{i}")
        with c2:
            lc_min = float(campos_arr[0]); lc_max = float(campos_arr[-1])
            lc_def = float(np.clip(p.get("lc", 10.0), lc_min, lc_max))
            campo_col = st.number_input("Lc (cm)", min_value=lc_min, max_value=lc_max,
                value=lc_def, step=0.5, key=f"lc_{i}", help="Campo colimador → Sc")
        with c3:
            leq_def = float(np.clip(p.get("leq", 10.0), lc_min, lc_max))
            campo_eq = st.number_input("Leq (cm)", min_value=lc_min, max_value=lc_max,
                value=leq_def, step=0.5, key=f"leq_{i}", help="Campo equivalente → Sp e TMR")
        with c4:
            prof_def = float(np.clip(p.get("prof", 5.0), float(prof_arr[0]), float(prof_arr[-1])))
            prof = st.number_input("Prof. ef. (cm)",
                min_value=float(prof_arr[0]), max_value=float(prof_arr[-1]),
                value=prof_def, step=0.5, key=f"prof_{i}")
        with c5:
            dist_def = float(p.get("dist", 100.0))
            dist = st.number_input("Dist. foco-ponto (cm)",
                min_value=50.0, max_value=200.0,
                value=dist_def, step=0.5, key=f"dist_{i}",
                help=f"FD = (SAD/{SAD_REF:.0f} / dist)². SSD + prof. efetiva.")
        with c6:
            dr = st.number_input("DR (cGy/UM)", min_value=0.5, max_value=2.0,
                value=1.0, step=0.01, key=f"dr_{i}")

        # Cálculo
        try:
            res = calcular_mu(
                campos_arr, sc_arr, sp_arr, prof_arr, tmr_arr,
                dose, campo_col, campo_eq, prof, dist, SAD_REF, dr
            )

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Sc",  f"{res['sc']:.4f}")
            m2.metric("Sp",  f"{res['sp']:.4f}")
            m3.metric("TMR", f"{res['tmr']:.4f}")
            m4.metric("FD",  f"{res['fd']:.4f}",
                      help=f"({SAD_REF:.0f}/{dist:.1f})² = {res['fd']:.4f}")

            mu_eclipse = p.get("mu_eclipse") or p.get("mu")
            if isinstance(mu_eclipse, (int, float)):
                diff = res["mu"] - mu_eclipse
                delta_str = f"{diff:+.1f} vs Eclipse ({mu_eclipse:.0f})"
                m5.metric("🎯 UM calculado", f"{res['mu']:.1f}", delta=delta_str,
                          delta_color="off")
            else:
                m5.metric("🎯 UM calculado", f"{res['mu']:.1f}")

            resultados.append({
                "nome": nome_campo, "resultado": res,
                "mu_eclipse": mu_eclipse if isinstance(mu_eclipse, (int,float)) else None,
            })

        except Exception as e:
            st.error(f"Erro no campo {i+1}: {e}")
            resultados.append(None)

# ── Botões adicionar / remover ─────────────────────────────────────────────────
ba, br, _ = st.columns([1, 1, 6])
with ba:
    if st.session_state.n_campos < 10:
        if st.button("➕ Adicionar campo"):
            st.session_state.n_campos += 1
            st.rerun()
    else:
        st.info("Máx. 10 campos.")
with br:
    if st.session_state.n_campos > 1:
        if st.button("➖ Remover último"):
            st.session_state.n_campos -= 1
            if (st.session_state.n_campos) in st.session_state.prefill:
                del st.session_state.prefill[st.session_state.n_campos]
            st.rerun()

st.divider()

# ── Exportar PDF ───────────────────────────────────────────────────────────────
st.subheader("Exportar")

campos_validos = [r for r in resultados if r is not None]

if campos_validos:
    col_btn, col_info = st.columns([2, 5])
    with col_btn:
        if st.button("📄 Gerar PDF", type="primary"):
            if not nome_paciente.strip():
                st.warning("Preencha o nome do paciente.")
            else:
                pdf = gerar_pdf(nome_paciente, id_paciente, data_calculo, campos_validos, SAD_REF)
                nome_arquivo = f"calculo_mu_{id_paciente or 'paciente'}_{data_calculo.strftime('%Y%m%d')}.pdf"
                st.download_button(
                    label="⬇️ Baixar PDF",
                    data=pdf, file_name=nome_arquivo,
                    mime="application/pdf", type="primary",
                )
    with col_info:
        st.caption(
            f"{len(campos_validos)} campo(s) calculado(s). "
            "O PDF inclui tabela resumo, fórmulas detalhadas e comparação com MU do Eclipse (quando disponível)."
        )
else:
    st.warning("Nenhum campo calculado com sucesso.")

# ── Info ───────────────────────────────────────────────────────────────────────
with st.expander("ℹ️ Fórmula, fatores e importação do Eclipse"):
    st.markdown(f"""
    **Fórmula:**  `UM = Dose (cGy) / (DR × Sc × Sp × TMR × FD)`

    | Fator | Descrição |
    |-------|-----------|
    | DR | Taxa de dose de referência (cGy/UM) |
    | Sc | Fator de colimador — campo colimador Lc = √(X·Y) |
    | Sp | Fator de espalhamento fantasma — campo equivalente Leq = 2·X·Y/(X+Y) |
    | TMR | Tissue Maximum Ratio interpolado (profundidade efetiva × Leq) |
    | **FD** | **Lei inverso do quadrado: (SAD_ref / dist)² = ({SAD_REF:.0f} / dist)²** |

    **Importação do PDF do Eclipse:**  
    O app lê automaticamente: nome do paciente, matrícula, dose por campo, SSD, profundidade efetiva e tamanho de campo X e Y.  
    Calcula: `dist = SSD + prof_efetiva`, `Lc = √(X·Y)`, `Leq = 2·X·Y/(X+Y)`.
    """)
