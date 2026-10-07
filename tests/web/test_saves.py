import json
import os

import pytest
from fastapi.testclient import TestClient

import persistencia
import web.estado as estado
from equipe import Equipe
from web.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def equipes_e_saves_de_teste(tmp_path, monkeypatch):
    """Isola os testes de um `equipes.json` e de um diretório `saves/` de
    teste (nunca os reais do projeto), e reseta o "jogo em andamento" em
    memória entre os testes.
    """
    dados = {
        "Campeonato Teste": [
            {"id": 901, "nome": "Time A", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"id": 902, "nome": "Time B", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
        ],
    }
    arquivo_equipes = tmp_path / "equipes.json"
    arquivo_equipes.write_text(json.dumps(dados), encoding="utf-8")
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(arquivo_equipes))
    monkeypatch.setattr(persistencia, "DIR_SAVES", str(tmp_path / "saves"))

    monkeypatch.setattr(estado, "_jogo_atual", None)
    yield


def _criar_save(
    nome, campeonato="Campeonato Teste", time_escolhido=None, temporada=2026, classificados="padrao", historico=None
):
    time_escolhido = time_escolhido or Equipe("Time A", id=901)
    if classificados == "padrao":
        classificados = [Equipe("Time A", id=901), Equipe("Time B", id=902)]
    persistencia.salvar_jogo(nome, campeonato, time_escolhido, temporada, classificados, historico)


def test_tela_saves_sem_nenhuma_carreira_mostra_mensagem_vazia():
    resposta = client.get("/saves")

    assert resposta.status_code == 200
    assert "Nenhuma carreira salva" in resposta.text


def test_tela_saves_lista_os_dados_certos():
    _criar_save("1_01_01_2026", temporada=2027)

    resposta = client.get("/saves")

    assert resposta.status_code == 200
    assert "1_01_01_2026" in resposta.text
    assert "Time A" in resposta.text
    assert "Campeonato Teste" in resposta.text
    assert "2027" in resposta.text


def test_carregar_save_valido_redireciona_e_preenche_o_estado():
    _criar_save("1_01_01_2026", temporada=2027)

    resposta = client.post("/saves/1_01_01_2026/carregar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fase"

    jogo = estado.obter_jogo()
    assert jogo is not None
    assert jogo.campeonato == "Campeonato Teste"
    assert jogo.time_escolhido.nome == "Time A"
    assert jogo.time_escolhido.id == 901
    assert jogo.temporada == 2027
    assert {str(time) for time in jogo.classificados} == {"Time A", "Time B"}
    assert jogo.historico == []


def test_carregar_save_leva_para_a_fase_e_o_fluxo_ja_existente_funciona():
    """Depois de carregar, `GET /fase` funciona normalmente — mesma asserção
    usada nos testes do ID-001 (com o time do jogador presente na fase, o
    fluxo redireciona para a disputa de pênaltis).
    """
    _criar_save("1_01_01_2026")
    client.post("/saves/1_01_01_2026/carregar")

    resposta = client.get("/fase", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fase/penaltis"


def test_carregar_save_com_classificados_none_sorteia_a_partir_do_elenco_base():
    _criar_save("1_01_01_2026", classificados=None)

    resposta = client.post("/saves/1_01_01_2026/carregar", follow_redirects=False)

    assert resposta.status_code == 303
    jogo = estado.obter_jogo()
    assert jogo.classificados is not None
    assert {str(time) for time in jogo.classificados} == {"Time A", "Time B"}


def test_carregar_save_copia_o_historico_para_o_estado():
    historico = [{"temporada": 2026, "campeao": 901, "fases": []}]
    _criar_save("1_01_01_2026", temporada=2027, historico=historico)

    client.post("/saves/1_01_01_2026/carregar")

    jogo = estado.obter_jogo()
    assert jogo.historico == historico


def test_carregar_save_inexistente_retorna_404():
    resposta = client.post("/saves/save_fantasma/carregar")

    assert resposta.status_code == 404


def test_confirmar_exclusao_mostra_tela_de_confirmacao_sem_excluir():
    _criar_save("1_01_01_2026")

    resposta = client.get("/saves/1_01_01_2026/excluir")

    assert resposta.status_code == 200
    assert "certeza" in resposta.text.lower()
    assert "1_01_01_2026" in resposta.text
    assert "1_01_01_2026" in persistencia.listar_saves()


def test_confirmar_exclusao_de_save_inexistente_retorna_404():
    resposta = client.get("/saves/save_fantasma/excluir")

    assert resposta.status_code == 404


def test_excluir_save_existente_some_da_listagem_seguinte():
    _criar_save("1_01_01_2026")

    resposta = client.post("/saves/1_01_01_2026/excluir", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/saves"
    assert "1_01_01_2026" not in persistencia.listar_saves()

    resposta_lista = client.get("/saves")
    assert "1_01_01_2026" not in resposta_lista.text


def test_excluir_save_inexistente_retorna_404():
    resposta = client.post("/saves/save_fantasma/excluir")

    assert resposta.status_code == 404


def test_tela_saves_mostra_um_escudo_por_carreira():
    _criar_save("1_01_01_2026")

    resposta = client.get("/saves")

    assert resposta.status_code == 200
    assert resposta.text.count('class="escudo"') == 1


def test_tela_saves_save_antigo_sem_cores_usa_cores_do_catalogo():
    """Save gravado antes do campo `cores` existir: o escudo do time
    escolhido busca as cores pelo id no catálogo do elenco padrão."""
    _criar_save("1_01_01_2026", time_escolhido=Equipe("São Paulo", id=1))
    arquivo = os.path.join(persistencia.DIR_SAVES, "1_01_01_2026.json")
    with open(arquivo, encoding="utf-8") as f:
        dados = json.load(f)
    dados["time_escolhido"].pop("cores", None)
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f)

    resposta = client.get("/saves")

    assert resposta.status_code == 200
    assert resposta.text.count('class="escudo"') == 1
    assert "#E30613" in resposta.text
