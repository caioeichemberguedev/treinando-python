import itertools
import json
import re
import xml.etree.ElementTree as ET

import pytest
from markupsafe import Markup

import catalogo
from equipe import Equipe
from web.escudo import (
    ALTURA_VIEWBOX,
    CORES_ESCUDO_PADRAO,
    LARGURA_DIAGONAL,
    LARGURA_VIEWBOX,
    escudo_svg,
)
from web.templates_config import templates

CORES_TESTE = ["#111111", "#222222", "#333333"]
NS = "{http://www.w3.org/2000/svg}"


def _id_clip(svg):
    return re.search(r'<clipPath id="([^"]+)"', svg).group(1)


def _faixas(svg):
    """As faixas coloridas: `<rect>` dentro do grupo recortado (fora o
    recorte do clipPath e a borda)."""
    raiz = ET.fromstring(svg)  # levanta ParseError se o SVG for inválido
    grupo = raiz.find(f"{NS}g")
    return grupo.findall(f"{NS}rect")


def _assert_usa_cores(svg, cores):
    assert [f.get("fill") for f in _faixas(svg)] == cores


def _borda(svg):
    """O `<rect class="escudo-borda">` do escudo."""
    raiz = ET.fromstring(svg)
    return raiz.find(f"{NS}rect[@class='escudo-borda']")


def _assert_borda_branca_fina(borda):
    assert borda is not None
    assert borda.get("stroke") == "#FFFFFF"
    assert borda.get("stroke-width") == "1"
    assert borda.get("vector-effect") == "non-scaling-stroke"
    assert borda.get("fill") == "none"


def test_borda_e_branca_fina_e_nao_escala():
    _assert_borda_branca_fina(_borda(str(escudo_svg(Equipe("X", cores=CORES_TESTE)))))


@pytest.mark.parametrize("tamanho", [20, 24, 40, 96])
def test_borda_inteira_dentro_do_viewbox_com_recuo_de_meio_pixel(tamanho):
    borda = _borda(str(escudo_svg(Equipe("X", cores=CORES_TESTE), tamanho)))

    x, y = float(borda.get("x")), float(borda.get("y"))
    largura, altura = float(borda.get("width")), float(borda.get("height"))
    assert x == pytest.approx(y)
    assert x > 0
    assert x + largura == pytest.approx(LARGURA_VIEWBOX - x, abs=0.001)
    assert y + altura == pytest.approx(ALTURA_VIEWBOX - y, abs=0.001)
    assert x * tamanho / ALTURA_VIEWBOX == pytest.approx(0.5, abs=0.001)
    assert float(borda.get("rx")) > 0


def test_previa_do_adm_tem_a_mesma_borda_branca():
    svg = str(escudo_svg(1, 96, cores=["#123456", "#654321"]))

    _assert_borda_branca_fina(_borda(svg))


def test_escudo_com_cores_tem_estrutura_completa():
    svg = str(escudo_svg(Equipe("X", cores=CORES_TESTE)))

    assert "<svg" in svg
    assert 'class="escudo"' in svg
    assert "<clipPath" in svg
    assert len(_faixas(svg)) == 3
    for cor in CORES_TESTE:
        assert cor in svg
    assert f'clip-path="url(#{_id_clip(svg)})"' in svg


def test_duas_chamadas_geram_ids_de_clip_diferentes():
    primeiro = str(escudo_svg(Equipe("X", cores=CORES_TESTE)))
    segundo = str(escudo_svg(Equipe("X", cores=CORES_TESTE)))

    assert _id_clip(primeiro) != _id_clip(segundo)


def test_string_crua_nao_busca_cores_no_catalogo():
    """String é só texto: mesmo com nome de time do catálogo, escudo cinza."""
    _assert_usa_cores(str(escudo_svg("São Paulo")), CORES_ESCUDO_PADRAO)


def test_id_do_catalogo_usa_cores_do_catalogo():
    _assert_usa_cores(str(escudo_svg(1)), catalogo.cores_do_time(1))


def test_equipe_com_id_do_catalogo_usa_cores_do_catalogo():
    _assert_usa_cores(
        str(escudo_svg(Equipe("X", id=1))), catalogo.cores_do_time(1)
    )


def test_id_do_catalogo_tem_prioridade_sobre_cores_da_equipe():
    _assert_usa_cores(
        str(escudo_svg(Equipe("X", id=1, cores=CORES_TESTE))),
        catalogo.cores_do_time(1),
    )


