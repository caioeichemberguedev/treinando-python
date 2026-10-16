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
