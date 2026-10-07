import re

from markupsafe import Markup

import persistencia
from equipe import Equipe
from web.escudo import CORES_ESCUDO_PADRAO, escudo_svg
from web.templates_config import templates

CORES_TESTE = ["#111111", "#222222", "#333333"]


def _id_clip(svg):
    return re.search(r'<clipPath id="([^"]+)"', svg).group(1)


def _assert_usa_cores(svg, cores):
    fills = re.findall(r'<rect [^>]*fill="([^"]+)"', svg)
    assert fills == cores


def test_escudo_com_cores_tem_estrutura_completa():
    svg = str(escudo_svg(Equipe("X", cores=CORES_TESTE)))

    assert "<svg" in svg
    assert 'class="escudo"' in svg
    assert "<clipPath" in svg
    assert svg.count("<rect") == 3
    for cor in CORES_TESTE:
        assert cor in svg
    assert f'clip-path="url(#{_id_clip(svg)})"' in svg


def test_duas_chamadas_geram_ids_de_clip_diferentes():
    primeiro = str(escudo_svg(Equipe("X", cores=CORES_TESTE)))
    segundo = str(escudo_svg(Equipe("X", cores=CORES_TESTE)))

    assert _id_clip(primeiro) != _id_clip(segundo)


def test_string_crua_usa_cores_do_catalogo():
    _assert_usa_cores(
        str(escudo_svg("São Paulo")), persistencia.cores_do_time("São Paulo")
    )


def test_equipe_sem_cores_usa_cores_do_catalogo():
    _assert_usa_cores(
        str(escudo_svg(Equipe("São Paulo"))),
        persistencia.cores_do_time("São Paulo"),
    )


def test_cores_da_equipe_tem_prioridade_sobre_o_catalogo():
    _assert_usa_cores(
        str(escudo_svg(Equipe("São Paulo", cores=CORES_TESTE))), CORES_TESTE
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


def test_quantidade_errada_de_cores_usa_escudo_cinza():
    svg = str(escudo_svg(Equipe("X", cores=["#111111", "#222222"])))

    _assert_usa_cores(svg, CORES_ESCUDO_PADRAO)


def test_tamanho_define_largura_e_altura():
    svg = str(escudo_svg(Equipe("X", cores=CORES_TESTE), 96))

    assert 'width="96"' in svg
    assert f'height="{round(96 * 1.2)}"' in svg


def test_tamanho_padrao_e_24():
    svg = str(escudo_svg(Equipe("X", cores=CORES_TESTE)))

    assert 'width="24"' in svg
    assert f'height="{round(24 * 1.2)}"' in svg


def test_nome_aparece_no_rotulo_e_no_title():
    svg = str(escudo_svg("São Paulo"))

    assert 'aria-label="Escudo do São Paulo"' in svg
    assert "<title>Escudo do São Paulo</title>" in svg


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

    assert 'width="96"' in html


def test_svg_e_xml_valido_com_faixas_verticais_na_ordem():
    import xml.etree.ElementTree as ET

    ns = "{http://www.w3.org/2000/svg}"
    svg = str(escudo_svg(Equipe("<b>&</b>", cores=CORES_TESTE), 48))

    raiz = ET.fromstring(svg)  # levanta ParseError se o SVG for inválido
    assert raiz.tag == f"{ns}svg"
    assert raiz.get("aria-label") == "Escudo do <b>&</b>"

    faixas = raiz.findall(f".//{ns}rect")
    xs = [float(f.get("x")) for f in faixas]
    assert xs == sorted(xs) and xs[0] == 0
    for faixa in faixas:
        assert float(faixa.get("y")) == 0
        assert float(faixa.get("height")) == 120
        assert float(faixa.get("width")) < 34
    assert xs[-1] + float(faixas[-1].get("width")) >= 100
    assert [f.get("fill") for f in faixas] == CORES_TESTE
