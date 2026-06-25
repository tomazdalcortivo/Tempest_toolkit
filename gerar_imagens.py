#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gerar_imagens.py
================
Gera imagens da tela da urna eletrônica de forma headless (sem abrir
navegador manualmente), renderizando o mesmo HTML/CSS fiel ao simulador
do TSE que usamos no gerador interativo.

Estratégia:
  - Monta o HTML da tela em memória (mesmas coordenadas do CSS real do TSE).
  - Usa Playwright (Chromium headless) para renderizar e tirar screenshot
    EXATAMENTE no tamanho ativo desejado (ex.: 1280x720).
  - Salva um PNG por estado da tela.

Esses PNGs são a "imagem ativa" (área visível). O blanking VESA é aplicado
depois, no pipeline de análise (ver rodar_analise.py), para manter as duas
coisas desacopladas.

Requisitos:
  pip install playwright
  playwright install chromium

Uso:
  python3 gerar_imagens.py --resolucao 1280x720 --saida output_imagens
  python3 gerar_imagens.py --resolucao 1280x720 --estados candidato confirmar
"""

import argparse
import os
import sys

# Estados disponíveis (devem casar com as classes est-* do HTML)
ESTADOS_VALIDOS = ["inicial", "digitando", "candidato", "confirmar", "nulo", "branco"]

# Conteúdo default da tela (editável por linha de comando se quiser)
CONTEUDO_DEFAULT = {
    "cargo": "Presidente",
    "d1": "1",
    "d2": "3",
    "nome": "FULANO DA SILVA",
    "partido": "PARTIDO EXEMPLO",
    "vice": "BELTRANO SOUZA",
    "iniciais": "FS",
}


def montar_html(largura, altura, estado, conteudo):
    """
    Constrói o HTML completo da tela da urna para uma resolução e estado.
    As coordenadas em px são proporcionais à base 642x480 e escaladas para
    (largura x altura) via transform: scale(). Como o screenshot é tirado
    do elemento #urna-tela já escalado, o PNG sai no tamanho-alvo.

    Mantém fidelidade ao CSS real do TSE (urna.css + presidente.css):
    sem barra "TREINAMENTO", sem elementos do navegador, fundo branco.
    """
    BASE_W, BASE_H = 642, 480
    sx = largura / BASE_W
    sy = altura / BASE_H

    c = conteudo

    # Tabela de visibilidade por estado: define quais blocos aparecem.
    # (Espelha as regras .est-* do HTML interativo.)
    vis = {k: "none" for k in [
        "num_label", "cx1", "cx2", "foto", "foto_label", "vice_box", "vice_label",
        "aviso_errado", "aviso_inexistente", "aviso_nulo", "aviso_branco",
        "aviso_conferir", "nome_label", "nome_val", "partido_label", "partido_val",
        "vice_label_txt", "vice_val", "regua", "instrucoes",
    ]}

    def liga(*chaves):
        for k in chaves:
            vis[k] = "block"

    if estado == "digitando":
        liga("num_label", "cx1", "cx2")
    elif estado == "candidato":
        liga("num_label", "cx1", "cx2", "foto", "foto_label", "vice_box", "vice_label",
             "nome_label", "nome_val", "partido_label", "partido_val",
             "vice_label_txt", "vice_val", "regua", "instrucoes")
    elif estado == "confirmar":
        liga("num_label", "cx1", "cx2", "foto", "foto_label", "vice_box", "vice_label",
             "nome_label", "nome_val", "partido_label", "partido_val",
             "vice_label_txt", "vice_val", "aviso_conferir", "regua", "instrucoes")
    elif estado == "nulo":
        liga("num_label", "cx1", "cx2", "aviso_errado", "aviso_inexistente",
             "aviso_nulo", "regua", "instrucoes")
    elif estado == "branco":
        liga("aviso_branco", "regua", "instrucoes")
    # "inicial" -> tudo none, só cargo + fase visíveis (que ficam sempre block)

    foto_disp = "flex" if vis["foto"] == "block" else "none"
    vice_disp = "flex" if vis["vice_box"] == "block" else "none"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"><style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:#fff;width:{largura}px;height:{altura}px;overflow:hidden}}
#urna-tela{{position:relative;background:#fff;width:642px;height:480px;
  overflow:hidden;transform:scale({sx},{sy});transform-origin:top left;
  font-family:Arial,sans-serif}}
#u-faixa-topo{{position:absolute;left:0;top:0;width:100%;height:26px;
  background:#dbe2ef;display:flex;align-items:center;justify-content:center;
  font-size:13px;font-weight:700;letter-spacing:1.2px;color:#1b305a}}
#u-painel{{position:absolute;left:49px;top:26px;width:547px;bottom:0;background:#fff}}
#u-fase{{position:absolute;left:0;top:4px;width:100%;text-align:center;
  font-size:17px;font-weight:600;color:#acacac;letter-spacing:.5px}}
#u-cargo{{position:absolute;left:91px;top:36px;font-size:22px;font-weight:400;
  letter-spacing:1.5px;color:#000}}
#u-num-label{{position:absolute;left:1px;top:90px;font-size:14px;font-weight:500;
  color:#000;padding:2px;display:{vis['num_label']}}}
#u-cx1,#u-cx2{{position:absolute;top:84px;width:24px;height:30px;border:1px solid #555;
  font-size:26px;text-align:center;line-height:30px;color:#000;background:#fff}}
#u-cx1{{left:90px;display:{vis['cx1']}}} #u-cx2{{left:120px;display:{vis['cx2']}}}
#u-foto-box{{position:absolute;left:446px;top:1px;width:101px;height:162px;
  border:1px solid #ccc;overflow:hidden;background:#e8e8e8;
  align-items:center;justify-content:center;display:{foto_disp}}}
#u-foto-ph{{display:flex;flex-direction:column;align-items:center;justify-content:center;
  width:100%;height:100%;color:#888;font-size:13px;font-weight:700}}
#u-foto-label{{position:absolute;left:447px;top:145px;width:97px;height:16px;
  background:#fff;text-align:center;font-size:11px;color:#333;
  border-top:1px solid #ccc;display:{vis['foto_label']}}}
#u-vice-box{{position:absolute;left:472px;top:168px;width:75px;height:118px;
  border:1px solid #ccc;overflow:hidden;background:#e8e8e8;
  align-items:center;justify-content:center;display:{vice_disp}}}
#u-vice-label{{position:absolute;left:473px;top:271px;width:71px;height:14px;
  background:#fff;text-align:center;font-size:9px;color:#333;
  border-top:1px solid #ccc;display:{vis['vice_label']}}}
#u-aviso-errado{{position:absolute;left:2px;top:128px;font-size:19px;
  letter-spacing:.5px;color:#c00;display:{vis['aviso_errado']}}}
#u-aviso-inexistente{{position:absolute;left:2px;top:168px;font-size:19px;
  letter-spacing:.5px;color:#c00;display:{vis['aviso_inexistente']}}}
#u-aviso-nulo{{position:absolute;left:188px;top:208px;font-size:36px;
  color:#c00;display:{vis['aviso_nulo']}}}
#u-aviso-branco{{position:absolute;left:118px;top:122px;font-size:32px;
  color:#c00;display:{vis['aviso_branco']}}}
#u-aviso-conferir{{position:absolute;left:118px;top:272px;font-size:24px;
  color:#000;display:{vis['aviso_conferir']}}}
#u-nome-label{{position:absolute;left:1px;top:122px;font-size:13px;font-weight:300;
  color:#000;padding:2px;display:{vis['nome_label']}}}
#u-nome-val{{position:absolute;left:88px;top:122px;width:352px;font-size:15px;
  font-weight:600;letter-spacing:.4px;color:#000;padding:2px;display:{vis['nome_val']}}}
#u-partido-label{{position:absolute;left:1px;top:162px;font-size:13px;font-weight:300;
  color:#000;padding:2px;display:{vis['partido_label']}}}
#u-partido-val{{position:absolute;left:88px;top:162px;width:352px;font-size:15px;
  font-weight:400;color:#000;padding:2px;display:{vis['partido_val']}}}
#u-vice-label-txt{{position:absolute;left:1px;top:209px;width:84px;font-size:12px;
  font-weight:300;color:#000;padding:2px;display:{vis['vice_label_txt']}}}
#u-vice-val{{position:absolute;left:88px;top:209px;width:352px;font-size:15px;
  font-weight:400;color:#000;padding:2px;display:{vis['vice_val']}}}
#u-regua{{position:absolute;left:0;top:262px;width:98%;height:0;
  border-top:2px solid #000;display:{vis['regua']}}}
#u-instrucoes{{position:absolute;left:1px;top:268px;width:440px;font-size:12px;
  letter-spacing:.4px;line-height:1.5;color:#000;display:{vis['instrucoes']}}}
</style></head><body>
<div id="urna-tela">
  <div id="u-faixa-topo">SEU VOTO PARA</div>
  <div id="u-painel">
    <div id="u-fase">SEU VOTO PARA</div>
    <div id="u-cargo">{c['cargo']}</div>
    <div id="u-num-label">Número:</div>
    <div id="u-cx1">{c['d1']}</div>
    <div id="u-cx2">{c['d2']}</div>
    <div id="u-foto-box"><div id="u-foto-ph">
      <svg width="40" height="40" viewBox="0 0 40 40"><circle cx="20" cy="14" r="9" fill="#bbb"/>
      <path d="M2 38c0-9.94 8.06-18 18-18s18 8.06 18 18" fill="#bbb"/></svg>
      <span>{c['iniciais']}</span></div></div>
    <div id="u-foto-label">{c['cargo']}</div>
    <div id="u-vice-box"><div id="u-foto-ph">
      <svg width="30" height="30" viewBox="0 0 40 40"><circle cx="20" cy="14" r="9" fill="#ccc"/>
      <path d="M2 38c0-9.94 8.06-18 18-18s18 8.06 18 18" fill="#ccc"/></svg></div></div>
    <div id="u-vice-label">Vice-Presidente</div>
    <div id="u-aviso-errado">NÚMERO ERRADO</div>
    <div id="u-aviso-inexistente">CANDIDATO INEXISTENTE</div>
    <div id="u-aviso-nulo">VOTO NULO</div>
    <div id="u-aviso-branco">VOTO EM BRANCO</div>
    <div id="u-aviso-conferir">CONFIRA O SEU VOTO</div>
    <div id="u-nome-label">Nome:</div>
    <div id="u-nome-val">{c['nome']}</div>
    <div id="u-partido-label">Partido:</div>
    <div id="u-partido-val">{c['partido']}</div>
    <div id="u-vice-label-txt">Vice-Presidente:</div>
    <div id="u-vice-val">{c['vice']}</div>
    <div id="u-regua"></div>
    <div id="u-instrucoes">Aperte a tecla:&nbsp;
      <span style="color:green;font-weight:700">CONFIRMA</span>&nbsp;para&nbsp;<strong>CONFIRMAR</strong>&nbsp;este voto&nbsp;·&nbsp;
      <span style="color:#e65c00;font-weight:700">CORRIGE</span>&nbsp;para&nbsp;<strong>REINICIAR</strong>&nbsp;este voto</div>
  </div>
</div>
</body></html>"""
    return html


