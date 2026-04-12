import os
import sys
import argparse
import subprocess
import shutil
from concurrent.futures import ThreadPoolExecutor

# --- Configuração de Argumentos ---
parser = argparse.ArgumentParser(description="YouTube Playlist Downloader")
parser.add_argument("url", help="URL da playlist do YouTube")
parser.add_argument("--processNumber", type=int, default=3, help="Número de downloads paralelos")
parser.add_argument("--musicPath", default="./yt_musics", help="Diretório de saída")
args = parser.parse_args()

# --- Validações ---
if not (shutil.which("yt-dlp") or shutil.which("youtube-dl")):
    print("Erro: Instale o 'yt-dlp' (recomendado) ou 'youtube-dl'.")
    sys.exit(1)

if not shutil.which("ffmpeg"):
    print("Erro: FFMPEG não encontrado. Instale o FFMPEG para conversão de áudio.")
    sys.exit(1)

if not os.path.exists(args.musicPath):
    os.makedirs(args.musicPath)

downloader = "yt-dlp" if shutil.which("yt-dlp") else "youtube-dl"

def download_video(video_url):
    """Baixa um vídeo individual da playlist com metadados completos."""
    cmd = [
        downloader,
        "-x",                           # Extrair áudio
        "--audio-format", "mp3",        # Formato MP3
        "--audio-quality", "0",         # Melhor qualidade
        "--add-metadata",               # Adiciona metadados do YT
        "--embed-thumbnail",            # Embutir capa do vídeo
        "-o", f"{args.musicPath}/%(title)s.%(ext)s",
        "--quiet", "--no-warnings",
        video_url
    ]

    try:
        print(f"Iniciando: {video_url}")
        subprocess.run(cmd, check=True)
        print(f"Finalizado: {video_url}")
    except Exception as e:
        print(f"Erro ao baixar {video_url}: {e}")

def get_playlist_urls(playlist_url):
    """Obtém a lista de URLs de todos os vídeos da playlist."""
    cmd = [downloader, "--flat-playlist", "--get-id", playlist_url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    ids = result.stdout.strip().split('\n')
    return [f"https://www.youtube.com/watch?v={id}" for id in ids if id]

def main():
    print(f"Buscando vídeos da playlist...")
    urls = get_playlist_urls(args.url)
    total = len(urls)
    print(f"Total de vídeos encontrados: {total}")

    # Execução Paralela
    with ThreadPoolExecutor(max_workers=args.processNumber) as executor:
        executor.map(download_video, urls)

    print("\nProcesso concluído!")

if __name__ == "__main__":
    main()