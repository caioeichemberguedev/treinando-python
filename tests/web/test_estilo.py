"""Testes da folha de estilo (E-022-T1): tokens e base do visual."""
import re

import pytest
from fastapi.testclient import TestClient

from web.main import app

client = TestClient(app)

TOKENS_DA_AUDITORIA = [
    "--cor-fundo",
    "--cor-card",
    "--cor-card-elevado",
    "--cor-linha",
    "--cor-borda",
    "--cor-borda-forte",
    "--cor-texto",
    "--cor-texto-suave",
    "--cor-acido",
    "--cor-link",
    "--cor-primaria",
    "--cor-destaque",
    "--cor-erro",
    "--cor-primaria-clara",
    "--cor-bloco",
    "--fonte-texto",
    "--fonte-numeros",
    "--espacamento",
    "--raio",
    "--raio-pequeno",
]


@pytest.fixture(scope="module")
def css():
    resposta = client.get("/static/css/estilo.css")
    assert resposta.status_code == 200
    return resposta.text


def _bloco(css, seletor):
    """Devolve o corpo do primeiro bloco cujo seletor é exatamente `seletor`."""
    sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    padrao = r"(?:^|\})\s*" + re.escape(seletor) + r"\s*\{([^}]*)\}"
    achado = re.search(padrao, sem_comentarios)
    assert achado, f"bloco {seletor!r} não encontrado"
    return achado.group(1)


def test_css_e_servido():
    resposta = client.get("/static/css/estilo.css")

    assert resposta.status_code == 200
    assert "text/css" in resposta.headers["content-type"]


@pytest.mark.parametrize("token", TOKENS_DA_AUDITORIA)
def test_root_define_os_tokens_da_auditoria(css, token):
    root = _bloco(css, ":root")

    assert re.search(re.escape(token) + r"\s*:", root)


def test_aliases_antigos_apontam_para_os_tokens_novos(css):
    root = _bloco(css, ":root")

    assert re.search(r"--cor-primaria-clara\s*:\s*var\(--cor-link\)", root)
    assert re.search(r"--cor-bloco\s*:\s*var\(--cor-card\)", root)


def test_css_nao_usa_important(css):
    assert "!important" not in css


def test_rodape_nao_usa_cor_da_borda_como_texto(css):
    footer = _bloco(css, "footer")

    assert not re.search(r"(?<![-\w])color\s*:\s*var\(--cor-borda\)", footer)
    assert re.search(r"(?<![-\w])color\s*:\s*var\(--cor-texto-suave\)", footer)


def test_links_usam_a_cor_de_link(css):
    links = _bloco(css, "a")

    assert re.search(r"(?<![-\w])color\s*:\s*var\(--cor-link\)", links)


def test_foco_visivel_global_em_acido(css):
    foco = _bloco(css, ":focus-visible")

    assert "outline: 3px solid var(--cor-acido)" in foco
    assert "outline-offset: 3px" in foco


def test_body_usa_a_fonte_de_texto(css):
    assert "font-family: var(--fonte-texto)" in _bloco(css, "body")


def test_numeros_em_mono_e_tabulares(css):
    assert "font-family: var(--fonte-numeros)" in _bloco(css, "thead th")
    assert "font-variant-numeric: tabular-nums" in _bloco(css, "td")
    assert "font-family: var(--fonte-numeros)" in _bloco(css, ".destaque")


def test_respeita_movimento_reduzido(css):
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_todo_var_usado_esta_definido(css):
    """Token renomeado sem alias faria uma tela perder estilo em silêncio."""
    definidos = set(re.findall(r"(--[\w-]+)\s*:", css))
    usados = set(re.findall(r"var\(\s*(--[\w-]+)", css))

    assert usados - definidos == set()


def test_color_mix_tem_fallback_solido_na_linha_anterior(css):
    linhas = css.splitlines()
    for numero, linha in enumerate(linhas):
        if "color-mix(" not in linha:
            continue
        propriedade = linha.split(":", 1)[0].strip()
        anterior = linhas[numero - 1].strip()

        assert anterior.startswith(propriedade + ":"), linha
        assert "color-mix(" not in anterior, linha


