#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tempest_core.py
================
Módulo central do toolkit de análise espectral TEMPEST.

Contém:
  - Tabela de timings VESA/CVT (incl. 1280x720@60 -> 1650x750)
  - Função de aplicação de blanking VESA a uma imagem
  - Função de FFT 2D (espectro de magnitude, dB, com média de frames)
  - Utilidades de leitura/conversão para tons de cinza

Referência de timings (artigo base):
  resolução ativa  : 1280 x 720 @ 60 Hz
  resolução total  : 1650 x 750  (Px x Py, inclui blank pixels)
  pixel clock      : 74.25 MHz
  captura SDR      : fs = 54 MS/s (USRP B200)

Autor: gerado para projeto de mestrado (ataques TEMPEST / urna eletrônica)
"""

import numpy as np
from PIL import Image


# =============================================================
# 1) TABELA DE TIMINGS VESA / CVT
# =============================================================
# Cada entrada descreve a varredura horizontal (h) e vertical (v):
#   active      : pixels/linhas ativos (visíveis)
#   front_porch : pixels/linhas após a área ativa, antes do sync
#   sync        : largura do pulso de sincronismo
#   back_porch  : pixels/linhas após o sync, antes da próxima área ativa
#   total       : soma de tudo (deve fechar com Px / Py do artigo)
#
# Para 1280x720@60 (CVT), a soma fecha em 1650 x 750, exatamente como
# especificado no artigo do professor.

VESA_TIMINGS = {
    "1280x720@60": {
        "refresh_hz": 60,
        "pixel_clock_mhz": 74.25,
        "h": {"active": 1280, "front_porch": 72, "sync": 80,  "back_porch": 218, "total": 1650},
        "v": {"active": 720,  "front_porch": 3,  "sync": 5,   "back_porch": 22,  "total": 750},
    },
    # Outras resoluções comuns (CVT padrão) — disponíveis caso o projeto evolua:
    "1024x768@60": {
        "refresh_hz": 60,
        "pixel_clock_mhz": 65.0,
        "h": {"active": 1024, "front_porch": 24, "sync": 136, "back_porch": 160, "total": 1344},
        "v": {"active": 768,  "front_porch": 3,  "sync": 6,   "back_porch": 29,  "total": 806},
    },
    "800x600@60": {
        "refresh_hz": 60,
        "pixel_clock_mhz": 40.0,
        "h": {"active": 800,  "front_porch": 40, "sync": 128, "back_porch": 88,  "total": 1056},
        "v": {"active": 600,  "front_porch": 1,  "sync": 4,   "back_porch": 23,  "total": 628},
    },
    "640x480@60": {
        "refresh_hz": 60,
        "pixel_clock_mhz": 25.175,
        "h": {"active": 640,  "front_porch": 16, "sync": 96,  "back_porch": 48,  "total": 800},
        "v": {"active": 480,  "front_porch": 10, "sync": 2,   "back_porch": 33,  "total": 525},
    },
}


def validar_timing(nome):
    """Confere que active + porches + sync == total, para h e v."""
    t = VESA_TIMINGS[nome]
    for eixo in ("h", "v"):
        d = t[eixo]
        soma = d["active"] + d["front_porch"] + d["sync"] + d["back_porch"]
        assert soma == d["total"], (
            f"Timing inconsistente em {nome} eixo {eixo}: "
            f"{soma} != {d['total']}"
        )
    return True


# =============================================================
# 2) LEITURA E CONVERSÃO
# =============================================================
def carregar_cinza(caminho):
    """
    Carrega uma imagem e converte para tons de cinza (luminância ITU-R BT.601),
    retornando array float64 normalizado em [0, 1].

    Usa os mesmos pesos do script Octave original:
        0.2989 R + 0.5870 G + 0.1140 B
    """
    img = Image.open(caminho).convert("RGB")
    arr = np.asarray(img, dtype=np.float64)
    cinza = 0.2989 * arr[:, :, 0] + 0.5870 * arr[:, :, 1] + 0.1140 * arr[:, :, 2]
    m = cinza.max()
    if m > 0:
        cinza = cinza / m
    return cinza


# =============================================================
# 3) BLANKING VESA
# =============================================================
def aplicar_blanking(img_ativa, nome_timing="1280x720@60",
                     nivel_blank=0.0, modo="centralizado"):
    """
    Coloca a imagem ativa dentro de um quadro total VESA, preenchendo
    a região de blanking com `nivel_blank` (0.0 = preto).

    Parâmetros
    ----------
    img_ativa : np.ndarray (H_ativa x W_ativa), valores em [0,1]
        A imagem visível (ex.: tela da urna em 1280x720).
    nome_timing : str
        Chave em VESA_TIMINGS (default "1280x720@60" -> 1650x750).
    nivel_blank : float
        Valor de preenchimento da área de blanking (0.0 a 1.0).
        No sinal de vídeo real os pixels de blanking ficam no nível
        de "preto"/sync, então 0.0 é o default fisicamente coerente.
    modo : str
        "centralizado"  -> centra a imagem no quadro total (didático)
        "vesa_real"     -> posiciona conforme a varredura real:
                           a área ativa fica após (back_porch) a partir
                           da origem, replicando a geometria do sinal.

    Retorna
    -------
    quadro : np.ndarray (Py x Px) com a imagem ativa embutida.
    info   : dict com offsets usados e o timing.
    """
    validar_timing(nome_timing)
    t = VESA_TIMINGS[nome_timing]
    Px = t["h"]["total"]   # 1650
    Py = t["v"]["total"]   # 750
    Wa = t["h"]["active"]  # 1280
    Ha = t["v"]["active"]  # 720

    # Garante que a imagem ativa tem o tamanho esperado; se não, redimensiona.
    h_in, w_in = img_ativa.shape
    if (h_in, w_in) != (Ha, Wa):
        img_pil = Image.fromarray((np.clip(img_ativa, 0, 1) * 255).astype(np.uint8))
        img_pil = img_pil.resize((Wa, Ha), Image.LANCZOS)
        img_ativa = np.asarray(img_pil, dtype=np.float64) / 255.0

    quadro = np.full((Py, Px), float(nivel_blank), dtype=np.float64)

    if modo == "centralizado":
        ox = (Px - Wa) // 2
        oy = (Py - Ha) // 2
    elif modo == "vesa_real":
        # Geometria do sinal: a área ativa começa após o back porch.
        # (Na varredura, a ordem por linha é: active, front, sync, back;
        #  o início visível de cada quadro fica deslocado pelo back porch.)
        ox = t["h"]["back_porch"]
        oy = t["v"]["back_porch"]
        # Protege contra estouro de borda
        ox = min(ox, Px - Wa)
        oy = min(oy, Py - Ha)
    else:
        raise ValueError("modo deve ser 'centralizado' ou 'vesa_real'")

    quadro[oy:oy + Ha, ox:ox + Wa] = img_ativa

    info = {
        "timing": nome_timing,
        "Px": Px, "Py": Py,
        "offset_x": ox, "offset_y": oy,
        "nivel_blank": nivel_blank,
        "modo": modo,
    }
    return quadro, info


# =============================================================
# 4) FFT 2D
# =============================================================
def fft2_magnitude(img, em_db=True, eps=None):
    """
    FFT 2D de uma imagem -> espectro de magnitude centralizado (fftshift).

    Parâmetros
    ----------
    img : np.ndarray 2D, valores em [0,1]
    em_db : bool
        Se True, retorna 20*log10(|F| + eps). Se False, retorna |F| linear.
    eps : float ou None
        Piso numérico para o log. Se None, usa np.finfo(float).eps.

    Retorna
    -------
    espectro : np.ndarray 2D (mesma forma de img)
    """
    if eps is None:
        eps = np.finfo(np.float64).eps
    F = np.fft.fft2(img)
    mag = np.abs(np.fft.fftshift(F))
    if em_db:
        return 20.0 * np.log10(mag + eps)
    return mag


def fft2_media_frames(lista_imgs, em_db=True):
    """
    Calcula o espectro de magnitude MÉDIO sobre vários frames.
    Replica a lógica do script Octave original: acumula |fftshift(F)|
    linear, tira a média, e só então converte para dB (se em_db=True).

    Parâmetros
    ----------
    lista_imgs : list[np.ndarray]
        Lista de imagens 2D já em tons de cinza normalizados, todas
        com a MESMA forma.
    em_db : bool
        Converte a média para dB ao final.

    Retorna
    -------
    espectro_medio : np.ndarray 2D
    """
    assert len(lista_imgs) > 0, "Lista de imagens vazia."
    forma = lista_imgs[0].shape
    acumulador = np.zeros(forma, dtype=np.float64)
    for img in lista_imgs:
        assert img.shape == forma, "Todas as imagens devem ter a mesma forma."
        F = np.fft.fft2(img)
        acumulador += np.abs(np.fft.fftshift(F))
    media = acumulador / len(lista_imgs)
    if em_db:
        eps = np.finfo(np.float64).eps
        return 20.0 * np.log10(media + eps)
    return media


# =============================================================
# 5) CONTRASTE POR PERCENTIL (para plotagem)
# =============================================================
def limites_percentil(espectro, p_low=5, p_high=99):
    """
    Retorna (vmin, vmax) baseados em percentis, para realçar o contraste
    do espectro na visualização — equivalente ao trecho do script Octave
    que ordena e pega 5% / 99%.
    """
    vmin = np.percentile(espectro, p_low)
    vmax = np.percentile(espectro, p_high)
    return vmin, vmax


# =============================================================
# Execução direta -> autoteste rápido
# =============================================================
if __name__ == "__main__":
    print("Validando timings VESA...")
    for nome in VESA_TIMINGS:
        validar_timing(nome)
        t = VESA_TIMINGS[nome]
        print(f"  {nome:14s} -> total {t['h']['total']} x {t['v']['total']} "
              f"@ {t['refresh_hz']}Hz, pclk {t['pixel_clock_mhz']} MHz  [OK]")

    print("\nTeste de blanking com imagem sintética 1280x720...")
    teste = np.random.rand(720, 1280)
    quadro, info = aplicar_blanking(teste, "1280x720@60", modo="vesa_real")
    print(f"  Quadro resultante: {quadro.shape}  (esperado 750 x 1650)")
    print(f"  Offsets: x={info['offset_x']}, y={info['offset_y']}")

    print("\nTeste de FFT 2D...")
    esp = fft2_magnitude(quadro)
    vmin, vmax = limites_percentil(esp)
    print(f"  Espectro: {esp.shape}, dB range [{vmin:.1f}, {vmax:.1f}]")
    print("\nTudo OK.")
