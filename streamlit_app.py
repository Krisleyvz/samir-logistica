import hmac
import html
import json
import math
import re
import unicodedata
import urllib.parse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
from PIL import Image

# Google é opcional nesta versão: usado apenas para preservar Logs_Acesso.
try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None

# =========================================================
# CONFIGURAÇÃO GERAL
# =========================================================
st.set_page_config(
    page_title="App de Rua | Logística",
    page_icon="🚚",
    layout="centered",
)

ARQUIVO_LOGO = "IMG_6008.PNG"
VERSAO_APP = "2026.08.19-CENTRAL-API-v0.3"
FUSO_ACRE = ZoneInfo("America/Rio_Branco")

# Preserva a configuração existente. Acrescente outros motoristas aqui futuramente.
MOTORISTAS = ["Tancremildo Filho"]
MOTORISTA_POR_USUARIO = {
    "tancremildo": "Tancremildo Filho",
}

STATUS = [
    "SEPARADO",
    "EM_ROTA",
    "ENTREGUE",
    "REAGENDAR",
    "NAO_LOCALIZADO",
    "NAO_DESEJA_CONTATO",
]

STATUS_LABEL = {
    "SEPARADO": "📦 Separado",
    "EM_ROTA": "🚚 Em rota",
    "ENTREGUE": "✅ Entregue",
    "REAGENDAR": "📅 Reagendar",
    "NAO_LOCALIZADO": "📍 Não localizado",
    "NAO_DESEJA_CONTATO": "🚫 Não deseja contato",
}

STATUS_CLASSE = {
    "SEPARADO": "status-separado",
    "EM_ROTA": "status-rota",
    "ENTREGUE": "status-entregue",
    "REAGENDAR": "status-reagendar",
    "NAO_LOCALIZADO": "status-problema",
    "NAO_DESEJA_CONTATO": "status-bloqueado",
}

