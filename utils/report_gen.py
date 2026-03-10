
import io
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage
from reportlab.lib.enums import TA_CENTER, TA_LEFT

def gerar_pdf_transposto(df_res, nome_paciente, id_paciente, nome_plano, data_calc, dose_ref, SAD=100.0, logo_bytes=None, instituicao=""):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=1.2*cm, rightMargin=1.2*cm, topMargin=1.2*cm, bottomMargin=1.2*cm)
    styles = getSampleStyleSheet()
    VERDE = colors.HexColor("#00c896")
    AZUL = colors.HexColor("#005088")
    
    s_tit  = ParagraphStyle("tit", parent=styles["Normal"], fontSize=14, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=2, textColor=AZUL)
    s_sub  = ParagraphStyle("sub", parent=styles["Normal"], fontSize=9, alignment=TA_CENTER, spaceAfter=8, textColor=colors.gray)
    s_sec  = ParagraphStyle("sec", parent=styles["Normal"], fontSize=11, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4, textColor=AZUL)
    
    story = []

    if logo_bytes:
        try:
            story.append(RLImage(io.BytesIO(logo_bytes), width=4*cm, height=1.6*cm, kind='proportional'))
            story.append(Spacer(1, 4))
        except: pass
    
    if instituicao:
        story.append(Paragraph(instituicao, ParagraphStyle("inst", parent=styles["Normal"], fontSize=10, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4)))

    story.append(Paragraph("Verificação Independente de Unidades Monitor", s_tit))
    info_fixa = f"Relatório Paramétrico Completo &nbsp;&nbsp;|&nbsp;&nbsp; Fator de Calibração: {dose_ref:.3f} cGy/UM &nbsp;&nbsp;|&nbsp;&nbsp; SAD: {SAD:.1f} cm"
    story.append(Paragraph(info_fixa, s_sub))
    story.append(HRFlowable(width="100%", thickness=1.5, color=VERDE))
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

    parametros = [
        ("Aparelho", lambda r: str(r["Aparelho"])),
        ("Energia (MV)", lambda r: str(r["Energia"])),
        ("Tamanho do Campo x (cm)", lambda r: f"{r['X']:.1f}"),
        ("Tamanho do Campo y (cm)", lambda r: f"{r['Y']:.1f}"),
        ("Campo Equivalente (cm)", lambda r: f"{r['EqSq Colimador']:.2f}"),
        ("Campo Colimado (cm)", lambda r: f"{r['EqSq Fantoma']:.2f}"),
        ("Distância Fonte Superfície (cm)", lambda r: f"{r['SSD']:.1f}"),
        ("Dose (cGy)", lambda r: f"{r['DOSE (cGy)']:.1f}"),
        ("Profundidade (cm)", lambda r: f"{r['Prof.']:.2f}"),
        ("Profundidade Efetiva (cm)", lambda r: f"{r['Prof. Ef.']:.2f}"),
        ("TPR/TMR", lambda r: f"{r['TMR']:.4f}"),
        ("Sc", lambda r: f"{r['Sc']:.4f}"),
        ("Sp", lambda r: f"{r['Sp']:.4f}"),
        ("Fator Filtro Dinâmico", lambda r: f"{r['Fator Filtro']:.3f}"),
        ("Fator OAR", lambda r: f"{r['OAR']:.3f}"),
        ("Fator Distância", lambda r: f"{r['ISQF']:.4f}"),
        ("UM Calculada Manualmente", lambda r: f"{r['UM Calculada']:.1f}"),
        ("UM Calculada pelo Eclipse", lambda r: f"{r['UM (Eclipse)']:.0f}"),
        ("Concordância cálculo/Eclipse (%)", lambda r: f"{r['Desvio_num']:+.2f}%")
    ]

    header = ["Parâmetro"] + [str(r["Campo"]) for _, r in df_res.iterrows()]
    data = [header]
    
    for nome_param, func in parametros:
        linha = [nome_param] + [func(row) for _, row in df_res.iterrows()]
        data.append(linha)

    largura_total_util = 27.3 * cm 
    largura_param = 6.5 * cm
    num_campos = max(1, len(df_res))
    largura_campo = (largura_total_util - largura_param) / num_campos
    
    t_res = Table(data, colWidths=[largura_param] + [largura_campo]*num_campos, repeatRows=1)
    
    estilo_tabela = [
        ("BACKGROUND", (0,0), (-1,0), AZUL), 
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("ALIGN", (0,0), (0,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"), 
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("FONTSIZE", (0,0), (-1,-1), 7.5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3)
    ]
    
    for i in range(1, len(data)):
        if i % 2 == 0:
            estilo_tabela.append(("BACKGROUND", (0,i), (-1,i), colors.whitesmoke))

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
