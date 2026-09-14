"""Testes do conversor DWG -> PDF.

Rodam fora do Streamlit (modo "bare"): os st.* viram avisos inofensivos.
Precisam do dwg2dxf em bin/ (Linux: bin/dwg2dxf do repo; Windows: bin/dwg2dxf.exe).
"""
import sys
import zlib
from pathlib import Path

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
OUTPUT = Path(__file__).parent / "output"

A4_PT = {595, 841}   # 210 x 297 mm arredondados para pontos (72 por polegada)


def abrir_pdf(data: bytes):
    """Confere a assinatura e devolve o documento aberto pelo PyMuPDF."""
    assert data[:5] == b"%PDF-", f"não é PDF: {data[:8]!r}"
    return pymupdf.open(stream=data, filetype="pdf")


def medir_tinta(page, dpi=72):
    """(bytes escuros, bytes totais, byte mais escuro) da página rasterizada.
    Serve para separar um desenho de verdade de uma folha em branco."""
    amostras = page.get_pixmap(dpi=dpi).samples
    brancos = amostras.count(255)
    return len(amostras) - brancos, len(amostras), min(amostras)


# --- inspeção do cabeçalho -------------------------------------------------

def test_header_dwg_2018():
    data = (FIXTURES / "sample_2018.dwg").read_bytes()
    assert app.inspect_header(data) == ("dwg", "2018")


def test_header_dxf_renomeado():
    data = b"  0\r\nSECTION\r\n  2\r\nHEADER\r\n  0\r\nENDSEC\r\n  0\r\nEOF\r\n"
    assert app.inspect_header(data)[0] == "dxf"


def test_header_impostores():
    assert app.inspect_header(b"%PDF-1.7 lixo")[0] == "outro"
    assert app.inspect_header(b"PK\x03\x04" + b"\x00" * 40)[0] == "outro"
    assert app.inspect_header(b"")[0] == "outro"


# --- avisos do LibreDWG ----------------------------------------------------

def test_resumo_de_avisos():
    stderr = (
        "Warning: Unstable Class object 506 MATERIAL (0x481) 67/AF\n"
        "Warning: Unhandled Object TABLESTYLE in out_dxf 101/D1\n"
        "Warning: Unknown object, skipping eed/reactors/xdic\n"
        "Warning: Unknown object, skipping eed/reactors/xdic\n"
        "Warning: Skip CELLSTYLEMAP\n"
        "Warning: Skip TABLEGEOMETRY\n"
        "Warning: Unhandled Object ACAD_TABLE in out_dxf 120/F0\n"
        "Warning: Skip HATCH common handles due to short handle stream\n"
    )
    unknown, classes = app.summarize_libredwg_warnings(stderr)
    assert unknown == 2
    # estilos/materiais não entram; "Skip HATCH common handles" não é perda
    # da hachura; tabela e geometria de tabela entram
    assert classes == ["ACAD_TABLE", "TABLEGEOMETRY"]


# --- reparo do DXF desalinhado ---------------------------------------------

def test_reparo_de_valor_com_quebra_de_linha(tmp_path):
    """Simula o defeito do LibreDWG: um valor de texto com quebra de linha
    no meio desalinha código/valor a partir dali."""
    import ezdxf
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0))
    msp.add_text("FICM").dxf.insert = (0, 5)
    msp.add_circle((5, 5), 2)
    good = tmp_path / "bom.dxf"
    doc.saveas(good)
    text = good.read_text(encoding="utf-8")
    assert text.count("\nFICM\n") == 1
    broken = tmp_path / "quebrado.dxf"
    broken.write_text(text.replace("\nFICM\n", "\nFICM: Electric\nlixo\n", 1), encoding="utf-8")
    with pytest.raises(Exception):
        ezdxf.readfile(broken)
    fixed, repairs = app.read_dxf_with_repair(broken)
    assert repairs == 1
    assert len(fixed.modelspace()) == 3


# --- página do PDF ---------------------------------------------------------

def test_pagina_a4_na_orientacao_do_desenho():
    """Desenho deitado sai em A4 deitado, desenho em pé sai em A4 em pé, e o
    tamanho é sempre o A4 — não depende do tamanho do desenho."""
    deitada, rotulo = app.page_for_extents(1000.0, 500.0)
    assert (round(deitada.width_in_mm), round(deitada.height_in_mm)) == (297, 210)
    assert "paisagem" in rotulo

    em_pe, rotulo = app.page_for_extents(500.0, 1000.0)
    assert (round(em_pe.width_in_mm), round(em_pe.height_in_mm)) == (210, 297)
    assert "retrato" in rotulo

    # desenho 60 000 vezes maior: mesma folha (no PDF o desenho é vetor, o
    # tamanho da página não decide nitidez)
    enorme, _ = app.page_for_extents(60_000_000.0, 30_000_000.0)
    assert (round(enorme.width_in_mm), round(enorme.height_in_mm)) == (297, 210)


# --- conversão de ponta a ponta -------------------------------------------

