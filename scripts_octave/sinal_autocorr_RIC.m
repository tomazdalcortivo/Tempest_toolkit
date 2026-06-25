
% PARAMETERS - edit these:
filename = 'D:\Programação\Python\Mestrado\Pesquisa\Arquivos\grabacion_splitter_40M_1344_806_px_freq_64995840.dat';%'grabacion_HDMI-1024-768-70-40MHz.dat';
N = 1.5e6;%4194304;              % number of complex samples you want
fs = 40e6;            % sampling rate in Hz (set to correct value if known; used for lag->time)
threshold = 1e-6;     % amplitude threshold to detect "valid" signal (adjust if needed)
min_run = 50;         % number of consecutive samples above threshold to consider region valid
chunk_complex = 2^16; % number of complex samples to read per chunk (tune for memory; ~65k)
skiplags=290000;      % find manually
M_dec = 16;            % fator de decimação para o RIC (tente 2, 4, 8, etc.)

% =============================================================
max_peak_value_filter = 1.0;
% =============================================================

% ==========================
% ==  compactRic Function ==
% ==========================
function xhat = compactric(x, C)
  x = x(:);
  L = floor(numel(x) / C);
  if L == 0
    error('Compaction factor C (%d) is greater than the size of the input vector (%d).', C, numel(x));
  endif
  x_trunc = x(1 : L * C);
  x_reshaped = reshape(x_trunc, C, L);
  xhat = sum(x_reshaped, 2);
endfunction

% -------------------------------------------------------------------------
% 0) Basic file info and type inference

info = dir(filename);
if isempty(info)
  error('File not found: %s', filename);
endif
filesize = info.bytes;
printf('File size: %d bytes\n', filesize);
if mod(filesize, 8) == 0
  likely_complex = true;
  printf('File size divisible by 8 -> likely interleaved float32 I,Q (complex64 samples)\n');
elseif mod(filesize,4) == 0
  likely_complex = false;
  printf('File size divisible by 4 but not 8 -> likely real float32 samples\n');
else
  error('File size not divisible by 4 -> unexpected binary format.');
endif
if ~likely_complex
  error('Script currently expects interleaved float32 IQ data. Aborting.');
endif

% -------------------------------------------------------------------------
% 1) Open file and scan for valid signal

fid = fopen(filename, 'rb');
if fid < 0
  error('Could not open file.');
endif
bytes_per_complex = 8;
chunk_floats = chunk_complex * 2;
found = false;
total_complex_seen = 0;
buffer_complex = [];
while ~found
  raw = fread(fid, chunk_floats, 'float32=>double');
  if isempty(raw)
    break;
  endif
  if mod(numel(raw), 2) ~= 0
    raw = raw(1:end-1);
  endif
  cchunk = raw(1:2:end) + 1i * raw(2:2:end);
  nc = numel(cchunk);
  buffer_complex = [buffer_complex; cchunk(:)];
  mag = abs(buffer_complex);
  above = mag > threshold;
  L = numel(above);
  idx_start = -1;
  if L >= min_run
    convv = conv(double(above), ones(min_run,1));
    good = find(convv(1:L) >= min_run, 1, 'first');
    if ~isempty(good)
      idx_start = good;
    endif
  endif
  if idx_start > 0
    absolute_start_index = total_complex_seen - (numel(buffer_complex) - nc) + idx_start;
    printf('Detected valid region starting at absolute complex-sample index: %d\n', absolute_start_index);
    start_idx = absolute_start_index;
    found = true;
    break;
  endif
  total_complex_seen = total_complex_seen + nc;
  if numel(buffer_complex) > (min_run-1)
    buffer_complex = buffer_complex(end-(min_run-1)+1:end);
  endif
endwhile
if ~found
  fclose(fid);
  error('No valid region found (increase sensitivity or reduce threshold).');
endif

% -------------------------------------------------------------------------
% 2) Seek and read N complex samples

