import pdfplumber
import re
import pandas as pd


def extrair_dados_rt(pdf_file, mu_threshold=50):
    """
    Parser robusto para relatórios Eclipse (External Beam Planning).

    Melhorias em relação à versão anterior:
      - Usa os nomes reais dos campos do relatório (ex: "TG INT", "LOC ANT")
        em vez de assumir numeração "Campo 1, Campo 2...".
      - Parsing por seções: identifica cabeçalhos como "Energia", "MU", "Dose",
        "SSD", etc. e extrai os valores linha a linha.
      - Filtra automaticamente campos de setup ("Setup field") e campos com
        UM abaixo do limiar configurável (mu_threshold).
      - Detecta Aparelho/Energia tanto em português quanto em inglês.

    Parâmetros
    ----------
    pdf_file : str ou file-like
        Caminho ou objeto de arquivo do PDF do Eclipse.
    mu_threshold : float
        Limiar mínimo de UM para incluir um campo nos resultados.
        Campos com UM < mu_threshold são descartados. Default: 50.

    Retorna
    -------
    dict com chaves:
        "df"   : pd.DataFrame com os dados paramétricos dos campos aceitos.
        "nome" : str — nome do paciente.
        "id"   : str — matrícula / ID do paciente.
    """
    texto_completo = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto_completo += (page.extract_text() or "") + "\n"

    # ══════════════════════════════════════════════════════════════════════
    # 1. DADOS DO PACIENTE E PLANO
    # ══════════════════════════════════════════════════════════════════════
    match_nome = re.search(r"Nome do Paciente:\s*(.+)", texto_completo, re.IGNORECASE)
    nome_pac = match_nome.group(1).strip() if match_nome else ""

    match_id = re.search(r"(?:Matricula|ID|Patient ID):\s*(.+)", texto_completo, re.IGNORECASE)
    id_pac = match_id.group(1).strip() if match_id else ""

    match_plano = re.search(r"(?:Plano|Plan):\s*(.+)", texto_completo, re.IGNORECASE)
    nome_plano = match_plano.group(1).strip() if match_plano else ""

    # ══════════════════════════════════════════════════════════════════════
    # 2. APARELHO E ENERGIA (detecção PT + EN)
    # ══════════════════════════════════════════════════════════════════════
    aparelho_default = "Clinac"
    energia_default = "6X"
    match_machine = re.search(
        r"(?:Unidade de tratamento|Treatment unit):\s*([^,]+),\s*(?:energia|energy):\s*(\S+)",
        texto_completo, re.IGNORECASE,
    )
    if match_machine:
        aparelho_default = match_machine.group(1).strip()
        energia_default = match_machine.group(2).strip()

    # ══════════════════════════════════════════════════════════════════════
    # 3. PARSING POR SEÇÕES
    # ══════════════════════════════════════════════════════════════════════
    lines = texto_completo.split("\n")

    # Cabeçalhos reconhecidos (PT e EN). A ordem importa para evitar
    # que "Profundidade" capture antes de "Profundidade Efetiva".
    SECTION_HEADERS = [
        "Energia", "Energy",
        "Tamanho do Campo Aberto X", "Open Field Size X",
        "Tamanho do Campo Aberto Y", "Open Field Size Y",
        "Jaw Y1", "Jaw Y2", "Jaw X1", "Jaw X2",
        "Filtro", "Filter",
        "MU",
        "Dose",
        "SSD",
        "Profundidade Efetiva", "Effective Depth",
        "Profundidade", "Depth",
    ]

    current_section = None
    section_data: dict[str, list[str]] = {}

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Verifica se a linha é um cabeçalho de seção
        matched_header = None
        for h in SECTION_HEADERS:
            if stripped == h:
                matched_header = h
                break

        if matched_header:
            current_section = matched_header
            section_data.setdefault(current_section, [])
            continue

        # Linhas "Campo ..." dentro de uma seção ativa
        if current_section and (stripped.startswith("Campo ") or stripped.startswith("Field ")):
            section_data[current_section].append(stripped)
        elif current_section and stripped.startswith(("Informações", "Information")):
            current_section = None  # fim das seções paramétricas

    # ══════════════════════════════════════════════════════════════════════
    # 4. DESCOBRIR NOMES DOS CAMPOS (seção "Energia")
    # ══════════════════════════════════════════════════════════════════════
    field_names: list[str] = []
    field_energies: dict[str, str] = {}

    energia_key = "Energia" if "Energia" in section_data else "Energy"
    for line in section_data.get(energia_key, []):
        m = re.match(
            r"(?:Campo|Field)\s+(.+?)\s+([\dXx]+(?:MV|MeV|X|E)?)\s*$",
            line.strip(), re.IGNORECASE,
        )
        if m:
            name = m.group(1).strip()
            energy = m.group(2).strip()
            field_names.append(name)
            field_energies[name] = energy

    if not field_names:
        return {"df": pd.DataFrame(), "nome": nome_pac, "id": id_pac}

    # ══════════════════════════════════════════════════════════════════════
    # 5. FUNÇÕES AUXILIARES
    # ══════════════════════════════════════════════════════════════════════
    def _extract_value_for_field(line: str, field_name: str):
        """Retorna a parte do valor após 'Campo <field_name> <valor> [unidade]'."""
        pattern = rf"(?:Campo|Field)\s+{re.escape(field_name)}\s+(.*?)$"
        m = re.match(pattern, line.strip())
        return m.group(1).strip() if m else None

    def _parse_numeric(val_str: str) -> float:
        """Extrai valor numérico de strings como '132 MU', '121.6 cGy', '+7.6 cm'."""
        if not val_str:
            return 0.0
        m = re.search(r"[+-]?([\d.]+)", val_str)
        return float(m.group(0)) if m else 0.0

    def _build_section_map(section_key: str) -> dict[str, str]:
        """Retorna {field_name: raw_value_string} para uma seção."""
        result = {}
        for line in section_data.get(section_key, []):
            # Testa cada nome de campo (mais longo primeiro para evitar match parcial)
            for fn in sorted(field_names, key=len, reverse=True):
                val = _extract_value_for_field(line, fn)
                if val is not None and fn not in result:
                    result[fn] = val
                    break
        return result

    def _build_jaw_map(section_key: str) -> dict[str, str]:
        """Parser especial para seções Jaw Y1/Y2.

        Linhas têm formato: 'Campo <n> Y1: +3.2 cm'
        Retorna {field_name: valor_numerico_string}.
        """
        result = {}
        for line in section_data.get(section_key, []):
            for fn in sorted(field_names, key=len, reverse=True):
                pattern = rf"(?:Campo|Field)\s+{re.escape(fn)}\s+(?:Y[12]|X[12]):\s*([+-]?[\d.]+)"
                m = re.match(pattern, line.strip())
                if m and fn not in result:
                    result[fn] = m.group(1).strip()
                    break
        return result

    # ══════════════════════════════════════════════════════════════════════
    # 6. MAPEAR VALORES POR SEÇÃO
    # ══════════════════════════════════════════════════════════════════════
    sec = {
        "X":      _build_section_map("Tamanho do Campo Aberto X") or _build_section_map("Open Field Size X"),
        "Y":      _build_section_map("Tamanho do Campo Aberto Y") or _build_section_map("Open Field Size Y"),
        "MU":     _build_section_map("MU"),
        "Dose":   _build_section_map("Dose"),
        "SSD":    _build_section_map("SSD"),
        "Prof":   _build_section_map("Profundidade") or _build_section_map("Depth"),
        "ProfEf": _build_section_map("Profundidade Efetiva") or _build_section_map("Effective Depth"),
        "Filtro": _build_section_map("Filtro") or _build_section_map("Filter"),
        "JawY1":  _build_jaw_map("Jaw Y1"),
        "JawY2":  _build_jaw_map("Jaw Y2"),
    }

    # ══════════════════════════════════════════════════════════════════════
    # 7. Fsx / Fsy POR BLOCO DE INFORMAÇÕES (não sequencial)
    # ══════════════════════════════════════════════════════════════════════
    # Cada campo tem um bloco "Campo <n>\n---\nInformações: ...\n---"
    # na seção "Informações do Campo". Precisamos associar o fsx/fsy
    # correto a cada campo. Campos com EDW (cunha dinâmica) não têm
    # dados de fluência total — nesse caso, usamos X, Y do colimador.

    padrao_fs = (
        r"(?:fluência total|total fluence).{0,100}?"
        r"fsx\s*=\s*([\d.]+)\s*mm"
        r"(?:.{0,50}?fsy\s*=\s*([\d.]+)\s*mm)?"
    )

    field_fluence: dict[str, tuple[float, float]] = {}

    # Isolar a seção de informações (após "Informações do Campo")
    info_start = re.search(
        r"(?:Informações do Campo|Field Information)", texto_completo, re.IGNORECASE
    )
    info_text = texto_completo[info_start.start():] if info_start else ""

    if info_text:
        # Cada bloco: "Campo <n>\n---\n<conteúdo>\n---"
        block_pattern = r"^(?:Campo|Field)\s+(.+?)\n-{3,}\n(.*?)(?=\n-{3,})"
        for m in re.finditer(block_pattern, info_text, re.MULTILINE | re.DOTALL):
            block_name = m.group(1).strip()
            block_content = m.group(2)

            # Identificar a qual campo pertence
            matched_fn = None
            for fn in sorted(field_names, key=len, reverse=True):
                if block_name == fn:
                    matched_fn = fn
                    break
            if not matched_fn:
                continue

            # Procurar fsx/fsy neste bloco
            fs_match = re.search(padrao_fs, block_content, re.IGNORECASE | re.DOTALL)
            if fs_match:
                fsx_mm = float(fs_match.group(1))
                fsy_mm = float(fs_match.group(2) or fs_match.group(1))
                field_fluence[matched_fn] = (fsx_mm / 10.0, fsy_mm / 10.0)

    # ══════════════════════════════════════════════════════════════════════
    # 8. MONTAR DataFrame FINAL (com filtro de threshold)
    # ══════════════════════════════════════════════════════════════════════
    dados_campos = {}

    for fn in field_names:
        mu_str = sec["MU"].get(fn, "")

        # Ignorar campos de setup
        if "setup" in mu_str.lower() or not mu_str:
            continue

        mu_val = _parse_numeric(mu_str)

        # Aplicar threshold de UM
        if mu_val < mu_threshold:
            continue

        # Filtro/wedge
        filtro_raw = sec["Filtro"].get(fn, "-")
        filtro = "Nenhum" if (not filtro_raw or filtro_raw == "-") else filtro_raw

        # Fsx/Fsy: usar dados de fluência se disponíveis,
        # senão fallback para tamanho do colimador (X, Y).
        # Isso é o correto para campos com EDW (campo aberto, sem MLC).
        x_val = _parse_numeric(sec["X"].get(fn, ""))
        y_val = _parse_numeric(sec["Y"].get(fn, ""))

        if fn in field_fluence:
            fsx, fsy = field_fluence[fn]
        else:
            # Fallback: colimador = fantoma (campo aberto / EDW)
            fsx, fsy = x_val, y_val

        dados_campos[fn] = {
            "Plano": nome_plano,
            "Campo": fn,
            "Aparelho": aparelho_default,
            "Energia": field_energies.get(fn, energia_default),
            "X": x_val,
            "Y": y_val,
            "Fsx (cm)": fsx,
            "Fsy (cm)": fsy,
            "Jaw Y1": _parse_numeric(sec["JawY1"].get(fn, "")),
            "Jaw Y2": _parse_numeric(sec["JawY2"].get(fn, "")),
            "FILTRO": filtro,
            "OAR": 1.000,
            "UM (Eclipse)": mu_val,
            "DOSE (cGy)": _parse_numeric(sec["Dose"].get(fn, "")),
            "SSD": _parse_numeric(sec["SSD"].get(fn, "")),
            "Prof.": _parse_numeric(sec["Prof"].get(fn, "")),
            "Prof. Ef.": _parse_numeric(sec["ProfEf"].get(fn, "")),
        }

    df = pd.DataFrame(dados_campos.values()) if dados_campos else pd.DataFrame()
    return {"df": df, "nome": nome_pac, "id": id_pac}
