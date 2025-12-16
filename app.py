# app.py
import streamlit as st
import pandas as pd
import requests
from io import StringIO

st.set_page_config(page_title="Calculadora de Unidade Monitora", layout="wide")
st.title("📊 Calculadora Manual de Unidade Monitora")
st.markdown("---")

def carregar_dados_do_github():
    """Carrega os dados diretamente do GitHub"""
    
    # URL do arquivo raw no GitHub
    github_url = "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/main/clinac_fac_tmr.txt"
    
    try:
        # Baixar o arquivo do GitHub
        response = requests.get(github_url)
        response.raise_for_status()
        
        # Usar StringIO para simular um arquivo
        conteudo = StringIO(response.text)
        linhas = conteudo.readlines()
        
        # Processar linha por linha
        dados_processados = []
        for linha in linhas:
            linha = linha.strip()
            if linha:  # Ignorar linhas vazias
                # Verificar se é a linha de cabeçalho "Prof."
                if linha.startswith("Prof."):
                    # Esta é a linha de cabeçalho, vamos pular mas registrar
                    # Ela está vazia depois de "Prof."
                    continue
                
                # Verificar se é linha de dados numéricos
                partes = linha.split('\t')
                
                # A primeira linha contém os campos
                if len(dados_processados) == 0:
                    # É a linha de campos (começa com "Campo")
                    if partes[0] == "Campo":
                        campos = [float(x) for x in partes[1:]]
                    else:
                        campos = [float(x) for x in partes]
                    dados_processados.append(campos)
                
                elif len(dados_processados) == 1:
                    # É a linha Sc
                    if partes[0] == "Sc":
                        sc = [float(x) for x in partes[1:]]
                    else:
                        sc = [float(x) for x in partes]
                    dados_processados.append(sc)
                
                elif len(dados_processados) == 2:
                    # É a linha Sp
                    if partes[0] == "Sp":
                        sp = [float(x) for x in partes[1:]]
                    else:
                        sp = [float(x) for x in partes]
                    dados_processados.append(sp)
                
                else:
                    # São linhas de TMR (profundidade + valores)
                    try:
                        profundidade = float(partes[0])
                        valores_tmr = [float(x) for x in partes[1:]]
                        if len(dados_processados) == 3:
                            # Inicializar dicionário de TMR
                            dados_processados.append({})
                        dados_processados[3][profundidade] = valores_tmr
                    except ValueError:
                        # Ignorar linhas que não podem ser convertidas
                        continue
        
        # Extrair os dados
        campos = dados_processados[0]
        sc = dados_processados[1]
        sp = dados_processados[2]
        tmr_data = dados_processados[3] if len(dados_processados) > 3 else {}
        
        return campos, sc, sp, tmr_data
        
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao carregar dados do GitHub: {e}")
        return None, None, None, None
    except Exception as e:
        st.error(f"Erro ao processar dados: {e}")
        return None, None, None, None

# Versão alternativa mais simples (se o formato for consistente):
def carregar_dados_simples():
    """Versão simplificada que assume formato específico"""
    
    github_url = "https://raw.githubusercontent.com/cuccuerj/CalculoUnidadeMonitora/main/clinac_fac_tmr.txt"
    
    try:
        response = requests.get(github_url)
        response.raise_for_status()
        
        linhas = response.text.split('\n')
        
        # Filtrar linhas vazias
        linhas = [linha.strip() for linha in linhas if linha.strip()]
        
        # Processar campos (primeira linha)
        campos_line = linhas[0].split('\t')
        if campos_line[0] == "Campo":
            campos = [float(x) for x in campos_line[1:]]
        else:
            campos = [float(x) for x in campos_line]
        
        # Processar Sc (segunda linha)
        sc_line = linhas[1].split('\t')
        if sc_line[0] == "Sc":
            sc = [float(x) for x in sc_line[1:]]
        else:
            sc = [float(x) for x in sc_line]
        
        # Processar Sp (terceira linha)
        sp_line = linhas[2].split('\t')
        if sp_line[0] == "Sp":
            sp = [float(x) for x in sp_line[1:]]
        else:
            sp = [float(x) for x in sp_line]
        
        # Processar TMR (começa na quinta linha porque a quarta é "Prof.")
        tmr_data = {}
        for linha in linhas[4:]:  # Pula as primeiras 4 linhas
            partes = linha.split('\t')
            if partes[0] and not partes[0].startswith("Prof."):
                try:
                    profundidade = float(partes[0])
                    valores_tmr = [float(x) for x in partes[1:]]
                    tmr_data[profundidade] = valores_tmr
                except ValueError:
                    continue
        
        return campos, sc, sp, tmr_data
        
    except Exception as e:
        st.error(f"Erro: {e}")
        return None, None, None, None

# Carregar dados usando a versão simples
with st.spinner("Carregando dados..."):
    campos, sc_vals, sp_vals, tmr_data = carregar_dados_simples()

