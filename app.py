# app.py
import streamlit as st
import pandas as pd
import requests
from io import StringIO
import math
import numpy as np
import fitz
import re

st.sidebar.title("Cálculo de Unidade Monitora")
selected_page = st.sidebar.selectbox(
    'Selecione o Acelerador Linear',
    ['CL2100', 'UNIQUE']
)

def extrair_info_pdf():
    pdf_plano = st.file_uploader("Importe o PDF do Plano", type =["pdf"])
    if pdf_plano is not None:
        with fitz.open(stream = pdf_plano.read(), filetype = "pdf") as doc:
            text = ""
            for page in doc:
                text += page.get_text()
            padrao = r"(?<=Energia)(.*?)(?=Tamanho do Campo Aberto X)"
            resultado = re.search(padrao, texto, re.DOTALL)
            if resultado:
              dados = resultado.group(1).strip()
              valores = re.findall(r"\s(\d+X)", dados)
              print(valores)


if selected_page =="CL2100":
    st.title("Cálculo de Unidade Monitora para o Acelerador Linear CL2100")
    extrair_info_pdf()
    
    cl_fac_tmr = "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/main/clinac_fac_tmr.txt"
    df = pd.read_csv(cl_fac_tmr,sep="\t",header = None)
    tam_campo = df.iloc[0,1:].astype(float).tolist()    
    sc = pd.Series(df.iloc[1,1:].astype(float).values,index = tam_campo,name = "Sc")
    sp = pd.Series(df.iloc[2,1:].astype(float).values,index = tam_campo,name = "Sp")
    tmr_raw = df.iloc[4:].reset_index(drop = True)
    tmr_raw.columns = ["Profundidade"]+tam_campo
    tmr_raw["Profundidade"] = tmr_raw["Profundidade"].astype(float)
    tmr = tmr_raw.set_index("Profundidade")
    

elif selected_page =="UNIQUE":
    st.title("Cálculo de Unidade Monitora para o Acelerador Linear UNIQUE")
    extrair_info_pdf()

# st.sidebar.header("Filtros")
# department = st.sidebar.selectbox(
#     'Selecione o departamento',
#     ['Vendas', 'Marketing', 'Engenharia']
# )

# data_range = st.sidebar.date_input('Selecione o intervalo de datas')

# st.title(f'Página: {selected_page}')
# st.write(f'Departamento: {department}')

    
# st.set_page_config(page_title="Calculadora de Unidade Monitora", layout="wide")
# st.title("🏥 Calculadora de Unidade Monitora (MU)")
# st.markdown("---")

# # Função para carregar dados (a mesma corrigida)
# def carregar_dados():
#     """Carrega os dados do arquivo"""
#     # Use a função que corrigimos anteriormente ou carregue localmente
#     # Aqui vou usar uma versão simplificada para o protótipo
#     github_url = "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/main/clinac_fac_tmr.txt"
    
#     try:
#         response = requests.get(github_url)
#         response.raise_for_status()
#         linhas = response.text.split('\n')
        
#         # Filtrar linhas vazias
#         linhas = [linha.strip() for linha in linhas if linha.strip()]
        
#         # Processar campos
#         campos_line = linhas[0].split('\t')
#         if campos_line[0] == "Campo":
#             campos = [float(x) for x in campos_line[1:]]
#         else:
#             campos = [float(x) for x in campos_line]
        
#         # Processar Sc
#         sc_line = linhas[1].split('\t')
#         if sc_line[0] == "Sc":
#             sc = [float(x) for x in sc_line[1:]]
#         else:
#             sc = [float(x) for x in sc_line]
        
#         # Processar Sp
#         sp_line = linhas[2].split('\t')
#         if sp_line[0] == "Sp":
#             sp = [float(x) for x in sp_line[1:]]
#         else:
#             sp = [float(x) for x in sp_line]
        