def test_equipe_com_id_fora_do_catalogo_usa_as_proprias_cores():
    _assert_usa_cores(
        str(escudo_svg(Equipe("X", id=901, cores=CORES_TESTE))), CORES_TESTE
    )


def test_equipe_sem_id_usa_as_proprias_cores():
    _assert_usa_cores(
        str(escudo_svg(Equipe("São Paulo", cores=CORES_TESTE))), CORES_TESTE
    )


def test_equipe_sem_id_e_sem_cores_usa_escudo_cinza():
    """Sem id, a `Equipe` não é mais buscada no catálogo pelo nome."""
    _assert_usa_cores(
        str(escudo_svg(Equipe("São Paulo"))), CORES_ESCUDO_PADRAO
    )


def test_id_desconhecido_usa_escudo_cinza():
    _assert_usa_cores(str(escudo_svg(999)), CORES_ESCUDO_PADRAO)


def test_equipe_com_id_desconhecido_e_sem_cores_usa_escudo_cinza():
    _assert_usa_cores(
        str(escudo_svg(Equipe("X", id=999))), CORES_ESCUDO_PADRAO
    )


def test_time_desconhecido_usa_escudo_cinza():
    _assert_usa_cores(str(escudo_svg("Time Fantasma")), CORES_ESCUDO_PADRAO)


def test_none_usa_escudo_cinza_com_rotulo_generico():
    svg = str(escudo_svg(None))

    _assert_usa_cores(svg, CORES_ESCUDO_PADRAO)
    assert 'aria-label="Escudo"' in svg


def test_string_vazia_usa_escudo_cinza_com_rotulo_generico():
    svg = str(escudo_svg(""))

    _assert_usa_cores(svg, CORES_ESCUDO_PADRAO)
    assert 'aria-label="Escudo"' in svg


def test_cor_invalida_usa_escudo_cinza():
    for invalida in ["red", '"><script>', "#12345", "#GGGGGG"]:
        equipe = Equipe("X", cores=["#111111", invalida, "#333333"])
        svg = str(escudo_svg(equipe))

        _assert_usa_cores(svg, CORES_ESCUDO_PADRAO)
        assert "<script>" not in svg


@pytest.mark.parametrize("cores", [[], ["#111111"] * 5])
def test_quantidade_errada_de_cores_usa_escudo_cinza(cores):
    svg = str(escudo_svg(Equipe("X", cores=cores)))

    _assert_usa_cores(svg, CORES_ESCUDO_PADRAO)


def test_escudo_padrao_tem_dois_tons_de_cinza():
    assert len(CORES_ESCUDO_PADRAO) == 2
    _assert_usa_cores(str(escudo_svg(None)), CORES_ESCUDO_PADRAO)


@pytest.mark.parametrize("quantidade", [1, 2, 3, 4])
def test_n_cores_geram_n_faixas_iguais_na_ordem(quantidade):
    cores = ["#111111", "#222222", "#333333", "#444444"][:quantidade]
    svg = str(escudo_svg(Equipe("X", id=901, cores=cores)))

    faixas = _faixas(svg)
    assert [f.get("fill") for f in faixas] == cores
    larguras = [float(f.get("width")) for f in faixas]
    assert len(set(larguras)) == 1
    assert sum(larguras) == pytest.approx(LARGURA_VIEWBOX, abs=0.001)
    xs = [float(f.get("x")) for f in faixas]
    assert xs == pytest.approx(
        [i * LARGURA_VIEWBOX / quantidade for i in range(quantidade)],
        abs=0.001,
    )
    for faixa in faixas:
        assert float(faixa.get("y")) == 0
        assert float(faixa.get("height")) == ALTURA_VIEWBOX


def test_tamanho_e_a_altura_e_largura_igual():
    raiz = ET.fromstring(str(escudo_svg(Equipe("X", cores=CORES_TESTE), 96)))

    assert raiz.get("height") == "96"
    assert raiz.get("width") == "96"
    assert raiz.get("viewBox") == "0 0 60 60"


def test_tamanho_padrao_e_24_de_altura():
    raiz = ET.fromstring(str(escudo_svg(Equipe("X", cores=CORES_TESTE))))

    assert raiz.get("height") == "24"
    assert raiz.get("width") == "24"


