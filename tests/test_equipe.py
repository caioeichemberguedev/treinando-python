import pytest

from equipe import Equipe


CORES_SAO_PAULO = ["#E30613", "#FFFFFF", "#000000"]


def test_equipe_sem_cores_tem_cores_none():
    """Sem informar cores, o time fica sem cores cadastradas (None)."""
    assert Equipe("X").cores is None


def test_equipe_com_cores_guarda_lista_com_os_tres_valores():
    """As cores podem vir em qualquer sequência (ex.: tupla), mas são
    guardadas como `list`.
    """
    equipe = Equipe("X", cores=("#000000", "#FFFFFF", "#000000"))

    assert isinstance(equipe.cores, list)
    assert equipe.cores == ["#000000", "#FFFFFF", "#000000"]


def test_equipe_copia_a_lista_de_cores_recebida():
    """Alterar a lista original depois de criar a equipe não muda as cores
    dela.
    """
    cores = list(CORES_SAO_PAULO)
    equipe = Equipe("São Paulo", cores=cores)

    cores[0] = "#123456"

    assert equipe.cores == CORES_SAO_PAULO


def test_to_dict_sempre_tem_a_chave_cores():
    assert Equipe("X").to_dict()["cores"] is None
    assert Equipe("X", cores=CORES_SAO_PAULO).to_dict()["cores"] == (
        CORES_SAO_PAULO
    )


def test_ida_e_volta_com_cores_preserva_todos_os_campos():
    original = Equipe(
        "São Paulo",
        financas=1_234,
        fas=5_678,
        titulos=3,
        forca=80,
        cores=CORES_SAO_PAULO,
    )

    copia = Equipe.from_dict(original.to_dict())

    assert copia.to_dict() == original.to_dict()


def test_ida_e_volta_sem_cores_preserva_todos_os_campos():
    original = Equipe("X", financas=1, fas=2, titulos=4, forca=10)

    copia = Equipe.from_dict(original.to_dict())

    assert copia.to_dict() == original.to_dict()
    assert copia.cores is None


def test_from_dict_de_save_antigo_sem_cores_carrega_sem_erro():
    """Saves antigos não têm a chave `cores` — devem carregar com None."""
    equipe = Equipe.from_dict({"nome": "X", "forca": 70})

    assert equipe.nome == "X"
    assert equipe.forca == 70
    assert equipe.cores is None


def test_from_dict_de_string_crua_fica_sem_cores():
    equipe = Equipe.from_dict("X")

    assert equipe.nome == "X"
    assert equipe.cores is None


def test_repr_inclui_cores():
    assert "cores=['#E30613', '#FFFFFF', '#000000']" in repr(
        Equipe("São Paulo", cores=CORES_SAO_PAULO)
    )


def test_equipe_sem_id_tem_id_none():
    assert Equipe("X").id is None


def test_equipe_com_id_guarda_o_valor():
    assert Equipe("X", id=7).id == 7


def test_id_e_somente_leitura():
    """`id` é uma propriedade sem setter: não pode ser trocado depois."""
    equipe = Equipe("X", id=7)

    with pytest.raises(AttributeError):
        equipe.id = 8

    assert equipe.id == 7


def test_to_dict_sempre_tem_a_chave_id():
    assert Equipe("X").to_dict()["id"] is None
    assert Equipe("X", id=7).to_dict()["id"] == 7


def test_ida_e_volta_com_id_preserva_id_e_demais_campos():
    original = Equipe(
        "São Paulo",
        financas=1_234,
        fas=5_678,
        titulos=3,
        forca=80,
        cores=CORES_SAO_PAULO,
        id=1,
    )

    copia = Equipe.from_dict(original.to_dict())

    assert copia.id == 1
    assert copia.to_dict() == original.to_dict()


def test_from_dict_sem_id_fica_com_id_none():
    """Dados antigos sem a chave `id` carregam sem erro, com id None."""
    assert Equipe.from_dict({"nome": "X"}).id is None


def test_from_dict_de_string_crua_fica_sem_id():
    assert Equipe.from_dict("X").id is None


def test_repr_inclui_id():
    assert "id=7" in repr(Equipe("X", id=7))
    assert "id=None" in repr(Equipe("X"))


def test_id_nao_muda_a_comparacao_por_nome_ainda():
    """Nesta etapa a igualdade continua pelo nome (a troca é na ID-007-T8)."""
    assert Equipe("X", id=1) == Equipe("X", id=2)
    assert Equipe("X", id=1) == "X"
