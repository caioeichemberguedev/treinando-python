"""Testes do isolamento automático feito pelo `tests/conftest.py`."""

import os

import persistencia


def test_dir_saves_aponta_para_tmp_path_em_qualquer_teste(tmp_path):
    assert persistencia.DIR_SAVES == str(tmp_path / "saves")


def test_caminho_save_fica_dentro_do_tmp_path(tmp_path):
    caminho = persistencia._caminho_save("x")

    assert caminho.startswith(str(tmp_path / "saves"))
    assert caminho == os.path.join(str(tmp_path / "saves"), "x.db")