@pytest.mark.parametrize("tamanho", [20, 24, 40, 96])
def test_escudo_e_quadrado(tamanho):
    raiz = ET.fromstring(
        str(escudo_svg(Equipe("X", cores=CORES_TESTE), tamanho))
    )

    assert float(raiz.get("height")) == tamanho
    assert float(raiz.get("width")) == tamanho
    assert raiz.get("viewBox") == f"0 0 {LARGURA_VIEWBOX} {ALTURA_VIEWBOX}"
    assert LARGURA_VIEWBOX == ALTURA_VIEWBOX


def test_recorte_e_retangulo_com_cantos_arredondados():
    raiz = ET.fromstring(str(escudo_svg(Equipe("X", cores=CORES_TESTE))))

    recorte = raiz.find(f".//{NS}clipPath/{NS}rect")
    assert recorte is not None
    assert float(recorte.get("rx")) > 0
    assert float(recorte.get("width")) == LARGURA_VIEWBOX
    assert float(recorte.get("height")) == ALTURA_VIEWBOX


def test_corinthians_tem_duas_faixas_preta_e_branca():
    _assert_usa_cores(str(escudo_svg(3)), ["#000000", "#FFFFFF"])


@pytest.mark.parametrize(
    "cores_catalogo", [["#111111"] * 5, ["#111111", "red"], []]
)
def test_cores_invalidas_no_catalogo_usam_escudo_cinza(
    monkeypatch, cores_catalogo
):
    monkeypatch.setattr(catalogo, "cores_do_time", lambda _id: cores_catalogo)

    _assert_usa_cores(
        str(escudo_svg(Equipe("X", id=1, cores=CORES_TESTE))),
        CORES_ESCUDO_PADRAO,
    )


def test_cores_explicitas_ignoram_o_catalogo():
    svg = str(escudo_svg(1, cores=["#123456"]))

    _assert_usa_cores(svg, ["#123456"])
    assert 'aria-label="Escudo do São Paulo"' in svg


def test_rotulo_da_previa_usa_nome_efetivo_do_catalogo():
    catalogo.salvar_time_no_catalogo(1, "Nome Adm", ["#FF0000"])

    svg = str(escudo_svg(1, cores=["#123456"]))

    assert 'aria-label="Escudo do Nome Adm"' in svg
    _assert_usa_cores(svg, ["#123456"])


def test_escudo_por_id_usa_cores_editadas_pelo_adm():
    catalogo.salvar_time_no_catalogo(1, "Nome Adm", ["#FF0000", "#00FF00"])

    _assert_usa_cores(str(escudo_svg(1)), ["#FF0000", "#00FF00"])


@pytest.mark.parametrize(
    "cores",
    [[], ["#111111"] * 5, ["red"], ["#FFF"], ['"><script>'], "#111111"],
)
def test_cores_explicitas_invalidas_usam_escudo_cinza(cores):
    svg = str(escudo_svg(1, cores=cores))

    _assert_usa_cores(svg, CORES_ESCUDO_PADRAO)
    assert "<script>" not in svg


def test_ids_de_clip_unicos_em_varios_escudos():
    svgs = [
        str(escudo_svg(t))
        for t in itertools.islice(itertools.cycle([1, 3, None, "X"]), 20)
    ]

    ids = [_id_clip(svg) for svg in svgs]
    assert len(set(ids)) == len(ids)
    for svg, id_clip in zip(svgs, ids):
        assert f'clip-path="url(#{id_clip})"' in svg


def test_nome_aparece_no_rotulo_e_no_title():
    svg = str(escudo_svg("São Paulo"))

    assert 'aria-label="Escudo do São Paulo"' in svg
    assert "<title>Escudo do São Paulo</title>" in svg


def test_rotulo_de_id_usa_nome_do_catalogo():
    svg = str(escudo_svg(1))

    assert 'aria-label="Escudo do São Paulo"' in svg
    assert "<title>Escudo do São Paulo</title>" in svg


def test_rotulo_de_equipe_com_id_do_catalogo_usa_nome_do_catalogo():
    svg = str(escudo_svg(Equipe("Qualquer", id=1)))

    assert 'aria-label="Escudo do São Paulo"' in svg


def test_rotulo_de_id_desconhecido():
    svg = str(escudo_svg(999))

    assert 'aria-label="Escudo do Time #999"' in svg