def test_movimento_reduzido_zera_transicoes_e_animacoes(css):
    inicio = css.index("@media (prefers-reduced-motion: reduce)")
    trecho = css[inicio:]

    assert re.search(r"\*,\s*\*::before,\s*\*::after\s*\{[^}]*transition:\s*none", trecho)
    assert re.search(r"\*,\s*\*::before,\s*\*::after\s*\{[^}]*animation:\s*none", trecho)


def test_aliases_nao_apontam_para_si_mesmos(css):
    root = _bloco(css, ":root")

    for nome, alvo in re.findall(r"(--[\w-]+)\s*:\s*var\((--[\w-]+)\)", root):
        assert nome != alvo
        assert re.search(re.escape(alvo) + r"\s*:\s*#[0-9a-fA-F]{6}\s*;", root), alvo


# --- E-022-T3: botões com variantes -------------------------------------------

def test_botao_primario_acido_com_alvo_de_toque(css):
    botao = _bloco(css, ".botao")

    assert "background-color: var(--cor-acido)" in botao
    assert re.search(r"(?<![-\w])color\s*:\s*var\(--cor-fundo\)", botao)
    assert "min-height: 2.75rem" in botao
    assert "display: inline-flex" in botao
    assert "border-radius: var(--raio-pequeno)" in botao


def test_button_botao_sem_visual_nativo(css):
    botao = _bloco(css, ".botao")

    assert "font: inherit" in botao
    assert "cursor: pointer" in botao


def test_hover_do_botao_nao_vira_ambar(css):
    assert "--cor-destaque" not in _bloco(css, ".botao:hover")


@pytest.mark.parametrize("seletor", [".botao-secundario", ".botao-perigo", ".botao-pequeno"])
def test_variantes_de_botao_existem(css, seletor):
    assert _bloco(css, seletor).strip()


def test_secundario_e_perigo_sao_transparentes_com_borda(css):
    secundario = _bloco(css, ".botao-secundario")
    perigo = _bloco(css, ".botao-perigo")

    assert "background-color: transparent" in secundario
    assert "border-color: var(--cor-borda-forte)" in secundario
    assert "background-color: transparent" in perigo
    assert "border-color: var(--cor-erro)" in perigo
    assert re.search(r"(?<![-\w])color\s*:\s*var\(--cor-erro\)", perigo)


def test_botao_pequeno_volta_a_44px_no_celular(css):
    achado = re.search(
        r"@media \(max-width: 40rem\), \(pointer: coarse\)\s*\{\s*\.botao-pequeno\s*\{([^}]*)\}", css
    )

    assert achado
    assert "min-height: 2.75rem" in achado.group(1)


def test_transicao_do_botao_zerada_no_movimento_reduzido(css):
    inicio = css.index("@media (prefers-reduced-motion: reduce)")
    trecho = css[inicio:]

    seletores_zerados = re.findall(r"([^{}]+)\{[^}]*transition:\s*none", trecho)

    assert any(re.search(r"(?<![-\w])\.botao(?![-\w])", sel) for sel in seletores_zerados)


def test_aviso_save_travado_e_card_de_erro(css):
    aviso = _bloco(css, ".aviso-save-travado")

    assert "background-color: var(--cor-card)" in aviso
    assert "var(--cor-erro)" in aviso


@pytest.mark.parametrize("variante", [".botao-secundario", ".botao-perigo", ".botao-pequeno"])
def test_variante_vem_depois_do_botao_na_cascata(css, variante):
    """Mesma especificidade de .botao: a variante só vence se vier depois."""
    sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    pos_botao = re.search(r"(?:^|\})\s*\.botao\s*\{", sem_comentarios).start()
    pos_variante = re.search(r"(?:^|\})\s*" + re.escape(variante) + r"\s*\{", sem_comentarios).start()

    assert pos_botao < pos_variante


@pytest.mark.parametrize("seletor", [".botao-secundario:hover", ".botao-perigo:hover"])
def test_hover_das_variantes_nao_vira_ambar(css, seletor):
    assert "--cor-destaque" not in _bloco(css, seletor)


# --- E-022-T5: componentes de dashboard e home ---------------------------------

