import streamlit as st
import pandas as pd
import sqlite3
import re

DB_FILE = "jogadores.db"

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

# 🔧 Funções do banco de dados
def conectar():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jogadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            ano INTEGER NOT NULL,
            posicao TEXT NOT NULL,
            competicao TEXT NOT NULL,
            gols INTEGER DEFAULT 0
        )
    """)
    cursor = conn.execute("PRAGMA table_info(jogadores)")
    colunas = [col[1] for col in cursor.fetchall()]
    if "minutagem" not in colunas:
        conn.execute("ALTER TABLE jogadores ADD COLUMN minutagem INTEGER DEFAULT 0")
    return conn

def listar_jogadores(conn):
    return pd.read_sql_query("SELECT * FROM jogadores", conn)

def adicionar_jogador(conn, nome, ano, posicao, competicao, gols, minutagem):
    conn.execute("""
        INSERT INTO jogadores (nome, ano, posicao, competicao, gols, minutagem)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (nome, ano, posicao, competicao, gols, minutagem))
    conn.commit()

def jogador_existe(conn, nome, ano):
    cursor = conn.execute("SELECT COUNT(*) FROM jogadores WHERE LOWER(nome) = LOWER(?) AND ano = ?", (nome, ano))
    return cursor.fetchone()[0] > 0

def remover_jogador(conn, jogador_id):
    conn.execute("DELETE FROM jogadores WHERE id = ?", (jogador_id,))
    conn.commit()

# 🔁 Inicialização
conn = conectar()
df_jogadores = listar_jogadores(conn)

# Título principal do aplicativo
st.markdown('<h1 style="text-align: center; color: #990000; font-weight: bold; font-size: 2.5em;">Convocações Vasco da Gama Sub-20</h1>', unsafe_allow_html=True)

# --- Botões na barra lateral para navegação ---
st.sidebar.header("Opções")

if "pagina" not in st.session_state:
    st.session_state.pagina = "visualizar"

if st.sidebar.button("👁️ Visualizar"):
    st.session_state.pagina = "visualizar"
if st.sidebar.button("➕ Adicionar"):
    st.session_state.pagina = "adicionar"
if st.sidebar.button("🗑️ Remover"):
    st.session_state.pagina = "remover"

# --- Conteúdo da página principal baseado no botão clicado ---
if st.session_state.pagina == "adicionar":
    st.subheader("Novo jogador")
    with st.form("adicionar_jogador_form"):
        nome = st.text_input("Nome do jogador")
        ano = st.selectbox("Ano da convocação", list(range(2020, 2026)))
        posicao = st.selectbox("Posição", [
            "Goleiro", "Zagueiro", "Lateral Direito", "Lateral Esquerdo",
            "Volante", "Meia Central", "Meia Ofensivo", "Ponta Direita",
            "Ponta Esquerda", "Centroavante"
        ])
        competicao = st.selectbox("Competição", ["Mundial", "Sul-Americano", "Outras"])
        gols = st.number_input("Gols marcados", min_value=0, step=1)
        minutagem = st.number_input("Minutagem em campo (minutos)", min_value=0, step=1)
        salvar = st.form_submit_button("Salvar jogador")

        if salvar:
            nome_limpo = nome.strip()
            if not nome_limpo:
                st.warning("⚠️ Nome do jogador é obrigatório.")
            elif not re.match("^[A-Za-zÀ-ÿ ']+$", nome_limpo):
                st.warning("⚠️ Nome inválido. Use apenas letras e espaços.")
            elif jogador_existe(conn, nome_limpo, ano):
                st.warning("⚠️ Esse jogador já foi adicionado para esse ano.")
            else:
                adicionar_jogador(conn, nome_limpo, ano, posicao, competicao, gols, minutagem)
                st.success(f"✅ {nome_limpo} adicionado com sucesso!")
                st.session_state.pagina = "visualizar"
                st.experimental_rerun()

elif st.session_state.pagina == "remover":
    st.subheader("Remover jogador")
    if not df_jogadores.empty:
        opcoes_remocao = df_jogadores.apply(
            lambda j: f"{j['nome']} ({j['ano']}) - {j['posicao']} / {j['competicao']}", axis=1
        ).tolist()
        jogador_index = st.selectbox(
            "Selecione o jogador para deletar:",
            options=[None] + list(df_jogadores.index),
            format_func=lambda i: "Selecione um jogador" if i is None else opcoes_remocao[i]
        )
        remover = st.button("Remover jogador selecionado")

        if remover and jogador_index is not None:
            jogador_id = int(df_jogadores.loc[jogador_index, "id"])
            nome_removido = df_jogadores.loc[jogador_index, "nome"]
            remover_jogador(conn, jogador_id)
            st.success(f"✅ {nome_removido} removido com sucesso!")
            st.session_state.pagina = "visualizar"
            st.experimental_rerun()
    else:
        st.info("Nenhum jogador para remover.")

else: # st.session_state.pagina == "visualizar"
    # Dividindo a página em duas colunas, com mais espaço para a tabela
    col_tabela, col_grafico = st.columns([0.7, 0.3])

    with col_tabela:
        st.subheader("📋 Jogadores Convocados - Seleção Sub-20")

        # 🔍 Filtros
        st.subheader("📅 Filtrar jogadores por ano")
        anos_disponiveis = sorted(df_jogadores["ano"].unique())
        ano_filtrado = st.selectbox("Escolha o ano", ["Todos"] + anos_disponiveis)

        busca_nome = st.text_input("Buscar jogador pelo nome")

        # 📋 Exibição da tabela
        st.subheader("📌 Lista de jogadores")

        df_filtrado = df_jogadores.copy()
        if ano_filtrado != "Todos":
            df_filtrado = df_filtrado[df_filtrado["ano"] == ano_filtrado]
        if busca_nome:
            df_filtrado = df_filtrado[df_filtrado["nome"].str.contains(busca_nome, case=False)]

        if not df_filtrado.empty:
            df_exibir = df_filtrado.drop(columns=["id"]).sort_values(by=["ano", "nome"])
            st.dataframe(df_exibir)
        else:
            st.info("Nenhum jogador encontrado com os filtros aplicados.")

    with col_grafico:
        # Conteúdo da coluna da direita sem borda
        st.subheader("📈 Estatísticas")
        st.write("Convocados por ano:")
        if not df_jogadores.empty:
            df_grafico = df_jogadores['ano'].value_counts().sort_index()
            st.bar_chart(df_grafico)
        else:
            st.info("Sem dados para exibir o gráfico.")

        # 📊 Informações gerais
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
            
    # 📥 Botão para baixar CSV
    if not df_jogadores.empty:
        st.download_button(
            label="📥 Baixar lista como CSV",
            data=df_jogadores.drop(columns=["id"]).to_csv(index=False).encode("utf-8"),
            file_name="jogadores_convocados.csv",
            mime="text/csv"
        )