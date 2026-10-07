import hashlib

import pytest

from web import sessao_admin
from web.sessao_admin import (
    COOKIE_SESSAO,
    DURACAO_SESSAO,
    area_admin_ativa,
    criar_token_sessao,
    senha_confere,
    token_sessao_valido,
)

SENHA = "senha-secreta-123"
AGORA = 1_800_000_000


@pytest.fixture
def com_senha(monkeypatch):
    monkeypatch.setenv("ADMIN_SENHA", SENHA)


@pytest.fixture
def sem_senha(monkeypatch):
    monkeypatch.delenv("ADMIN_SENHA", raising=False)


def _trocar_caractere(texto, posicao):
    novo = "0" if texto[posicao] != "0" else "1"
    return texto[:posicao] + novo + texto[posicao + 1:]


def test_constantes_da_sessao():
    assert COOKIE_SESSAO == "sessao_admin"
    assert DURACAO_SESSAO == 8 * 60 * 60


# --- área desligada -------------------------------------------------------

def test_sem_admin_senha_area_fica_desligada(sem_senha):
    assert area_admin_ativa() is False
    assert senha_confere("") is False
    assert senha_confere("qualquer") is False
    assert token_sessao_valido("123.abc") is False


def test_admin_senha_vazia_desliga_a_area(monkeypatch):
    monkeypatch.setenv("ADMIN_SENHA", "")

    assert area_admin_ativa() is False
    assert senha_confere("") is False
    assert senha_confere("qualquer") is False
    assert token_sessao_valido("123." + "a" * 64) is False


@pytest.mark.parametrize("senha", ["   ", "\t\n "])
def test_admin_senha_so_com_espacos_desliga_a_area(monkeypatch, senha):
    monkeypatch.setenv("ADMIN_SENHA", senha)

    assert area_admin_ativa() is False
    assert senha_confere(senha) is False
    with pytest.raises(RuntimeError):
        criar_token_sessao()


def test_admin_senha_com_caractere_nao_codificavel_desliga_a_area(monkeypatch):
    senha_invalida = "abc" + chr(0xD800)
    monkeypatch.setattr(sessao_admin.os, "environ", {"ADMIN_SENHA": senha_invalida})

    assert area_admin_ativa() is False
    assert senha_confere(senha_invalida) is False
    assert token_sessao_valido("123." + "a" * 64) is False


def test_token_criado_fica_invalido_se_a_senha_for_removida(com_senha, monkeypatch):
    token = criar_token_sessao(agora=AGORA)
    monkeypatch.delenv("ADMIN_SENHA")

    assert token_sessao_valido(token, agora=AGORA) is False


def test_criar_token_sem_senha_levanta_erro(sem_senha):
    with pytest.raises(RuntimeError):
        criar_token_sessao()


# --- senha ----------------------------------------------------------------

def test_com_admin_senha_area_fica_ativa(com_senha):
    assert area_admin_ativa() is True


def test_senha_certa_confere(com_senha):
    assert senha_confere(SENHA) is True


@pytest.mark.parametrize("tentativa", ["", "errada", SENHA + " ", SENHA.upper()])
def test_senha_errada_ou_vazia_nao_confere(com_senha, tentativa):
    assert senha_confere(tentativa) is False


def test_senha_com_acento_confere(monkeypatch):
    monkeypatch.setenv("ADMIN_SENHA", "coração")

    assert senha_confere("coração") is True
    assert senha_confere("coracao") is False


def test_senha_confere_usa_compare_digest(com_senha, monkeypatch):
    chamadas = []
    original = sessao_admin.secrets.compare_digest

    def espiao(a, b):
        chamadas.append((a, b))
        return original(a, b)

    monkeypatch.setattr(sessao_admin.secrets, "compare_digest", espiao)

    assert senha_confere(SENHA) is True
    assert len(chamadas) == 1


# --- token ----------------------------------------------------------------

def test_token_recem_criado_e_valido(com_senha):
    token = criar_token_sessao(agora=AGORA)

    assert token_sessao_valido(token, agora=AGORA) is True
    assert token_sessao_valido(token, agora=AGORA + DURACAO_SESSAO - 1) is True


def test_token_sem_agora_usa_relogio_atual(com_senha):
    assert token_sessao_valido(criar_token_sessao()) is True


def test_token_expirado_e_invalido(com_senha):
    token = criar_token_sessao(agora=AGORA)

    assert token_sessao_valido(token, agora=AGORA + DURACAO_SESSAO) is False
    assert token_sessao_valido(token, agora=AGORA + DURACAO_SESSAO + 3600) is False


def test_token_com_assinatura_adulterada_e_invalido(com_senha):
    token = criar_token_sessao(agora=AGORA)
    posicao = len(token) - 1

    assert token_sessao_valido(_trocar_caractere(token, posicao), agora=AGORA) is False


def test_token_com_expiracao_adulterada_e_invalido(com_senha):
    token = criar_token_sessao(agora=AGORA)
    expira, assinatura = token.split(".")
    adiada = str(int(expira) + 999_999)

    assert token_sessao_valido(_trocar_caractere(token, 0), agora=AGORA) is False
    assert token_sessao_valido(f"{adiada}.{assinatura}", agora=AGORA) is False


@pytest.mark.parametrize(
    "token",
    ["", "abc", "1.2.3", ".", "abc.def", "123.", ".abc", "-1.abc", "١٢٣.abc", "123.ção", None],
)
def test_token_malformado_e_invalido_sem_excecao(com_senha, token):
    assert token_sessao_valido(token, agora=AGORA) is False


def test_token_com_expiracao_gigante_e_invalido_sem_excecao(com_senha):
    # Mais dígitos que o limite de conversão str -> int do Python.
    token = "1" * 5000 + "." + "a" * 64

    assert token_sessao_valido(token, agora=AGORA) is False


def test_token_com_expiracao_de_13_digitos_e_invalido(com_senha):
    assert token_sessao_valido("1" * 13 + "." + "a" * 64, agora=AGORA) is False


def test_senha_com_caractere_invalido_nao_confere_sem_excecao(com_senha):
    assert senha_confere(chr(0xD800)) is False
    assert senha_confere(SENHA + chr(0xD800)) is False


def test_token_fica_invalido_ao_trocar_admin_senha(com_senha, monkeypatch):
    token = criar_token_sessao(agora=AGORA)
    monkeypatch.setenv("ADMIN_SENHA", "outra-senha")

    assert token_sessao_valido(token, agora=AGORA) is False


def test_token_fica_invalido_ao_trocar_a_chave_do_servidor(com_senha, monkeypatch):
    token = criar_token_sessao(agora=AGORA)
    monkeypatch.setattr(sessao_admin, "CHAVE", b"x" * 32)

    assert token_sessao_valido(token, agora=AGORA) is False


def test_token_nao_contem_a_senha_nem_o_hash_dela(com_senha):
    token = criar_token_sessao(agora=AGORA)

    assert SENHA not in token
    assert hashlib.sha256(SENHA.encode("utf-8")).hexdigest() not in token
    assert hashlib.sha256(SENHA.encode("utf-8")).hexdigest().upper() not in token


def test_formato_do_token_e_expiracao_ponto_assinatura(com_senha):
    expira, assinatura = criar_token_sessao(agora=AGORA).split(".")

    assert int(expira) == AGORA + DURACAO_SESSAO
    assert len(assinatura) == 64
    int(assinatura, 16)