def test_nome_com_caracteres_especiais_e_escapado():
    svg = str(escudo_svg(Equipe("<b>&</b>")))

    assert "&lt;b&gt;&amp;" in svg
    assert "<b>" not in svg


def test_retorna_markup():
    assert isinstance(escudo_svg("São Paulo"), Markup)


def test_global_do_jinja_renderiza_svg_sem_escape():
    html = templates.env.from_string("{{ escudo(t) }}").render(
        t=Equipe("X", cores=CORES_TESTE)
    )

    assert html.startswith("<svg")
    assert "&lt;svg" not in html


def test_global_do_jinja_aceita_tamanho():
    html = templates.env.from_string("{{ escudo(t, 96) }}").render(t="Brasil")

    assert 'height="96"' in html
    assert 'width="96"' in html


def test_global_do_jinja_aceita_cores_da_previa():
    html = templates.env.from_string(
        "{{ escudo(1, 96, cores=c) }}"
    ).render(c=["#123456", "#654321"])

    _assert_usa_cores(html, ["#123456", "#654321"])


def test_svg_e_xml_valido_com_nome_escapado():
    svg = str(escudo_svg(Equipe("<b>&</b>", cores=CORES_TESTE), 48))

    raiz = ET.fromstring(svg)  # levanta ParseError se o SVG for inválido
    assert raiz.tag == f"{NS}svg"
    assert raiz.get("aria-label") == "Escudo do <b>&</b>"
    _assert_usa_cores(svg, CORES_TESTE)


def test_global_nome_time_resolve_id_do_catalogo():
    html = templates.env.from_string("{{ nome_time(1) }}").render()

    assert html == "São Paulo"


def test_global_nome_time_aceita_equipe_e_id_desconhecido():
    html = templates.env.from_string(
        "{{ nome_time(e) }}|{{ nome_time(999) }}"
    ).render(e=Equipe("Time A", id=901))

    assert html == "Time A|Time #999"


def test_global_nome_time_escapa_html():
    html = templates.env.from_string("{{ nome_time(t) }}").render(
        t=Equipe("<b>", id=901)
    )

    assert html == "&lt;b&gt;"


# --- E-012-T3: padrões horizontais e diagonal --------------------------------

def _numero_svg(valor):
    return f"{valor:.4f}".rstrip("0").rstrip(".")


def _grupo_diagonal(svg):
    raiz = ET.fromstring(svg)
    return raiz.find(f"{NS}g/{NS}g[@class='escudo-diagonal']")


def _assert_verticais(svg, cores):
    """Faixas verticais: só `rect` diretos, de altura cheia, sem diagonal."""
    assert _grupo_diagonal(svg) is None
    faixas = _faixas(svg)
    assert [f.get("fill") for f in faixas] == cores
    for faixa in faixas:
        assert float(faixa.get("height")) == ALTURA_VIEWBOX


def _assert_diagonal(svg, cores, angulo):
    fundo = _faixas(svg)
    assert len(fundo) == 1
    assert fundo[0].get("fill") == cores[0]
    assert float(fundo[0].get("width")) == LARGURA_VIEWBOX
    assert float(fundo[0].get("height")) == ALTURA_VIEWBOX

    grupo = _grupo_diagonal(svg)
    assert grupo is not None
    centro = _numero_svg(LARGURA_VIEWBOX / 2)
    assert grupo.get("transform") == f"rotate({angulo} {centro} {centro})"
    faixas = grupo.findall(f"{NS}rect")
    assert [f.get("fill") for f in faixas] == cores[1:]


def _gravar_catalogo_a_mao(edicoes):
    with open(catalogo.ARQUIVO_CATALOGO, "w", encoding="utf-8") as arquivo:
        json.dump(edicoes, arquivo)
    catalogo.limpar_cache()


@pytest.mark.parametrize("quantidade", [1, 2, 3, 4])
def test_horizontais_n_cores_geram_n_faixas_iguais_de_cima_para_baixo(
    quantidade,
):
    cores = ["#111111", "#222222", "#333333", "#444444"][:quantidade]
    svg = str(escudo_svg(901, cores=cores, padrao="horizontais"))

    assert _grupo_diagonal(svg) is None
    faixas = _faixas(svg)
    assert [f.get("fill") for f in faixas] == cores
    alturas = [float(f.get("height")) for f in faixas]
    assert len(set(alturas)) == 1
    assert sum(alturas) == pytest.approx(ALTURA_VIEWBOX, abs=0.001)
    ys = [float(f.get("y")) for f in faixas]
    assert ys == pytest.approx(
        [i * ALTURA_VIEWBOX / quantidade for i in range(quantidade)],
        abs=0.001,
    )
    for faixa in faixas:
        assert float(faixa.get("x")) == 0
        assert float(faixa.get("width")) == LARGURA_VIEWBOX


