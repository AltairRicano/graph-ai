"""`graph multiedit` sobre los documentos de Estado_Proyecto."""

from __future__ import annotations

import io

import pytest

from grafo_ia import templates
from grafo_ia.paths import doc_path

from conftest import read_doc, write

HOY = templates.today()


@pytest.fixture
def batch(run, monkeypatch):
    """Corre `graph multiedit` con el lote por stdin."""

    def _batch(root, text: str, *args: str):
        monkeypatch.setattr("sys.stdin", io.StringIO(text))
        return run(root, "multiedit", *args)

    return _batch


def _antiguo(root, name: str, fecha: str = "2026-01-01") -> None:
    p = doc_path(root, name)
    p.write_text(p.read_text(encoding="utf-8").replace(HOY, fecha), encoding="utf-8")


def test_varios_documentos_en_un_lote(initialized, batch):
    _antiguo(initialized, "Estado")
    code, out = batch(initialized, (
        "=== Estado_Proyecto/Estado.md#Hecho ===\n- Backend desplegado.\n"
        "=== Estado#Falta ===\n- Frontend en TypeScript.\n"
        "=== Estado_Proyecto/Decisiones.md ===\n## dinero_en_centavos\nCon flotantes no cuadra.\n"))
    assert code == 0, out
    assert "multiedit: 2 documentos escritos: Estado, Decisiones (2 secciones escritas)" in out
    estado = read_doc(initialized, "Estado")
    assert "## Hecho\n- Backend desplegado.\n\n## En curso" in estado and "## Falta\n- Frontend en TypeScript.\n" in estado
    assert "Lo que ya está completo" not in estado  # el texto guía de la sección se reemplazó
    assert "**Elaboración:**" not in estado  # Estado no lleva fechas por sección
    assert f"fecha_elaboracion: 2026-01-01\nfecha_actualizacion: {HOY}\n" in estado
    assert f"## dinero_en_centavos\n**Elaboración:** {HOY} | **Actualización:** {HOY}\n\nCon flotantes no cuadra.\n" in read_doc(initialized, "Decisiones")
    assert templates.is_shell("Plan", read_doc(initialized, "Plan"))  # los demás no se tocan


def test_seccion_reemplaza_y_conserva_elaboracion(initialized, batch):
    assert batch(initialized, "=== Decisiones ===\n## a\nUno.\n## b\nDos.\n")[0] == 0
    _antiguo(initialized, "Decisiones")
    assert batch(initialized, "=== Decisiones#a ===\n## a\nUno, corregido.\n")[0] == 0  # el heading repetido se quita
    text = read_doc(initialized, "Decisiones")
    assert f"## a\n**Elaboración:** 2026-01-01 | **Actualización:** {HOY}\n\nUno, corregido.\n" in text
    assert "## b\n**Elaboración:** 2026-01-01 | **Actualización:** 2026-01-01\n\nDos.\n" in text  # no se tocó
    assert text.count("## a\n") == 1


def test_append_y_override(initialized, batch):
    assert batch(initialized, "=== Estado#Falta ===\n- Uno.\n")[0] == 0
    assert batch(initialized, "=== Estado#Falta [append] ===\n- Dos.\n")[0] == 0
    assert "## Falta\n- Uno.\n\n- Dos.\n" in read_doc(initialized, "Estado")
    code, out = batch(initialized, "=== Plan [override] ===\n## frente & Frente\n### bloque\n- [ ] tarea\n")
    assert code == 0 and "1 cuerpo reemplazado" in out
    plan = read_doc(initialized, "Plan")
    assert plan.startswith("---\ntipo: plan\n") and plan.endswith("---\n## frente & Frente\n### bloque\n- [ ] tarea\n")


