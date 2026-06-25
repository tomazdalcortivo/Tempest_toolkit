% ============================================================
% fft2_imagem.m
% ------------------------------------------------------------
% FFT 2D de imagens da tela da urna (versão Octave/MATLAB).
% Evolução do script original, com:
%   - eixos de frequência em ciclos/pixel
%   - espectro médio sobre múltiplos frames (tela_*.png)
%   - perfis 1D (cortes no DC) horizontal e vertical
%
% Uso: coloque as imagens tela_*.png na mesma pasta e rode.
% ============================================================
clear; clc; close all;

% ---- Parâmetros ----
padrao = 'tela_*.png';   % padrão das imagens
p_low  = 5;              % percentil inferior p/ contraste (%)
p_high = 99;             % percentil superior p/ contraste (%)

arquivos = dir(padrao);
num_imgs = length(arquivos);
assert(num_imgs > 0, 'Nenhuma imagem encontrada (%s).', padrao);
printf('Encontradas %d imagem(ns).\n', num_imgs);

espectro_medio = [];

for k = 1:num_imgs
    nome = arquivos(k).name;
    img = imread(nome);

    % Tons de cinza (luminância BT.601), sem pacotes externos
    if ndims(img) == 3
        img = 0.2989*double(img(:,:,1)) + 0.5870*double(img(:,:,2)) + 0.1140*double(img(:,:,3));
    else
        img = double(img);
    end
    img = img / max(img(:));   % normaliza [0,1]

    % FFT 2D + centralização
    F = fft2(img);
    espectro_tmp = abs(fftshift(F));

    if isempty(espectro_medio)
        espectro_medio = espectro_tmp;
    else
        espectro_medio = espectro_medio + espectro_tmp;
    end
end

% Média e conversão para dB
espectro_medio = espectro_medio / num_imgs;
espectro_db = 20*log10(espectro_medio + eps);

% Eixos de frequência (ciclos/pixel)
[Py, Px] = size(espectro_db);
fx = ((0:Px-1) - floor(Px/2)) / Px;
fy = ((0:Py-1) - floor(Py/2)) / Py;

% Contraste por percentil (manual)
v = sort(espectro_db(:));
n = numel(v);
vmin = v(max(1, round(p_low/100  * n)));
vmax = v(max(1, round(p_high/100 * n)));

% ---- Figura 1: espectro 2D ----
figure(1); clf;
imagesc(fx, fy, espectro_db);
colormap jet; colorbar;
caxis([vmin vmax]);
set(gca, 'YDir', 'normal');
xlabel('Frequência espacial horizontal (ciclos/pixel)');
ylabel('Frequência espacial vertical (ciclos/pixel)');
title('Espectro médio — FFT 2D (imagens)');

% ---- Figura 2: perfis 1D no DC ----
corte_h = espectro_db(round(Py/2)+1, :);
corte_v = espectro_db(:, round(Px/2)+1);

figure(2); clf;
subplot(2,1,1);
plot(fx, corte_h, 'LineWidth', 0.7);
grid on; xlabel('ciclos/pixel'); ylabel('dB');
title('Corte horizontal no DC');
subplot(2,1,2);
plot(fy, corte_v, 'LineWidth', 0.7, 'Color', [0.85 0.33 0.1]);
grid on; xlabel('ciclos/pixel'); ylabel('dB');
title('Corte vertical no DC');

printf('Pronto. Espectro %dx%d, dB em [%.1f, %.1f].\n', Px, Py, vmin, vmax);
