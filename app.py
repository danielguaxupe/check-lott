import streamlit as st
import requests
import time
import re

st.set_page_config(
    page_title="Conferidor de Loterias CAIXA",
    page_icon="🍀",
    layout="centered"
)

API_BASE = "https://loteriascaixa-api.herokuapp.com/api"

def fmt_lista(lista):
    if not lista: return "[]"
    itens = ", ".join([f"{int(d):02d}" for d in sorted(list(lista))])
    return f"[{itens}]"

def normalizar_nome(nome):
    nome = nome.lower().strip()
    mapa = {
        "mega-sena": "megasena", "lotofácil": "lotofacil", "quina": "quina",
        "lotomania": "lotomania", "dupla-sena": "duplasena", "mais-milionária": "maismilionaria",
        "+milionária": "maismilionaria", "mais milionária": "maismilionaria"
    }
    for chave, valor in mapa.items():
        if chave in nome: return valor
    return nome

def parse_valor(val):
    if val is None: return None, 0.0
    if isinstance(val, (int, float)):
        if val <= 0: return None, 0.0
        fmt = f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return fmt, float(val)
    elif isinstance(val, str):
        val_clean = val.strip().replace("R$", "").strip()
        if not val_clean or val_clean in ["0,00", "0.00", "0"]: return None, 0.0
        try:
            num_str = val_clean.replace(".", "").replace(",", ".")
            f_val = float(num_str)
        except: f_val = 0.0
        fmt = f"R$ {val_clean}" if not val_clean.startswith("R$") else val_clean
        return fmt, f_val
    return None, 0.0

def extrair_valor(loteria, acertos, trevos, res, sorteio_idx=None):
    premiacoes = res.get('premiacoes') or res.get('listaRateio', [])
    if not premiacoes: return None, 0.0
    if loteria == "duplasena" and sorteio_idx is not None:
        premiacoes = premiacoes[0:4] if sorteio_idx == 0 else premiacoes[4:8]
    for f in premiacoes:
        desc = f.get('descricao', '').lower()
        val = f.get('valorPremio') if f.get('valorPremio') is not None else f.get('valor')
        if f"{acertos} acertos" in desc: return parse_valor(val)
        if loteria == "maismilionaria" and f"{acertos}+{trevos}" in desc.replace(" ", ""): return parse_valor(val)
    return None, 0.0

def verificar_faixa_premio(loteria, acertos, trevos=0):
    if loteria == "megasena": return acertos >= 4
    elif loteria == "lotofacil": return acertos >= 11
    elif loteria == "quina": return acertos >= 2
    elif loteria == "lotomania": return acertos >= 15 or acertos == 0
    elif loteria == "duplasena": return acertos >= 3
    elif loteria == "maismilionaria":
        if trevos == 2: return acertos >= 2
        elif trevos == 1: return acertos >= 3
        elif trevos == 0: return acertos == 6
        return False
    return False

# Inicializa a memória da sessão para os jogos
if "lista_jogos" not in st.session_state:
    st.session_state.lista_jogos = []

st.title("🍀 Gerenciador & Conferidor de Loterias")

aba = st.radio("Escolha o modo:", ["📝 Criar / Gerenciar Meus Jogos", "🚀 Conferir Resultados"], horizontal=True)

mapa_nomes = {
    "megasena": "Mega-Sena", "quina": "Quina", "duplasena": "Dupla-Sena",
    "lotofacil": "Lotofácil", "lotomania": "Lotomania", "maismilionaria": "Mais Milionária"
}

