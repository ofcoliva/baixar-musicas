import os
import csv
import subprocess
import shutil
import urllib.parse
import urllib.request
import json
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor

class DownloaderBackend:
    def __init__(self, log_callback, progress_callback):
        self.log = log_callback
        self.progress = progress_callback
        self.downloader_cmd = ""
        self.has_kid3 = False
        
    def check_dependencies(self):
        """Verifica se as ferramentas necessárias estão instaladas."""
        if shutil.which("yt-dlp"):
            self.downloader_cmd = "yt-dlp"
        elif shutil.which("youtube-dl"):
            self.downloader_cmd = "youtube-dl"
        else:
            self.log("[bold red]ERRO: yt-dlp ou youtube-dl não encontrado.[/]")
            return False

        self.log(f"[green]Downloader detectado: {self.downloader_cmd}[/]")

        if not shutil.which("ffmpeg"):
            self.log("[bold red]ERRO: ffmpeg não encontrado.[/]")
            return False
            
        self.has_kid3 = shutil.which("kid3-cli") is not None
        if self.has_kid3:
            self.log("[green]kid3-cli detectado para metadados avançados.[/]")
        
        return True

    def sanitize_filename(self, name):
        return re.sub(r'[<>:"/\\|?*]', '_', name)

    def get_lyrics(self, track_name, artist_name, album_name, duration_ms, file_base_name):
        try:
            duration = int(int(duration_ms) / 1000)
            params = {
                'track_name': track_name, 'artist_name': artist_name,
                'album_name': album_name, 'duration': duration
            }
            query_string = urllib.parse.urlencode(params)
            url = f"https://lrclib.net/api/get?{query_string}"
            req = urllib.request.Request(url, headers={'User-Agent': "SDB v0.0.1"})
            
            with urllib.request.urlopen(req) as response:
                if response.getcode() == 200:
                    data = json.loads(response.read().decode())
                    synced_lyrics, plain_lyrics = data.get('syncedLyrics'), data.get('plainLyrics')
                    
                    if synced_lyrics:
                        with open(f"{file_base_name}.lrc", "w", encoding='utf-8') as f:
                            f.write(synced_lyrics)
                        return "lrc"
                    elif plain_lyrics:
                        with open(f"{file_base_name}.txt", "w", encoding='utf-8') as f:
                            f.write(plain_lyrics)
                        return "txt"
        except Exception:
            pass
        return None

    def process_song(self, row, music_path):
        try:
            title = row.get("Track Name", "")
            artist = row.get("Artist Name(s)", "")
            album = row.get("Album Name", "")
            duration_ms = row.get("Track Duration (ms)", "0")
            image_url = row.get("Album Image URL", "")
        except Exception as e:
            self.log(f"[red]Erro lendo CSV: {e}[/]")
            return

        song_identifier = f"{title} - {artist}"
        sanitized_name = self.sanitize_filename(song_identifier)
        final_mp3_path = os.path.join(music_path, f"{sanitized_name}.mp3")

        if os.path.exists(final_mp3_path):
            self.log(f"[dim]Pulando (já existe): {sanitized_name}[/]")
            self.progress()
            return

        self.log(f"[cyan]Baixando:[/] {song_identifier}")
        temp_dir = tempfile.mkdtemp()
        temp_file_base = os.path.join(temp_dir, sanitized_name)
        
        try:
            q_title = urllib.parse.quote_plus(title)
            q_artist = urllib.parse.quote_plus(artist)
            song_url = f"https://music.youtube.com/search?q={q_title}+{q_artist}#Songs"

            if image_url:
                subprocess.run(["curl", "-s", image_url, "-o", f"{temp_file_base}.jpg"], check=False)

            dl_cmd = [
                self.downloader_cmd, "-o", f"{temp_file_base}.%(ext)s",
                song_url, "-I", "1", "-x", "--audio-format", "mp3", 
                "--audio-quality", "0", "--quiet", "--no-warnings"
            ]
            subprocess.run(dl_cmd, check=True)

            temp_mp3 = f"{temp_file_base}.mp3"
            if not os.path.exists(temp_mp3):
                self.log(f"[red]Falha ao obter áudio:[/] {title}")
                return

            self.get_lyrics(title, artist, album, duration_ms, temp_file_base)

            imagem_path = f"{temp_file_base}.jpg"
            has_image = False

            if image_url:
                try:
                    req = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response, open(imagem_path, 'wb') as out_file:
                        shutil.copyfileobj(response, out_file)
                    
                    # Checa se o arquivo foi criado e não está vazio
                    if os.path.exists(imagem_path) and os.path.getsize(imagem_path) > 0:
                        has_image = True
                except Exception as e:
                    self.log(f"[yellow]Aviso: Falha ao baixar capa de '{title}': {e}[/]")

            if self.has_kid3:
                kid3_cmds = [
                    "kid3-cli", "-c", f"set title '{title.replace('\'', '\\\'')}'",
                    "-c", f"set artist '{artist.replace('\'', '\\\'')}'",
                    "-c", f"set album '{album.replace('\'', '\\\'')}'", temp_mp3
                ]

                # Se tiver imagem, adiciona o comando de capa
                if has_image:
                    kid3_cmds.extend(["-c", f"set picture:'{imagem_path}' ''"])
                
                # O arquivo alvo precisa ser o último parâmetro
                kid3_cmds.append(temp_mp3)

                subprocess.run(kid3_cmds, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                shutil.move(temp_mp3, final_mp3_path)
            else:
                # Fallback FFMPEG
                if has_image:
                    ffmpeg_cmd = [
                        "ffmpeg", 
                        "-i", temp_mp3, 
                        "-i", imagem_path,
                        "-map", "0:a", "-map", "1:v", 
                        "-c:a", "copy", 
                        "-c:v", "mjpeg", # A MÁGICA: Força a imagem a virar um JPEG compatível!
                        "-id3v2_version", "3",
                        "-metadata:s:v", "title=Album cover", 
                        "-metadata:s:v", "comment=Cover (front)",
                        "-metadata", f"artist={artist}", 
                        "-metadata", f"title={title}",
                        "-hide_banner", "-loglevel", "error", 
                        final_mp3_path, "-y"
                    ]
                else:
                    ffmpeg_cmd = [
                        "ffmpeg", "-i", temp_mp3, 
                        "-codec", "copy", "-id3v2_version", "3",
                        "-metadata", f"artist={artist}", "-metadata", f"title={title}",
                        "-hide_banner", "-loglevel", "error", 
                        final_mp3_path, "-y"
                    ]
                    
                subprocess.run(ffmpeg_cmd, check=False)

            self.log(f"[green]Finalizado:[/] {title}")
        
        except Exception as e:
            self.log(f"[red]Erro processando {title}: {e}[/]")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            self.progress()

    def run(self, csv_path, music_path, workers):
        """Método principal que gerencia as threads e a leitura do CSV."""
        if not os.path.exists(music_path):
            try:
                os.mkdir(music_path)
                self.log(f"Diretório criado: {music_path}")
            except OSError:
                self.log(f"[bold red]Falha ao criar diretório: {music_path}[/]")
                return

        rows = []
        try:
            with open(csv_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception as e:
            self.log(f"[bold red]Erro ao ler CSV: {e}[/]")
            return

        self.log(f"[bold yellow]Total de músicas encontradas: {len(rows)}[/]")
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for row in rows:
                executor.submit(self.process_song, row, music_path)