COMPONENTES = [
    ".cabecalho-tela",
    ".cards",
    ".card",
    ".card-largo",
    ".card-estreito",
    ".card-destaque",
    ".card-erro",
    ".card > h2",
    ".rotulo",
    ".metricas",
    ".metrica",
    ".metrica dt",
    ".metrica dd",
    ".placar",
    ".placar-gols",
    ".placar-x",
    ".chip",
    ".chip-acido",
    ".chip-destaque",
    ".chip-erro",
    ".opcoes",
    ".opcao",
    ".campo",
    ".erros",
    ".acoes-centro",
    ".numero",
    ".visualmente-oculto",
    ".tabela-rolavel",
]


def _bloco_lista(css, *seletores):
    """Como `_bloco`, para um grupo de seletores separados por vírgula (qualquer quebra de linha)."""
    sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    grupo = r",\s*".join(re.escape(seletor) for seletor in seletores)
    achado = re.search(r"(?:^|\})\s*" + grupo + r"\s*\{([^}]*)\}", sem_comentarios)
    assert achado, f"bloco {seletores!r} não encontrado"
    return achado.group(1)


@pytest.mark.parametrize("seletor", COMPONENTES)
def test_componentes_de_dashboard_existem(css, seletor):
    assert _bloco(css, seletor).strip()


def test_componentes_ficam_numa_secao_propria(css):
    assert "/* Componentes (E-022)" in css


def test_card_tem_fundo_de_card_e_topo_acido(css):
    card = _bloco(css, ".card")

    assert "background-color: var(--cor-card)" in card
    assert "border-top: 2px solid var(--cor-acido)" in card
    assert "min-width: 0" in card


def test_grades_usam_min_para_nao_estourar_no_celular(css):
    for seletor in (".cards", ".metricas", ".opcoes", ".blocos"):
        assert re.search(r"minmax\(min\([\d.]+rem, 100%\)", _bloco(css, seletor)), seletor


def test_tabela_rolavel_tem_rolagem_e_borda_de_card(css):
    tabela = _bloco(css, ".tabela-rolavel")

    assert "overflow-x: auto" in tabela
    assert "background-color: var(--cor-card)" in tabela
    assert re.search(r"border:\s*1px solid var\(--cor-borda\)", tabela)


def test_tabela_rolavel_definida_uma_vez(css):
    sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)

    assert len(re.findall(r"(?:^|\})\s*\.tabela-rolavel\s*\{", sem_comentarios)) == 1


def test_opcao_marcada_e_focada_acende_em_acido(css):
    assert "border-color: var(--cor-acido)" in _bloco(css, ".opcao:has(:checked)")
    assert "border-color: var(--cor-acido)" in _bloco(css, ".opcao:focus-within")
    assert "min-height: 2.75rem" in _bloco(css, ".opcao")


def test_campo_tem_altura_de_toque(css):
    assert "min-height: 2.75rem" in _bloco(css, ".campo input,\n.campo select")


def test_numeros_dos_componentes_em_mono(css):
    for seletor in (".numero", ".metrica dd", ".placar-gols", ".chip"):
        assert "font-family: var(--fonte-numeros)" in _bloco(css, seletor), seletor


def test_visualmente_oculto_nao_usa_display_none(css):
    oculto = _bloco(css, ".visualmente-oculto")

    assert "display: none" not in oculto
    assert "position: absolute" in oculto
    assert "overflow: hidden" in oculto


def test_bloco_da_home_vira_card_com_topo_acido(css):
    bloco = _bloco(css, ".bloco")

    assert "background-color: var(--cor-card)" in bloco
    assert "border-top: 2px solid var(--cor-acido)" in bloco
    assert "border-color: var(--cor-acido)" in _bloco(css, ".bloco:hover,\n.bloco:focus-visible")


def test_bloco_destaque_continua_ambar(css):
    assert "border-color: var(--cor-destaque)" in _bloco(css, ".bloco-destaque")


def test_textos_secundarios_sem_opacity(css):
    """Texto suave vem do token, não de opacity (contraste previsível)."""
    for seletor in (".bloco p", ".inicio-hero p"):
        bloco = _bloco(css, seletor)
        assert "opacity" not in bloco, seletor
        assert "color: var(--cor-texto-suave)" in bloco, seletor