#         # Processar TMR (pular linha "Prof.")
#         tmr_data = {}
#         for linha in linhas[4:]:
#             partes = linha.split('\t')
#             if partes[0] and not partes[0].startswith("Prof."):
#                 try:
#                     profundidade = float(partes[0])
#                     valores_tmr = [float(x) for x in partes[1:]]
#                     tmr_data[profundidade] = valores_tmr
#                 except ValueError:
#                     continue
        
#         return campos, sc, sp, tmr_data
        
#     except:
#         # Fallback: carregar localmente
#         try:
#             with open('clinac_fac_tmr.txt', 'r') as f:
#                 linhas = f.readlines()
            
#             # Mesmo processamento...
#             # (código similar ao acima)
#             pass
#         except:
#             return None, None, None, None

# # Função de interpolação
# def interpolar(valor_alvo, valores_x, valores_y):
#     """Interpolação linear"""
#     if valor_alvo in valores_x:
#         return valores_y[valores_x.index(valor_alvo)]
    
#     for i in range(len(valores_x) - 1):
#         if valores_x[i] <= valor_alvo <= valores_x[i + 1]:
#             x0, x1 = valores_x[i], valores_x[i + 1]
#             y0, y1 = valores_y[i], valores_y[i + 1]
#             return y0 + (valor_alvo - x0) * (y1 - y0) / (x1 - x0)
    
#     # Extrapolação se necessário
#     if valor_alvo < valores_x[0]:
#         return valores_y[0]
#     else:
#         return valores_y[-1]

# # Função para calcular campo equivalente
# def calcular_campo_equivalente(X, Y):
#     """Calcula campo equivalente para campo retangular"""
#     if X == Y:
#         return X
#     else:
#         return (2 * X * Y) / (X + Y)

# # Função para calcular fator de distância (inverso do quadrado)
# def calcular_fator_distancia(SCD, SSD, profundidade_efetiva):
#     """Calcula fator de correção de distância"""
#     # Fórmula: (SCD / (SSD + d))²
#     return (SCD / (SSD + profundidade_efetiva)) ** 2

# # Carregar dados
# with st.spinner("Carregando dados do acelerador..."):
#     campos, sc_vals, sp_vals, tmr_data = carregar_dados()

# if campos is None:
#     st.error("Não foi possível carregar os dados. Verifique a conexão ou o arquivo local.")
#     st.stop()

# # INÍCIO DA INTERFACE DE CÁLCULO
# st.subheader("📝 Entrada de Parâmetros para Cálculo")

# # Criar abas para organização
# tab1, tab2, tab3 = st.tabs(["📋 Dados Básicos", "⚙️ Parâmetros Técnicos", "📊 Resultados"])

# with tab1:
#     st.markdown("### Informações do Paciente/Tumor")
    
#     col1, col2 = st.columns(2)
    
#     with col1:
#         dose_prescrita = st.number_input(
#             "Dose prescrita (cGy):",
#             min_value=0.0,
#             max_value=1000.0,
#             value=200.0,
#             step=1.0,
#             help="Dose a ser administrada no ponto de cálculo"
#         )
    
#     with col2:
#         n_fracoes = st.number_input(
#             "Número de frações:",
#             min_value=1,
#             max_value=50,
#             value=1,
#             step=1
#         )
        
#         dose_por_fracao = dose_prescrita / n_fracoes if n_fracoes > 0 else dose_prescrita
#         st.info(f"Dose por fração: **{dose_por_fracao:.1f} cGy**")

# with tab2:
#     st.markdown("### Parâmetros Técnicos do Campo")
    
#     col1, col2, col3 = st.columns(3)
    
#     with col1:
#         campo_X = st.number_input(
#             "Campo X (cm):",
#             min_value=0.1,
#             max_value=40.0,
#             value=10.0,
#             step=0.1,
#             help="Largura do campo na direção X"
#         )
        
#         campo_Y = st.number_input(
#             "Campo Y (cm):",
#             min_value=0.1,
#             max_value=40.0,
#             value=10.0,
#             step=0.1,
#             help="Altura do campo na direção Y"
#         )
        