@pytest.mark.parametrize(
    "padrao, angulo", [("diagonal_sobe", -45), ("diagonal_desce", 45)]
)
@pytest.mark.parametrize("quantidade", [2, 3, 4])
def test_diagonal_tem_fundo_na_cor_1_e_faixa_com_as_demais(
    padrao, angulo, quantidade
):
    cores = ["#111111", "#222222", "#333333", "#444444"][:quantidade]
    svg = str(escudo_svg(901, cores=cores, padrao=padrao))

    _assert_diagonal(svg, cores, angulo)
    faixas = _grupo_diagonal(svg).findall(f"{NS}rect")
    espessuras = [float(f.get("height")) for f in faixas]
    assert len(set(espessuras)) == 1
    assert sum(espessuras) == pytest.approx(LARGURA_DIAGONAL, abs=0.001)
    ys = [float(f.get("y")) for f in faixas]
    inicio = ALTURA_VIEWBOX / 2 - LARGURA_DIAGONAL / 2
    assert ys == pytest.approx(
        [inicio + i * LARGURA_DIAGONAL / (quantidade - 1)
         for i in range(quantidade - 1)],
        abs=0.001,
    )
    for faixa in faixas:
        # Comprida de sobra para cobrir o quadrado depois de girada.
        x, largura = float(faixa.get("x")), float(faixa.get("width"))
        assert x < 0
        assert x + largura > LARGURA_VIEWBOX


def test_faixa_diagonal_visivel_no_escudo_de_20_px():
    svg = str(escudo_svg(
        901, 20, cores=["#000000", "#FFFFFF"], padrao="diagonal_sobe"
    ))

    assert ET.fromstring(svg).get("height") == "20"
    _assert_diagonal(svg, ["#000000", "#FFFFFF"], -45)
    # Espessura da faixa em pixels de tela: pelo menos 6 px.
    assert LARGURA_DIAGONAL * 20 / ALTURA_VIEWBOX >= 6


def test_id_salvo_como_diagonal_no_catalogo_desenha_diagonal():
    catalogo.salvar_time_no_catalogo(
        6, "Vasco", ["#000000", "#FFFFFF"], padrao="diagonal_sobe"
    )

    _assert_diagonal(str(escudo_svg(6)), ["#000000", "#FFFFFF"], -45)
    _assert_diagonal(
        str(escudo_svg(Equipe("X", id=6))), ["#000000", "#FFFFFF"], -45
    )


def test_id_salvo_como_horizontais_no_catalogo_desenha_horizontais():
    cores = ["#FF0000", "#FFFFFF", "#000000"]
    catalogo.salvar_time_no_catalogo(1, "São Paulo", cores, padrao="horizontais")

    faixas = _faixas(str(escudo_svg(1)))
    assert [f.get("fill") for f in faixas] == cores
    assert [float(f.get("width")) for f in faixas] == [LARGURA_VIEWBOX] * 3


@pytest.mark.parametrize(
    "time",
    [
        Equipe("Vasco", cores=["#000000", "#FFFFFF"]),
        Equipe("X", id=901, cores=["#000000", "#FFFFFF"]),
        "Vasco",
        None,
        999,
    ],
)
def test_sem_id_conhecido_desenha_verticais(time):
    catalogo.salvar_time_no_catalogo(
        6, "Vasco", ["#000000", "#FFFFFF"], padrao="diagonal_sobe"
    )

    svg = str(escudo_svg(time))

    assert _grupo_diagonal(svg) is None
    for faixa in _faixas(svg):
        assert float(faixa.get("height")) == ALTURA_VIEWBOX


def test_diagonal_com_uma_cor_vira_verticais():
    _assert_verticais(
        str(escudo_svg(901, cores=["#123456"], padrao="diagonal_sobe")),
        ["#123456"],
    )


@pytest.mark.parametrize("padrao", ["lixo", "", "VERTICAIS", 3, ["x"]])
def test_padrao_explicito_invalido_vira_verticais(padrao):
    cores = ["#111111", "#222222"]

    _assert_verticais(str(escudo_svg(901, cores=cores, padrao=padrao)), cores)