if aba == "📝 Criar / Gerenciar Meus Jogos":
    st.subheader("🎛️ Volante Digital (Adicionar Novo Jogo)")
    
    col1, col2 = st.columns(2)
    with col1:
        loteria_escolhida = st.selectbox("Loteria", ["Mega-Sena", "Lotofácil", "Quina", "Lotomania", "Dupla-Sena", "Mais Milionária"])
    with col2:
        tipo_conc = st.radio("Intervalo de Concursos", ["Concurso Único", "Faixa de Concursos"])
        
    c_ini, c_fim = 1, 1
    if tipo_conc == "Concurso Único":
        c_ini = st.number_input("Número do Concurso", min_value=1, value=3000, step=1)
        c_fim = c_ini
    else:
        c_col1, c_col2 = st.columns(2)
        with c_col1: c_ini = st.number_input("Concurso Inicial", min_value=1, value=3000, step=1)
        with c_col2: c_fim = st.number_input("Concurso Final", min_value=1, value=3010, step=1)

    max_num = 60
    if loteria_escolhida == "Lotofácil": max_num = 25
    elif loteria_escolhida == "Quina": max_num = 80
    elif loteria_escolhida in ["Lotomania", "Mais Milionária"]: max_num = 50
    elif loteria_escolhida == "Dupla-Sena": max_num = 50

    st.write(f"Selecione seus números para a **{loteria_escolhida}**:")
    numeros_selecionados = st.multiselect("Dezenas apostadas", options=list(range(1, max_num + 1)), format_func=lambda x: f"{x:02d}")
    
    trevos_selecionados = []
    if loteria_escolhida == "Mais Milionária":
        st.write("Selecione os Trevos (1 a 6):")
        trevos_selecionados = st.multiselect("Trevos", options=list(range(1, 7)), format_func=lambda x: f"{x:02d}")

    if st.button("➕ Adicionar este Jogo à Lista", type="primary"):
        if not numeros_selecionados:
            st.warning("⚠️ Selecione pelo menos um número.")
        else:
            lot_key = normalizar_nome(loteria_escolhida)
            nums_str = ",".join([f"{d:02d}" for d in sorted(numeros_selecionados)])
            
            linha_texto = f"{loteria_escolhida} {c_ini}"
            if c_ini != c_fim:
                linha_texto += f" a {c_fim}"
            
            if trevos_selecionados:
                trevos_str = ",".join([f"{t:02d}" for t in sorted(trevos_selecionados)])
                linha_texto += f" = {nums_str}-{trevos_str}"
            else:
                linha_texto += f" = {nums_str}"

            st.session_state.lista_jogos.append({
                "linha": linha_texto,
                "loteria": lot_key,
                "conc_ini": c_ini,
                "conc_fim": c_fim,
                "aposta": sorted(numeros_selecionados),
                "trevos": sorted(trevos_selecionados)
            })
            st.success("✅ Jogo adicionado com sucesso!")

    st.markdown("---")
    st.subheader("📋 Seus Jogos Cadastrados Atualmente")
    
    if not st.session_state.lista_jogos:
        st.info("Nenhum jogo cadastrado ainda. Use o volante acima ou envie um arquivo de texto abaixo.")
    else:
        for idx, j in enumerate(st.session_state.lista_jogos):
            col_a, col_b = st.columns([5, 1])
            with col_a:
                st.text(f"[{idx+1}] {j['linha']}")
            with col_b:
                if st.button("🗑️ Excluir", key=f"del_{idx}"):
                    st.session_state.lista_jogos.pop(idx)
                    st.rerun()

        texto_arquivo = "\n".join([j['linha'] for j in st.session_state.lista_jogos]) + "\nHISTÓRICO:"
        st.download_button(
            label="💾 Baixar arquivo 'jogos.txt' para salvar no celular",
            data=texto_arquivo,
            file_name="jogos.txt",
            mime="text/plain"
        )

    st.markdown("---")
    st.write("Ou, se preferir carregar um arquivo `jogos.txt` pronto que você já tinha:")
    arquivo_up = st.file_uploader("Enviar jogos.txt existente", type=["txt"])
    if arquivo_up:
        conteudo = arquivo_up.getvalue().decode("utf-8")
        linhas_lidas = conteudo.splitlines()
        for idx, linha in enumerate(linhas_lidas):
            linha = linha.strip()
            if not linha or "HISTÓRICO:" in linha.upper(): break
            try:
                match = re.match(r"(.+?)\s+(\d+)(?:\s+a\s+(\d+))?\s*=\s*(.+)", linha)
                if match:
                    lot_bruta, c_ini, c_fim, dezenas_raw = match.groups()
                    lot = normalizar_nome(lot_bruta)
                    c_fim = int(c_fim) if c_fim else int(c_ini)
                    if "-" in dezenas_raw: d_str, t_str = dezenas_raw.split("-")
                    elif "/" in dezenas_raw: d_str, t_str = dezenas_raw.split("/")
                    else: d_str, t_str = dezenas_raw, ""
                    
                    st.session_state.lista_jogos.append({
                        "linha": linha,
                        "loteria": lot,
                        "conc_ini": int(c_ini),
                        "conc_fim": c_fim,
                        "aposta": [int(d) for d in d_str.split(",") if d.strip().isdigit()],
                        "trevos": [int(t) for t in t_str.split(",") if t.strip().isdigit()]
                    })
            except: continue
        st.success("✅ Arquivo importado com sucesso! Vá para a aba 'Conferir Resultados'.")

