# -*- coding: utf-8 -*-
"""
Dashboard Streamlit para visualização e gerenciamento de convocações
de jogadores da base do Club de Regatas Vasco da Gama.
Os dados são lidos e escritos em uma Planilha Google.
"""

import streamlit as st
import pandas as pd
import gspread
from typing import List, Dict, Optional

# --- CONSTANTES DE CONFIGURAÇÃO ---

PAGE_CONFIG = {
    "page_title": "Convocações da Base - Vasco",
    "page_icon": "⚽",
    "layout": "wide"
}

JOGADORES_COLS = ['nome', 'ano', 'posicao', 'competicao', 'gols', 'minutagem', 'categoria']
TITULOS_COLS = ['titulo', 'categoria']
NUMERIC_COLS = ['ano', 'gols', 'minutagem']

# --- FUNÇÕES DE INTERAÇÃO COM GOOGLE SHEETS ---

@st.cache_resource(ttl=3600)
def conectar_sheets() -> Optional[gspread.Spreadsheet]:
    try:
        # A verificação de 'gcp_service_account' em st.secrets agora é mais segura
        if "gcp_service_account" not in st.secrets or "google_sheets" not in st.secrets:
            st.error("Configuração de segredos (secrets) incompleta. Verifique 'gcp_service_account' e 'google_sheets'.")
            return None
        creds = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds)
        sheet_url = st.secrets["google_sheets"]["sheet_url"]
        return gc.open_by_url(sheet_url)
    except Exception as e:
        st.error(f"Erro de conexão com a planilha: {e}")
        return None

# Movido para cá para evitar o erro de tokenização com o cache do Streamlit
CUSTOM_CSS = """
    <style>
    body, * {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    h1, h2, h3 { color: #000000; font-weight: bold; }
    .stApp { background-color: #ffffff; }
    </style>
"""

def get_worksheet(spreadsheet: gspread.Spreadsheet, name: str) -> Optional[gspread.Worksheet]:
    try:
        return spreadsheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Aba '{name}' não encontrada na planilha. Verifique o nome.")
        return None

def fetch_data(worksheet: Optional[gspread.Worksheet], required_columns: List[str]) -> pd.DataFrame:
    if not worksheet: return pd.DataFrame(columns=required_columns)
    try:
        data = worksheet.get_all_records()
        if not data: return pd.DataFrame(columns=required_columns)
        df = pd.DataFrame(data)
        if '' in df.columns: df = df.drop(columns=[''])
        df.columns = df.columns.str.lower().str.strip()
        for col in required_columns:
            if col not in df.columns: df[col] = pd.NA
        for col in NUMERIC_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
        return df[required_columns]
    except Exception as e:
        st.error(f"Erro ao processar dados da aba '{worksheet.title}': {e}")
        return pd.DataFrame(columns=required_columns)