# =========================================================
# IDENTIDADE VISUAL
# =========================================================
st.markdown(
    """
    <style>
        .stApp { background-color: #0A1C2E !important; }
        [data-testid="stMainBlockContainer"] { max-width: 780px; padding-top: 4.25rem !important; padding-bottom: 3rem; }
        h1, h2, h3, h4, p, label, div.stMarkdown, div[data-testid="stMetric"] { color: #FFFFFF !important; }
        [data-testid="stCaptionContainer"] p { color: #B8C8D9 !important; }
        div[data-baseweb="select"] > div, textarea { background-color: #152B45 !important; color: #FFFFFF !important; border-color: #315A82 !important; }
        [data-testid="stTextInput"] div[data-baseweb="input"],
        [data-testid="stTextInput"] div[data-baseweb="input"] > div,
        [data-testid="stTextInput"] input { background-color: #F5F7FA !important; }
        [data-testid="stTextInput"] input, [data-testid="stTextInput"] input:focus { color: #0A1C2E !important; caret-color: #0A1C2E !important; -webkit-text-fill-color: #0A1C2E !important; }
        [data-testid="stTextInput"] input::placeholder { color: #66788A !important; -webkit-text-fill-color: #66788A !important; opacity: 1 !important; }
        [data-testid="stTextArea"] textarea, [data-testid="stNumberInput"] input { color: #FFFFFF !important; }
        [data-testid="stVerticalBlockBorderWrapper"] { background: #122943; border: 1px solid #284A6B !important; border-radius: 14px !important; box-shadow: 0 8px 18px rgba(0,0,0,.16); }
        [data-testid="stMetric"] { background: #122943; border: 1px solid #284A6B; border-radius: 12px; padding: .65rem .8rem; }
        [data-testid="stMetricLabel"] p { color: #B8C8D9 !important; font-size: .78rem !important; }
        [data-testid="stMetricValue"] { color: #FFFFFF !important; }
        .status-chip { display:inline-block; padding:.25rem .62rem; border-radius:999px; font-weight:700; font-size:.76rem; margin-bottom:.4rem; }
        .status-separado { background:#244666; color:#DCEBFA; }
        .status-rota { background:#0C5EAF; color:#FFFFFF; }
        .status-entregue { background:#147A42; color:#FFFFFF; }
        .status-reagendar { background:#8A6412; color:#FFFFFF; }
        .status-problema { background:#9C3B3B; color:#FFFFFF; }
        .status-bloqueado { background:#5D6470; color:#FFFFFF; }
        .endereco-principal { font-size:1.02rem; font-weight:700; color:#FFFFFF; line-height:1.35; }
        .cabecalho-operacao { background:linear-gradient(135deg,#102A45 0%,#183C60 100%); border:1px solid #315A82; border-radius:14px; padding:.9rem 1rem; margin-bottom:.8rem; }
        .cabecalho-operacao strong { color:#FFFFFF; } .cabecalho-operacao span { color:#B8C8D9; }
        .stButton > button, [data-testid="stDownloadButton"] button { min-height:44px; border-radius:9px !important; font-weight:700 !important; background:#1769C2 !important; border:1px solid #4B8ED6 !important; color:#FFFFFF !important; }
        .stButton > button p, .stButton > button span, [data-testid="stDownloadButton"] button p, [data-testid="stDownloadButton"] button span { color:#FFFFFF !important; }
        .botao-link-acao { display:flex; align-items:center; justify-content:center; width:100%; min-height:44px; box-sizing:border-box; padding:.55rem .7rem; border:1px solid #3D6790; border-radius:9px; color:#FFFFFF !important; font-weight:700; line-height:1.15; text-align:center; text-decoration:none !important; }
        .botao-rota { background:#1769C2; } .botao-whatsapp { background:#147A42; } .botao-telefone { background:#244666; }
        hr { border-color:#284A6B !important; }
        @media (max-width:640px) { [data-testid="stMainBlockContainer"] { padding-left:.75rem; padding-right:.75rem; padding-top:4rem !important; } h1{font-size:1.65rem!important;} h2{font-size:1.35rem!important;} h3{font-size:1.12rem!important;} }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# UTILITÁRIOS
# =========================================================
def agora_acre():
    return datetime.now(FUSO_ACRE)


def texto_limpo(valor):
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"nan", "none", "nat", "<na>"}:
        return ""
    return texto


def normalizar_texto(valor):
    texto = texto_limpo(valor)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().upper()


def inteiro_seguro(valor):
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return 0


def configuracao_central():
    try:
        base_url = str(st.secrets["CENTRAL_API_URL"]).strip().rstrip("/")
        api_key = str(st.secrets["LOGISTICS_API_KEY"]).strip()
    except Exception as erro:
        raise RuntimeError(
            "Inclua CENTRAL_API_URL e LOGISTICS_API_KEY nos Secrets do App de Logística."
        ) from erro
    if not base_url or not api_key:
        raise RuntimeError("CENTRAL_API_URL e LOGISTICS_API_KEY não podem ficar vazios.")
    return base_url, api_key


def api_headers():
    _, api_key = configuracao_central()
    return {"x-logistics-key": api_key, "Accept": "application/json", "Content-Type": "application/json"}


def erro_api(resposta):
    try:
        payload = resposta.json()
        return payload.get("error", {}).get("message") or payload.get("message") or resposta.text
    except Exception:
        return resposta.text or f"HTTP {resposta.status_code}"


def gerar_link_mapa(endereco):
    params = urllib.parse.urlencode({"api": "1", "destination": endereco, "travelmode": "driving", "dir_action": "navigate"})
    return f"https://www.google.com/maps/dir/?{params}"


def gerar_link_rota_multipla(enderecos):
    enderecos = [texto_limpo(e) for e in enderecos if texto_limpo(e)][:4]
    if not enderecos:
        return ""
    params = {"api": "1", "destination": enderecos[-1], "travelmode": "driving", "dir_action": "navigate"}
    if len(enderecos) > 1:
        params["waypoints"] = "|".join(enderecos[:-1])
    return "https://www.google.com/maps/dir/?" + urllib.parse.urlencode(params)


def gerar_link_whatsapp(telefone_normalizado, nome, motorista):
    primeiro_nome = texto_limpo(nome).split()[0] if texto_limpo(nome) else ""
    saudacao = f"Olá, {primeiro_nome}!" if primeiro_nome else "Olá!"
    mensagem = (
        f"{saudacao} Aqui é {motorista}, da equipe do Samir Bestene. "
        "Estou organizando a entrega dos materiais que você solicitou. "
        "Posso confirmar se você está no endereço informado no cadastro?"
    )
    telefone = re.sub(r"\D", "", texto_limpo(telefone_normalizado))
    if telefone and not telefone.startswith("55"):
        telefone = "55" + telefone
    return f"https://api.whatsapp.com/send?phone={telefone}&text={urllib.parse.quote(mensagem)}"


def renderizar_link_acao(rotulo, url, classe="botao-rota", nova_aba=True):
    destino = html.escape(texto_limpo(url), quote=True)
    texto = html.escape(texto_limpo(rotulo))
    alvo = "_blank" if nova_aba else "_self"
    st.markdown(
        f'<a class="botao-link-acao {classe}" href="{destino}" target="{alvo}" rel="noopener noreferrer">{texto}</a>',
        unsafe_allow_html=True,
    )

# =========================================================
# API DA CENTRAL
# =========================================================
@st.cache_data(ttl=15, show_spinner=False)
def carregar_entregas_api(statuses="SEPARADO,EM_ROTA,REAGENDAR,NAO_LOCALIZADO"):
    base_url, _ = configuracao_central()
    try:
        response = requests.get(
            f"{base_url}/api/logistics/deliveries",
            headers=api_headers(),
            params={"status": statuses, "limit": 250},
            timeout=12,
        )
    except requests.RequestException as erro:
        raise RuntimeError(f"Não foi possível conectar à Central de Materiais: {erro}") from erro
    if response.status_code != 200:
        raise RuntimeError(f"Central respondeu com erro: {erro_api(response)}")
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("error", {}).get("message", "Falha ao carregar entregas."))
    return payload.get("results", [])


def atualizar_entrega_api(entrega, novo_status, observacao, motorista, usuario):
    base_url, _ = configuracao_central()
    try:
        response = requests.patch(
            f"{base_url}/api/logistics/deliveries/{entrega['id_delivery']}/status",
            headers=api_headers(),
            json={
                "status": novo_status,
                "driverName": motorista,
                "driverUser": usuario,
                "observation": texto_limpo(observacao),
            },
            timeout=12,
        )
    except requests.RequestException as erro:
        st.error(f"Não foi possível comunicar a atualização à Central: {erro}")
        return
    if response.status_code != 200:
        st.error(erro_api(response))
        return
    carregar_entregas_api.clear()
    st.session_state["mensagem_operacao"] = f"Entrega de {entrega['order']['name']} atualizada para {STATUS_LABEL.get(novo_status, novo_status)}."
    st.rerun()


def preparar_dataframe(entregas):
    registros = []
    for entrega in entregas:
        pedido = entrega.get("order", {})
        itens = pedido.get("items", [])
        solicitacao = ", ".join(
            f"{item.get('material_name', 'Material')}: {inteiro_seguro(item.get('separated_qty') or item.get('approved_qty'))}"
            for item in itens
        )
        registros.append({
            "ID_ENTREGA": entrega.get("id_delivery", ""),
            "STATUS": entrega.get("delivery_status", "SEPARADO"),
            "MOTORISTA": texto_limpo(entrega.get("driver_name")),
            "USUARIO_MOTORISTA": texto_limpo(entrega.get("driver_user")),
            "TENTATIVAS": inteiro_seguro(entrega.get("attempts")),
            "OBSERVACAO": texto_limpo(entrega.get("observation")),
            "ATUALIZADO_EM": texto_limpo(entrega.get("updated_at")),
            "ID_PEDIDO": pedido.get("id_order", ""),
            "NOME": pedido.get("name", "Nome não informado"),
            "TELEFONE_EXIBICAO": pedido.get("phone", ""),
            "TELEFONE_E164": pedido.get("normalized_phone", ""),
            "MUNICIPIO": pedido.get("municipality", ""),
            "BAIRRO": pedido.get("neighborhood", ""),
            "ENDERECO_COMPLETO": pedido.get("full_address", ""),
            "COMPLEMENTO": pedido.get("complement", ""),
            "SOLICITACAO": solicitacao,
            "ITENS": itens,
            "_RAW": entrega,
        })
    return pd.DataFrame(registros)

# =========================================================
# LOG DE ACESSO (OPCIONAL, PRESERVA PLANILHA EXISTENTE)
# =========================================================
def registrar_acesso(usuario):
    try:
        if gspread is None or Credentials is None:
            return
        spreadsheet_id = "1pZw4r8rAVMUnI7O73vEHk5Aj6uJUjDEsUegAWIrQFxE"
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_json" in st.secrets:
            info = json.loads(str(st.secrets["gcp_json"]))
        elif "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
        else:
            return
        if isinstance(info.get("private_key"), str) and "\\n" in info["private_key"]:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        ws = gspread.authorize(creds).open_by_key(spreadsheet_id).worksheet("Logs_Acesso")
        agora = agora_acre()
        motorista = MOTORISTA_POR_USUARIO.get(usuario)
        identificacao = f"{motorista or usuario} (Logística Central)"
        ws.append_row([identificacao, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M:%S")], value_input_option="RAW")
    except Exception as erro:
        print(f"Falha ao registrar acesso: {erro}")

# =========================================================
# LOGIN
# =========================================================
def verificar_login():
    if st.session_state.get("autenticado_logistica"):
        return True
    st.markdown("## 🔐 Acesso da equipe de logística")
    st.caption("Entre com o usuário e a senha cadastrados nos Secrets do Streamlit.")
    try:
        senhas = dict(st.secrets["senhas"])
    except Exception:
        st.error("A seção [senhas] não foi encontrada nos Secrets do Streamlit.")
        return False
    usuario = st.text_input("Usuário", key="login_usuario").strip()
    senha = st.text_input("Senha", type="password", key="login_senha")
    if st.button("Entrar", type="primary", use_container_width=True):
        senha_cadastrada = str(senhas.get(usuario, ""))
        if usuario in senhas and hmac.compare_digest(senha, senha_cadastrada):
            st.session_state["autenticado_logistica"] = True
            st.session_state["usuario_logistica"] = usuario
            registrar_acesso(usuario)
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")
    return False


def encerrar_sessao():
    for chave in ["autenticado_logistica", "usuario_logistica", "login_usuario", "login_senha"]:
        st.session_state.pop(chave, None)
    st.rerun()

# =========================================================
# LOGO
# =========================================================
@st.cache_resource
def carregar_logo_recortada(caminho):
    imagem = Image.open(caminho).convert("RGBA")
    caixa = imagem.getchannel("A").getbbox()
    if caixa:
        imagem = imagem.crop(caixa)
    return imagem


def exibir_logo():
    caminho = Path(ARQUIVO_LOGO)
    if not caminho.exists():
        st.markdown("<h2 style='text-align:center;margin-bottom:0;'>SAMIR BESTENE</h2>", unsafe_allow_html=True)
        return
    _, col_logo, _ = st.columns([1, 1.35, 1])
    with col_logo:
        st.image(carregar_logo_recortada(str(caminho)), use_container_width=True)

# =========================================================
# MANIFESTO E FILTROS
# =========================================================
def criar_manifesto(df):
    if df.empty:
        return b""
    cols = ["ID_ENTREGA", "STATUS", "MOTORISTA", "ID_PEDIDO", "NOME", "TELEFONE_EXIBICAO", "MUNICIPIO", "BAIRRO", "ENDERECO_COMPLETO", "COMPLEMENTO", "SOLICITACAO", "OBSERVACAO", "TENTATIVAS"]
    manifesto = df[cols].copy()
    manifesto.columns = ["ID Entrega", "Status", "Motorista", "Pedido", "Nome", "Telefone", "Município", "Bairro", "Endereço", "Complemento", "Materiais", "Observação", "Tentativas"]
    return manifesto.to_csv(index=False).encode("utf-8-sig")


def ordenar_entregas(df, criterio):
    if df.empty:
        return df
    df = df.copy()
    if criterio == "Bairro e endereço":
        return df.sort_values(["MUNICIPIO", "BAIRRO", "ENDERECO_COMPLETO", "NOME"])
    if criterio == "Status e bairro":
        ordem = {s: i for i, s in enumerate(STATUS)}
        df["ORDEM_STATUS"] = df["STATUS"].map(ordem).fillna(99)
        return df.sort_values(["ORDEM_STATUS", "MUNICIPIO", "BAIRRO", "NOME"])
    return df.sort_values(["ATUALIZADO_EM", "NOME"], ascending=[False, True])

# =========================================================
# APLICAÇÃO
# =========================================================
exibir_logo()
if not verificar_login():
    st.stop()

usuario_logado = st.session_state.get("usuario_logistica", "")
motorista_padrao = MOTORISTA_POR_USUARIO.get(usuario_logado)
motorista = motorista_padrao or st.selectbox("Motorista responsável:", MOTORISTAS)

st.markdown("## 📦 Operação de Entrega de Materiais")
st.caption(f"Central integrada • versão {VERSAO_APP}")
st.markdown(
    f'<div class="cabecalho-operacao"><strong>🚚 Motorista: {html.escape(motorista)}</strong><br><span>Usuário conectado: {html.escape(usuario_logado)}</span></div>',
    unsafe_allow_html=True,
)

c1, c2 = st.columns(2)
with c1:
    if st.button("🔄 Atualizar dados", use_container_width=True):
        carregar_entregas_api.clear()
        st.rerun()
with c2:
    if st.button("Sair", use_container_width=True):
        encerrar_sessao()

if st.session_state.get("mensagem_operacao"):
    st.success(st.session_state.pop("mensagem_operacao"))

try:
    with st.spinner("Buscando entregas prontas na Central..."):
        entregas_api = carregar_entregas_api()
        entregas = preparar_dataframe(entregas_api)
except Exception as erro:
    st.error("Não foi possível consultar a Central de Materiais.")
    st.warning("Confirme se a Central está ligada e se CENTRAL_API_URL e LOGISTICS_API_KEY estão corretos.")
    with st.expander("Detalhes técnicos"):
        st.code(f"{type(erro).__name__}: {erro}")
    st.stop()

if entregas.empty:
    st.info("Nenhum pedido separado está disponível para entrega neste momento.")
    st.stop()

st.markdown("---")
st.subheader("🔎 Filtros da rota")

# Visão de trabalho: pedidos sem motorista + pedidos já assumidos pelo usuário/motorista.
visao = st.selectbox("Fila:", ["Disponíveis e minhas", "Somente disponíveis", "Minhas entregas", "Todas em andamento"])
base = entregas.copy()
if visao == "Somente disponíveis":
    base = base[base["MOTORISTA"].eq("")]
elif visao == "Minhas entregas":
    base = base[(base["USUARIO_MOTORISTA"] == usuario_logado) | (base["MOTORISTA"] == motorista)]
elif visao == "Disponíveis e minhas":
    base = base[base["MOTORISTA"].eq("") | (base["USUARIO_MOTORISTA"] == usuario_logado) | (base["MOTORISTA"] == motorista)]

municipios = sorted(x for x in base["MUNICIPIO"].fillna("").unique() if x)
municipio = st.selectbox("Município:", ["Todos os municípios"] + municipios)
if municipio != "Todos os municípios":
    base = base[base["MUNICIPIO"] == municipio]

bairros = sorted(x for x in base["BAIRRO"].fillna("").unique() if x)
bairro = st.selectbox("Bairro:", ["Todos os bairros"] + bairros)
if bairro != "Todos os bairros":
    base = base[base["BAIRRO"] == bairro]

busca = st.text_input("Pesquisar:", placeholder="Nome, telefone, pedido, rua, bairro ou município")
if busca.strip():
    termo = normalizar_texto(busca)
    cols_busca = ["NOME", "TELEFONE_EXIBICAO", "ID_PEDIDO", "MUNICIPIO", "BAIRRO", "ENDERECO_COMPLETO"]
    mask = base[cols_busca].fillna("").astype(str).apply(lambda r: termo in normalizar_texto(" ".join(r)), axis=1)
    base = base[mask]

criterio = st.selectbox("Ordenar por:", ["Bairro e endereço", "Atualização mais recente", "Status e bairro"])
base = ordenar_entregas(base, criterio)

m1, m2 = st.columns(2)
m1.metric("Entregas exibidas", len(base))
m2.metric("Separadas", int((base["STATUS"] == "SEPARADO").sum()))
m3, m4 = st.columns(2)
m3.metric("Em rota", int((base["STATUS"] == "EM_ROTA").sum()))
m4.metric("Ocorrências", int(base["STATUS"].isin(["REAGENDAR", "NAO_LOCALIZADO"]).sum()))

col_manifesto, col_rota = st.columns(2)
with col_manifesto:
    st.download_button("⬇️ Baixar manifesto", data=criar_manifesto(base), file_name=f"manifesto_central_{agora_acre():%Y%m%d_%H%M}.csv", mime="text/csv", use_container_width=True, disabled=base.empty)
enderecos_rota = base[~base["STATUS"].isin(["ENTREGUE", "NAO_DESEJA_CONTATO"])]["ENDERECO_COMPLETO"].head(4).tolist()
link_rota = gerar_link_rota_multipla(enderecos_rota)
with col_rota:
    if link_rota:
        renderizar_link_acao("🧭 Rota de até 4 paradas", link_rota, "botao-rota")
    else:
        st.button("🧭 Sem rota disponível", disabled=True, use_container_width=True)

st.markdown("---")
if base.empty:
    st.info("Nenhuma entrega encontrada para os filtros selecionados.")
    st.stop()

itens_por_pagina = st.selectbox("Entregas por página:", [10, 20, 30], index=1)
total_paginas = max(1, math.ceil(len(base) / itens_por_pagina))
if st.session_state.get("pagina_entregas", 1) > total_paginas:
    st.session_state["pagina_entregas"] = 1
pagina = st.number_input("Página:", min_value=1, max_value=total_paginas, step=1, key="pagina_entregas")
inicio = (pagina - 1) * itens_por_pagina
pagina_df = base.iloc[inicio:inicio + itens_por_pagina]

for numero, (_, row) in enumerate(pagina_df.iterrows(), start=inicio + 1):
    entrega = row["_RAW"]
    status_atual = row["STATUS"]
    with st.container(border=True):
        st.markdown(f'<span class="status-chip {STATUS_CLASSE.get(status_atual, "status-separado")}">{STATUS_LABEL.get(status_atual, status_atual)}</span>', unsafe_allow_html=True)
        st.markdown(f"### {numero:02d}. {row['NOME']}")
        st.caption(f"Pedido {row['ID_PEDIDO']} • Entrega {row['ID_ENTREGA']}")
        st.markdown(f'<div class="endereco-principal">📍 {html.escape(row["ENDERECO_COMPLETO"])}</div>', unsafe_allow_html=True)
        if row["COMPLEMENTO"]:
            st.write(f"💬 **Referência:** {row['COMPLEMENTO']}")
        st.write(f"📦 **Materiais separados:** {row['SOLICITACAO']}")
        st.write(f"📞 **Telefone:** {row['TELEFONE_EXIBICAO']}")
        if row["MOTORISTA"]:
            st.caption(f"Motorista: {row['MOTORISTA']} • Tentativas: {row['TENTATIVAS']}")
        if row["OBSERVACAO"]:
            st.info(f"Observação registrada: {row['OBSERVACAO']}")

        ca, cb = st.columns(2)
        with ca:
            renderizar_link_acao("🧭 Iniciar navegação", gerar_link_mapa(row["ENDERECO_COMPLETO"]), "botao-rota")
        with cb:
            if row["TELEFONE_E164"] and status_atual != "NAO_DESEJA_CONTATO":
                renderizar_link_acao("💬 WhatsApp", gerar_link_whatsapp(row["TELEFONE_E164"], row["NOME"], motorista), "botao-whatsapp")
            else:
                st.button("💬 Contato indisponível", disabled=True, use_container_width=True, key=f"wpp_{row['ID_ENTREGA']}")
        if row["TELEFONE_E164"] and status_atual != "NAO_DESEJA_CONTATO":
            renderizar_link_acao("📞 Ligar", f"tel:+{re.sub(r'\D', '', row['TELEFONE_E164'])}", "botao-telefone", nova_aba=False)

        if status_atual != "ENTREGUE":
            cr, ce = st.columns(2)
            with cr:
                if st.button("🚚 Marcar em rota", use_container_width=True, disabled=status_atual == "EM_ROTA", key=f"rota_{row['ID_ENTREGA']}"):
                    atualizar_entrega_api(entrega, "EM_ROTA", row["OBSERVACAO"], motorista, usuario_logado)
            with ce:
                if st.button("✅ Confirmar entrega", type="primary", use_container_width=True, key=f"entregue_{row['ID_ENTREGA']}"):
                    atualizar_entrega_api(entrega, "ENTREGUE", row["OBSERVACAO"], motorista, usuario_logado)

        with st.expander("📝 Atualizar situação da entrega"):
            opcoes = ["SEPARADO", "EM_ROTA", "ENTREGUE", "REAGENDAR", "NAO_LOCALIZADO", "NAO_DESEJA_CONTATO"]
            indice = opcoes.index(status_atual) if status_atual in opcoes else 0
            novo_status = st.selectbox("Situação:", opcoes, index=indice, format_func=lambda v: STATUS_LABEL[v], key=f"status_{row['ID_ENTREGA']}")
            observacao = st.text_area("Observação:", value=row["OBSERVACAO"], placeholder="Ex.: morador ausente; retornar após 18h.", key=f"obs_{row['ID_ENTREGA']}")
            if st.button("Salvar atualização", type="primary", use_container_width=True, key=f"salvar_{row['ID_ENTREGA']}"):
                atualizar_entrega_api(entrega, novo_status, observacao, motorista, usuario_logado)

st.markdown("---")
st.caption("As entregas desta tela vêm diretamente da Central de Materiais. Alterações de situação são registradas no D1 e atualizam o acompanhamento público do pedido.")
