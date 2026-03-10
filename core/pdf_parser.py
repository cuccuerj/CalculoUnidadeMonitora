
import pdfplumber
import re
import pandas as pd

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
