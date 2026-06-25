# Toolkit de Análise Espectral TEMPEST — Urna Eletrônica

Conjunto de ferramentas para o projeto de caracterização espectral de
vazamento eletromagnético (TEMPEST) da interface da urna eletrônica
brasileira. Reconstrói telas da urna em diferentes resoluções, aplica
o blanking VESA e produz análises espectrais (FFT 2D) — material para
o artigo.

## Estrutura

```
tempest_toolkit/
├── tempest_core.py          # Módulo central: timings VESA, blanking, FFT 2D
├── gerar_imagens.py         # Gera imagens da tela (headless, via Playwright)
├── rodar_analise.py         # Pipeline de análise FFT 2D (com/sem blanking)
├── rotina_completa.py       # Orquestra tudo num comando só
├── gerador_tela_urna.html   # Gerador interativo (browser) — uso manual
├── scripts_octave/          # Versões .m individuais (Octave/MATLAB)
│   ├── fft2_imagem.m            # FFT 2D de imagem
│   ├── fft2_imagem_blanking.m   # FFT 2D com blanking VESA
│   ├── sinal_autocorr_RIC.m     # (seu) autocorrelação + RIC do sinal
│   └── sinal_autocorr_original.m# (seu) autocorrelação do sinal
├── output_imagens/          # PNGs gerados das telas
└── output_analises/         # Espectros, perfis e dados .npz
```

## Instalação

```bash
pip install numpy pillow matplotlib playwright
python3 -m playwright install chromium
```

(Octave: os `.m` em `scripts_octave/` rodam direto; `fft2_imagem_blanking.m`
usa `imresize` apenas se a imagem não estiver já em 1280×720 — nesse caso
carregue o pacote: `pkg load image`.)

## Uso rápido

**Tudo de uma vez** (gera imagens + analisa):
```bash
python3 rotina_completa.py --resolucoes 1280x720
```

**Só gerar imagens:**
```bash
python3 gerar_imagens.py --resolucao 1280x720
```

**Só analisar imagens existentes:**
```bash
python3 rodar_analise.py --imagens output_imagens
```

**Várias resoluções:**
```bash
python3 rotina_completa.py --resolucoes 1280x720 1024x768 800x600
```

**Customizar conteúdo da tela:**
```bash
python3 gerar_imagens.py --resolucao 1280x720 \
  --nome "MARIA SANTOS" --partido "PARTIDO X" --d1 2 --d2 7
```

## Timings VESA

O timing principal é **1280×720@60** (CVT), conforme o artigo:

| | Ativos | Front | Sync | Back | **Total** |
|---|---|---|---|---|---|
| Horizontal | 1280 | 72 | 80 | 218 | **1650** |
| Vertical | 720 | 3 | 5 | 22 | **750** |

Pixel clock = 1650 × 750 × 60 = **74.25 MHz**.

Outras resoluções (1024×768, 800×600, 640×480) já estão na tabela
`VESA_TIMINGS` em `tempest_core.py`. Para adicionar mais, edite essa tabela.

### Modos de blanking
- `vesa_real` (default): a área ativa fica deslocada pelo *back porch*
  (x=218, y=22), replicando a geometria da varredura do sinal.
- `centralizado`: centra a imagem ativa no quadro total (mais didático).

```bash
python3 rotina_completa.py --resolucoes 1280x720 --modo-blank centralizado
```

## Saídas da análise

Para cada imagem `tela_*.png`:
- `*_fft_ativa.png` — espectro FFT 2D da imagem ativa (1280×720)
- `*_fft_blanking.png` — espectro FFT 2D com blanking VESA (1650×750)
- `*_ativa_perfis1d.png` / `*_blanking_perfis1d.png` — cortes 1D no DC
- `*_dados.npz` — arrays NumPy (espectros e quadro) para refazer figuras

E os espectros médios de todos os frames:
- `MEDIA_<res>_ativa.png`
- `MEDIA_<res>_blanking.png`

Os perfis 1D (cortes horizontal/vertical no DC) servem para comparar
com a caracterização linha-a-linha do sinal TEMPEST capturado.

## Scripts de sinal (Octave)

Os scripts `sinal_autocorr_*.m` são os seus originais, que processam o
sinal IQ capturado (autocorrelação via FFT, com e sem RIC). Mantidos
aqui para o fluxo de comparação imagem × sinal. O caminho do arquivo
`.dat` e os parâmetros (fs, N, skiplags) devem ser ajustados dentro de
cada script conforme sua captura.

> Para a captura do artigo: fs = 54 MS/s (USRP B200), parede de alvenaria
> separando alvo e rádio, suíte gr-tempest.
# Tempest_toolkit
# Tempest_toolkit
