% ============================================================
% fft2_imagem_blanking.m
% ------------------------------------------------------------
% Aplica BLANKING VESA a cada imagem ativa e calcula a FFT 2D.
%
% Timing 1280x720@60 (CVT), conforme artigo:
%   ativo total : 1280 x 720
%   com blank   : 1650 x 750   (Px x Py)
%   pixel clock : 74.25 MHz
%
% A região de blanking é preenchida com nível 0 (preto), coerente
% com o nível de "preto"/sync do sinal de vídeo real.
%
% Uso: imagens tela_*.png na mesma pasta. Rode e veja os espectros.
% ============================================================
clear; clc; close all;

% ---- Timing VESA (edite aqui p/ outras resoluções) ----
H_active = 1280; H_front = 72; H_sync = 80; H_back = 218;  % total 1650
V_active = 720;  V_front = 3;  V_sync = 5;  V_back = 22;   % total 750
Px = H_active + H_front + H_sync + H_back;   % 1650
Py = V_active + V_front + V_sync + V_back;   % 750
nivel_blank = 0.0;       % 0 = preto
modo = 'vesa_real';      % 'vesa_real' (offset=back porch) ou 'centralizado'

% ---- Parâmetros de plot ----
padrao = 'tela_*.png';
p_low = 5; p_high = 99;

assert(Px == 1650 && Py == 750, ...
  'Timing inconsistente: %dx%d (esperado 1650x750).', Px, Py);

arquivos = dir(padrao);
num_imgs = length(arquivos);
assert(num_imgs > 0, 'Nenhuma imagem encontrada (%s).', padrao);
printf('Encontradas %d imagem(ns). Quadro total: %dx%d.\n', num_imgs, Px, Py);

% Offsets da área ativa dentro do quadro
if strcmp(modo, 'vesa_real')
    ox = H_back; oy = V_back;          % início após back porch
else
    ox = floor((Px - H_active)/2);
    oy = floor((Py - V_active)/2);
end

espectro_medio = [];

for k = 1:num_imgs
    nome = arquivos(k).name;
    img = imread(nome);
    if ndims(img) == 3
        img = 0.2989*double(img(:,:,1)) + 0.5870*double(img(:,:,2)) + 0.1140*double(img(:,:,3));
    else
        img = double(img);
    end
    img = img / max(img(:));

    % Redimensiona p/ tamanho ativo se necessário
    if size(img,1) ~= V_active || size(img,2) ~= H_active
        img = imresize(img, [V_active, H_active]);  % requer pkg image; ver nota
    end

    % Monta quadro com blanking
    quadro = ones(Py, Px) * nivel_blank;
    quadro(oy+1:oy+V_active, ox+1:ox+H_active) = img;

    % FFT 2D
    F = fft2(quadro);
    espectro_tmp = abs(fftshift(F));

    if isempty(espectro_medio)
        espectro_medio = espectro_tmp;
    else
        espectro_medio = espectro_medio + espectro_tmp;
    end
end

espectro_medio = espectro_medio / num_imgs;
espectro_db = 20*log10(espectro_medio + eps);

% Eixos de frequência
fx = ((0:Px-1) - floor(Px/2)) / Px;
fy = ((0:Py-1) - floor(Py/2)) / Py;

% Contraste por percentil
v = sort(espectro_db(:)); n = numel(v);
vmin = v(max(1, round(p_low/100  * n)));
vmax = v(max(1, round(p_high/100 * n)));

figure(1); clf;
imagesc(fx, fy, espectro_db);
colormap jet; colorbar; caxis([vmin vmax]);
set(gca, 'YDir', 'normal');
xlabel('Frequência espacial horizontal (ciclos/pixel)');
ylabel('Frequência espacial vertical (ciclos/pixel)');
title(sprintf('Espectro médio — FFT 2D com blanking VESA (%dx%d)', Px, Py));

printf('Pronto. Offsets ativos: x=%d, y=%d.\n', ox, oy);
printf('NOTA: imresize requer o pacote "image" (pkg load image).\n');
printf('      Se as imagens já forem 1280x720, o resize nao e usado.\n');
