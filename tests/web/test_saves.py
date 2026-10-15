import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import catalogo
import persistencia
import web.estado as estado
import web.rotas.saves as saves_rotas
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
    nome,
    campeonato="Campeonato Teste",
    time_escolhido=None,
    temporada=2026,
    classificados="padrao",
    historico=None,
    fases_da_temporada=None,
):
    time_escolhido = time_escolhido or Equipe("Time A", id=901)
    if classificados == "padrao":
        classificados = [Equipe("Time A", id=901), Equipe("Time B", id=902)]
    persistencia.salvar_jogo(
        nome, campeonato, time_escolhido, temporada, classificados, historico, fases_da_temporada
    )


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
    assert resposta.headers["location"] == "/carreira"

    jogo = estado.obter_jogo()
    assert jogo is not None
    assert jogo.campeonato == "Campeonato Teste"
    assert jogo.time_escolhido.nome == "Time A"
    assert jogo.time_escolhido.id == 901
    assert jogo.temporada == 2027
    assert {str(time) for time in jogo.classificados} == {"Time A", "Time B"}
    assert jogo.historico == []


def test_carregar_save_leva_ao_dashboard_e_o_fluxo_da_fase_funciona():
    """Carregar abre o dashboard (`/carreira`, E-019); de lá, "Jogar próxima
    fase" (`GET /fase`) funciona normalmente — mesma asserção
    usada nos testes do ID-001 (com o time do jogador presente na fase, o
    fluxo redireciona para a disputa de pênaltis).
    """
    _criar_save("1_01_01_2026")
    carregar = client.post("/saves/1_01_01_2026/carregar", follow_redirects=False)
    assert carregar.headers["location"] == "/carreira"
    assert client.get("/carreira").status_code == 200

    resposta = client.get("/fase", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fase/penaltis"


def test_carregar_save_com_classificados_none_sorteia_a_partir_do_elenco_base():
    _criar_save("1_01_01_2026", classificados=None)

    resposta = client.post("/saves/1_01_01_2026/carregar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/carreira"
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
    """Retrato do time escolhido sem cores no save (`cores` NULL): o
    escudo busca as cores pelo id no catálogo do elenco padrão."""
    _criar_save("1_01_01_2026", time_escolhido=Equipe("São Paulo", id=1))

    resposta = client.get("/saves")

    assert resposta.status_code == 200
    assert resposta.text.count('class="escudo"') == 1
    assert "#E30613" in resposta.text


def test_tela_saves_mostra_nome_do_catalogo_do_adm():
    """O save guarda o retrato antigo ("São Paulo"), mas a tela resolve o
    nome pelo id no catálogo editado pelo adm."""
    catalogo.salvar_time_no_catalogo(1, "Nome Adm", ["#FF0000"])
    _criar_save("1_01_01_2026", time_escolhido=Equipe("São Paulo", id=1))
    _criar_save("2_01_01_2026")

    resposta = client.get("/saves")

    assert resposta.status_code == 200
    assert "Nome Adm" in resposta.text
    assert "São Paulo" not in resposta.text
    assert "Time A" in resposta.text


def _bytes_do_save(nome):
    return Path(persistencia._caminho_save(nome)).read_bytes()


def test_carregar_save_guarda_o_nome_do_save_no_estado():
    _criar_save("1_01_01_2026")

    client.post("/saves/1_01_01_2026/carregar", follow_redirects=False)

    assert estado.obter_jogo().nome_save == "1_01_01_2026"


def test_carregar_save_no_meio_da_temporada_nao_grava_nada():
    """Com `classificados` já preenchidos, carregar não regrava o arquivo
    nem cria outro (paridade com `menu.carregar_jogo`)."""
    _criar_save("1_01_01_2026", temporada=2027)
    antes = _bytes_do_save("1_01_01_2026")
    arquivos_antes = sorted(os.listdir(persistencia.DIR_SAVES))

    resposta = client.post("/saves/1_01_01_2026/carregar", follow_redirects=False)

    assert resposta.status_code == 303
    assert _bytes_do_save("1_01_01_2026") == antes
    assert sorted(os.listdir(persistencia.DIR_SAVES)) == arquivos_antes
    assert persistencia.listar_saves() == ["1_01_01_2026"]


def test_carregar_save_com_classificados_none_grava_o_sorteio_no_mesmo_arquivo():
    historico = [{"temporada": 2026, "campeao": 901, "fases": []}]
    _criar_save("1_01_01_2026", temporada=2027, classificados=None, historico=historico)
    arquivos_antes = sorted(os.listdir(persistencia.DIR_SAVES))

    resposta = client.post("/saves/1_01_01_2026/carregar", follow_redirects=False)

    assert resposta.status_code == 303
    jogo = estado.obter_jogo()
    salvo = persistencia.carregar_jogo_salvo("1_01_01_2026")
    assert salvo["classificados"] is not None
    assert [time.id for time in salvo["classificados"]] == [time.id for time in jogo.classificados]
    assert salvo["temporada"] == 2027
    assert salvo["historico"] == historico
    assert salvo["time_escolhido"].id == 901
    assert sorted(os.listdir(persistencia.DIR_SAVES)) == arquivos_antes
    assert persistencia.listar_saves() == ["1_01_01_2026"]


def test_carregar_save_com_classificados_none_preserva_a_ordem_do_sorteio(monkeypatch):
    """A ordem gravada é exatamente a do estado — força um sorteio que
    inverte a ordem do elenco para não depender da sorte."""
    monkeypatch.setattr(saves_rotas, "sortear_classificados", lambda times: list(reversed(times)))
    _criar_save("1_01_01_2026", classificados=None)

    client.post("/saves/1_01_01_2026/carregar", follow_redirects=False)

    salvo = persistencia.carregar_jogo_salvo("1_01_01_2026")
    assert [time.id for time in estado.obter_jogo().classificados] == [902, 901]
    assert [time.id for time in salvo["classificados"]] == [902, 901]


def test_carregar_save_none_com_elenco_insuficiente_da_400_e_nao_grava():
    """Sem times suficientes para sortear, o carregar falha antes de gravar:
    o arquivo continua igual e nenhum jogo fica em andamento."""
    _criar_save("1_01_01_2026", campeonato="Campeonato Vazio", classificados=None)
    antes = _bytes_do_save("1_01_01_2026")
    arquivos_antes = sorted(os.listdir(persistencia.DIR_SAVES))

    resposta = client.post("/saves/1_01_01_2026/carregar", follow_redirects=False)

    assert resposta.status_code == 400
    assert _bytes_do_save("1_01_01_2026") == antes
    assert sorted(os.listdir(persistencia.DIR_SAVES)) == arquivos_antes
    assert estado.obter_jogo() is None


def test_carregar_save_inexistente_nao_cria_arquivo():
    _criar_save("1_01_01_2026")
    arquivos_antes = sorted(os.listdir(persistencia.DIR_SAVES))

    resposta = client.post("/saves/9_01_01_2026/carregar", follow_redirects=False)

    assert resposta.status_code == 404
    assert sorted(os.listdir(persistencia.DIR_SAVES)) == arquivos_antes
    assert estado.obter_jogo() is None


# --- E-019-T6: sem a mensagem do antigo "Salvar e sair" ---


@pytest.mark.parametrize("url", ["/saves", "/saves?salvo=1"])
def test_tela_saves_nao_mostra_progresso_salvo(url):
    _criar_save("1_01_01_2026")

    resposta = client.get(url)

    assert resposta.status_code == 200
    assert "Progresso salvo!" not in resposta.text
    assert "1_01_01_2026" in resposta.text


# --- B-020: o time do jogador é um objeto só depois de carregar ---


def _jogar_ate_o_campeao(jogo):
    """Joga (pênaltis no canto 1) e segue até a temporada ter campeão."""
    while jogo.campeao is None:
        resposta = client.get("/fase", follow_redirects=False)
        if resposta.status_code == 303 and resposta.headers["location"] == "/fase/penaltis":
            client.get("/fase/penaltis")
            while True:
                cobranca = client.post("/fase/penaltis", data={"canto": "1"}, follow_redirects=False)
                assert cobranca.status_code == 303
                if cobranca.headers["location"] == "/fase":
                    break
        seguir = client.post("/fase/seguir", follow_redirects=False)
        assert seguir.status_code == 303


def _esta_na_lista(objeto, lista):
    return any(item is objeto for item in lista)


def test_carregar_no_meio_da_temporada_ficha_soma_o_titulo_do_jogador():
    bicampeao = Equipe("Time A", id=901, titulos=2)
    _criar_save("1_01_01_2026", time_escolhido=bicampeao, classificados=[bicampeao, Equipe("Time B", id=902)])

    client.post("/saves/1_01_01_2026/carregar", follow_redirects=False)
    jogo = estado.obter_jogo()

    assert _esta_na_lista(jogo.time_escolhido, jogo.classificados)

    _jogar_ate_o_campeao(jogo)
    esperado = 2 + (1 if jogo.campeao.id == 901 else 0)

    html = client.get("/carreira").text
    assert f"<th>Títulos</th><td>{esperado}</td>" in html


def test_carregar_entre_temporadas_sorteia_com_o_proprio_time_escolhido():
    _criar_save("1_01_01_2026", time_escolhido=Equipe("Time A", id=901, titulos=2), classificados=None)

    client.post("/saves/1_01_01_2026/carregar", follow_redirects=False)
    jogo = estado.obter_jogo()

    assert jogo.time_escolhido.titulos == 2
    assert _esta_na_lista(jogo.time_escolhido, jogo.classificados)
    assert _esta_na_lista(jogo.time_escolhido, jogo.times_do_campeonato)

    _jogar_ate_o_campeao(jogo)
    esperado = 2 + (1 if jogo.campeao.id == 901 else 0)
    assert jogo.time_escolhido.titulos == esperado

    resposta = client.post("/campeao/continuar", follow_redirects=False)

    assert resposta.status_code == 303
    assert _esta_na_lista(jogo.time_escolhido, jogo.classificados)
    assert _esta_na_lista(jogo.time_escolhido, jogo.times_do_campeonato)
    assert f"<th>Títulos</th><td>{esperado}</td>" in client.get("/carreira").text


# --- E-014-T5: fases da temporada em andamento ---------------------------------

FASES_EM_ANDAMENTO = [
    {"nome_fase": "Semifinal - Campeonato Teste", "confrontos": [[901, 903, 901, 2, 1], [902, 904, 902, 1, 0]]},
]


def test_carregar_save_no_meio_da_temporada_devolve_as_fases_do_save():
    _criar_save("1_01_01_2026", fases_da_temporada=FASES_EM_ANDAMENTO)

    resposta = client.post("/saves/1_01_01_2026/carregar", follow_redirects=False)

    assert resposta.status_code == 303
    assert estado.obter_jogo().fases_da_temporada == FASES_EM_ANDAMENTO


def test_carregar_save_no_meio_com_fases_nao_grava_nada():
    _criar_save("1_01_01_2026", fases_da_temporada=FASES_EM_ANDAMENTO)
    antes = _bytes_do_save("1_01_01_2026")

    client.post("/saves/1_01_01_2026/carregar", follow_redirects=False)

    assert _bytes_do_save("1_01_01_2026") == antes


def test_carregar_save_antigo_sem_fases_comeca_com_lista_vazia():
    _criar_save("1_01_01_2026")

    client.post("/saves/1_01_01_2026/carregar", follow_redirects=False)

    assert estado.obter_jogo().fases_da_temporada == []


def test_carregar_save_entre_temporadas_comeca_sem_fases_e_grava_vazio():
    _criar_save("1_01_01_2026", temporada=2027, classificados=None)

    client.post("/saves/1_01_01_2026/carregar", follow_redirects=False)

    assert estado.obter_jogo().fases_da_temporada == []
    assert persistencia.carregar_jogo_salvo("1_01_01_2026")["fases_da_temporada"] == []
