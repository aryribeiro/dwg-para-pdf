# 📐 Conversor de DWG para PDF

Aplicação web em Python/[Streamlit](https://streamlit.io/) que converte desenhos **DWG (AutoCAD) para PDF**, sem AutoCAD.

## 🎯 O que faz

| Entrada | Saída |
| --- | --- |
| `.dwg` (AutoCAD, R13 a 2018) | **`.pdf`** (uma página A4, desenho em vetor, fundo branco) |

Escopo único e fixo — este app não lida com nenhum outro formato de entrada ou saída.

- Interface de tela única (upload → converter → prévia → baixar)
- Converte o espaço do modelo: linhas, arcos, polilinhas, hachuras, textos, cotas e blocos
- Mostra a versão do AutoCAD, a contagem de elementos e camadas, o tamanho da página e a fonte usada — e **avisa quando a leitura foi parcial**
- Processamento em diretórios temporários — nenhum arquivo é armazenado

## 📄 O PDF sai em vetor, não é uma foto do desenho

O desenho entra no PDF como traços e curvas. Ampliar 10 vezes não borra nada, porque não há pixels guardados no arquivo. Isso é conferido por teste automatizado: na página gerada a partir de `example_2018.dwg` o PyMuPDF encontra **221 formas vetoriais e nenhuma imagem embutida** (`page.get_drawings()` cheio, `page.get_images()` vazio). Se algum dia a cadeia passasse a rasterizar, o teste reprovaria — seria o contrário: uma imagem e nenhuma forma.

Limite honesto do mesmo mecanismo: o texto vai desenhado, letra por letra, e **não é texto selecionável nem pesquisável** no leitor de PDF. É assim que o ezdxf desenha, para que o resultado seja igual ao do AutoCAD mesmo quando o leitor de PDF não tem a fonte do projeto.

## 📐 Por que a página é A4

O app irmão que gera PNG usa uma "página" de 10 polegadas, e esse número existe só para chegar a 4000 pixels no lado maior: **PNG tem resolução, PDF não tem**. No PDF o tamanho da página não decide nitidez — decide folha. Por isso aqui a escolha é **A4**, na orientação do desenho (deitado ou em pé), com margem de 10 mm e encaixe proporcional: o desenho entra inteiro, sem corte e sem distorção.

A4 é a folha que todo mundo tem e que qualquer visualizador e qualquer impressora entendem sem ajuste. Quem precisa plotar em A1 amplia na hora de imprimir e não perde nada, justamente por ser vetor. Não há opção a escolher na tela: uma decisão, tomada aqui.

## ⚙️ Como converte

1. **GNU LibreDWG** (`bin/dwg2dxf`, binário Linux estático, versão 0.14) lê o DWG e grava um DXF.
2. **ezdxf** interpreta o DXF (cores por camada, blocos, hachuras, textos).
3. **PyMuPDF** monta o PDF vetorial e rasteriza a **primeira página do PDF já pronto** para a prévia da tela — a prévia é o próprio arquivo que será baixado, não um segundo desenho por outro caminho.

Limites honestos do leitor livre: tabelas do AutoCAD (`ACAD_TABLE`), objetos de complementos (Architecture, Civil 3D) e sólidos 3D não são desenhados. Quando isso acontece, a interface avisa em vez de entregar um "sucesso" silencioso. Um DXF renomeado para `.dwg` é detectado e convertido sem passar pelo LibreDWG.

Resiliência incorporada (herdada do app irmão, medida numa varredura de 164 DWG reais, de R13 a 2018):

- **DXF desalinhado**: em DWG com bits corrompidos o LibreDWG grava lixo com quebra de linha dentro de textos, e a saída muda a cada execução. O app conserta o desalinhamento apontado pelo erro e relê, em vez de falhar.
- **Desenho sem imagem**: linhas infinitas (XLINE/RAY), camadas desligadas e sólidos 3D não viram desenho no papel; o app explica em vez de estourar.
- **Fontes do desenho**: o DWG pede fontes pelo nome (Arial, na maioria dos projetos). Sem elas o leitor cai numa substituta mais larga, o texto quebra numa linha a mais e as linhas se atropelam — e no PDF isso fica gravado no arquivo entregue. `static/fonts/` traz a coleção de 180 fontes dos apps irmãos, incluindo a Arial, e o app a registra **antes de abrir o desenho** (a ordem importa: quem mede um texto primeiro decide, para o resto da vida do processo, qual arquivo responde pelo nome "arial.ttf").
- **Concorrência e disco**: no máximo 2 conversões simultâneas e limpeza de pastas temporárias órfãs, como nos apps irmãos.
- **Desenhos pesados** (dezenas de MB de geometria em blocos dinâmicos) podem levar mais de um minuto.

## 🚀 Rodar localmente

Pré-requisitos: Python 3.10+ e o `dwg2dxf` da LibreDWG.

- **Linux/macOS**: o binário Linux já está em `bin/`. No macOS, instale a LibreDWG (`brew install libredwg`) — o app usa o `dwg2dxf` do PATH.
- **Windows**: baixe `libredwg-0.14-win64.zip` em https://github.com/LibreDWG/libredwg/releases e copie `dwg2dxf.exe` para `bin/` (o `.gitignore` já ignora).

```bash
pip install -r requirements.txt
streamlit run app.py
```

Abre em `http://localhost:8501`.

## 🧪 Testes

```bash
pip install pytest
pytest -q
```

Saída real desta suíte no Windows:

```
..................                                                       [100%]
18 passed in 31.76s
```

Os testes cobrem a detecção de versão e de impostores, o resumo de avisos do LibreDWG, o reparo do DXF desalinhado, a escolha da página, a conversão de ponta a ponta com DWG reais de `tests/fixtures/` (arquivos de teste do próprio projeto LibreDWG), a prova de que o PDF é vetorial, a prévia que sai do PDF entregue e a ordem de registro das fontes. Os PDF gerados ficam em `tests/output/`.

O teste de fontes mede, em processos separados, a largura da mesma frase com e sem Arial: **96,4853 unidades pela Arial e 108,1463 pela DejaVu** (12% mais larga). O app tem de entregar a medida da Arial; inverter a ordem (ler o desenho antes de registrar as fontes) devolve a da DejaVu — e o pior é que, mesmo assim, o ezdxf continua dizendo que a Arial está registrada. É esse silêncio que o teste quebra.

Para provar o ambiente de deploy (Debian trixie com Python 3.13 e os pacotes do `packages.txt`):

```bash
docker build --load -f tests/Dockerfile.smoke -t dwg-pdf-smoke . && docker run --rm dwg-pdf-smoke
```

Saída real nesse espelho:

```
..................                                                       [100%]
18 passed in 14.40s
```

## ☁️ Deploy no Streamlit Cloud

1. Faça push para o GitHub
2. Em [share.streamlit.io](https://share.streamlit.io), conecte o repositório
3. Em **Advanced settings**, escolha **Python 3.13** (ou 3.12). Com Python 3.14 a instalação falha: o Streamlit 1.39 exige pillow abaixo da versão 11, que não tem pacote pronto para 3.14 e não compila na imagem do Cloud. A versão do Python não pode ser trocada depois; é preciso apagar o app e implantar de novo.
4. Nenhum pacote de sistema é obrigatório: o `bin/dwg2dxf` é estático e os demais motores vêm do `requirements.txt`. O `packages.txt` só acrescenta as fontes de sistema.
5. Deploy

## 🔁 Reconstruir o binário do LibreDWG

O `bin/dwg2dxf` foi compilado a partir do código-fonte oficial (release 0.14) com o `bin/build/Dockerfile`:

```bash
cd bin/build
docker build -t libredwg-static .
docker create --name tmp libredwg-static && docker cp tmp:/out/dwg2dxf ../dwg2dxf && docker rm tmp
```

## 📋 Estrutura

```
dwg-para-pdf/
├── app.py              # Aplicação principal
├── requirements.txt    # streamlit, ezdxf, pymupdf
├── bin/
│   ├── dwg2dxf         # LibreDWG 0.14, Linux x86_64 estático
│   └── build/          # Dockerfile que gera o binário + licença da LibreDWG
├── static/fonts/       # fontes que o desenho pede pelo nome
├── tests/              # pytest + fixtures DWG reais
├── NOTICE.md           # Licenças dos componentes
└── README.md
```

## 🛠️ Tecnologias

- **[Streamlit](https://streamlit.io/)** — interface web
- **[GNU LibreDWG](https://www.gnu.org/software/libredwg/)** — leitura do DWG
- **[ezdxf](https://ezdxf.mozman.at/)** — interpretação do DXF e desenho
- **[PyMuPDF](https://pymupdf.readthedocs.io/)** — montagem do PDF e prévia

## 🔒 Privacidade

Os arquivos são processados em diretórios temporários e removidos após a conversão. Nada é armazenado permanentemente.

---

Desenvolvido com ❤️ usando Python e Streamlit.
