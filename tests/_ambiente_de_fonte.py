"""Ajudante do teste de ordem de registro das fontes.

Roda em processo SEPARADO de propósito. O ezdxf guarda o desenho de cada
fonte num cache global do processo (`TrueTypeFont._glyph_caches`), com
chave no nome PEDIDO — "arial.ttf" — e não no arquivo encontrado. Quem
mede um texto primeiro decide, para o resto da vida do processo, qual
arquivo de fonte responde por aquele nome. É por isso que a ORDEM importa
e é por isso que um único processo não conseguiria comparar as duas ordens.

Uso: python tests/_ambiente_de_fonte.py <modo> [arquivo.dxf]
Imprime uma linha JSON com a largura medida da frase de referência.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ezdxf import bbox                       # noqa: E402
from ezdxf.fonts import fonts as ezfonts     # noqa: E402

import app                                   # noqa: E402

FRASE = "Largura do tropo em metros e modulo de aco inox para a torre"
ALTURA = 2.5


def servidor_sem_arial():
    """Simula o servidor do Streamlit Cloud antes da correção: tem fonte de
    sistema (DejaVu), não tem Arial. É o ambiente em que o defeito aparece —
    no Windows, com a Arial do sistema, ele não aparece."""
    tmp = Path(tempfile.mkdtemp(prefix="fontes_"))
    shutil.copy2(ROOT / "static" / "fonts" / "DejaVuSans.ttf", tmp / "DejaVuSans.ttf")
    fm = ezfonts.font_manager
    fm.clear()
    fm.build([str(tmp)], support_dirs=False)
    fm.add_synonyms(ezfonts.FONT_SYNONYMS, reverse=True)


def largura_medida():
    """Largura que o ezdxf dá hoje para a frase pedida em 'arial.ttf'."""
    return round(ezfonts.make_font("arial.ttf", ALTURA).text_width(FRASE), 4)


def main():
    modo = sys.argv[1]
    dxf = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    if modo == "sem-arial":
        # referência: quanto mede a frase quando só há DejaVu
        servidor_sem_arial()
    elif modo == "com-arial":
        # referência: quanto mede a frase com as fontes do repositório
        app.prepare_font_environment()
    elif modo == "app":
        # o app de verdade, num servidor sem Arial
        servidor_sem_arial()
        app.dxf_to_pdf(dxf)
    elif modo == "ordem-invertida":
        # o defeito da v1.1.2 do app irmão: ler (e medir) antes de registrar
        servidor_sem_arial()
        doc, _ = app.read_dxf_with_repair(dxf)
        bbox.extents(doc.modelspace(), fast=True)
        app.prepare_font_environment()
    else:
        raise SystemExit(f"modo desconhecido: {modo}")

    print(json.dumps({
        "modo": modo,
        "largura": largura_medida(),
        "arial_resolve_para": ezfonts.resolve_font_face("Arial").filename,
    }))


if __name__ == "__main__":
    main()
