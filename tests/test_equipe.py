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
