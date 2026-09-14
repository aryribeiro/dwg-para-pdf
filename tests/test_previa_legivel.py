"""A prévia precisa ter resolução para o texto de uma prancha de CAD.

Mesma queixa do app irmão dwg-para-dxf: a prancha "saiu sem os textos". O
artefato entregue estava certo — o que faltava era resolução e largura na
PRÉVIA. Numa prancha de 30 unidades com cotas de 0,12, a 150 dpi a folha A4
virava 1754 px, a menor cota ficava com 2,5 px na imagem e sumia ao ser
reduzida para a largura da coluna. Este teste mede e reprova na configuração
antiga.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app  # noqa: E402

ALTURA_MINIMA_PX = 12.0
LARGURA_DESENHO = 30.0
ALTURA_TEXTO = 0.12


def prancha_com_texto_pequeno(tmp_path: Path) -> Path:
    import ezdxf
    doc = ezdxf.new("R2004", setup=True)
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (LARGURA_DESENHO, 0), (LARGURA_DESENHO, LARGURA_DESENHO), (0, LARGURA_DESENHO)],
        close=True,
    )
    texto = msp.add_text("2.00", height=ALTURA_TEXTO)
    texto.dxf.insert = (LARGURA_DESENHO / 2, LARGURA_DESENHO / 2)
    caminho = tmp_path / "prancha.dxf"
    doc.saveas(caminho)
    return caminho


def test_a_menor_letra_sobrevive_na_previa(tmp_path):
    import pymupdf

    caminho = prancha_com_texto_pequeno(tmp_path)
    pdf, _info = app.dxf_to_pdf(caminho)
    pix = pymupdf.Pixmap(app.render_preview(pdf))

    # o desenho é quadrado e ocupa a altura útil da folha A4 menos as margens
    lado_util = min(pix.width, pix.height)
    altura_na_imagem = ALTURA_TEXTO / LARGURA_DESENHO * lado_util
    assert altura_na_imagem >= ALTURA_MINIMA_PX, (
        f"a menor letra sai com {altura_na_imagem:.1f} px na prévia de "
        f"{pix.width}x{pix.height}; abaixo de {ALTURA_MINIMA_PX} px o texto "
        "desaparece quando a imagem é reduzida para a largura da coluna"
    )


def test_o_texto_realmente_vira_tinta_na_previa(tmp_path):
    """Resolução não basta: o texto tem de ser DESENHADO. Mede tinta na faixa
    central da imagem, longe da moldura das bordas."""
    import pymupdf

    caminho = prancha_com_texto_pequeno(tmp_path)
    pdf, _info = app.dxf_to_pdf(caminho)
    pix = pymupdf.Pixmap(app.render_preview(pdf))

    y0, y1 = int(pix.height * 0.45), int(pix.height * 0.55)
    x0, x1 = int(pix.width * 0.15), int(pix.width * 0.85)
    escuros = sum(
        1
        for y in range(y0, y1)
        for x in range(x0, x1, 2)
        if sum(pix.pixel(x, y)[:3]) < 400
    )
    assert escuros > 50, f"nenhum texto desenhado no meio da prévia ({escuros} pixels escuros)"


@pytest.mark.skipif(
    not (Path(__file__).parent / "fixtures" / "private" / "torre.dwg").exists(),
    reason="prancha real do dono ausente (fica fora do git)",
)
def test_prancha_real_do_dono_tem_texto_legivel():
    """Desenho real que motivou a queixa: 717 entidades, 33 MTEXT, cotas de
    0,12 unidade. Conta as faixas de tinta do carimbo, no canto inferior
    direito — onde ficam o título e o nome do proprietário."""
    import pymupdf

    privado = Path(__file__).parent / "fixtures" / "private" / "torre.dwg"
    _pdf, preview, info = app.convert_dwg_to_pdf(str(privado))
    assert info["entities"] == 717
    pix = pymupdf.Pixmap(preview)
    assert max(pix.width, pix.height) >= 3500, (pix.width, pix.height)

    x0, x1 = int(pix.width * 0.66), pix.width - 1
    y0, y1 = int(pix.height * 0.62), int(pix.height * 0.98)
    linhas_com_tinta = sum(
        1
        for y in range(y0, y1, 3)
        if any(sum(pix.pixel(x, y)[:3]) < 400 for x in range(x0, x1, 3))
    )
    assert linhas_com_tinta > 40, f"carimbo quase vazio: {linhas_com_tinta} linhas com tinta"
