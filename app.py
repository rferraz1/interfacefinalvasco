import streamlit as st
import pandas as pd
import gspread
import io

# ⚽ Configuração da página
st.set_page_config(
    page_title="Convocações da Base - Vasco",
    page_icon="⚽",
    layout="wide"
)

# 🎨 Estilo personalizado
st.markdown("""
    <style>
    body, * {
        color: #000000 !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    h2, h3 { color: #000000; font-weight: bold; }
    .stApp { background-color: #ffffff; }
    </style>
""", unsafe_allow_html=True)

# --- Funções de Conexão e Leitura ---

@st.cache_resource
def conectar_sheets():
    try:
        creds = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds)
        sheet_url = st.secrets["google_sheets"]["sheet_url"]
        return gc.open_by_url(sheet_url)
    except Exception as e:
        st.error(f"Erro de conexão com a planilha: {e}"); return None

def get_worksheet(sheet, name, headers):
    try:
        worksheet = sheet.worksheet(name)
        if headers and not worksheet.acell('A1').value:
            worksheet.update('A1', [headers])
        return worksheet
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Aba '{name}' não encontrada."); return None

def fetch_data(worksheet, required_columns, default_fills=None):
    if not worksheet: return pd.DataFrame(columns=required_columns)
    data = worksheet.get_all_records()
    if not data: return pd.DataFrame(columns=required_columns)
    
    df = pd.DataFrame(data)

    # Linha de blindagem para ignorar colunas fantasmas
    if '' in df.columns:
        df = df.drop(columns=[''])
    
    df.columns = df.columns.str.lower().str.strip()
    
    # Mantém apenas as colunas oficiais para evitar erros
    cols_to_keep = [col for col in required_columns if col in df.columns]
    df = df[cols_to_keep]
    
    for col in required_columns:
        if col not in df.columns: df[col] = pd.NA
            
    if default_fills:
        for col, value in default_fills.items():
            if col in df.columns:
                df[col] = df[col].fillna(value)
                
    numeric_cols = ['ano', 'gols', 'minutagem']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
            
    return df

# --- Lógica de Carregamento ---
def load_data(force=False):
    if "data_loaded" not in st.session_state or force:
        with st.spinner("Buscando dados da planilha..."):
            spreadsheet = conectar_sheets()
            if spreadsheet:
                st.session_state.jogadores_ws = get_worksheet(spreadsheet, "Jogadores", ['nome', 'ano', 'posicao', 'competicao', 'gols', 'minutagem', 'categoria'])
                st.session_state.titulos_ws = get_worksheet(spreadsheet, "Titulos", ['titulo', 'categoria'])
                
                st.session_state.df_jogadores = fetch_data(st.session_state.jogadores_ws, 
                                                           ['nome', 'ano', 'posicao', 'competicao', 'gols', 'minutagem', 'categoria'], 
                                                           {'categoria': 'Sub-20'})
                st.session_state.df_titulos = fetch_data(st.session_state.titulos_ws, ['titulo', 'categoria'])
                st.session_state.data_loaded = True

# --- Funções de Escrita ---
def adicionar_jogadores_massa(worksheet, df_novos):
    df_atual = st.session_state.get('df_jogadores', pd.DataFrame())
    for col in ['ano', 'gols', 'minutagem']:
        if col in df_atual.columns:
            df_atual[col] = pd.to_numeric(df_atual[col], errors='coerce').astype('Int64')
    df_atualizado = pd.concat([df_atual, df_novos], ignore_index=True)
    st.session_state.df_jogadores = df_atualizado
    
    if worksheet and not df_novos.empty:
        colunas_ordenadas = ['nome', 'ano', 'posicao', 'competicao', 'gols', 'minutagem', 'categoria']
        df_para_enviar = pd.DataFrame()
        for col in colunas_ordenadas:
            if col in df_novos.columns:
                df_para_enviar[col] = df_novos[col]
            else:
                df_para_enviar[col] = ''
        lista_para_enviar = df_para_enviar.fillna('').values.tolist()
        worksheet.append_rows(lista_para_enviar, value_input_option='USER_ENTERED')

# --- Início da Interface ---
st.markdown('<h1 style="text-align: center; color: #000000;">Convocações da Base - Vasco da Gama</h1>', unsafe_allow_html=True)
load_data()

# Lógica de Login
SENHA_ADMIN = st.secrets.get("admin_password", "depanalise")
senha = st.sidebar.text_input("Senha Admin:", type="password")
st.session_state.admin_logged_in = senha == SENHA_ADMIN
modo_admin = st.session_state.get('admin_logged_in', False)

if modo_admin: st.sidebar.success("Modo Admin Ativo!")
elif senha: st.sidebar.error("Senha incorreta.")

# Barra Lateral
st.sidebar.header("Opções")
if st.sidebar.button("🔄 Atualizar Dados da Planilha"): 
    st.cache_resource.clear()
    load_data(force=True)
    st.toast("Dados atualizados!")
df_para_download = st.session_state.get('df_jogadores', pd.DataFrame())
if not df_para_download.empty:
    st.sidebar.download_button("📥 Baixar CSV Jogadores", df_para_download.to_csv(index=False).encode("utf-8"), "jogadores_convocados.csv")