@pytest.mark.parametrize("seletor", [".bloco", ".opcao"])
def test_transicoes_dos_componentes_zeradas_no_movimento_reduzido(css, seletor):
    inicio = css.index("@media (prefers-reduced-motion: reduce)")
    trecho = css[inicio:]

    seletores_zerados = re.findall(r"([^{}]+)\{[^}]*transition:\s*none", trecho)

    assert any(re.search(re.escape(seletor) + r"(?![-\w])", sel) for sel in seletores_zerados)


def test_toda_classe_com_transition_e_zerada_no_movimento_reduzido(css):
    sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    inicio = sem_comentarios.index("@media (prefers-reduced-motion: reduce)")
    antes, trecho = sem_comentarios[:inicio], sem_comentarios[inicio:]

    com_transicao = re.findall(r"(?:^|\})\s*([^{}@]+?)\s*\{[^}]*\btransition\s*:\s*(?!none)", antes)
    zerados = " ".join(re.findall(r"([^{}]+)\{[^}]*transition:\s*none", trecho))

    for seletor in com_transicao:
        assert re.search(re.escape(seletor.strip()) + r"(?![-\w])", zerados), seletor


# --- E-022-T6b: acento azul no lugar do verde-limão ---------------------------

HEX_VERDES_ANTIGOS = ["#c6ff3d", "#d6ff70", "#7ddc6f", "#283b1d", "#2a1f1c"]


@pytest.mark.parametrize("hex_antigo", HEX_VERDES_ANTIGOS)
def test_t6b_hex_verde_antigo_nao_aparece_mais(css, hex_antigo):
    assert hex_antigo not in css.lower()


@pytest.mark.parametrize(
    "token, valor",
    [
        ("--cor-acido", "#00bfff"),
        ("--cor-acido-claro", "#66d9ff"),
        ("--cor-azul-2", "#1e90ff"),
        ("--cor-link", "#7cc8ff"),
    ],
)
def test_t6b_tokens_azuis(css, token, valor):
    root = _bloco(css, ":root")

    assert re.search(re.escape(token) + r"\s*:\s*" + re.escape(valor) + r"\s*;", root, re.I)


def test_t6b_todo_var_usado_esta_definido(css):
    sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    usados = set(re.findall(r"var\(\s*(--[\w-]+)", sem_comentarios))
    definidos = set(re.findall(r"(--[\w-]+)\s*:", sem_comentarios))

    assert usados - definidos == set()


def _luminancia(hex_cor):
    canais = [int(hex_cor.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contraste(a, b):
    claro, escuro = sorted([_luminancia(a), _luminancia(b)], reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


def _token(css, nome):
    root = _bloco(css, ":root")
    achado = re.search(re.escape(nome) + r"\s*:\s*(#[0-9a-fA-F]{6})", root)
    assert achado, f"token {nome} sem hex"
    return achado.group(1)


@pytest.mark.parametrize("texto", ["--cor-acido", "--cor-link"])
@pytest.mark.parametrize("fundo", ["--cor-fundo", "--cor-card", "--cor-card-elevado"])
def test_t6b_azul_de_texto_tem_contraste_aa_sobre_fundos(css, texto, fundo):
    assert _contraste(_token(css, texto), _token(css, fundo)) >= 4.5


@pytest.mark.parametrize("fundo", ["--cor-fundo", "--cor-card", "--cor-card-elevado"])
def test_t6b_azul_2_de_borda_tem_contraste_nao_textual(css, fundo):
    # WCAG 1.4.11: componente de interface (borda) pede 3:1.
    assert _contraste(_token(css, "--cor-azul-2"), _token(css, fundo)) >= 3


def test_t6b_azul_2_so_e_usado_em_borda(css):
    sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    propriedades = re.findall(r"([\w-]+)\s*:[^;{}]*var\(--cor-azul-2\)", sem_comentarios)

    assert propriedades
    assert all(p.startswith("border") for p in propriedades)


@pytest.mark.parametrize("fundo_botao", ["--cor-acido", "--cor-acido-claro"])
def test_t6b_texto_do_botao_primario_tem_contraste_aa(css, fundo_botao):
    assert _contraste(_token(css, "--cor-fundo"), _token(css, fundo_botao)) >= 4.5


def test_t6b_botao_hover_usa_azul_claro(css):
    hover = _bloco(css, ".botao:hover")

    assert "var(--cor-acido-claro)" in hover
