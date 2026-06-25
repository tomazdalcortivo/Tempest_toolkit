#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rodar_analise.py
================
Pipeline de análise espectral das imagens da urna.

Para cada imagem encontrada (tela_*.png), produz:
  1) Espectro FFT 2D da imagem ATIVA (sem blanking)
  2) Espectro FFT 2D da imagem com BLANKING VESA (1650x750)
  3) Perfis 1D (horizontal e vertical) do espectro — úteis para
     comparar com a caracterização linha-a-linha do sinal TEMPEST
  4) Figuras .png e arrays .npz salvos em output_analises/

Também gera, ao final, um espectro MÉDIO de todos os frames (como o
script Octave original faz), nas duas variantes (com/sem blanking).

Uso:
  python3 rodar_analise.py
  python3 rodar_analise.py --imagens output_imagens --saida output_analises
  python3 rodar_analise.py --timing 1280x720@60 --modo-blank vesa_real
  python3 rodar_analise.py --sem-blanking      # só análise da imagem ativa
"""

import argparse
import glob
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")  # backend sem display (headless)
import matplotlib.pyplot as plt

from tempest_core import (
    carregar_cinza, aplicar_blanking, fft2_magnitude,
    fft2_media_frames, limites_percentil, VESA_TIMINGS,
)


def salvar_espectro_2d(espectro, titulo, caminho_png, freq_axes=None):
    """
    Salva uma figura do espectro 2D em dB com contraste por percentil.
    freq_axes: opcional (fx, fy) para rotular eixos em ciclos/pixel.
    """
    vmin, vmax = limites_percentil(espectro, 5, 99)
    fig, ax = plt.subplots(figsize=(8, 6))

    if freq_axes is not None:
        fx, fy = freq_axes
        extent = [fx[0], fx[-1], fy[0], fy[-1]]
        im = ax.imshow(espectro, cmap="jet", vmin=vmin, vmax=vmax,
                       origin="lower", extent=extent, aspect="auto")
        ax.set_xlabel("Frequência espacial horizontal (ciclos/pixel)")
        ax.set_ylabel("Frequência espacial vertical (ciclos/pixel)")
    else:
        im = ax.imshow(espectro, cmap="jet", vmin=vmin, vmax=vmax, origin="lower",
                       aspect="auto")
        ax.set_xlabel("Frequência espacial horizontal (bins)")
        ax.set_ylabel("Frequência espacial vertical (bins)")

    fig.colorbar(im, ax=ax, label="Magnitude (dB)")
    ax.set_title(titulo)
    fig.tight_layout()
    fig.savefig(caminho_png, dpi=130)
    plt.close(fig)


def eixos_frequencia(forma):
    """Eixos de frequência normalizada (ciclos/pixel) centrados, p/ fftshift."""
    Py, Px = forma
    fx = np.fft.fftshift(np.fft.fftfreq(Px))
    fy = np.fft.fftshift(np.fft.fftfreq(Py))
    return fx, fy


def perfis_1d(espectro_db):
    """
    Extrai perfis 1D do espectro 2D:
      - perfil horizontal: média ao longo das linhas (colapsa eixo vertical)
      - perfil vertical:   média ao longo das colunas (colapsa eixo horizontal)
      - linha central horizontal e vertical (corte exato no DC)
    """
    Py, Px = espectro_db.shape
    perfil_h_medio = espectro_db.mean(axis=0)      # vetor de tamanho Px
    perfil_v_medio = espectro_db.mean(axis=1)      # vetor de tamanho Py
    corte_h = espectro_db[Py // 2, :]              # linha do DC
    corte_v = espectro_db[:, Px // 2]              # coluna do DC
    return perfil_h_medio, perfil_v_medio, corte_h, corte_v


def salvar_perfis(espectro_db, nome_base, saida, timing_nome):
    """Salva figura com os 4 perfis 1D e devolve os vetores."""
    ph, pv, ch, cv = perfis_1d(espectro_db)
    fx, fy = eixos_frequencia(espectro_db.shape)

    fig, axs = plt.subplots(2, 2, figsize=(12, 7))
    axs[0, 0].plot(fx, ch, lw=0.7); axs[0, 0].set_title("Corte horizontal no DC")
    axs[0, 0].set_xlabel("ciclos/pixel"); axs[0, 0].set_ylabel("dB"); axs[0, 0].grid(True, alpha=.3)
    axs[0, 1].plot(fy, cv, lw=0.7, color="tab:orange"); axs[0, 1].set_title("Corte vertical no DC")
    axs[0, 1].set_xlabel("ciclos/pixel"); axs[0, 1].set_ylabel("dB"); axs[0, 1].grid(True, alpha=.3)
    axs[1, 0].plot(fx, ph, lw=0.7, color="tab:green"); axs[1, 0].set_title("Perfil horizontal médio")
    axs[1, 0].set_xlabel("ciclos/pixel"); axs[1, 0].set_ylabel("dB médio"); axs[1, 0].grid(True, alpha=.3)
    axs[1, 1].plot(fy, pv, lw=0.7, color="tab:red"); axs[1, 1].set_title("Perfil vertical médio")
    axs[1, 1].set_xlabel("ciclos/pixel"); axs[1, 1].set_ylabel("dB médio"); axs[1, 1].grid(True, alpha=.3)

    fig.suptitle(f"Perfis 1D do espectro — {nome_base} [{timing_nome}]")
    fig.tight_layout()
    cam = os.path.join(saida, f"{nome_base}_perfis1d.png")
    fig.savefig(cam, dpi=120)
    plt.close(fig)
    return ph, pv, ch, cv


def processar_imagem(caminho_img, saida, timing_nome, modo_blank,
                     fazer_blanking, nivel_blank):
    """Processa uma imagem: FFT ativa + FFT com blanking + perfis + salvar."""
    nome = os.path.splitext(os.path.basename(caminho_img))[0]
    print(f"\n>> {nome}")

    img = carregar_cinza(caminho_img)
    print(f"   imagem ativa: {img.shape[1]}x{img.shape[0]}")

    # --- FFT da imagem ativa (sem blanking) ---
    esp_ativa = fft2_magnitude(img, em_db=True)
    fx, fy = eixos_frequencia(esp_ativa.shape)
    salvar_espectro_2d(
        esp_ativa, f"FFT 2D (ativa) — {nome}",
        os.path.join(saida, f"{nome}_fft_ativa.png"), (fx, fy))
    salvar_perfis(esp_ativa, f"{nome}_ativa", saida, "sem blanking")

    resultado = {"esp_ativa": esp_ativa}

    # --- FFT com blanking VESA ---
    if fazer_blanking:
        quadro, info = aplicar_blanking(
            img, timing_nome, nivel_blank=nivel_blank, modo=modo_blank)
        print(f"   com blanking: {quadro.shape[1]}x{quadro.shape[0]} "
              f"(modo={modo_blank}, offset x={info['offset_x']} y={info['offset_y']})")
        esp_blank = fft2_magnitude(quadro, em_db=True)
        fxb, fyb = eixos_frequencia(esp_blank.shape)
        salvar_espectro_2d(
            esp_blank, f"FFT 2D (com blanking VESA {info['Px']}x{info['Py']}) — {nome}",
            os.path.join(saida, f"{nome}_fft_blanking.png"), (fxb, fyb))
        salvar_perfis(esp_blank, f"{nome}_blanking", saida, timing_nome)
        resultado["esp_blank"] = esp_blank
        resultado["quadro_blank"] = quadro

    # salva arrays para reuso/figuras do artigo
    np.savez_compressed(
        os.path.join(saida, f"{nome}_dados.npz"),
        **{k: v for k, v in resultado.items()})

    return resultado


def main():
    ap = argparse.ArgumentParser(description="Pipeline de análise espectral (FFT 2D).")
    ap.add_argument("--imagens", default="output_imagens")
    ap.add_argument("--saida", default="output_analises")
    ap.add_argument("--timing", default="1280x720@60",
                    choices=list(VESA_TIMINGS.keys()))
    ap.add_argument("--modo-blank", default="vesa_real",
                    choices=["vesa_real", "centralizado"])
    ap.add_argument("--nivel-blank", type=float, default=0.0,
                    help="Nível dos pixels de blanking (0.0=preto)")
    ap.add_argument("--sem-blanking", action="store_true",
                    help="Analisa apenas a imagem ativa (pula o blanking)")
    ap.add_argument("--padrao", default="tela_*.png",
                    help="Glob das imagens (default tela_*.png)")
    args = ap.parse_args()

    os.makedirs(args.saida, exist_ok=True)
    arquivos = sorted(glob.glob(os.path.join(args.imagens, args.padrao)))
    if not arquivos:
        print(f"Nenhuma imagem '{args.padrao}' em {args.imagens}/")
        return

    print(f"Encontradas {len(arquivos)} imagem(ns). Timing: {args.timing}")
    fazer_blanking = not args.sem_blanking

    imgs_ativas, imgs_blank = [], []
    for caminho in arquivos:
        res = processar_imagem(
            caminho, args.saida, args.timing, args.modo_blank,
            fazer_blanking, args.nivel_blank)
        # acumula imagens (re-lê em cinza p/ média de frames de magnitude linear)
        imgs_ativas.append(carregar_cinza(caminho))
        if fazer_blanking:
            q, _ = aplicar_blanking(imgs_ativas[-1], args.timing,
                                    nivel_blank=args.nivel_blank, modo=args.modo_blank)
            imgs_blank.append(q)

    # --- Espectro médio (como no script Octave original) ---
    if len(imgs_ativas) > 1:
        print("\n>> Espectro MÉDIO de todos os frames (ativa)")
        media_ativa = fft2_media_frames(imgs_ativas, em_db=True)
        fx, fy = eixos_frequencia(media_ativa.shape)
        salvar_espectro_2d(media_ativa, "Espectro médio FFT 2D (ativa)",
                           os.path.join(args.saida, "MEDIA_fft_ativa.png"), (fx, fy))

        if fazer_blanking:
            print(">> Espectro MÉDIO de todos os frames (com blanking)")
            media_blank = fft2_media_frames(imgs_blank, em_db=True)
            fxb, fyb = eixos_frequencia(media_blank.shape)
            salvar_espectro_2d(media_blank,
                               f"Espectro médio FFT 2D (blanking {args.timing})",
                               os.path.join(args.saida, "MEDIA_fft_blanking.png"), (fxb, fyb))

    print(f"\nConcluído. Resultados em {args.saida}/")


if __name__ == "__main__":
    main()