# Filtros
st.sidebar.header("Filtros")
df_jogadores = st.session_state.get('df_jogadores', pd.DataFrame())
if not df_jogadores.empty:
    categorias_disponiveis = sorted(df_jogadores["categoria"].dropna().unique())
else:
    categorias_disponiveis = []
categoria_filtrada = st.sidebar.selectbox("📂 Filtrar por categoria:", ["Todas"] + categorias_disponiveis)
if not df_jogadores.empty and categoria_filtrada != "Todas":
    df_filtrado = df_jogadores[df_jogadores["categoria"] == categoria_filtrada]
else:
    df_filtrado = df_jogadores.copy() 

# Conteúdo Principal
if df_filtrado.empty:
    st.info("Nenhum jogador cadastrado ou correspondente ao filtro.")
else:
    tab_jogadores, tab_estatisticas = st.tabs(["📋 Jogadores Convocados", "📊 Estatísticas e Títulos"])
    with tab_jogadores:
        st.dataframe(df_filtrado.sort_values(by=["ano", "nome"]), use_container_width=True)
        st.subheader("Informações Gerais (de acordo com os filtros)")
        st.markdown(f"""<div style="background-color:#f0f0f0;padding:10px;border-radius:8px;">
        <b>Total de convocações:</b> {len(df_filtrado)}<br>
        <b>Total de gols:</b> {int(df_filtrado["gols"].sum())}<br>
        <b>Total de minutos:</b> {int(df_filtrado["minutagem"].sum())}</div>""", unsafe_allow_html=True)
    with tab_estatisticas:
        col_graficos, col_titulos = st.columns([0.6, 0.4])
        with col_graficos:
            st.subheader("📈 Estatísticas (de acordo com os filtros)")
            st.write("Convocados por ano:"); st.bar_chart(df_filtrado['ano'].value_counts().sort_index())
            st.write("Convocados por competição:"); st.bar_chart(df_filtrado['competicao'].value_counts())
        with col_titulos:
            st.subheader("🏆 Títulos da Base")
            df_titulos = st.session_state.get('df_titulos', pd.DataFrame())
            if not df_titulos.empty:
                if 'categoria' not in df_titulos.columns:
                    st.error("A coluna 'categoria' não foi encontrada na sua planilha 'Titulos'.")
                else:
                    df_titulos_filtrado = df_titulos
                    if categoria_filtrada != "Todas":
                        df_titulos_filtrado = df_titulos[df_titulos['categoria'] == categoria_filtrada]
                    if not df_titulos_filtrado.empty:
                        if categoria_filtrada == "Todas":
                            for cat, group in df_titulos_filtrado.groupby('categoria'):
                                st.markdown(f"**{cat}**"); [st.markdown(f"- {titulo}") for titulo in sorted(group['titulo'])]
                        else:
                            for titulo in sorted(df_titulos_filtrado['titulo']): st.markdown(f"- {titulo}")
                    else: st.info("Nenhum título para a categoria selecionada.")

# Ferramentas de Admin
if modo_admin:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠️ Ferramentas de Gerenciamento")
    jogadores_ws = st.session_state.get('jogadores_ws')
    if jogadores_ws:
        with st.sidebar.expander("⬆️ Adicionar em Massa (CSV)"):
            modelo_csv = pd.DataFrame([{'nome':'', 'ano':'', 'posicao':'', 'competicao':'', 'gols':'', 'minutagem':'', 'categoria':''}])
            st.download_button(label="Baixar modelo CSV", data=modelo_csv.to_csv(index=False, sep=',', encoding='utf-8').encode('utf-8'), file_name='modelo_convocados.csv', mime='text/csv')
            
            if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
            csv_file = st.file_uploader("Selecione o arquivo CSV", type="csv", key=st.session_state.uploader_key)
            
            if csv_file is not None:
                if st.button("Enviar Arquivo CSV"):
                    try:
                        df_novos = pd.read_csv(csv_file, sep=',', encoding='utf-8')
                        df_novos.columns = df_novos.columns.str.strip().str.lower()
                        colunas_necessarias = ['nome', 'ano', 'posicao', 'competicao', 'gols', 'minutagem', 'categoria']
                        colunas_faltando = [col for col in colunas_necessarias if col not in df_novos.columns]
                        if colunas_faltando:
                            st.error(f"Erro no CSV! Colunas não encontradas: {', '.join(colunas_faltando)}")
                        else:
                            for col in ['ano', 'gols', 'minutagem']:
                                df_novos[col] = pd.to_numeric(df_novos[col], errors='coerce').astype('Int64')
                            adicionar_jogadores_massa(jogadores_ws, df_novos)
                            st.success(f"✅ {len(df_novos)} jogadores adicionados!")
                            st.session_state.uploader_key += 1
                            st.rerun()
                    except Exception as e:
                        st.error(f"Ocorreu um erro ao processar o arquivo: {e}")
        # Outras ferramentas de admin (Adicionar Jogador, Títulos, Remover Jogador) podem ser adicionadas aqui.