else:
    st.subheader("🚀 Conferência de Jogos")
    
    # Permite também carregar o arquivo direto na hora da conferência caso queira
    arquivo_conf_up = st.file_uploader("📂 Enviar arquivo jogos.txt para conferência rápida", type=["txt"], key="conf_up")
    if arquivo_conf_up:
        conteudo_conf = arquivo_conf_up.getvalue().decode("utf-8")
        st.session_state.lista_jogos = []
        for idx, linha in enumerate(conteudo_conf.splitlines()):
            linha = linha.strip()
            if not linha or "HISTÓRICO:" in linha.upper(): break
            try:
                match = re.match(r"(.+?)\s+(\d+)(?:\s+a\s+(\d+))?\s*=\s*(.+)", linha)
                if match:
                    lot_bruta, c_ini, c_fim, dezenas_raw = match.groups()
                    lot = normalizar_nome(lot_bruta)
                    c_fim = int(c_fim) if c_fim else int(c_ini)
                    if "-" in dezenas_raw: d_str, t_str = dezenas_raw.split("-")
                    elif "/" in dezenas_raw: d_str, t_str = dezenas_raw.split("/")
                    else: d_str, t_str = dezenas_raw, ""
                    
                    st.session_state.lista_jogos.append({
                        "id_bilhete": idx,
                        "linha": linha,
                        "loteria": lot,
                        "conc_ini": int(c_ini),
                        "conc_fim": c_fim,
                        "aposta": [int(d) for d in d_str.split(",") if d.strip().isdigit()],
                        "trevos": [int(t) for t in t_str.split(",") if t.strip().isdigit()]
                    })
            except: continue

    if not st.session_state.lista_jogos:
        st.warning("⚠️ Nenhum jogo cadastrado. Vá na aba 'Criar / Gerenciar Meus Jogos' ou envie um arquivo acima.")
    else:
        # Garante id_bilhete para todos
        for i, j in enumerate(st.session_state.lista_jogos):
            if "id_bilhete" not in j:
                j["id_bilhete"] = i

        if st.button("▶️ Iniciar Conferência Agora", type="primary"):
            meus_jogos = st.session_state.lista_jogos
            api_cache = {}
            st.markdown("---")
            status_container = st.container()

            resumo_premiados = []
            concursos_premiados_set = set()
            bilhetes_premiados_dict = {}

            for j in meus_jogos:
                lot = j['loteria']
                nome_lot = mapa_nomes.get(lot, lot.upper())
                nums_fmt = fmt_lista(j['aposta'])
                trevos_str = f" | Trevos: {fmt_lista(j['trevos'])}" if j['trevos'] else ""
                
                with status_container:
                    st.markdown(f"**{nome_lot}** — Jogados: `{nums_fmt}`{trevos_str}")
                
                for c in range(j['conc_ini'], j['conc_fim'] + 1):
                    cache_key = (lot, c)
                    if cache_key not in api_cache:
                        try:
                            res = requests.get(f"{API_BASE}/{lot}/{c}", timeout=10).json()
                            if "error" not in res and "dezenas" in res:
                                api_cache[cache_key] = res
                            else:
                                api_cache[cache_key] = None
                            time.sleep(0.02)
                        except:
                            api_cache[cache_key] = None
                    
                    res = api_cache[cache_key]
                    if not res: continue
                        
                    data_str = res.get('data', res.get('dataApuracao', 'N/A'))
                    dezs = res.get('dezenas', [])
                    
                    sorteios = []
                    if lot == "duplasena" and len(dezs) >= 12:
                        sorteios.append((" (1º Sorteio)", dezs[0:6], 0))
                        sorteios.append((" (2º Sorteio)", dezs[6:12], 1))
                    else:
                        sorteios = [("", dezs, None)]

                    for prefixo, sorteado_raw, s_idx in sorteios:
                        sorteados = [int(d) for d in sorteado_raw]
                        hits = set(j['aposta']).intersection(set(sorteados))
                        ac_t = 0
                        t_sort = []
                        if lot == "maismilionaria":
                            t_sort = [int(t) for t in res.get('trevos', [])]
                            ac_t = len(set(j['trevos']).intersection(set(t_sort)))

                        is_win = verificar_faixa_premio(lot, len(hits), ac_t)
                        valor_str, valor_num = extrair_valor(lot, len(hits), ac_t, res, s_idx)
                        
                        premio_txt = f" | 💰 Prêmio: {valor_str}" if valor_str else (" | 💰 Prêmio: Não informado" if is_win else "")
                        trevos_res_txt = f" | Trevos: {t_sort}" if lot == "maismilionaria" else ""
                        
                        with status_container:
                            if is_win:
                                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;✅ **Data: {data_str} | Conc: {c}{prefixo} | Acertos: {len(hits):2d} {fmt_lista(hits)}{trevos_res_txt}{premio_txt}**")
                            else:
                                st.text(f"    Data: {data_str} | Conc: {c}{prefixo} | Acertos: {len(hits):2d} {fmt_lista(hits)}{trevos_res_txt}")

                        if is_win:
                            concursos_premiados_set.add((lot, c))
                            resumo_premiados.append({
                                "id_bilhete": j['id_bilhete'],
                                "loteria": lot,
                                "concurso": c,
                                "info": f"Data: {data_str} | Conc: {c} | {lot.upper()}{prefixo}",
                                "detalhe": f"Sorteados: {fmt_lista(sorteados)}" + (f" | Trevos: {t_sort}" if lot=="maismilionaria" else "") + f"\n    Seus Acertos: {len(hits)} {fmt_lista(hits)}",
                                "valor_str": valor_str,
                                "valor_num": valor_num
                            })
                            
                            if j['id_bilhete'] not in bilhetes_premiados_dict:
                                bilhetes_premiados_dict[j['id_bilhete']] = {
                                    "id_bilhete": j['id_bilhete'],
                                    "loteria": lot,
                                    "soma_num": 0.0,
                                    "tem_desconhecido": False
                                }
                            bilhetes_premiados_dict[j['id_bilhete']]["soma_num"] += valor_num