#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rotina_completa.py
==================
Orquestrador do toolkit. Executa, de ponta a ponta:

  1) GERA as imagens da tela da urna (headless) na(s) resolução(ões) pedidas
  2) RODA a análise espectral de cada imagem:
        - FFT 2D da imagem ativa
        - FFT 2D com blanking VESA (1650x750)
        - perfis 1D (cortes no DC)
  3) GERA espectros médios (todos os frames)
  4) Salva tudo em output_analises/ e organiza um resumo

É a forma "um comando faz tudo". Os scripts individuais
(gerar_imagens.py, rodar_analise.py) continuam utilizáveis à parte.

Uso:
  python3 rotina_completa.py
  python3 rotina_completa.py --resolucoes 1280x720
  python3 rotina_completa.py --resolucoes 1280x720 1024x768 --modo-blank vesa_real
  python3 rotina_completa.py --so-analise        # pula geração (usa imagens existentes)
  python3 rotina_completa.py --so-imagens        # só gera imagens
"""

import argparse
import os
import sys

# Mapeia "1280x720" (ativo) -> chave de timing "1280x720@60"
def timing_de_resolucao(res_ativa):
    return f"{res_ativa}@60"


def main():
    ap = argparse.ArgumentParser(
        description="Rotina completa: gera imagens + análise espectral TEMPEST.")
    ap.add_argument("--resolucoes", nargs="+", default=["1280x720"],
                    help="Resoluções ativas, ex.: 1280x720 1024x768")
    ap.add_argument("--estados", nargs="+",
                    default=["inicial", "digitando", "candidato",
                             "confirmar", "nulo", "branco"],
                    help="Estados da tela a gerar")
    ap.add_argument("--imagens", default="output_imagens")
    ap.add_argument("--saida", default="output_analises")
    ap.add_argument("--modo-blank", default="vesa_real",
                    choices=["vesa_real", "centralizado"])
    ap.add_argument("--nivel-blank", type=float, default=0.0)
    ap.add_argument("--sem-blanking", action="store_true")
    ap.add_argument("--so-imagens", action="store_true",
                    help="Apenas gera imagens (não analisa)")
    ap.add_argument("--so-analise", action="store_true",
                    help="Apenas analisa (não gera imagens)")
    # overrides de conteúdo da tela
    ap.add_argument("--nome"); ap.add_argument("--partido"); ap.add_argument("--vice")
    ap.add_argument("--d1"); ap.add_argument("--d2"); ap.add_argument("--cargo")
    args = ap.parse_args()

    from tempest_core import VESA_TIMINGS

    # valida timings disponíveis
    for res in args.resolucoes:
        tnome = timing_de_resolucao(res)
        if tnome not in VESA_TIMINGS:
            print(f"AVISO: timing '{tnome}' não está na tabela VESA_TIMINGS.\n"
                  f"  Disponíveis: {list(VESA_TIMINGS.keys())}\n"
                  f"  Edite tempest_core.py para adicionar.", file=sys.stderr)
            sys.exit(1)

    # ---------- 1) Geração de imagens ----------
    if not args.so_analise:
        from gerar_imagens import gerar, CONTEUDO_DEFAULT
        conteudo = dict(CONTEUDO_DEFAULT)
        for chave in ("nome", "partido", "vice", "d1", "d2", "cargo"):
            val = getattr(args, chave, None)
            if val is not None:
                conteudo[chave] = val

        print("=" * 60)
        print("ETAPA 1 — GERAÇÃO DE IMAGENS")
        print("=" * 60)
        for res in args.resolucoes:
            largura, altura = map(int, res.lower().split("x"))
            print(f"\nResolução {largura}x{altura}:")
            gerar(largura, altura, args.estados, args.imagens, conteudo)

    # ---------- 2/3) Análise ----------
    if not args.so_imagens:
        print("\n" + "=" * 60)
        print("ETAPA 2 — ANÁLISE ESPECTRAL")
        print("=" * 60)

        # roda análise por resolução (cada uma usa seu timing)
        import glob
        from tempest_core import (carregar_cinza, aplicar_blanking,
                                  fft2_media_frames)
        from rodar_analise import (processar_imagem, salvar_espectro_2d,
                                    eixos_frequencia)

        for res in args.resolucoes:
            tnome = timing_de_resolucao(res)
            largura, altura = map(int, res.lower().split("x"))
            padrao = f"tela_urna_{largura}x{altura}_*.png"
            arquivos = sorted(glob.glob(os.path.join(args.imagens, padrao)))
            if not arquivos:
                print(f"  (sem imagens {padrao})")
                continue

            print(f"\nResolução {res} [{tnome}] — {len(arquivos)} imagem(ns)")
            os.makedirs(args.saida, exist_ok=True)
            fazer_blanking = not args.sem_blanking

            imgs_ativas, imgs_blank = [], []
            for caminho in arquivos:
                processar_imagem(caminho, args.saida, tnome, args.modo_blank,
                                 fazer_blanking, args.nivel_blank)
                imgs_ativas.append(carregar_cinza(caminho))
                if fazer_blanking:
                    q, _ = aplicar_blanking(imgs_ativas[-1], tnome,
                                            nivel_blank=args.nivel_blank,
                                            modo=args.modo_blank)
                    imgs_blank.append(q)

            # médias por resolução
            if len(imgs_ativas) > 1:
                media_ativa = fft2_media_frames(imgs_ativas, em_db=True)
                fx, fy = eixos_frequencia(media_ativa.shape)
                salvar_espectro_2d(
                    media_ativa, f"Espectro médio FFT 2D (ativa) {res}",
                    os.path.join(args.saida, f"MEDIA_{res}_ativa.png"), (fx, fy))
                if fazer_blanking:
                    media_blank = fft2_media_frames(imgs_blank, em_db=True)
                    fxb, fyb = eixos_frequencia(media_blank.shape)
                    salvar_espectro_2d(
                        media_blank,
                        f"Espectro médio FFT 2D (blanking {tnome}) {res}",
                        os.path.join(args.saida, f"MEDIA_{res}_blanking.png"),
                        (fxb, fyb))

    print("\n" + "=" * 60)
    print("CONCLUÍDO")
    print("=" * 60)
    if not args.so_imagens:
        print(f"  Análises: {args.saida}/")
    if not args.so_analise:
        print(f"  Imagens:  {args.imagens}/")


if __name__ == "__main__":
    main()