#         # Calcular campo equivalente
#         campo_eq = calcular_campo_equivalente(campo_X, campo_Y)
#         st.success(f"**Campo equivalente:** {campo_eq:.2f} cm")
    
#     with col2:
#         sdd = st.number_input(
#             "SDD (cm):",
#             min_value=50.0,
#             max_value=150.0,
#             value=100.0,
#             step=1.0,
#             help="Source to Detector Distance"
#         )
        
#         profundidade = st.number_input(
#             "Profundidade (cm):",
#             min_value=0.0,
#             max_value=50.0,
#             value=10.0,
#             step=0.1,
#             help="Profundidade do ponto de cálculo"
#         )
        
#         # Calcular SSD
#         ssd = sdd - profundidade
#         st.info(f"**SSD calculado:** {ssd:.1f} cm")
    
#     with col3:
#         scd = st.number_input(
#             "SCD (cm):",
#             min_value=80.0,
#             max_value=120.0,
#             value=100.0,
#             step=1.0,
#             help="Source to Calibration Distance"
#         )
        
#         profundidade_efetiva = st.number_input(
#             "Profundidade efetiva (cm):",
#             min_value=0.0,
#             max_value=50.0,
#             value=10.0,
#             step=0.1,
#             help="Profundidade efetiva considerando obliquidade, etc."
#         )
        
#         # Verificar consistência
#         if ssd < 0:
#             st.error("SSD negativo! Verifique SDD e profundidade.")

# # CÁLCULO EM TEMPO REAL
# with tab3:
#     st.markdown("### Resultados do Cálculo")
    
#     if st.button("▶️ Calcular Unidade Monitora", type="primary"):
#         with st.spinner("Calculando..."):
            
#             # 1. Obter Sc e Sp para o campo equivalente
#             sc_valor = interpolar(campo_eq, campos, sc_vals)
#             sp_valor = interpolar(campo_eq, campos, sp_vals)
            
#             # 2. Obter TMR para profundidade e campo equivalente
#             # Primeiro, obter TMR para todas as profundidades disponíveis para este campo
#             profundidades_disponiveis = sorted(tmr_data.keys())
#             tmrs_para_campo = []
            
#             for prof in profundidades_disponiveis:
#                 tmr_vals = tmr_data[prof]
#                 tmr_interpolado = interpolar(campo_eq, campos, tmr_vals)
#                 tmrs_para_campo.append((prof, tmr_interpolado))
            
#             # Separar profundidades e valores TMR
#             profs = [p[0] for p in tmrs_para_campo]
#             tmrs = [p[1] for p in tmrs_para_campo]
            
#             # Interpolar TMR para a profundidade desejada
#             tmr_valor = interpolar(profundidade, profs, tmrs)
            
#             # 3. Calcular fator de distância
#             fator_dist = calcular_fator_distancia(scd, ssd, profundidade_efetiva)
            
#             # 4. Calcular Unidade Monitora
#             # UM = Dose / (Sc * Sp * TMR * fator_dist)
#             if sc_valor and sp_valor and tmr_valor and fator_dist:
#                 denominador = sc_valor * sp_valor * tmr_valor * fator_dist
                
#                 if denominador > 0:
#                     um = dose_por_fracao / denominador
                    
#                     # Mostrar resultados
#                     st.markdown("---")
                    
#                     col_res1, col_res2 = st.columns(2)
                    
#                     with col_res1:
#                         st.metric("Sc", f"{sc_valor:.4f}")
#                         st.metric("Sp", f"{sp_valor:.4f}")
#                         st.metric("TMR", f"{tmr_valor:.4f}")
#                         st.metric("Fator Distância", f"{fator_dist:.4f}")
                    
#                     with col_res2:
#                         st.metric("Dose por fração", f"{dose_por_fracao:.1f} cGy")
#                         st.metric("Denominador", f"{denominador:.4f}")
#                         st.markdown("---")
#                         st.success(f"### 🎯 Unidades Monitora: {um:.0f} MU")
                        
#                         # Para todas as frações
#                         um_total = um * n_fracoes
#                         st.info(f"Total para {n_fracoes} frações: **{um_total:.0f} MU**")
                    
