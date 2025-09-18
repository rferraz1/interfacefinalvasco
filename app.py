import streamlit as st
import pandas as pd
import gspread

# ⚽ Configuração da página com layout amplo
st.set_page_config(
    page_title="Seleção Sub-20 - Vasco",
    page_icon="⚽",
    layout="wide"
)

# 🎨 Estilo personalizado
st.markdown("""
    <style>
    /* Estilo para o corpo da página e todos os elementos de texto */
    body, * {
        color: #000000 !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
    }

    /* Cores e estilos do Vasco */
    h2, h3 {
        color: #990000;
        font-weight: bold;
    }

    /* Ajuste da largura para usar a tela inteira */
    .stApp {
        background-color: #ffffff;
        max-width: 100vw;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    /* Centralizar o título H1 */
    .st-emotion-cache-1dp5k74 {
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# 🔧 Funções para interagir com o Google Sheets
def conectar_sheets():
    try:
        creds = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds)

        # SUBSTITUA ESTE URL pelo URL da sua planilha
        sheet_url = "https://docs.google.com/spreadsheets/d/1l0UqpIEOa4uAQPSQD_pNvT2LoaA2wvPWxh37LqCEp9M/edit?gid=0#gid=0"
        sheet = gc.open_by_url(sheet_url)

        # SUBSTITUA 'Sheet1' pelo nome da sua aba (ex: 'Planilha1')
        worksheet = sheet.worksheet("Sheet1")
        return worksheet
    except gspread.exceptions.GSpreadException as e:
        st.error(f"Erro de conexão com a planilha. Verifique o URL e as permissões. Detalhes: {e}")
        return None

def listar_jogadores_sheets(worksheet):
    if worksheet:
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        df['ano'] = pd.to_numeric(df['ano'], errors='coerce').astype('Int64')
        df['gols'] = pd.to_numeric(df['gols'], errors='coerce').astype('Int64')
        df['minutagem'] = pd.to_numeric(df['minutagem'], errors='coerce').astype('Int64')
        return df
    return pd.DataFrame()

def adicionar_jogador_sheets(worksheet, nome, ano, posicao, competicao, gols, minutagem):
    if worksheet:
        row_to_add = [nome, ano, posicao, competicao, gols, minutagem]
        worksheet.append_row(row_to_add)

def remover_jogador_sheets(worksheet, row_index):
    if worksheet:
        worksheet.delete_rows(row_index)

# Título principal do aplicativo
st.markdown('<h1 style="text-align: center; color: #990000; font-weight: bold; font-size: 2.5em;">Convocações Vasco da Gama Sub-20</h1>', unsafe_allow_html=True)

# Lógica de login
SENHA_ADMIN = st.secrets.get("admin_password", "vasco123")
modo_admin = False
senha = st.sidebar.text_input("Senha Admin:", type="password")

if senha == SENHA_ADMIN:
    modo_admin = True
    st.sidebar.success("Modo Admin Ativo!")
elif senha:
    st.sidebar.error("Senha incorreta.")

# Carrega os dados da planilha
worksheet = conectar_sheets()
df_jogadores = listar_jogadores_sheets(worksheet)

# --- Barra lateral e Download ---
st.sidebar.header("Opções")
if not df_jogadores.empty:
    st.sidebar.download_button(
        label="📥 Baixar lista como CSV",
        data=df_jogadores.to_csv(index=False).encode("utf-8"),
        file_name="jogadores_convocados.csv",
        mime="text/csv"
    )

# --- Conteúdo principal: Visualização ---
col_tabela, col_grafico = st.columns([0.7, 0.3])

with col_tabela:
    st.subheader("📋 Jogadores Convocados - Seleção Sub-20")
    st.subheader("📅 Filtrar jogadores por ano")
    anos_disponiveis = sorted(df_jogadores["ano"].unique())
    ano_filtrado = st.selectbox("Escolha o ano", ["Todos"] + anos_disponiveis)
    busca_nome = st.text_input("Buscar jogador pelo nome")
    st.subheader("📌 Lista de jogadores")
    df_filtrado = df_jogadores.copy()
    if ano_filtrado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["ano"] == ano_filtrado]
    if busca_nome:
        df_filtrado = df_filtrado[df_filtrado["nome"].str.contains(busca_nome, case=False)]
    if not df_filtrado.empty:
        st.dataframe(df_filtrado.sort_values(by=["ano", "nome"]))
    else:
        st.info("Nenhum jogador encontrado com os filtros aplicados.")

with col_grafico:
    st.subheader("📈 Estatísticas")
    st.write("Convocados por ano:")
    if not df_jogadores.empty:
        df_grafico = df_jogadores['ano'].value_counts().sort_index()
        st.bar_chart(df_grafico)
    else:
        st.info("Sem dados para exibir o gráfico.")
    st.subheader("Informações gerais")
    total_convocados = len(df_jogadores)
    total_gols = df_jogadores["gols"].sum() if "gols" in df_jogadores.columns else 0
    total_minutagem = df_jogadores["minutagem"].sum() if "minutagem" in df_jogadores.columns else 0
    st.markdown(f"""
    <div style="background-color:#f0f0f0;padding:10px;border-radius:8px">
    <b>Total de convocados:</b> {total_convocados}<br>
    <b>Total de gols marcados:</b> {total_gols}<br>
    <b>Total de minutagem:</b> {total_minutagem} minutos
    </div>
    """, unsafe_allow_html=True)

# Se o modo Admin estiver ativo, mostra as opções de gerenciamento
if modo_admin:
    st.markdown("---")
    st.subheader("🛠️ Ferramentas de Gerenciamento (Modo Admin)")
    col_add, col_remove = st.columns(2)
    with col_add:
        st.subheader("➕ Adicionar novo jogador")
        with st.form("adicionar_jogador_form"):
            nome = st.text_input("Nome do jogador").strip()
            ano = st.selectbox("Ano da convocação", list(range(2020, 2031)))
            posicao = st.selectbox("Posição", ["Goleiro", "Zagueiro", "Lateral Direito", "Lateral Esquerdo", "Volante", "Meia Central", "Meia Ofensivo", "Ponta Direita", "Ponta Esquerda", "Centroavante"])
            competicao = st.selectbox("Competição", ["Mundial", "Sul-Americano", "Outras"])
            gols = st.number_input("Gols marcados", min_value=0, step=1)
            minutagem = st.number_input("Minutagem em campo (minutos)", min_value=0, step=1)
            salvar = st.form_submit_button("Salvar jogador")
            if salvar:
                if worksheet:
                    if nome and competicao:
                        adicionar_jogador_sheets(worksheet, nome, ano, posicao, competicao, gols, minutagem)
                        st.success(f"✅ {nome} adicionado com sucesso!")
                        st.experimental_rerun()
                    else:
                        st.warning("⚠️ Nome e Competição são obrigatórios.")
                else:
                    st.warning("⚠️ Não foi possível adicionar. Verifique a conexão com a planilha.")

    with col_remove:
        st.subheader("🗑️ Remover jogador")
        if not df_jogadores.empty:
            df_jogadores_com_indice = df_jogadores.reset_index(drop=True).reset_index().rename(columns={'index': 'linha_id'})
            df_jogadores_com_indice['linha_id'] = df_jogadores_com_indice['linha_id'] + 2
            opcoes_remocao = df_jogadores_com_indice.apply(lambda j: f"{j['nome']} ({j['ano']}) - {j['posicao']}", axis=1)
            jogador_selecionado = st.selectbox("Selecione o jogador:", options=[None] + list(opcoes_remocao.index), format_func=lambda i: "Selecione um jogador" if i is None else opcoes_remocao.loc[i])
            remover = st.button("Remover jogador selecionado")
            if remover and jogador_selecionado is not None:
                if worksheet:
                    row_to_delete = df_jogadores_com_indice.loc[jogador_selecionado, 'linha_id']
                    remover_jogador_sheets(worksheet, row_to_delete)
                    st.success(f"✅ Jogador removido com sucesso!")
                    st.experimental_rerun()
                else:
                    st.warning("⚠️ Não foi possível remover. Verifique a conexão com a planilha.")
        else:
            st.info("Nenhum jogador para remover.")