@pytest.mark.skipif(app.find_dwg2dxf() is None, reason="dwg2dxf ausente em bin/")
@pytest.mark.parametrize("name", ["sample_2018.dwg", "example_2018.dwg", "Leader_2000.dwg"])
def test_dwg_para_pdf(name):
    OUTPUT.mkdir(exist_ok=True)
    pdf, preview, info = app.convert_dwg_to_pdf(str(FIXTURES / name))
    doc = abrir_pdf(pdf)
    assert doc.page_count == 1
    page = doc[0]
    assert {round(page.rect.width), round(page.rect.height)} == A4_PT
    escuros, total, mais_escuro = medir_tinta(page)
    assert mais_escuro < 100, "a página saiu em branco"
    assert 0 < escuros < total * 0.9, f"tinta fora do razoável: {escuros}/{total}"
    assert info["entities"] > 0
    assert info["dwgversion"] in ("2018", "2000")
    assert info["page"].startswith("A4 ")
    assert preview[:8] == b"\x89PNG\r\n\x1a\n"
    doc.close()
    (OUTPUT / (Path(name).stem + ".pdf")).write_bytes(pdf)


@pytest.mark.skipif(app.find_dwg2dxf() is None, reason="dwg2dxf ausente em bin/")
def test_pdf_e_vetorial_e_nao_uma_imagem_dentro_de_um_pdf():
    """O que separa este app de "tirar uma foto do desenho e colar no PDF":
    a página tem traços e curvas de verdade e nenhuma imagem embutida, então
    ampliar não borra. Se a cadeia virasse rasterização, o teste reprovaria:
    haveria 1 imagem e nenhum traço."""
    pdf, _preview, _info = app.convert_dwg_to_pdf(str(FIXTURES / "example_2018.dwg"))
    doc = abrir_pdf(pdf)
    page = doc[0]

    assert page.get_images(full=True) == [], "há imagem embutida: o PDF virou foto"

    desenhos = page.get_drawings()
    assert len(desenhos) > 10, f"quase nada vetorial na página: {len(desenhos)}"
    tipos = {item[0] for d in desenhos for item in d["items"]}
    assert tipos & {"l", "c", "qu", "re"}, f"sem traços nem curvas: {tipos}"

    # ampliar 8x não perde definição: o mesmo traço é redesenhado maior, e o
    # arquivo continua do mesmo tamanho (não há pixels guardados nele)
    pequeno = page.get_pixmap(dpi=72)
    grande = page.get_pixmap(dpi=576)
    assert grande.width >= pequeno.width * 7
    assert min(grande.samples) < 100
    doc.close()


@pytest.mark.skipif(app.find_dwg2dxf() is None, reason="dwg2dxf ausente em bin/")
def test_previa_e_a_primeira_pagina_do_pdf_entregue():
    """A prévia na tela sai do próprio arquivo que a pessoa baixa, e não de
    um segundo desenho por outro caminho."""
    pdf, preview, _info = app.convert_dwg_to_pdf(str(FIXTURES / "Leader_2000.dwg"))
    doc = abrir_pdf(pdf)
    esperado = doc[0].get_pixmap(dpi=app.PREVIEW_DPI)
    doc.close()
    imagem = pymupdf.Pixmap(preview)
    assert (imagem.width, imagem.height) == (esperado.width, esperado.height)
    assert imagem.samples == esperado.samples


@pytest.mark.skipif(app.find_dwg2dxf() is None, reason="dwg2dxf ausente em bin/")
def test_dxf_renomeado_nao_passa_pelo_libredwg(tmp_path):
    # DXF mínimo válido com uma linha, salvo como .dwg
    import ezdxf
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0), (100, 50))
    fake = tmp_path / "renomeado.dwg"
    doc.saveas(fake)
    pdf, _preview, info = app.convert_dwg_to_pdf(str(fake))
    documento = abrir_pdf(pdf)
    assert documento.page_count == 1
    documento.close()
    assert info["dwgversion"] == "DXF renomeado"
    assert info["entities"] == 1


def test_desenho_sem_nada_desenhavel_da_mensagem_clara(tmp_path):
    """Dois casos que o ezdxf resolveria com ValueError cru: desenho só com
    linha infinita (não tem limites) e desenho cujo único traço está numa
    camada desligada (tem limites, mas nada é desenhado)."""
    import ezdxf

    so_infinita = ezdxf.new("R2010")
    so_infinita.modelspace().add_xline((0, 0), (1, 1))
    caminho = tmp_path / "infinita.dwg"
    so_infinita.saveas(caminho)
    with pytest.raises(app.ConversionError):
        app.convert_dwg_to_pdf(str(caminho))

    apagada = ezdxf.new("R2010")
    apagada.layers.add("OCULTA").off()
    apagada.modelspace().add_line((0, 0), (10, 10), dxfattribs={"layer": "OCULTA"})
    caminho = tmp_path / "camada_desligada.dwg"
    apagada.saveas(caminho)
    with pytest.raises(app.ConversionError):
        app.convert_dwg_to_pdf(str(caminho))


def test_arquivo_que_nao_e_dwg(tmp_path):
    fake = tmp_path / "foto.dwg"
    fake.write_bytes(b"\x89PNG\r\n\x1a\n" + zlib.compress(b"x" * 100))
    with pytest.raises(app.ConversionError):
        app.convert_dwg_to_pdf(str(fake))


@pytest.mark.skipif(app.find_dwg2dxf() is None, reason="dwg2dxf ausente em bin/")
def test_dwg_corrompido(tmp_path):
    data = bytearray((FIXTURES / "sample_2018.dwg").read_bytes())
    data[64:] = b"\x00" * (len(data) - 64)
    fake = tmp_path / "corrompido.dwg"
    fake.write_bytes(bytes(data))
    with pytest.raises(app.ConversionError):
        app.convert_dwg_to_pdf(str(fake))
