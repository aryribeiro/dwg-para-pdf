"""Fontes do desenho: sem elas o texto quebra onde não devia e embola.

O DWG referencia fontes pelo nome (aqui, Arial). Sem Arial no servidor o
ezdxf cai numa substituta mais larga, o MTEXT quebra numa linha a mais e as
linhas se atropelam — e no PDF isso fica gravado no arquivo entregue.

O ponto delicado é a ORDEM: o ezdxf guarda o desenho de cada fonte num
cache global do processo, com chave no nome PEDIDO ("arial.ttf") e não no
arquivo encontrado (ezdxf/fonts/fonts.py, TrueTypeFont.create_cache). Quem
mede um texto primeiro decide qual arquivo responde por aquele nome pelo
resto da vida do processo. Por isso prepare_font_environment() é a primeira
linha de dxf_to_pdf, antes de ler o desenho.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app  # noqa: E402

AJUDANTE = str(Path(__file__).parent / "_ambiente_de_fonte.py")


def test_arial_vem_no_repositorio():
    """A coleção de fontes tem de trazer a Arial: é ela que a maioria dos
    desenhos pede e que não existe no servidor."""
    assert (ROOT / "static" / "fonts" / "arial.ttf").is_file()


def test_ezdxf_resolve_arial_para_o_arquivo_do_repositorio():
    from ezdxf.fonts import fonts

    app.prepare_font_environment()
    for pedido in ("Arial", "ARIAL.TTF", "arial.ttf"):
        face = (fonts.get_font_face(pedido) if pedido.lower().endswith(".ttf")
                else fonts.resolve_font_face(pedido))
        assert face.filename.lower() == "arial.ttf", (pedido, face)


def _desenho_que_pede_arial(destino: Path):
    import ezdxf
    doc = ezdxf.new("R2010", setup=True)
    doc.styles.add("ARIAL", font="arial.ttf")
    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 0))
    mtext = msp.add_mtext(
        "Largura do tropo em metros e modulo de aco inox para a torre metalica",
        dxfattribs={"style": "ARIAL", "char_height": 2.5},
    )
    mtext.dxf.width = 40.0
    mtext.dxf.insert = (0, 5)
    doc.saveas(destino)
    return destino


def _medir(modo: str, dxf: Path | None = None):
    """Roda um modo do ajudante em processo separado — o cache de fontes do
    ezdxf é global e só um processo novo permite comparar duas ordens."""
    cmd = [sys.executable, AJUDANTE, modo]
    if dxf is not None:
        cmd.append(str(dxf))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    linhas = [l for l in r.stdout.splitlines() if l.startswith("{")]
    assert linhas, f"modo {modo} não produziu saída (rc={r.returncode}): {r.stderr[-500:]}"
    return json.loads(linhas[-1])


@pytest.mark.skipif(app.find_dwg2dxf() is None, reason="dwg2dxf ausente em bin/")
def test_fontes_sao_registradas_antes_de_ler_o_desenho(tmp_path):
    """Prova medida, não declaração: num servidor com fonte de sistema e sem
    Arial, a mesma frase mede 108,1 unidades pela DejaVu e 96,5 pela Arial
    (12% a mais). O app tem de entregar a medida da Arial. Inverter a ordem —
    ler o desenho antes de registrar as fontes — devolve a medida da DejaVu,
    e é isso que o teste reprovaria."""
    dxf = _desenho_que_pede_arial(tmp_path / "arial.dxf")

    sem_arial = _medir("sem-arial")
    com_arial = _medir("com-arial")
    assert sem_arial["largura"] != com_arial["largura"], (
        "as duas fontes mediriam igual: o teste não discriminaria nada")

    do_app = _medir("app", dxf)
    assert do_app["largura"] == com_arial["largura"], (
        f"o app mediu o texto com a fonte errada: {do_app} vs {com_arial}")

    invertida = _medir("ordem-invertida", dxf)
    assert invertida["largura"] == sem_arial["largura"], (
        "a ordem invertida deveria fixar a fonte errada; se isto falhar, o "
        "teste deixou de discriminar o defeito")
    # e o mais traiçoeiro: com a ordem invertida o ezdxf ainda diz que a
    # Arial está registrada — só que o texto já foi medido com a outra
    assert invertida["arial_resolve_para"].lower() == "arial.ttf"