#                     # Tabela de resumo
#                     st.markdown("---")
#                     st.subheader("📋 Resumo do Cálculo")
                    
#                     resumo = pd.DataFrame({
#                         'Parâmetro': ['Dose Prescrita', 'Campo X', 'Campo Y', 'Campo Equivalente', 
#                                      'SDD', 'SSD', 'SCD', 'Profundidade', 'Profundidade Efetiva',
#                                      'Sc', 'Sp', 'TMR', 'Fator Distância', 'UM'],
#                         'Valor': [f"{dose_prescrita} cGy", f"{campo_X} cm", f"{campo_Y} cm", 
#                                  f"{campo_eq:.2f} cm", f"{sdd} cm", f"{ssd:.1f} cm", 
#                                  f"{scd} cm", f"{profundidade} cm", f"{profundidade_efetiva} cm",
#                                  f"{sc_valor:.4f}", f"{sp_valor:.4f}", f"{tmr_valor:.4f}",
#                                  f"{fator_dist:.4f}", f"{um:.0f}"]
#                     })
                    
#                     st.dataframe(resumo, use_container_width=True, hide_index=True)
                    
#                     # Opção para exportar
#                     csv = resumo.to_csv(index=False)
#                     st.download_button(
#                         label="📥 Exportar Resultados (CSV)",
#                         data=csv,
#                         file_name="calculo_um.csv",
#                         mime="text/csv"
#                     )
#                 else:
#                     st.error("Erro no cálculo: denominador zero ou negativo.")
#             else:
#                 st.error("Não foi possível obter todos os valores necessários para o cálculo.")

# # VISUALIZAÇÃO GRÁFICA
# st.markdown("---")
# st.subheader("📊 Visualização dos Fatores")

# if 'campo_eq' in locals():
#     # Gráfico de Sc e Sp vs Campo
#     import plotly.graph_objects as go
    
#     fig = go.Figure()
    
#     # Sc
#     fig.add_trace(go.Scatter(
#         x=campos, 
#         y=sc_vals, 
#         mode='lines',
#         name='Sc',
#         line=dict(color='blue', width=2)
#     ))
    
#     # Sp
#     fig.add_trace(go.Scatter(
#         x=campos, 
#         y=sp_vals, 
#         mode='lines',
#         name='Sp',
#         line=dict(color='green', width=2)
#     ))
    
#     # Marcar o ponto do campo equivalente
#     if 'sc_valor' in locals() and 'sp_valor' in locals():
#         fig.add_trace(go.Scatter(
#             x=[campo_eq],
#             y=[sc_valor],
#             mode='markers',
#             name=f'Sc para {campo_eq:.1f} cm',
#             marker=dict(color='blue', size=10, symbol='circle')
#         ))
        
#         fig.add_trace(go.Scatter(
#             x=[campo_eq],
#             y=[sp_valor],
#             mode='markers',
#             name=f'Sp para {campo_eq:.1f} cm',
#             marker=dict(color='green', size=10, symbol='square')
#         ))
    
#     fig.update_layout(
#         title='Fatores de Colimação (Sc) e Phantom (Sp)',
#         xaxis_title='Campo Equivalente (cm)',
#         yaxis_title='Valor',
#         hovermode='x unified'
#     )
    
#     st.plotly_chart(fig, use_container_width=True)

# # TMR para diferentes profundidades
# if 'tmr_data' in locals():
#     st.subheader("TMR para Diferentes Profundidades")
    
#     # Selecionar algumas profundidades para mostrar
#     profs_selecionadas = st.multiselect(
#         "Selecione profundidades para visualizar TMR:",
#         options=sorted(tmr_data.keys()),
#         default=[0.0, 5.0, 10.0, 20.0, 30.0]
#     )
    
#     if profs_selecionadas:
#         fig2 = go.Figure()
        
#         for prof in profs_selecionadas:
#             if prof in tmr_data:
#                 fig2.add_trace(go.Scatter(
#                     x=campos,
#                     y=tmr_data[prof],
#                     mode='lines',
#                     name=f'{prof} cm'
#                 ))
        
