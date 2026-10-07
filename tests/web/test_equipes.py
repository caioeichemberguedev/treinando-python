import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import catalogo
import persistencia
import web.estado as estado
from equipe import Equipe
from web.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def equipes_de_teste(tmp_path, monkeypatch):
    """Isola os testes de um `equipes.json` e de um diretório `saves/` de
    teste (nunca os reais do projeto), e reseta o "jogo em andamento" em
    memória entre os testes.
    """
    dados = {
        "Campeonato Teste": [
            {"id": 901, "nome": "Time A", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"id": 902, "nome": "Time B", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
        ],
        "Outro Campeonato": [
            {"id": 903, "nome": "Time C", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
        ],
    }
    arquivo = tmp_path / "equipes.json"
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(arquivo))
    monkeypatch.setattr(persistencia, "DIR_SAVES", str(tmp_path / "saves"))
    monkeypatch.setattr(estado, "_jogo_atual", None)
    yield arquivo


def _ler_equipes_salvas(arquivo):
    return json.loads(arquivo.read_text(encoding="utf-8"))


def test_tela_equipes_lista_campeonatos():
    resposta = client.get("/equipes")

    assert resposta.status_code == 200
    assert "Campeonato Teste" in resposta.text
    assert "Outro Campeonato" in resposta.text


def test_tela_equipes_campeonato_lista_os_times_certos():
    resposta = client.get("/equipes/Campeonato Teste")

    assert resposta.status_code == 200
    assert "Time A" in resposta.text
    assert "Time B" in resposta.text
    assert "Time C" not in resposta.text


def test_tela_equipes_campeonato_inexistente_retorna_404():
    resposta = client.get("/equipes/Campeonato Fantasma")

    assert resposta.status_code == 404


@pytest.mark.parametrize("trecho", ["nome_novo", "/adicionar", "/remover", "/renomear", "Adicionar equipe"])
def test_tela_equipes_campeonato_nao_oferece_adicionar_renomear_nem_remover(trecho):
    resposta = client.get("/equipes/Campeonato Teste")

    assert resposta.status_code == 200
    assert trecho not in resposta.text


@pytest.mark.parametrize(
    ("metodo", "caminho", "dados"),
    [
        ("post", "/equipes/Campeonato Teste/adicionar", {"nome": "X"}),
        ("get", "/equipes/Campeonato Teste/Time A/remover", None),
        ("post", "/equipes/Campeonato Teste/Time A/remover", None),
        ("post", "/equipes/Campeonato Teste/Time A/renomear", {"nome_novo": "X"}),
    ],
)
def test_rotas_de_adicionar_renomear_e_remover_nao_existem_e_nao_alteram_equipes(
    equipes_de_teste, metodo, caminho, dados
):
    conteudo_antes = equipes_de_teste.read_bytes()

    if metodo == "post":
        resposta = client.post(caminho, data=dados, follow_redirects=False)
    else:
        resposta = client.get(caminho, follow_redirects=False)

    assert resposta.status_code in (404, 405)
    assert equipes_de_teste.read_bytes() == conteudo_antes


def _criar_save_de_teste():
    persistencia.salvar_jogo(
        "1_01_01_2026", "Campeonato Teste", Equipe("Time A", id=901), 2026, [Equipe("Time A", id=901)]
    )


def _equipe_salva(arquivo, campeonato, id_equipe):
    dados = _ler_equipes_salvas(arquivo)
    return next(time for time in dados[campeonato] if time["id"] == id_equipe)


def test_tela_editar_equipe_sem_saves_mostra_o_formulario():
    resposta = client.get("/equipes/Campeonato Teste/901/editar")

    assert resposta.status_code == 200
    assert 'name="financas"' in resposta.text
    assert 'name="fas"' in resposta.text
    assert 'name="forca"' in resposta.text
    assert "Não é possível editar" not in resposta.text


def test_tela_editar_equipe_com_id_inexistente_retorna_404():
    resposta = client.get("/equipes/Campeonato Teste/999/editar")

    assert resposta.status_code == 404


def test_tela_editar_equipe_com_id_de_outro_campeonato_retorna_404():
    resposta = client.get("/equipes/Campeonato Teste/903/editar")

    assert resposta.status_code == 404


@pytest.mark.parametrize("metodo", ["get", "post"])
def test_editar_equipe_com_nome_no_lugar_do_id_nao_da_500_nem_altera(equipes_de_teste, metodo):
    cliente = TestClient(app, raise_server_exceptions=False)
    conteudo_antes = equipes_de_teste.read_bytes()

    if metodo == "post":
        resposta = cliente.post(
            "/equipes/Campeonato Teste/Time A/editar",
            data={"financas": "1", "fas": "2", "forca": "3"},
            follow_redirects=False,
        )
    else:
        resposta = cliente.get("/equipes/Campeonato Teste/Time A/editar")

    assert resposta.status_code in (404, 422)
    assert equipes_de_teste.read_bytes() == conteudo_antes


def test_editar_equipe_com_id_de_outro_campeonato_retorna_404_e_nao_altera(equipes_de_teste):
    conteudo_antes = equipes_de_teste.read_bytes()

    resposta = client.post(
        "/equipes/Campeonato Teste/903/editar",
        data={"financas": "1", "fas": "2", "forca": "3"},
        follow_redirects=False,
    )

    assert resposta.status_code == 404
    assert equipes_de_teste.read_bytes() == conteudo_antes


def test_editar_equipe_sem_saves_altera_os_valores_e_persiste(equipes_de_teste):
    resposta = client.post(
        "/equipes/Campeonato Teste/901/editar",
        data={"financas": "2500000", "fas": "75000", "forca": "88"},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"].endswith("/equipes/Campeonato%20Teste")

    time_a = _equipe_salva(equipes_de_teste, "Campeonato Teste", 901)
    assert time_a["financas"] == 2_500_000
    assert time_a["fas"] == 75_000
    assert time_a["forca"] == 88

    time_b = _equipe_salva(equipes_de_teste, "Campeonato Teste", 902)
    assert time_b["forca"] == 50


@pytest.mark.parametrize(
    "dados_formulario",
    [
        {"financas": "-1", "fas": "1000", "forca": "50"},
        {"financas": "1000", "fas": "abc", "forca": "50"},
        {"financas": "1000", "fas": "1000", "forca": "101"},
        {"financas": "", "fas": "1000", "forca": "50"},
    ],
)
def test_editar_equipe_com_valor_invalido_nao_altera_e_mostra_erro(equipes_de_teste, dados_formulario):
    resposta = client.post("/equipes/Campeonato Teste/901/editar", data=dados_formulario)

    assert resposta.status_code == 400
    assert "digite um número inteiro" in resposta.text

    time_a = _equipe_salva(equipes_de_teste, "Campeonato Teste", 901)
    assert time_a == {"id": 901, "nome": "Time A", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50}


def _conteudo_do_save_de_teste():
    return (Path(persistencia.DIR_SAVES) / "1_01_01_2026.json").read_bytes()


def test_tela_editar_equipe_com_save_mostra_o_formulario_e_o_aviso():
    _criar_save_de_teste()

    resposta = client.get("/equipes/Campeonato Teste/901/editar")

    assert resposta.status_code == 200
    assert 'name="financas"' in resposta.text
    assert 'name="fas"' in resposta.text
    assert 'name="forca"' in resposta.text
    assert "carreiras novas" in resposta.text
    assert "Não é possível editar" not in resposta.text


def test_tela_equipes_campeonato_com_save_mostra_link_de_editar_e_o_aviso():
    _criar_save_de_teste()

    resposta = client.get("/equipes/Campeonato Teste")

    assert resposta.status_code == 200
    assert "/equipes/Campeonato Teste/901/editar" in resposta.text
    assert "/equipes/Campeonato Teste/902/editar" in resposta.text
    assert "carreiras novas" in resposta.text
    assert "Não é possível editar" not in resposta.text


def test_link_de_editar_da_listagem_abre_o_formulario_do_time_certo():
    """O `url_for` do Starlette não codifica o espaço do campeonato no
    href; o navegador (e o TestClient) codifica ao seguir o link.
    """
    listagem = client.get("/equipes/Campeonato Teste")
    assert 'href="http://testserver/equipes/Campeonato Teste/902/editar"' in listagem.text

    resposta = client.get("http://testserver/equipes/Campeonato Teste/902/editar")

    assert resposta.status_code == 200
    assert "Editar Time B" in resposta.text


def test_tela_equipes_campeonato_sem_saves_mostra_link_de_editar():
    resposta = client.get("/equipes/Campeonato Teste")

    assert "/equipes/Campeonato Teste/901/editar" in resposta.text
    assert "/equipes/Campeonato Teste/902/editar" in resposta.text
    assert "Time A/editar" not in resposta.text
    assert "carreiras novas" in resposta.text
    assert "Não é possível editar" not in resposta.text


def test_editar_equipe_com_save_persiste_e_nao_toca_no_save(equipes_de_teste):
    _criar_save_de_teste()
    save_antes = _conteudo_do_save_de_teste()

    resposta = client.post(
        "/equipes/Campeonato Teste/901/editar",
        data={"financas": "2500000", "fas": "75000", "forca": "88"},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    time_a = _equipe_salva(equipes_de_teste, "Campeonato Teste", 901)
    assert time_a["financas"] == 2_500_000
    assert time_a["fas"] == 75_000
    assert time_a["forca"] == 88
    assert _conteudo_do_save_de_teste() == save_antes


def test_tela_equipes_tem_link_para_restaurar_padrao():
    resposta = client.get("/equipes")

    assert "/equipes/restaurar" in resposta.text


def test_confirmar_restauracao_mostra_tela_de_confirmacao_sem_restaurar(equipes_de_teste):
    resposta = client.get("/equipes/restaurar")

    assert resposta.status_code == 200
    assert "certeza" in resposta.text.lower()

    dados = _ler_equipes_salvas(equipes_de_teste)
    assert list(dados.keys()) == ["Campeonato Teste", "Outro Campeonato"]


def _assert_equipes_iguais_ao_padrao(arquivo):
    dados = _ler_equipes_salvas(arquivo)
    esperado = {}
    for time in catalogo.TIMES_PADRAO:
        equipe = Equipe(time["nome"], cores=time["cores"], id=time["id"])
        esperado.setdefault(time["campeonato"], []).append(equipe.to_dict())
    assert dados == esperado


def test_restaurar_padrao_sobrescreve_equipes_json_sem_saves(equipes_de_teste):
    resposta = client.post("/equipes/restaurar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"].endswith("/equipes")
    _assert_equipes_iguais_ao_padrao(equipes_de_teste)


def test_restaurar_padrao_funciona_mesmo_com_saves(equipes_de_teste):
    _criar_save_de_teste()

    resposta = client.post("/equipes/restaurar", follow_redirects=False)

    assert resposta.status_code == 303
    _assert_equipes_iguais_ao_padrao(equipes_de_teste)
    assert persistencia.listar_saves() == ["1_01_01_2026"]


def test_editar_e_restaurar_nao_afetam_jogo_em_andamento():
    time_a = Equipe("Time A", forca=50, id=901)
    time_b = Equipe("Time B", forca=50, id=902)
    jogo = estado.iniciar_jogo("Campeonato Teste", time_a, 2026, [time_a, time_b])

    client.post(
        "/equipes/Campeonato Teste/901/editar", data={"financas": "1", "fas": "2", "forca": "99"}
    )
    client.post("/equipes/restaurar")

    assert estado.obter_jogo() is jogo
    assert jogo.time_escolhido is time_a
    assert jogo.classificados == [time_a, time_b]
    assert jogo.classificados[0] is time_a
    assert time_a.forca == 50
    assert time_a.financas == Equipe("Time A").financas
    assert time_a.fas == Equipe("Time A").fas


def test_tela_equipes_campeonato_mostra_um_escudo_por_time():
    resposta = client.get("/equipes/Campeonato Teste")

    assert resposta.status_code == 200
    assert resposta.text.count('class="escudo"') == 2
    assert 'aria-label="Escudo do Time A"' in resposta.text
    assert 'aria-label="Escudo do Time B"' in resposta.text


def test_tela_editar_equipe_mostra_o_escudo_do_time():
    resposta = client.get("/equipes/Campeonato Teste/901/editar")

    assert resposta.status_code == 200
    assert resposta.text.count('class="escudo"') == 1
    assert 'aria-label="Escudo do Time A"' in resposta.text


def test_tela_editar_equipe_nao_tem_campo_de_cor():
    resposta = client.get("/equipes/Campeonato Teste/901/editar")

    assert resposta.status_code == 200
    assert 'type="color"' not in resposta.text
    assert 'name="cores"' not in resposta.text


def test_editar_equipe_nao_altera_as_cores_salvas(equipes_de_teste):
    cores = ["#111111", "#222222", "#333333"]
    dados = _ler_equipes_salvas(equipes_de_teste)
    dados["Campeonato Teste"][0]["cores"] = cores
    equipes_de_teste.write_text(json.dumps(dados), encoding="utf-8")

    resposta = client.post(
        "/equipes/Campeonato Teste/901/editar",
        data={"financas": "2500000", "fas": "75000", "forca": "88", "cores": "#FFFFFF"},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    time_a = _equipe_salva(equipes_de_teste, "Campeonato Teste", 901)
    assert time_a["forca"] == 88
    assert time_a["cores"] == cores


@pytest.mark.parametrize("valor", ["²", "³", "①"])
def test_editar_equipe_com_digito_unicode_nao_numerico_retorna_400_e_nao_500(equipes_de_teste, valor):
    """`str.isdigit()` aceita caracteres como "²" que `int()` não converte —
    a validação precisa responder 400 com a mensagem amigável, nunca 500.
    """
    cliente = TestClient(app, raise_server_exceptions=False)

    resposta = cliente.post(
        "/equipes/Campeonato Teste/901/editar", data={"financas": valor, "fas": "1000", "forca": "50"}
    )

    assert resposta.status_code == 400
    assert "digite um número inteiro" in resposta.text

    time_a = _equipe_salva(equipes_de_teste, "Campeonato Teste", 901)
    assert time_a["financas"] == 1_000_000