def adicionar_jogadores_massa(worksheet: gspread.Worksheet, df_novos: pd.DataFrame):
    try:
        df_para_enviar = df_novos.reindex(columns=JOGADORES_COLS, fill_value='')
        lista_para_enviar = df_para_enviar.fillna('').values.tolist()
        worksheet.append_rows(lista_para_enviar, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Erro ao enviar dados para a planilha: {e}")
        return False

def adicionar_titulo(worksheet: gspread.Worksheet, titulo: str, categoria: str) -> bool:
    """Adiciona uma nova linha na aba de Títulos."""
    try:
        worksheet.append_row([titulo, categoria], value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar título na planilha: {e}")
        return False

# --- FUNÇÕES DE LÓGICA DO APP ---

def load_all_data(force_refresh: bool = False):
    if "data_loaded" in st.session_state and not force_refresh: return
    with st.spinner("Buscando e atualizando dados da planilha..."):
        spreadsheet = conectar_sheets()
        if spreadsheet:
            st.session_state.jogadores_ws = get_worksheet(spreadsheet, "Jogadores")
            st.session_state.titulos_ws = get_worksheet(spreadsheet, "Titulos")
            st.session_state.df_jogadores = fetch_data(st.session_state.get('jogadores_ws'), JOGADORES_COLS)
            st.session_state.df_titulos = fetch_data(st.session_state.get('titulos_ws'), TITULOS_COLS)
            st.session_state.data_loaded = True
        else:
            # Garante que DataFrames vazios sejam criados se a conexão falhar
            st.session_state.df_jogadores = pd.DataFrame(columns=JOGADORES_COLS)
            st.session_state.df_titulos = pd.DataFrame(columns=TITULOS_COLS)


def authenticate_admin():
    senha_correta = st.secrets.get("admin_password", "depanalise")
    senha_digitada = st.sidebar.text_input("Senha Admin:", type="password", key="admin_password_input")
    if senha_digitada:
        if senha_digitada == senha_correta:
            st.session_state.admin_logged_in = True
            st.sidebar.success("Modo Admin Ativo!")
        else:
            st.session_state.admin_logged_in = False
            st.sidebar.error("Senha incorreta.")
    else:
        st.session_state.admin_logged_in = False

# --- FUNÇÕES DE RENDERIZAÇÃO DA INTERFACE ---

def render_sidebar_filters(df_jogadores: pd.DataFrame) -> Dict:
    """Renderiza os filtros na barra lateral e retorna os valores selecionados."""
    st.sidebar.markdown("---")
    st.sidebar.header("Filtros de Visualização")

    # Adiciona uma verificação para evitar erro se a planilha não for carregada
    if df_jogadores.empty:
        st.sidebar.warning("Dados dos jogadores não disponíveis. Verifique a conexão com a planilha.")
        return {"nome": "", "categoria": "Todas", "posicao": "Todas", "competicao": "Todas"}

    # Filtro por nome
    nome_filtrado = st.sidebar.text_input("🔎 Filtrar por nome:")
    # Filtro por categoria
    categorias = ["Todas"] + sorted(df_jogadores["categoria"].dropna().unique())
    categoria_selecionada = st.sidebar.selectbox("📂 Filtrar por categoria:", options=categorias)
    # Filtro por posição
    posicoes = ["Todas"] + sorted(df_jogadores["posicao"].dropna().unique())
    posicao_selecionada = st.sidebar.selectbox("🏃 Filtrar por posição:", options=posicoes)
    # Filtro por competição
    competicoes = ["Todas"] + sorted(df_jogadores["competicao"].dropna().unique())
    competicao_selecionada = st.sidebar.selectbox("🏆 Filtrar por competição:", options=competicoes)

    return {
        "nome": nome_filtrado,
        "categoria": categoria_selecionada,
        "posicao": posicao_selecionada,
        "competicao": competicao_selecionada
    }

def render_jogadores_page(df_jogadores: pd.DataFrame):
    """Renderiza a página principal com a lista de jogadores e estatísticas."""
    
    filtros = render_sidebar_filters(df_jogadores)
    
    # Se o df estiver vazio, não há necessidade de filtrar ou exibir nada.
    if df_jogadores.empty:
        st.warning("Não foi possível carregar os dados dos jogadores. Verifique a conexão e as configurações.")
        return

    df_filtrado = df_jogadores.copy()
    # Aplica os filtros
    if filtros["nome"]:
        df_filtrado = df_filtrado[df_filtrado["nome"].str.contains(filtros["nome"], case=False, na=False)]
    if filtros["categoria"] != "Todas":
        df_filtrado = df_filtrado[df_filtrado["categoria"] == filtros["categoria"]]
    if filtros["posicao"] != "Todas":
        df_filtrado = df_filtrado[df_filtrado["posicao"] == filtros["posicao"]]
    if filtros["competicao"] != "Todas":
        df_filtrado = df_filtrado[df_filtrado["competicao"] == filtros["competicao"]]

    if df_filtrado.empty:
        st.info("Nenhum jogador encontrado para os filtros selecionados.")
        return

    tab_jogadores, tab_estatisticas = st.tabs(["📋 Jogadores Convocados", "📊 Estatísticas"])
    with tab_jogadores:
        st.dataframe(df_filtrado.sort_values(by=["ano", "nome"]), use_container_width=True, hide_index=True)
        st.subheader("Resumo dos Dados Filtrados")
        total_convocacoes = len(df_filtrado)
        total_gols = int(df_filtrado["gols"].sum())
        total_minutos = int(df_filtrado["minutagem"].sum())
        st.markdown(f"""
        <div style="background-color:#f0f0f0;padding:12px;border-radius:8px;">
            <b>Total de convocações:</b> {total_convocacoes}<br>
            <b>Total de gols:</b> {total_gols}<br>
            <b>Total de minutos jogados:</b> {total_minutos}
        </div>
        """, unsafe_allow_html=True)

    with tab_estatisticas:
        st.subheader("📈 Estatísticas Visuais")
        st.write("Convocados por ano:")
        st.bar_chart(df_filtrado['ano'].value_counts().sort_index())
        st.write("Convocados por competição:")
        st.bar_chart(df_filtrado['competicao'].value_counts())

def render_titulos_page(df_titulos: pd.DataFrame):
    """Renderiza a página dedicada à exibição de títulos."""
    st.header("🏆 Títulos da Base")
    if df_titulos.empty:
        st.info("Nenhum título cadastrado ou não foi possível carregar os dados.")
        return
        
    categorias_disponiveis = ["Todas"] + sorted(df_titulos["categoria"].dropna().unique())
    categoria_filtrada = st.selectbox("Filtrar por categoria:", options=categorias_disponiveis)
    df_titulos_filtrado = df_titulos
    if categoria_filtrada != "Todas":
        df_titulos_filtrado = df_titulos[df_titulos['categoria'] == categoria_filtrada]
    if df_titulos_filtrado.empty:
        st.info("Nenhum título para a categoria selecionada.")
    elif categoria_filtrada == "Todas":
        for cat, group in df_titulos_filtrado.sort_values(by='categoria').groupby('categoria'):
            st.markdown(f"### {cat}")
            for titulo in sorted(group['titulo']):
                st.markdown(f"- {titulo}")
    else:
        for titulo in sorted(df_titulos_filtrado['titulo']):
            st.markdown(f"- {titulo}")

def render_admin_tools():
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠️ Ferramentas de Admin")
    
    with st.sidebar.expander("⬆️ Adicionar em Massa (via CSV)"):
        modelo_csv = pd.DataFrame(columns=JOGADORES_COLS)
        st.download_button(label="Baixar modelo CSV", data=modelo_csv.to_csv(index=False).encode('utf-8'),
                           file_name='modelo_convocados.csv', mime='text/csv')
        uploaded_file = st.file_uploader("Selecione o arquivo CSV", type="csv",
                                         key=f"uploader_{st.session_state.get('uploader_key', 0)}")
        if uploaded_file:
            if st.button("Enviar e Adicionar Jogadores"):
                try:
                    df_novos = pd.read_csv(uploaded_file, sep=',')
                    df_novos.columns = df_novos.columns.str.lower().str.strip()
                    colunas_faltando = [col for col in JOGADORES_COLS if col not in df_novos.columns]
                    if colunas_faltando:
                        st.error(f"Erro no CSV! Colunas não encontradas: {', '.join(colunas_faltando)}")
                    else:
                        for col in NUMERIC_COLS:
                            df_novos[col] = pd.to_numeric(df_novos[col], errors='coerce').astype('Int64')
                        if adicionar_jogadores_massa(st.session_state.jogadores_ws, df_novos):
                            st.success(f"✅ {len(df_novos)} jogadores adicionados com sucesso!")
                            st.session_state.uploader_key = st.session_state.get('uploader_key', 0) + 1
                            load_all_data(force_refresh=True)
                            st.rerun()
                except Exception as e:
                    st.error(f"Ocorreu um erro ao processar o arquivo: {e}")

    with st.sidebar.expander("🏆 Adicionar Título"):
        novo_titulo = st.text_input("Nome do Título:", key="titulo_input")
        categoria_titulo = st.text_input("Categoria do Título:", key="categoria_titulo_input", help="Ex: Sub-20, Sub-17, etc.")
        
        if st.button("Salvar Novo Título"):
            if novo_titulo and categoria_titulo and st.session_state.get('titulos_ws'):
                if adicionar_titulo(st.session_state.titulos_ws, novo_titulo, categoria_titulo):
                    st.success(f"🏆 Título '{novo_titulo}' adicionado!")
                    # Limpa os campos de texto após o envio
                    st.session_state.titulo_input = ""
                    st.session_state.categoria_titulo_input = ""
                    load_all_data(force_refresh=True)
                    st.rerun()
            elif not st.session_state.get('titulos_ws'):
                st.error("Aba de títulos não foi encontrada. Não é possível adicionar.")
            else:
                st.warning("Por favor, preencha o nome do título e a categoria.")

# --- EXECUÇÃO PRINCIPAL DO SCRIPT ---

def main():
    st.set_page_config(**PAGE_CONFIG)
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown('<h1 style="text-align: center;">Convocações da Base - Vasco da Gama</h1>', unsafe_allow_html=True)
    
    load_all_data()

    # --- Sidebar Principal ---
    st.sidebar.header("Navegação")
    pagina_selecionada = st.sidebar.radio("Escolha a página:", ["Jogadores", "Títulos"])
    if st.sidebar.button("🔄 Atualizar Dados da Planilha"):
        load_all_data(force_refresh=True)
        st.toast("Dados atualizados com sucesso!")
        st.rerun()

    df_jogadores = st.session_state.get('df_jogadores', pd.DataFrame())
    if not df_jogadores.empty:
        csv_data = df_jogadores.to_csv(index=False).encode("utf-8")
        st.sidebar.download_button("📥 Baixar CSV (Jogadores)", data=csv_data, file_name="jogadores_convocados_vasco.csv")
    
    authenticate_admin()

    # --- Renderização da Página Selecionada ---
    if pagina_selecionada == "Jogadores":
        render_jogadores_page(df_jogadores)
    elif pagina_selecionada == "Títulos":
        df_titulos = st.session_state.get('df_titulos', pd.DataFrame())
        render_titulos_page(df_titulos)

    if st.session_state.get('admin_logged_in', False):
        render_admin_tools()

if __name__ == "__main__":
    main()