#         if 'campo_eq' in locals():
#             # Adicionar linha vertical no campo equivalente
#             fig2.add_vline(
#                 x=campo_eq, 
#                 line_width=2, 
#                 line_dash="dash", 
#                 line_color="red",
#                 annotation_text=f"Campo Eq: {campo_eq:.1f} cm"
#             )
        
#         fig2.update_layout(
#             title='TMR vs Campo Equivalente',
#             xaxis_title='Campo Equivalente (cm)',
#             yaxis_title='TMR'
#         )
        
#         st.plotly_chart(fig2, use_container_width=True)

# # EXEMPLOS PRÉ-DEFINIDOS
# st.markdown("---")
# st.subheader("💡 Exemplos Práticos")

# col_ex1, col_ex2, col_ex3 = st.columns(3)

# with col_ex1:
#     if st.button("Exemplo 1: Campo 10x10"):
#         st.session_state.dose = 200.0
#         st.session_state.campo_x = 10.0
#         st.session_state.campo_y = 10.0
#         st.session_state.profundidade = 10.0
#         st.rerun()

# with col_ex2:
#     if st.button("Exemplo 2: Campo 15x20"):
#         st.session_state.dose = 180.0
#         st.session_state.campo_x = 15.0
#         st.session_state.campo_y = 20.0
#         st.session_state.profundidade = 5.0
#         st.rerun()

# with col_ex3:
#     if st.button("Exemplo 3: Campo 5x5"):
#         st.session_state.dose = 240.0
#         st.session_state.campo_x = 5.0
#         st.session_state.campo_y = 5.0
#         st.session_state.profundidade = 15.0
#         st.rerun()

# # FÓRMULA EXPLICATIVA
# with st.expander("📖 Fórmula do Cálculo"):
#     st.markdown("""
#     ### Fórmula da Unidade Monitora (MU)
    
#     ```
#     UM = Dose / (Sc × Sp × TMR × FatorDistância)
#     ```
    
#     Onde:
#     - **Dose**: Dose prescrita no ponto de cálculo (cGy)
#     - **Sc**: Fator de colimação (collimator scatter factor)
#     - **Sp**: Fator de phantom (phantom scatter factor)
#     - **TMR**: Tissue Maximum Ratio
#     - **FatorDistância**: Correção para diferença entre SCD e SSD+d
    
#     ### Cálculo do Fator de Distância
    
#     ```
#     FatorDistância = (SCD / (SSD + d))²
#     ```
    
#     - **SCD**: Source to Calibration Distance (distância de calibração)
#     - **SSD**: Source to Surface Distance
#     - **d**: Profundidade efetiva
    
#     ### Campo Equivalente (para campos retangulares)
    
#     ```
#     CampoEq = (2 × X × Y) / (X + Y)
#     ```
#     """)

# # VALIDAÇÕES E VERIFICAÇÕES
# st.markdown("---")
# st.subheader("⚠️ Verificações")

# if 'um' in locals():
#     if um < 0:
#         st.error("❌ UN calculada é negativa! Verifique os parâmetros.")
#     elif um > 1000:
#         st.warning("⚠️ UN muito alta (>1000). Verifique se os parâmetros estão corretos.")
#     else:
#         st.success("✅ Cálculo dentro de faixa razoável.")
    
#     # Verificar se profundidade está dentro dos limites
#     profundidades_disponiveis = sorted(tmr_data.keys())
#     if profundidade < min(profundidades_disponiveis) or profundidade > max(profundidades_disponiveis):
#         st.warning(f"⚠️ Profundidade {profundidade} cm está fora da faixa tabelada ({min(profundidades_disponiveis)}-{max(profundidades_disponiveis)} cm). O resultado é extrapolado.")

# # FOOTER
# st.markdown("---")
# st.caption("Calculadora desenvolvida para fins educacionais e de planejamento. Sempre verifique os cálculos manualmente.")
