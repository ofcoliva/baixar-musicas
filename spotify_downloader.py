import os
import sys
import csv
import argparse
import subprocess
import shutil
import urllib.parse
import urllib.request
import json
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

# --- Configuração de Argumentos ---
parser = argparse.ArgumentParser(description="Spotify Downloader (Python Port)")
parser.add_argument("csv_file", help="Path to the .csv file from Exportify")
parser.add_argument("--downloader", help="Specify downloader (yt-dlp or youtube-dl)", default="")
parser.add_argument("--processNumber", type=int, default=5, help="Number of parallel downloads")
parser.add_argument("--musicPath", default="./spotify_musics", help="Output directory")
parser.add_argument("--additionalKeywords", default="", help="Additional search keywords")

args = parser.parse_args()

# --- Variáveis Globais e Locks ---
csv_file = args.csv_file
music_path = args.musicPath
additional_keywords = args.additionalKeywords
print_lock = Lock()
started_songs = 0
total_songs = 0

# --- Validações Iniciais ---
if not os.path.isfile(csv_file):
    print("ERROR: No .csv file provided or file not found. Obtain one here: https://watsonbox.github.io/exportify/")
    sys.exit(1)

if music_path and not os.path.exists(music_path):
    os.mkdir(music_path)
    print(f"ERROR: Selected path does not exist: {music_path}")
    # sys.exit(1)

# Detectar Downloader
downloader_cmd = args.downloader
if not downloader_cmd:
    if shutil.which("yt-dlp"):
        downloader_cmd = "yt-dlp"
    elif shutil.which("youtube-dl"):
        downloader_cmd = "youtube-dl"
    else:
        print("No downloader provided or detected. Install 'yt-dlp' or 'youtube-dl'.")
        sys.exit(1)

print(f"Using '{downloader_cmd}' as downloader.")

if not shutil.which("ffmpeg"):
    print("ERROR: FFMPEG could not be found. Install 'FFMPEG'.")
    sys.exit(1)

# Checagem opcional de ferramentas para Tagging avançado
has_kid3 = shutil.which("kid3-cli") is not None
# jq não é estritamente necessário pois Python lida com JSON nativamente

# --- Funções Auxiliares ---

def sanitize_filename(name):
    """Remove caracteres inválidos para nomes de arquivos."""
    return re.sub(r'[<>:"/\\|?*]', '', name)

def get_lyrics(track_name, artist_name, album_name, duration_ms, file_base_name):
    """Baixa letras da API lrclib.net e salva como .lrc ou .txt"""
    try:
        duration = int(int(duration_ms) / 1000)

        params = {
            'track_name': track_name,
            'artist_name': artist_name,
            'album_name': album_name,
            'duration': duration
        }
        query_string = urllib.parse.urlencode(params)
        url = f"https://lrclib.net/api/get?{query_string}"

        req = urllib.request.Request(url)
        req.add_header('User-Agent', "SDB v0.0.1 (Python Port)")

        with urllib.request.urlopen(req) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode())

                synced_lyrics = data.get('syncedLyrics')
                plain_lyrics = data.get('plainLyrics')

                if synced_lyrics:
                    with open(f"{file_base_name}.lrc", "w", encoding='utf-8') as f:
                        f.write(synced_lyrics)
                    return "lrc"
                elif plain_lyrics:
                    with open(f"{file_base_name}.txt", "w", encoding='utf-8') as f:
                        f.write(plain_lyrics)
                    return "txt"
    except Exception:
        # Silenciosamente falha se não achar letra, similar ao script original
        return None
    return None

def download_image(url, output_path):
    try:
        # Usando curl como no original para manter fidelidade, ou urllib
        # O script original usa curl -s "$image" > ...
        subprocess.run(["curl", "-s", url, "-o", output_path], check=True)
    except subprocess.CalledProcessError:
        pass