def gerar(largura, altura, estados, saida, conteudo):
    """Renderiza e salva um PNG por estado."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERRO: Playwright não instalado.\n"
              "  pip install playwright\n"
              "  playwright install chromium", file=sys.stderr)
        sys.exit(1)

    os.makedirs(saida, exist_ok=True)
    gerados = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for estado in estados:
            html = montar_html(largura, altura, estado, conteudo)
            page = browser.new_page(viewport={"width": largura, "height": altura})
            page.set_content(html)
            page.wait_for_timeout(120)  # deixa fontes/SVG assentarem
            el = page.query_selector("#urna-tela")
            nome = f"tela_urna_{largura}x{altura}_{estado}.png"
            caminho = os.path.join(saida, nome)
            el.screenshot(path=caminho)
            page.close()
            gerados.append(caminho)
            print(f"  [OK] {nome}")
        browser.close()

    return gerados


def main():
    ap = argparse.ArgumentParser(description="Gera imagens da tela da urna (headless).")
    ap.add_argument("--resolucao", default="1280x720",
                    help="Resolução ATIVA, ex.: 1280x720")
    ap.add_argument("--estados", nargs="+", default=ESTADOS_VALIDOS,
                    help=f"Estados a gerar. Opções: {ESTADOS_VALIDOS}")
    ap.add_argument("--saida", default="output_imagens",
                    help="Pasta de saída dos PNGs")
    # overrides de conteúdo
    ap.add_argument("--cargo");   ap.add_argument("--d1"); ap.add_argument("--d2")
    ap.add_argument("--nome");    ap.add_argument("--partido"); ap.add_argument("--vice")
    ap.add_argument("--iniciais")
    args = ap.parse_args()

    try:
        largura, altura = map(int, args.resolucao.lower().split("x"))
    except ValueError:
        print("Resolução inválida. Use o formato LARGURAxALTURA, ex.: 1280x720",
              file=sys.stderr)
        sys.exit(1)

    for e in args.estados:
        if e not in ESTADOS_VALIDOS:
            print(f"Estado inválido: {e}. Válidos: {ESTADOS_VALIDOS}", file=sys.stderr)
            sys.exit(1)

    conteudo = dict(CONTEUDO_DEFAULT)
    for chave in CONTEUDO_DEFAULT:
        val = getattr(args, chave, None)
        if val is not None:
            conteudo[chave] = val

    print(f"Gerando {len(args.estados)} imagem(ns) em {largura}x{altura}...")
    gerar(largura, altura, args.estados, args.saida, conteudo)
    print("Concluído.")


if __name__ == "__main__":
    main()