def test_seccion_nueva_solo_donde_el_documento_crece_por_entradas(initialized, batch):
    code, out = batch(initialized, "=== Tecnologias#base_datos & MySQL 8.4 ===\nAjustado a 300 MB.\n")
    assert code == 0, out
    tec = read_doc(initialized, "Tecnologias")
    assert tec.endswith(f"## base_datos & MySQL 8.4\n**Elaboración:** {HOY} | **Actualización:** {HOY}\n\nAjustado a 300 MB.\n")
    assert batch(initialized, "=== Tecnologias#base_datos ===\nAhora 8.5.\n")[0] == 0  # por su identificador
    assert read_doc(initialized, "Tecnologias").count("## base_datos") == 2  # la del ejemplo de la cáscara y la real
    code, out = batch(initialized, "=== Estado#Hechos ===\n- x\n")
    assert code == 2 and "no existe la sección 'Hechos'" in out and "Hecho, En curso, Falta, Siguientes pasos" in out


def test_arquitectura_fecha_los_sub_headings(initialized, batch):
    assert batch(initialized, "=== Arquitectura#Hardware ===\n### servidor\nUn host con Docker.\n")[0] == 0
    arq = read_doc(initialized, "Arquitectura")
    assert f"## Hardware\n### servidor\n**Elaboración:** {HOY} | **Actualización:** {HOY}\n\nUn host con Docker.\n\n## Tecnología" in arq


def test_un_error_no_aplica_nada(initialized, batch):
    antes = read_doc(initialized, "Estado")
    code, out = batch(initialized, "=== Estado#Hecho ===\n- Sí.\n=== src/pagos#Propósito ===\nNo.\n=== Estado#Nada ===\nx\n")
    assert code == 2 and "no se aplicó nada" in out
    assert "línea 3 (src/pagos#Propósito)" in out and "no es un documento de Estado_Proyecto" in out and "comentario del propio código" in out
    assert "línea 5 (Estado#Nada)" in out
    assert read_doc(initialized, "Estado") == antes


def test_lote_invalido(initialized, batch):
    assert batch(initialized, "")[0] == 2
    code, out = batch(initialized, "texto suelto\n=== Estado ===\nx\n")
    assert code == 2 and "antes del primer separador" in out
    code, out = batch(initialized, "=== Estado#Hecho ===\n\n")
    assert code == 2 and "entrada sin contenido" in out
    code, out = batch(initialized, "=== Estado#Hecho ===\n## Hecho\n")
    assert code == 2 and "solo trae el heading" in out


def test_separador_dentro_de_bloque_de_codigo_no_corta(initialized, batch):
    code, out = batch(initialized, "=== Decisiones ===\n## formato\nEjemplo:\n```\n=== Estado ===\n```\nFin.\n")
    assert code == 0, out
    assert "=== Estado ===" in read_doc(initialized, "Decisiones") and "1 documento escrito: Decisiones" in out
    code, out = batch(initialized, "=== Decisiones ===\n## otra\n```\n=== Estado ===\nsin cerrar\n")
    assert code == 0 and "[AVISO]" in out and "bloque de código sin cerrar" in out


def test_lote_por_archivo_se_borra(initialized, run):
    lote = write(initialized, "lote.txt", "=== Estado#Hecho ===\nEntrada.\n")
    assert run(initialized, "multiedit", "-f", "lote.txt")[0] == 0
    assert not lote.exists()
    lote = write(initialized, "lote.txt", "=== Estado#Hecho ===\nOtra.\n")
    assert run(initialized, "multiedit", "-f", "lote.txt", "--keep")[0] == 0
    assert lote.exists() and "Otra." in read_doc(initialized, "Estado")


def test_no_inventa_fechas_en_secciones_que_no_toco(initialized, batch):
    p = doc_path(initialized, "Decisiones")
    p.write_text(p.read_text(encoding="utf-8") + "\n## sin_fecha\nNadie la fechó.\n", encoding="utf-8")
    assert batch(initialized, "=== Decisiones#otra ===\nNueva.\n")[0] == 0
    text = read_doc(initialized, "Decisiones")
    assert "## sin_fecha\nNadie la fechó.\n" in text
    assert f"## otra\n**Elaboración:** {HOY} | **Actualización:** {HOY}\n\nNueva.\n" in text


def test_documento_borrado_nace_de_su_cascara(initialized, batch):
    doc_path(initialized, "Estado").unlink()
    assert batch(initialized, "=== Estado#Hecho ===\n- De vuelta.\n")[0] == 0
    assert "## Hecho\n- De vuelta.\n\n## En curso" in read_doc(initialized, "Estado")