def process_song(row):
    global started_songs

    # Mapeamento de colunas (Baseado no Exportify padrão)
    try:
        title = row.get("Track Name", "")
        artist = row.get("Artist Name", "")
        album = row.get("Album Name", "")
        album_artist = row.get("Album Artist Name(s)", "")
        release_date = row.get("Album Release Date", "")
        image_url = row.get("Album Image URL", "")
        disc_num = row.get("Disc Number", "")
        track_num = row.get("Track Number", "")
        duration_ms = row.get("Track Duration (ms)", "0")
        popularity = int(row.get("Popularity", "0"))
        isrc = row.get("ISRC", "")
    except Exception as e:
        print(f"Error parsing row: {e}")
        return

    # Nome do arquivo final
    song_identifier = f"{title} - {artist}"
    sanitized_name = sanitize_filename(song_identifier)
    final_mp3_path = os.path.join(music_path, f"{sanitized_name}.mp3")

    if os.path.exists(final_mp3_path):
        with print_lock:
            print(f"Skipping: {title}.mp3 - (File already exists in: {music_path})")
        return

    # Atualiza status
    with print_lock:
        started_songs += 1
        percent = (started_songs / total_songs) * 100
        print(f"Status: #{started_songs} downloads started - {percent:.2f}%")

    # Cria diretório temporário
    temp_dir = tempfile.mkdtemp()
    temp_file_base = os.path.join(temp_dir, sanitized_name)

    try:
        # Construção da URL de busca (YouTube Music)
        # O script original usa urlencode manual, Python usa quote_plus
        q_title = urllib.parse.quote_plus(title)
        q_artist = urllib.parse.quote_plus(artist)
        q_keywords = urllib.parse.quote_plus(additional_keywords)

        # Nota: O original usa espaço como separador na query string do youtube
        # Vamos replicar a construção exata
        search_query = f"{q_title}+{q_artist}+{q_keywords}"
        song_url = f"https://music.youtube.com/search?q={search_query}#Songs"

        # Download da Capa
        download_image(image_url, f"{temp_file_base}.jpg")

        # Download do Áudio com yt-dlp
        dl_cmd = [
            downloader_cmd,
            "-o", f"{temp_file_base}.%(ext)s",
            song_url,
            "-I", "1", # Item 1
            "-x",      # Extract audio
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--quiet",
            "--no-warnings"
        ]

        subprocess.run(dl_cmd, check=True)

        temp_mp3 = f"{temp_file_base}.mp3"
        if not os.path.exists(temp_mp3):
            # As vezes o yt-dlp falha silenciosamente ou a busca não retorna nada
            print(f"Failed to download audio for: {title}")
            return

        # --- Tagging ---

        # Baixar letras
        lyrics_type = get_lyrics(title, artist, album, duration_ms, temp_file_base)

        if has_kid3:
            # Caminho A: kid3-cli (Mais rico em metadados)
            kid3_cmds = [
                "kid3-cli",
                "-c", f"set title '{title.replace('\'', '\\\'')}'",
                "-c", f"set artist '{artist.replace('\'', '\\\'')}'",
                "-c", f"set albumartist '{album_artist.replace('\'', '\\\'')}'",
                "-c", f"set album '{album.replace('\'', '\\\'')}'",
                "-c", f"set date '{release_date}'",
                "-c", f"set discnumber '{disc_num}'",
                "-c", f"set tracknumber '{track_num}'",
                "-c", f"set rating {int(popularity * 255 / 100)}",
                "-c", f"set isrc '{isrc}'",
                temp_mp3
            ]
            subprocess.run(kid3_cmds, check=False) # check=False pois kid3 pode reclamar mas funcionar

            # Lyrics
            if lyrics_type == "lrc":
                lrc_path = f"{temp_file_base}.lrc"
                subprocess.run(["kid3-cli", "-c", f"set SYLT:'{lrc_path}' ''", "-c", f"set USLT:'{lrc_path}' ''", temp_mp3], check=False)
            elif lyrics_type == "txt":
                txt_path = f"{temp_file_base}.txt"
                subprocess.run(["kid3-cli", "-c", f"set USLT:'{txt_path}' ''", temp_mp3], check=False)

            # Capa
            if os.path.exists(f"{temp_file_base}.jpg"):
                jpg_path = f"{temp_file_base}.jpg"
                subprocess.run(["kid3-cli", "-c", f"set picture:'{jpg_path}' '1'", temp_mp3], check=False)

            # Mover para final
            shutil.move(temp_mp3, final_mp3_path)

        else:
            # Caminho B: FFMPEG (Fallback)
            ffmpeg_cmd = [
                "ffmpeg",
                "-i", temp_mp3,
                "-i", f"{temp_file_base}.jpg",
                "-map", "0:0", "-map", "1:0",
                "-codec", "copy",
                "-id3v2_version", "3",
                "-metadata:s:v", "title=Album cover",
                "-metadata:s:v", "comment=Cover (front)",
                "-metadata", f"artist={artist}",
                "-metadata", f"album={album}",
                "-metadata", f"album_artist={album_artist}",
                "-metadata", f"disc={disc_num}",
                "-metadata", f"title={title}",
                "-metadata", f"track={track_num}",
                "-hide_banner", "-loglevel", "error",
                final_mp3_path, "-y"
            ]

            # Se não tiver imagem, ajusta o comando ffmpeg para não quebrar
            if not os.path.exists(f"{temp_file_base}.jpg"):
                 # Versão sem capa
                 ffmpeg_cmd = [
                    "ffmpeg", "-i", temp_mp3,
                    "-codec", "copy", "-id3v2_version", "3",
                    "-metadata", f"artist={artist}",
                    "-metadata", f"album={album}",
                    "-metadata", f"title={title}",
                    "-hide_banner", "-loglevel", "error",
                    final_mp3_path, "-y"
                 ]

            subprocess.run(ffmpeg_cmd, check=False)

        with print_lock:
            print(f"Finished: {title}")

    except Exception as e:
        print(f"Error processing {title}: {e}")
    finally:
        # Limpeza
        shutil.rmtree(temp_dir, ignore_errors=True)

# --- Execução Principal ---

def main():
    global total_songs, started_songs

    # Ler CSV para memória
    rows = []
    try:
        with open(csv_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        sys.exit(1)

    total_songs = len(rows)
    print(f"Found: {total_songs} entries")

    # Execução Paralela
    with ThreadPoolExecutor(max_workers=args.processNumber) as executor:
        futures = [executor.submit(process_song, row) for row in rows]
        # Esperar todos terminarem
        for future in futures:
            future.result()

    print("All downloads have been started/completed.")

if __name__ == "__main__":
    main()