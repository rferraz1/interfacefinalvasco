import streamlit as st
import pandas as pd
import gspread
from collections import Counter

# ⚽ Configuração da página
st.set_page_config(
    page_title="Seleção Sub-20 - Vasco",
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
        st.error(f"Erro de conexão com a planilha. Verifique a URL e as permissões. Detalhes: {e}")
        return None

def get_worksheet(sheet, name, headers):
    try:
        worksheet = sheet.worksheet(name)
        if not worksheet.acell('A1').value:
            worksheet.update('A1', [headers])
            st.toast(f"Aba '{name}' configurada com sucesso!")
        return worksheet
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Aba '{name}' não encontrada. Crie uma aba com este nome.")
        return None

def fetch_jogadores_data(_worksheet):
    required_columns = ['nome', 'ano', 'posicao', 'competicao', 'gols', 'minutagem']
    if not _worksheet: return pd.DataFrame(columns=required_columns)
    data = _worksheet.get_all_records()
    if not data: return pd.DataFrame(columns=required_columns)
    df = pd.DataFrame(data)
    for col in required_columns:
        if col not in df.columns: df[col] = pd.NA
    for col in ['ano', 'gols', 'minutagem']:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
    return df[required_columns]

def fetch_titulos_data(_worksheet):
    if not _worksheet: return []
    return _worksheet.col_values(1)[1:]

# --- Lógica de Carregamento de Dados na Sessão ---

def load_data(force=False):
    if "data_loaded" not in st.session_state or force:
        with st.spinner("Buscando dados da planilha..."):
            spreadsheet = conectar_sheets()
            if spreadsheet:
                st.session_state.jogadores_ws = get_worksheet(spreadsheet, "Jogadores", ['nome', 'ano', 'posicao', 'competicao', 'gols', 'minutagem'])
                st.session_state.titulos_ws = get_worksheet(spreadsheet, "Titulos", ['titulo'])
                st.session_state.df_jogadores = fetch_jogadores_data(st.session_state.jogadores_ws)
                st.session_state.lista_titulos = fetch_titulos_data(st.session_state.titulos_ws)
                st.session_state.data_loaded = True

# --- Funções de Escrita ---

def adicionar_jogador(worksheet, dados):
    if worksheet:
        worksheet.append_row(dados)
        load_data(force=True)

def remover_jogador(worksheet, row_index):
    if worksheet:
        worksheet.delete_rows(row_index)
        load_data(force=True)
    
def adicionar_titulos(worksheet, titulos):
    if worksheet and titulos:
        worksheet.append_rows([[t] for t in titulos])
        load_data(force=True)

# ===== NOVA FUNÇÃO PARA REMOVER TÍTULOS =====
def remover_titulo(worksheet, titulo_para_remover):
    if worksheet and titulo_para_remover:
        try:
            # Encontra a primeira ocorrência do título
            cell = worksheet.find(titulo_para_remover)
            if cell:
                worksheet.delete_rows(cell.row)
                load_data(force=True)
                return True
        except gspread.exceptions.CellNotFound:
            st.error(f"Título '{titulo_para_remover}' não encontrado para remoção.")
    return False

def adicionar_jogadores_massa(worksheet, df_novos):
    if worksheet and not df_novos.empty:
        colunas_ordenadas = ['nome', 'ano', 'posicao', 'competicao', 'gols', 'minutagem']
        lista_de_listas = df_novos[colunas_ordenadas].values.tolist()
        worksheet.append_rows(lista_de_listas, value_input_option='USER_ENTERED')
        load_data(force=True)

# --- Início da Interface ---

st.markdown('<h1 style="text-align: center; color: #000000;">Convocações Vasco da Gama Sub-20</h1>', unsafe_allow_html=True)

load_data()

# Lógica de Login
SENHA_ADMIN = st.secrets.get("admin_password", "depanalise")
senha = st.sidebar.text_input("Senha Admin:", type="password")

if senha == SENHA_ADMIN:
    st.session_state.admin_logged_in = True
else:
    st.session_state.admin_logged_in = False

modo_admin = st.session_state.get('admin_logged_in', False)

if modo_admin:
    st.sidebar.success("Modo Admin Ativo!")
elif senha:
    st.sidebar.error("Senha incorreta.")

# Barra Lateral
st.sidebar.header("Opções")
if st.sidebar.button("🔄 Atualizar Dados"):
    load_data(force=True)
    st.toast("Dados atualizados com sucesso!")

df_jogadores = st.session_state.get('df_jogadores', pd.DataFrame())
if not df_jogadores.empty:
    st.sidebar.download_button("📥 Baixar lista como CSV", df_jogadores.to_csv(index=False).encode("utf-8"), "jogadores_convocados.csv")

# Conteúdo Principal
col_tabela, col_grafico = st.columns([0.7, 0.3])
with col_tabela:
    st.subheader("📋 Jogadores Convocados")
    df_filtrado = df_jogadores.copy()
    if not df_filtrado.empty:
        anos_disponiveis = sorted(df_filtrado["ano"].dropna().unique(), reverse=True)
        ano_filtrado = st.selectbox("📅 Filtrar por ano:", ["Todos"] + anos_disponiveis)
        busca_nome = st.text_input("🔎 Buscar jogador pelo nome:")
        if ano_filtrado != "Todos":
            df_filtrado = df_filtrado[df_filtrado["ano"] == ano_filtrado]
        if busca_nome:
            df_filtrado = df_filtrado[df_filtrado["nome"].str.contains(busca_nome, case=False, na=False)]
        st.dataframe(df_filtrado.sort_values(by=["ano", "nome"]))
    else:
        st.info("Nenhum jogador cadastrado. Adicione um no modo Admin.")

with col_grafico:
    st.subheader("📈 Estatísticas")
    if not df_jogadores.empty and not df_jogadores['ano'].dropna().empty:
        st.write("Convocados por ano:")
        st.bar_chart(df_jogadores['ano'].value_counts().sort_index())
    
    st.subheader("🏆 Títulos da Base")
    lista_titulos = st.session_state.get('lista_titulos', [])
    if lista_titulos:
        contagem = Counter(lista_titulos)
        display_list = [f"- {t} (x{c})" if c > 1 else f"- {t}" for t, c in sorted(contagem.items())]
        st.markdown("\n".join(display_list))
    else:
        st.info("Nenhum título cadastrado.")
    
    st.subheader("Informações Gerais")
    st.markdown(f"""
    <div style="background-color:#f0f0f0;padding:10px;border-radius:8px; margin-top: 15px;">
    <b>Total de convocados:</b> {len(df_jogadores)}<br>
    <b>Total de gols:</b> {int(df_jogadores["gols"].sum())}<br>
    <b>Total de minutos:</b> {int(df_jogadores["minutagem"].sum())}
    </div>
    """, unsafe_allow_html=True)

if modo_admin:
    st.markdown("---")
    st.subheader("🛠️ Ferramentas de Gerenciamento")
    
    jogadores_ws = st.session_state.get('jogadores_ws')
    titulos_ws = st.session_state.get('titulos_ws')

    if jogadores_ws and titulos_ws:
        with st.expander("➕ Adicionar Jogador"):
            with st.form("form_add_jogador", clear_on_submit=True):
                dados = {'nome': st.text_input("Nome").strip(), 'ano': st.selectbox("Ano", list(range(2025, 2019, -1))), 'posicao': st.selectbox("Posição", ["Goleiro", "Zagueiro", "Lateral", "Volante", "Meia", "Ponta", "Atacante"]), 'competicao': st.selectbox("Competição", ["Mundial", "Sul-Americano", "Amistoso", "Outras"]), 'gols': st.number_input("Gols", 0, 100, 0, 1), 'minutagem': st.number_input("Minutos", 0, 5000, 0, 1)}
                if st.form_submit_button("Salvar Jogador"):
                    if dados['nome']:
                        row_to_add = [dados['nome'], dados['ano'], dados['posicao'], dados['competicao'], dados['gols'], dados['minutagem']]
                        adicionar_jogador(jogadores_ws, row_to_add)
                        st.success(f"✅ {dados['nome']} adicionado!")
                        st.rerun()
                    else: st.warning("⚠️ Nome é obrigatório.")

        with st.expander("⬆️ Adicionar em Massa (CSV)"):
            modelo_csv = pd.DataFrame([{'nome':'', 'ano':'', 'posicao':'', 'competicao':'', 'gols':'', 'minutagem':''}])
            st.download_button("Baixar modelo CSV", modelo_csv.to_csv(index=False).encode('utf-8'), 'modelo_convocados.csv', 'text/csv')
            csv_file = st.file_uploader("Escolha um arquivo CSV para upload", type="csv")
            if csv_file is not None:
                if st.button("Carregar dados do CSV"):
                    try:
                        df_novos = pd.read_csv(csv_file).fillna('')
                        colunas_obrigatorias = {'nome', 'ano', 'posicao', 'competicao', 'gols', 'minutagem'}
                        if colunas_obrigatorias.issubset(df_novos.columns):
                            adicionar_jogadores_massa(jogadores_ws, df_novos)
                            st.success(f"✅ {len(df_novos)} jogadores adicionados!")
                            st.rerun()
                        else: st.error(f"O arquivo CSV não tem as colunas obrigatórias. Verifique o modelo.")
                    except Exception as e: st.error(f"Ocorreu um erro ao processar o arquivo: {e}")

        with st.expander("🏆 Adicionar Títulos"):
            with st.form("form_add_titulos", clear_on_submit=True):
                titulos_predef = sorted(["Brasileiro", "Carioca", "Copa do Brasil", "Libertadores", "Copa Rio"])
                quantidades = {t: st.number_input(t, 0, 10, 0, 1) for t in titulos_predef}
                custom = st.text_input("Outro Título:")
                if st.form_submit_button("Adicionar Títulos"):
                    para_add = [t for t, q in quantidades.items() for _ in range(q)]
                    if custom: para_add.append(custom)
                    if para_add:
                        adicionar_titulos(titulos_ws, para_add)
                        st.success("Títulos atualizados!")
                        st.rerun()

        # ===== NOVA SEÇÃO PARA REMOVER TÍTULOS =====
        with st.expander("🗑️ Remover Título"):
            if lista_titulos:
                # Mostra cada título como uma opção única para remoção
                titulo_para_remover = st.selectbox("Selecione o título para remover:", ["Selecione..."] + lista_titulos)
                if st.button("Remover Título Selecionado") and titulo_para_remover != "Selecione...":
                    if remover_titulo(titulos_ws, titulo_para_remover):
                        st.success(f"✅ Título '{titulo_para_remover}' removido!")
                        st.rerun()
            else:
                st.info("Nenhum título para remover.")

        with st.expander("🗑️ Remover Jogador"):
            df_remover = df_jogadores.copy()
            if not df_remover.empty:
                df_remover['display'] = df_remover.apply(lambda r: f"{r['nome']} ({r['ano']})", axis=1)
                idx_para_remover = st.selectbox("Selecione para remover:", options=df_remover.index, format_func=lambda i: df_remover.loc[i, 'display'], index=None, placeholder="Selecione um jogador...")
                if st.button("Remover Jogador Selecionado") and idx_para_remover is not None:
                    remover_jogador(jogadores_ws, int(idx_para_remover + 2))
                    st.success(f"✅ Jogador removido!")
                    st.rerun()
    else:
        st.warning("Não foi possível carregar as ferramentas de admin. Tente atualizar os dados.")