@pytest.mark.parametrize("padrao", ["xadrez", None, 7])
def test_padrao_invalido_gravado_no_arquivo_vira_verticais(padrao):
    cores = ["#000000", "#FFFFFF"]
    _gravar_catalogo_a_mao(
        {"6": {"nome": "Vasco", "cores": cores, "padrao": padrao}}
    )

    _assert_verticais(str(escudo_svg(6)), cores)


def test_diagonal_gravada_com_uma_cor_no_arquivo_vira_verticais():
    _gravar_catalogo_a_mao(
        {"6": {"nome": "Vasco", "cores": ["#000000"], "padrao": "diagonal_sobe"}}
    )

    _assert_verticais(str(escudo_svg(6)), ["#000000"])


def test_cores_invalidas_com_padrao_diagonal_viram_cinza_vertical():
    svg = str(escudo_svg(1, cores=["red", "#000000"], padrao="diagonal_sobe"))

    _assert_verticais(svg, CORES_ESCUDO_PADRAO)


def test_cores_invalidas_no_catalogo_com_diagonal_viram_cinza_vertical():
    _gravar_catalogo_a_mao(
        {"6": {"nome": "Vasco", "cores": ["red", "#000000"],
               "padrao": "diagonal_sobe"}}
    )

    _assert_verticais(str(escudo_svg(6)), CORES_ESCUDO_PADRAO)


def test_previa_com_padrao_ignora_o_padrao_do_catalogo():
    catalogo.salvar_time_no_catalogo(
        1, "São Paulo", ["#FF0000", "#000000"], padrao="diagonal_desce"
    )
    cores = ["#123456", "#654321", "#ABCDEF"]

    svg = str(escudo_svg(1, 96, cores=cores, padrao="horizontais"))

    assert _grupo_diagonal(svg) is None
    faixas = _faixas(svg)
    assert [f.get("fill") for f in faixas] == cores
    assert [float(f.get("width")) for f in faixas] == [LARGURA_VIEWBOX] * 3


def test_previa_sem_padrao_usa_o_padrao_do_catalogo():
    catalogo.salvar_time_no_catalogo(
        6, "Vasco", ["#000000", "#FFFFFF"], padrao="diagonal_desce"
    )

    svg = str(escudo_svg(6, 96, cores=["#123456", "#654321"]))

    _assert_diagonal(svg, ["#123456", "#654321"], 45)


@pytest.mark.parametrize("padrao", list(catalogo.PADROES))
@pytest.mark.parametrize("tamanho", [20, 96])
def test_todos_os_padroes_mantem_borda_recorte_e_xml_valido(padrao, tamanho):
    svg = str(escudo_svg(
        Equipe("<b>&</b>", id=901), tamanho,
        cores=["#111111", "#222222", "#333333"], padrao=padrao,
    ))

    raiz = ET.fromstring(svg)  # levanta ParseError se o SVG for inválido
    _assert_borda_branca_fina(_borda(svg))
    recorte = raiz.find(f".//{NS}clipPath/{NS}rect")
    assert float(recorte.get("rx")) > 0
    assert float(recorte.get("width")) == LARGURA_VIEWBOX
    grupo = raiz.find(f"{NS}g")
    assert grupo.get("class") == "escudo-faixas"
    assert grupo.get("clip-path") == f"url(#{_id_clip(svg)})"
    # A borda vem depois do grupo recortado (desenhada por cima).
    filhos = list(raiz)
    borda = raiz.find(f"{NS}rect[@class='escudo-borda']")
    assert filhos.index(grupo) < filhos.index(borda)


def test_ids_de_clip_unicos_com_padroes_diferentes():
    svgs = [
        str(escudo_svg(901, cores=["#111111", "#222222"], padrao=padrao))
        for padrao in catalogo.PADROES
    ]

    ids = [_id_clip(svg) for svg in svgs]
    assert len(set(ids)) == len(ids)


def test_global_do_jinja_aceita_padrao_da_previa():
    html = templates.env.from_string(
        "{{ escudo(901, 96, cores=c, padrao=p) }}"
    ).render(c=["#123456", "#654321"], p="diagonal_sobe")

    _assert_diagonal(html, ["#123456", "#654321"], -45)