if campos is not None:
    st.success(f"✅ Dados carregados! {len(campos)} campos, {len(tmr_data)} profundidades")
    
    # Exibir uma prévia dos dados
    with st.expander("📋 Visualizar dados carregados"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**Campos (cm):**")
            st.write(campos[:5], "...")
        
        with col2:
            st.write("**Sc (primeiros valores):**")
            st.write(sc_vals[:5], "...")
        
        with col3:
            st.write("**Profundidades disponíveis:**")
            st.write(list(tmr_data.keys())[:5], "...")
    
    # INTERFACE PRINCIPAL
    st.markdown("---")
    
    # Seleção de campo
    st.subheader("🔍 Busca de Valores")
    
    col1, col2 = st.columns(2)
    
    with col1:
        campo_selecionado = st.selectbox(
            "Selecione o tamanho do campo (cm):",
            options=campos,
            format_func=lambda x: f"{x} cm"
        )
        
        # Encontrar índice
        idx = campos.index(campo_selecionado)
        
        # Mostrar valores
        st.metric("Sc", f"{sc_vals[idx]:.4f}")
        st.metric("Sp", f"{sp_vals[idx]:.4f}")
    
    with col2:
        # Seleção de profundidade para TMR
        profundidades = sorted(list(tmr_data.keys()))
        profundidade_selecionada = st.selectbox(
            "Selecione a profundidade (cm):",
            options=profundidades,
            format_func=lambda x: f"{x} cm"
        )
        
        # Obter TMR
        if profundidade_selecionada in tmr_data:
            tmr_valor = tmr_data[profundidade_selecionada][idx]
            st.metric("TMR", f"{tmr_valor:.4f}")
    
    # Função de interpolação
    st.markdown("---")
    st.subheader("📈 Interpolação")
    
    def interpolar(valor_alvo, valores_x, valores_y):
        """Interpolação linear simples"""
        if valor_alvo in valores_x:
            return valores_y[valores_x.index(valor_alvo)]
        
        # Encontrar intervalo
        for i in range(len(valores_x) - 1):
            if valores_x[i] <= valor_alvo <= valores_x[i + 1]:
                x0, x1 = valores_x[i], valores_x[i + 1]
                y0, y1 = valores_y[i], valores_y[i + 1]
                return y0 + (valor_alvo - x0) * (y1 - y0) / (x1 - x0)
        
        # Extrapolação se necessário
        if valor_alvo < valores_x[0]:
            return valores_y[0]
        else:
            return valores_y[-1]
    
    col3, col4 = st.columns(2)
    
    with col3:
        campo_personalizado = st.number_input(
            "Campo personalizado (cm):",
            min_value=float(min(campos)),
            max_value=float(max(campos)),
            value=10.0,
            step=0.1
        )
        
        if campo_personalizado:
            sc_interp = interpolar(campo_personalizado, campos, sc_vals)
            sp_interp = interpolar(campo_personalizado, campos, sp_vals)
            st.write(f"Sc interpolado: **{sc_interp:.4f}**")
            st.write(f"Sp interpolado: **{sp_interp:.4f}**")
    
    with col4:
        profundidade_personalizada = st.number_input(
            "Profundidade personalizada (cm):",
            min_value=0.0,
            max_value=30.0,
            value=10.0,
            step=0.1
        )
        
        if profundidade_personalizada and campo_personalizado:
            # Interpolar TMR para profundidade personalizada
            profs_interp = []
            tmrs_interp = []
            
            for prof in profundidades:
                tmr_vals = tmr_data[prof]
                tmr_interp = interpolar(campo_personalizado, campos, tmr_vals)
                profs_interp.append(prof)
                tmrs_interp.append(tmr_interp)
            
            tmr_final = interpolar(profundidade_personalizada, profs_interp, tmrs_interp)
            st.write(f"TMR interpolado: **{tmr_final:.4f}**")
    
    # Visualização
    st.markdown("---")
    st.subheader("📊 Visualização Gráfica")
    
    import plotly.graph_objects as go
    
    tab1, tab2 = st.tabs(["Sc e Sp", "TMR"])
    
    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=campos, y=sc_vals, mode='lines+markers', name='Sc'))
        fig.add_trace(go.Scatter(x=campos, y=sp_vals, mode='lines+markers', name='Sp'))
        fig.update_layout(
            title='Fatores de Colimação (Sc) e Phantom (Sp)',
            xaxis_title='Campo (cm)',
            yaxis_title='Valor'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        # Selecionar algumas profundidades para mostrar
        profs_para_grafico = st.multiselect(
            "Selecione profundidades para o gráfico:",
            options=profundidades,
            default=[0.0, 5.0, 10.0, 20.0, 30.0]
        )
        
        fig2 = go.Figure()
        for prof in profs_para_grafico:
            if prof in tmr_data:
                fig2.add_trace(go.Scatter(
                    x=campos, 
                    y=tmr_data[prof], 
                    mode='lines+markers',
                    name=f'{prof} cm'
                ))
        
        fig2.update_layout(
            title='TMR vs Campo para Diferentes Profundidades',
            xaxis_title='Campo (cm)',
            yaxis_title='TMR'
        )
        st.plotly_chart(fig2, use_container_width=True)

else:
    st.error("Não foi possível carregar os dados. Verifique:")
    st.error("1. A URL do GitHub está correta?")
    st.error("2. O arquivo existe no repositório?")
    st.error("3. Tem acesso à internet?")
    
    # Opção para usar arquivo local como fallback
    st.info("Ou faça upload do arquivo local:")
    arquivo_local = st.file_uploader("Escolha o arquivo clinac_fac_tmr.txt", type=['txt'])
    
    if arquivo_local:
        # Processar arquivo local
        linhas = arquivo_local.read().decode('utf-8').split('\n')
        # ... (código similar para processar)