byte_offset = (start_idx - 1) * bytes_per_complex;
fseek(fid, byte_offset, 'bof');
floats_to_read = N * 2;
raw2 = fread(fid, floats_to_read, 'float32=>double');
fclose(fid);
if mod(numel(raw2), 2) ~= 0
  raw2 = raw2(1:end-1);
endif
iq = raw2(1:2:end) + 1i * raw2(2:2:end);
Lread = numel(iq);
printf('Read %d complex samples (requested %d).\n', Lread, N);
s = iq(1:min(N, Lread));

% -------------------------------------------------------------------------
% 3) Compute autocorrelation (FFT -> PSD -> RIC -> IFFT) and normalize

Ls = numel(s);
nfft = 2^nextpow2(2*Ls - 1);
Sfft = fft(s, nfft);
psd = Sfft .* conj(Sfft);

C_ric = nfft / M_dec;
if (mod(nfft, M_dec) ~= 0)
  error("nfft não é divisível pelo fator de decimação (M_dec).");
endif
printf('Applying the RIC function with C = %d (nfft/%d)...\n', C_ric, M_dec);
ric = compactric(psd, C_ric);

r_compact_full = (1/M_dec)*ifft(ric); % Fator de escala adaptável
r_full = zeros(nfft, 1); % Inicializa com o tamanho de nfft
r_full(1:M_dec:end) = r_compact_full; % Preenche os valores pulando os "vazios"

r = r_full(1:Ls);
lags = (0:Ls-1)';
if abs(r(1)) < 1e-9
    warning('Autocorrelation at lag zero is close to zero.');
    r_norm = r;
else
    r_norm = r ./ r(1); % Normaliza pelo lag 0
endif
printf("Using biased normalization (dividing by r(1)).\n");

% -------------------------------------------------------------------------
% 4) Find lag of highest value (excluding lag 0 if desired)

search_end = min(N, Ls);
search_range = skiplags:search_end;

[peak_val, peak_idx_local] = max(abs(r_norm(search_range)));
peak_idx_global = search_range(peak_idx_local);
lag_samples = lags(peak_idx_global);
lag_time = lag_samples / fs;

printf('Maximum |R(τ)| at lag = %d samples (%.6g seconds)\n', ...
        lag_samples, lag_time);

r_nozero = abs(r_norm(search_range));
r_nozero(1) = 0;

r_nozero(r_nozero > max_peak_value_filter) = 0;
printf("Searching for peak with max_peak_value filter = %.2f\n", max_peak_value_filter);

[peak_val2, peak_idx2_local] = max(r_nozero);
peak_idx2_global = search_range(peak_idx2_local);
lag_samples2 = lags(peak_idx2_global);
lag_time2 = lag_samples2 / fs;

printf('Next highest (nonzero, filtered) |R(τ)| at lag = %d samples (%.6g seconds)\n', ...
        lag_samples2, lag_time2);

peak_index = peak_idx2_global;
printf('Peak bin index: %d\n', peak_index);
if mod(peak_index, 2) == 0
    printf('Index parity: EVEN\n');
else
    printf('Index parity: ODD\n');
endif

% -------------------------------------------------------------------------
% 5) Plot results

plot_range = search_range;
time_lag = lags(plot_range) / fs;

% plot(time_lag, abs(r_norm(skiplags:N-skiplags)));
plot(time_lag, abs(r_norm(plot_range)));

hold on;

% plot(lag_time2, abs(r_norm(peak_idx2)), 'ro', ...);
plot(lag_time2, abs(r_norm(peak_idx2_global)), 'ro', 'markersize', 8, 'linewidth', 2);

xlabel('Lag (s)');
ylabel('|R(\tau)| (normalized)');
title('Normalized autocorrelation with RIC (magnitude)');
grid on;

printf('Peak marker plotted at lag %.6g s (sample %d)\n', lag_time2, lag_samples2);
