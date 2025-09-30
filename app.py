# -*- coding: utf-8 -*-
"""
Dashboard Streamlit v1.0 para visualização e gerenciamento de convocações
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
TITULOS_COLS = ['categoria', 'titulo', 'ano']
## NOVO: Colunas para a aba Transfermarkt
TRANSFERMARKT_COLS = ['jogador', 'valor_de_mercado', 'contrato_ate', 'link']
NUMERIC_COLS = ['ano', 'gols', 'minutagem']

# --- FUNÇÕES DE INTERAÇÃO COM GOOGLE SHEETS ---

@st.cache_resource(ttl=3600)
def conectar_sheets() -> Optional[gspread.Spreadsheet]:
    try:
        if "gcp_service_account" not in st.secrets or "google_sheets" not in st.secrets:
            st.error("Configuração de segredos (secrets) incompleta.")
            return None
        creds = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds)
        sheet_url = st.secrets["google_sheets"]["sheet_url"]
        return gc.open_by_url(sheet_url)
    except Exception as e:
        st.error(f"Erro de conexão com a planilha: {e}")
        return None

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
        # Não mostra erro, apenas retorna None. A interface tratará a ausência da aba.
        return None

def fetch_data(worksheet: Optional[gspread.Worksheet], required_columns: List[str]) -> pd.DataFrame:
    if not worksheet: return pd.DataFrame(columns=required_columns)
    try:
        data = worksheet.get_all_records()
        if not data: return pd.DataFrame(columns=required_columns)
        df = pd.DataFrame(data)
        if '' in df.columns: df = df.drop(columns=[''])
        df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
        for col in required_columns:
            if col not in df.columns: df[col] = pd.NA
        extended_numeric_cols = list(set(NUMERIC_COLS + ['ano']))
        for col in extended_numeric_cols:
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

def adicionar_titulos_massa(worksheet: gspread.Worksheet, df_novos: pd.DataFrame):
    try:
        df_para_enviar = df_novos.reindex(columns=TITULOS_COLS, fill_value='')
        lista_para_enviar = df_para_enviar.fillna('').values.tolist()
        worksheet.append_rows(lista_para_enviar, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Erro ao enviar dados de títulos para a planilha: {e}")
        return False

def adicionar_titulo(worksheet: gspread.Worksheet, categoria: str, titulo: str, ano: int) -> bool:
    try:
        worksheet.append_row([categoria, titulo, ano], value_input_option='USER_ENTERED')
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
            st.session_state.transfermarkt_ws = get_worksheet(spreadsheet, "Transfermarkt") ## NOVO
            
            st.session_state.df_jogadores = fetch_data(st.session_state.get('jogadores_ws'), JOGADORES_COLS)
            st.session_state.df_titulos = fetch_data(st.session_state.get('titulos_ws'), TITULOS_COLS)
            st.session_state.df_transfermarkt = fetch_data(st.session_state.get('transfermarkt_ws'), TRANSFERMARKT_COLS) ## NOVO
            st.session_state.data_loaded = True
        else:
            st.session_state.df_jogadores = pd.DataFrame(columns=JOGADORES_COLS)
            st.session_state.df_titulos = pd.DataFrame(columns=TITULOS_COLS)
            st.session_state.df_transfermarkt = pd.DataFrame(columns=TRANSFERMARKT_COLS) ## NOVO

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
    st.sidebar.markdown("---")
    st.sidebar.header("Filtros de Visualização")
    if df_jogadores.empty:
        st.sidebar.warning("Dados dos jogadores não disponíveis.")
        return {"nome": "", "categoria": "Todas", "posicao": "Todas", "competicao": "Todas"}
    nome_filtrado = st.sidebar.text_input("🔎 Filtrar por nome:")
    categorias = ["Todas"] + sorted(df_jogadores["categoria"].dropna().unique())
    categoria_selecionada = st.sidebar.selectbox("📂 Filtrar por categoria:", options=categorias)
    posicoes = ["Todas"] + sorted(df_jogadores["posicao"].dropna().unique())
    posicao_selecionada = st.sidebar.selectbox("🏃 Filtrar por posição:", options=posicoes)
    competicoes = ["Todas"] + sorted(df_jogadores["competicao"].dropna().unique())
    competicao_selecionada = st.sidebar.selectbox("🏆 Filtrar por competição:", options=competicoes)
    return {"nome": nome_filtrado, "categoria": categoria_selecionada, "posicao": posicao_selecionada, "competicao": competicao_selecionada}

def render_main_page(df_jogadores: pd.DataFrame, df_titulos: pd.DataFrame, df_transfermarkt: pd.DataFrame):
    filtros = render_sidebar_filters(df_jogadores)
    
    df_filtrado = df_jogadores.copy()
    if not df_jogadores.empty:
        if filtros["nome"]: df_filtrado = df_filtrado[df_filtrado["nome"].str.contains(filtros["nome"], case=False, na=False)]
        if filtros["categoria"] != "Todas": df_filtrado = df_filtrado[df_filtrado["categoria"] == filtros["categoria"]]
        if filtros["posicao"] != "Todas": df_filtrado = df_filtrado[df_filtrado["posicao"] == filtros["posicao"]]
        if filtros["competicao"] != "Todas": df_filtrado = df_filtrado[df_filtrado["competicao"] == filtros["competicao"]]

    ## MUDANÇA: Adicionada a aba "Transfermarkt"
    tabs = st.tabs(["📋 Jogadores Convocados", "🏆 Títulos", "📊 Estatísticas", "🌐 Transfermarkt"])
    
    with tabs[0]: # Jogadores Convocados
        if df_jogadores.empty:
            st.warning("Não foi possível carregar os dados dos jogadores.")
        elif df_filtrado.empty:
            st.info("Nenhum jogador encontrado para os filtros selecionados.")
        else:
            st.dataframe(df_filtrado.sort_values(by=["ano", "nome"]), use_container_width=True, hide_index=True)
            st.subheader("Resumo dos Dados")
            total_convocacoes = len(df_filtrado)
            total_gols = int(df_filtrado["gols"].sum())
            total_minutos = int(df_filtrado["minutagem"].sum())
            total_titulos_geral = len(df_titulos)
            st.markdown(f"""<div style="background-color:#f0f0f0;padding:12px;border-radius:8px;"><b>Total de convocações (filtrado):</b> {total_convocacoes}<br><b>Total de gols (filtrado):</b> {total_gols}<br><b>Total de minutos (filtrado):</b> {total_minutos}<br><hr><b>🏆 Total de títulos cadastrados (base):</b> {total_titulos_geral}</div>""", unsafe_allow_html=True)

    with tabs[1]: # Títulos
        st.header("Títulos da Base Cadastrados")
        if df_titulos.empty:
            st.info("Nenhum título cadastrado ou aba 'Titulos' não encontrada na planilha.")
        else:
            st.dataframe(df_titulos.sort_values(by="ano", ascending=False), use_container_width=True, hide_index=True)

    with tabs[2]: # Estatísticas
        st.subheader("📈 Estatísticas Visuais dos Jogadores Filtrados")
        if df_filtrado.empty:
            st.info("Nenhum jogador encontrado para gerar estatísticas.")
        else:
            st.write("Convocados por ano:")
            st.bar_chart(df_filtrado['ano'].value_counts().sort_index())
            st.write("Convocados por competição:")
            st.bar_chart(df_filtrado['competicao'].value_counts())
            
    ## NOVO: Conteúdo da aba Transfermarkt
    with tabs[3]: # Transfermarkt
        st.header("🌐 Dados de Mercado (Transfermarkt)")
        if df_transfermarkt.empty:
            st.info("Aguardando a criação da aba 'Transfermarkt' na planilha e a inserção dos dados.")
            st.markdown("Para ativar esta aba, crie uma página na sua Planilha Google com o nome `Transfermarkt` e adicione colunas como `jogador`, `valor_de_mercado`, `contrato_ate`, `link`, etc.")
        else:
            st.dataframe(
                df_transfermarkt,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "link": st.column_config.LinkColumn("Link TM")
                }
            )

def render_admin_tools():
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠️ Ferramentas de Admin")
    
    # ... (Nenhuma mudança nas ferramentas de Admin)
    with st.sidebar.expander("⬆️ Adicionar Jogadores em Massa (CSV)"):
        modelo_csv = pd.DataFrame(columns=JOGADORES_COLS); st.download_button(label="Baixar modelo CSV (Jogadores)", data=modelo_csv.to_csv(index=False).encode('utf-8'), file_name='modelo_convocados.csv', mime='text/csv')
        uploaded_file = st.file_uploader("Selecione o arquivo CSV de jogadores", type="csv", key=f"uploader_jogadores_{st.session_state.get('uploader_key_jogadores', 0)}")
        if uploaded_file:
            if st.button("Enviar e Adicionar Jogadores"):
                try:
                    df_novos = pd.read_csv(uploaded_file, sep=','); df_novos.columns = df_novos.columns.str.lower().str.strip()
                    if all(col in df_novos.columns for col in JOGADORES_COLS):
                        for col in NUMERIC_COLS: df_novos[col] = pd.to_numeric(df_novos[col], errors='coerce').astype('Int64')
                        if adicionar_jogadores_massa(st.session_state.jogadores_ws, df_novos):
                            st.success(f"✅ {len(df_novos)} jogadores adicionados!"); st.session_state.uploader_key_jogadores = st.session_state.get('uploader_key_jogadores', 0) + 1; load_all_data(force_refresh=True); st.rerun()
                    else: st.error(f"Erro no CSV! Colunas esperadas: {', '.join(JOGADORES_COLS)}")
                except Exception as e: st.error(f"Ocorreu um erro ao processar o arquivo: {e}")
    with st.sidebar.expander("🏆 Adicionar Título Individual"):
        categoria_titulo = st.text_input("Categoria do Título:", key="categoria_titulo_input", help="Ex: Sub-20, Sub-17"); novo_titulo = st.text_input("Nome do Título:", key="titulo_input"); ano_titulo = st.number_input("Ano do Título:", min_value=1900, max_value=2100, value=None, step=1, key="ano_titulo_input")
        if st.button("Salvar Novo Título"):
            if novo_titulo and categoria_titulo and ano_titulo and st.session_state.get('titulos_ws'):
                if adicionar_titulo(st.session_state.titulos_ws, categoria_titulo, novo_titulo, int(ano_titulo)):
                    st.success(f"🏆 Título '{novo_titulo}' ({ano_titulo}) adicionado!"); load_all_data(force_refresh=True); st.rerun()
            else: st.warning("Por favor, preencha todos os campos: categoria, título e ano.")
    with st.sidebar.expander("⬆️ Adicionar Títulos em Massa (CSV)"):
        modelo_csv_titulos = pd.DataFrame(columns=TITULOS_COLS); st.download_button(label="Baixar modelo CSV (Títulos)", data=modelo_csv_titulos.to_csv(index=False).encode('utf-8'), file_name='modelo_titulos.csv', mime='text/csv')
        uploaded_file_titulos = st.file_uploader("Selecione o arquivo CSV de títulos", type="csv", key=f"uploader_titulos_{st.session_state.get('uploader_key_titulos', 0)}")
        if uploaded_file_titulos:
            if st.button("Enviar e Adicionar Títulos"):
                try:
                    df_novos_titulos = pd.read_csv(uploaded_file_titulos, sep=','); df_novos_titulos.columns = df_novos_titulos.columns.str.lower().str.strip()
                    if all(col in df_novos_titulos.columns for col in TITULOS_COLS):
                        df_novos_titulos['ano'] = pd.to_numeric(df_novos_titulos['ano'], errors='coerce').astype('Int64')
                        if adicionar_titulos_massa(st.session_state.titulos_ws, df_novos_titulos):
                            st.success(f"✅ {len(df_novos_titulos)} títulos adicionados!"); st.session_state.uploader_key_titulos = st.session_state.get('uploader_key_titulos', 0) + 1; load_all_data(force_refresh=True); st.rerun()
                    else: st.error(f"Erro no CSV! Colunas esperadas na ordem correta: {', '.join(TITULOS_COLS)}")
                except Exception as e: st.error(f"Ocorreu um erro ao processar o arquivo de títulos: {e}")

# --- EXECUÇÃO PRINCIPAL DO SCRIPT ---

def main():
    st.set_page_config(**PAGE_CONFIG)
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown('<h1 style="text-align: center;">Convocações da Base - Vasco da Gama</h1>', unsafe_allow_html=True)
    
    load_all_data()
    
    st.sidebar.header("Controles")
    if st.sidebar.button("🔄 Atualizar Dados da Planilha"):
        load_all_data(force_refresh=True)
        st.toast("Dados atualizados com sucesso!")
        st.rerun()

    df_jogadores = st.session_state.get('df_jogadores', pd.DataFrame(columns=JOGADORES_COLS))
    if not df_jogadores.empty:
        csv_data = df_jogadores.to_csv(index=False).encode("utf-8")
        st.sidebar.download_button("📥 Baixar CSV (Jogadores)", data=csv_data, file_name="jogadores_convocados_vasco.csv")
    
    authenticate_admin()

    render_main_page(
        df_jogadores,
        st.session_state.get('df_titulos', pd.DataFrame(columns=TITULOS_COLS)),
        st.session_state.get('df_transfermarkt', pd.DataFrame(columns=TRANSFERMARKT_COLS))
    )

    if st.session_state.get('admin_logged_in', False):
        render_admin_tools()

if __name__ == "__main__":
    main()