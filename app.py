import streamlit as st
import numpy as np
from pathlib import Path


# ── Carregar dados dosimétricos do arquivo ─────────────────────────────────────

@st.cache_data
def carregar_dados(caminho="clinac_fac_tmr.txt"):
    """
    Lê o arquivo de dados dosimétricos no formato TSV:
      Linha 1 : cabeçalho de campos (3, 3.5, ... 40)
      Linha 2 : Sc
      Linha 3 : Sp
      Linha 4 : "Prof." (vazio)
      Linhas 5+: profundidade \t TMR(campo_1) \t TMR(campo_2) ...
    """
    caminho = Path(caminho)
    if not caminho.exists():
        st.error(f"Arquivo não encontrado: `{caminho}`\n\nColoque o arquivo na pasta `dados/`.")
        st.stop()

    linhas = caminho.read_text(encoding="utf-8").strip().splitlines()

    campos      = [float(v) for v in linhas[0].split("\t")[1:]]
    sc_vals     = [float(v) for v in linhas[1].split("\t")[1:]]
    sp_vals     = [float(v) for v in linhas[2].split("\t")[1:]]

    profundidades, tmr_data = [], []
    for linha in linhas[4:]:          # pula linha "Prof."
        partes = linha.split("\t")
        if not partes[0].strip():
            continue
        profundidades.append(float(partes[0]))
        tmr_data.append([float(v) for v in partes[1:]])

    return (
        np.array(campos),
        np.array(sc_vals),
        np.array(sp_vals),
        np.array(profundidades),
        np.array(tmr_data),           # shape: (n_profundidades, n_campos)
    )


# ── Funções de interpolação ────────────────────────────────────────────────────

def get_sc(campos, sc_vals, campo):
    return float(np.interp(campo, campos, sc_vals))

def get_sp(campos, sp_vals, campo):
    return float(np.interp(campo, campos, sp_vals))

def get_tmr(campos, profundidades, tmr_data, prof, campo):
    # Bilinear: interpola profundidade em cada campo, depois interpola no campo
    coluna_interpolada = np.array([
        np.interp(prof, profundidades, tmr_data[:, j])
        for j in range(len(campos))
    ])
    return float(np.interp(campo, campos, coluna_interpolada))

def calcular_mu(campos, sc_vals, sp_vals, profundidades, tmr_data,
                dose_cgy, campo_col, campo_eq, prof, dr=1.0):
    sc  = get_sc(campos, sc_vals, campo_col)
    sp  = get_sp(campos, sp_vals, campo_eq)
    tmr = get_tmr(campos, profundidades, tmr_data, prof, campo_eq)
    denom = dr * sc * sp * tmr
    mu = dose_cgy / denom
    return mu, sc, sp, tmr, denom


# ── Interface Streamlit ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Cálculo Manual de UM",
    page_icon="☢️",
    layout="centered",
)

st.title("☢️ Cálculo Manual de Unidades Monitor")

# Carrega dados (cacheado — relê só quando o arquivo mudar)
campos, sc_vals, sp_vals, profundidades, tmr_data = carregar_dados("clinac_fac_tmr.txt")

st.caption(
    f"Dados: `dados/clinac_6mv.txt` · "
    f"Campos: {campos[0]:.0f}–{campos[-1]:.0f} cm · "
    f"Profundidades: {profundidades[0]:.1f}–{profundidades[-1]:.1f} cm · "
    f"SAD = 100 cm"
)

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Parâmetros do Campo")

    dose = st.number_input(
        "Dose prescrita (cGy)",
        min_value=1.0, max_value=5000.0,
        value=200.0, step=1.0,
    )
    campo_col = st.number_input(
        "Campo colimador — Lc (cm)",
        min_value=float(campos[0]), max_value=float(campos[-1]),
        value=10.0, step=0.5,
        help="Usado para calcular Sc",
    )
    campo_eq = st.number_input(
        "Campo equivalente — Leq (cm)",
        min_value=float(campos[0]), max_value=float(campos[-1]),
        value=10.0, step=0.5,
        help="Usado para calcular Sp e TMR. Para campo quadrado = Lc.",
    )
    prof = st.number_input(
        "Profundidade do ponto de cálculo (cm)",
        min_value=float(profundidades[0]), max_value=float(profundidades[-1]),
        value=5.0, step=0.5,
    )
    dr = st.number_input(
        "Taxa de dose de referência — DR (cGy/UM)",
        min_value=0.5, max_value=2.0,
        value=1.0, step=0.01,
        help="Tipicamente 1,0 cGy/UM para máquinas calibradas em condições de referência",
    )

with col2:
    st.subheader("Resultado")

    try:
        mu, sc, sp, tmr, denom = calcular_mu(
            campos, sc_vals, sp_vals, profundidades, tmr_data,
            dose, campo_col, campo_eq, prof, dr,
        )

        st.metric("🎯 Unidades Monitor (UM)", f"{mu:.1f}")

        st.divider()
        st.markdown("**Fatores interpolados:**")
        ca, cb, cc = st.columns(3)
        ca.metric("Sc", f"{sc:.4f}")
        cb.metric("Sp", f"{sp:.4f}")
        cc.metric("TMR", f"{tmr:.4f}")

        st.divider()
        st.markdown("**Fórmula aplicada:**")
        st.latex(r"UM = \frac{Dose}{DR \times Sc \times Sp \times TMR}")
        st.code(
            f"UM = {dose:.1f} / ({dr:.2f} × {sc:.4f} × {sp:.4f} × {tmr:.4f})\n"
            f"UM = {dose:.1f} / {denom:.6f}\n"
            f"UM = {mu:.2f}",
            language="text",
        )

        # Avisos de limite
        if campo_col < campos[2] or campo_col > campos[-3]:
            st.warning("⚠️ Campo colimador próximo do limite da tabela.")
        if campo_eq < campos[2] or campo_eq > campos[-3]:
            st.warning("⚠️ Campo equivalente próximo do limite da tabela.")
        if prof > profundidades[-3]:
            st.warning("⚠️ Profundidade elevada — verificar validade clínica.")

    except Exception as e:
        st.error(f"Erro no cálculo: {e}")

st.divider()

with st.expander("ℹ️ Sobre este calculador"):
    st.markdown(f"""
    **Fórmula:** `UM = Dose (cGy) / (DR × Sc × Sp × TMR)`

    **Arquivo de dados:** `clinac_fac_tmr.txt`  
    **Campos disponíveis:** {campos[0]} – {campos[-1]} cm (passo 0,5 cm)  
    **Profundidades disponíveis:** {profundidades[0]} – {profundidades[-1]} cm  
    **Normalização TMR:** dmax = 1,4 cm (TMR = 1,000)  
    **Interpolação:** linear para Sc/Sp; bilinear para TMR (profundidade × campo)

    > Este calculador é uma ferramenta de auxílio ao cálculo manual.  
    > O resultado deve sempre ser verificado pelo físico médico responsável.
    """)
