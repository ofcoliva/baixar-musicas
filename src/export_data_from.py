import csv
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from concurrent.futures import ThreadPoolExecutor, as_completed

class BasePlaylistExporter:
    """Classe base. Contém a lógica comum de escrever o CSV e atualizar a interface."""
    def __init__(self, log_callback, progress_callback):
        self.log = log_callback
        self.progress = progress_callback

    def extrair_dados(self, playlist_url, max_workers):
        """Método que as classes filhas (YouTube/Spotify) DEVEM sobrescrever."""
        raise NotImplementedError("As subclasses devem implementar este método.")

    def gerar_csv(self, playlist_url, output_csv="export.csv", max_workers=4):
        # 1. Pede para a classe filha extrair os dados na sua própria plataforma
        entries = self.extrair_dados(playlist_url, max_workers)

        if not entries:
            self.log("[bold red]Nenhuma música encontrada ou ocorreu um erro.[/]")
            return

        # 2. Lógica universal para salvar os dados em CSV
        headers = [
            "Track Name", "Artist Name(s)", "Album Name", "Album Artist Name(s)", 
            "Album Release Date", "Album Image URL", "Disc Number", "Track Number",
            "Track Duration (ms)", "Popularity", "ISRC"
        ]

        with open(output_csv, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for entry in entries:
                writer.writerow(entry)
                self.progress() # Avança a barra para cada linha salva no CSV

        self.log(f"[bold green]Sucesso! Arquivo '{output_csv}' gerado com {len(entries)} músicas.[/]")


class YouTubeExporter(BasePlaylistExporter):
    """Implementação específica para baixar metadados do YouTube."""
    def extrair_dados(self, playlist_url, max_workers):
        ydl_opts = {
            'extract_flat': 'in_playlist',
            'quiet': True,
            'extractor_args': {'youtube': {'lang': ['pt']}}
        }

        self.log("[cyan]Acessando o YouTube...[/]")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
        except Exception as e:
            self.log(f"[bold red]Erro no YouTube: {e}[/]")
            return []

        raw_entries = [e for e in info.get('entries', []) if e]
        playlist_name = info.get('title', 'YouTube Playlist')
        self.progress(total=len(raw_entries))

        def fetch_video(entry):
            # Cada thread tem sua própria instância — yt_dlp não é thread-safe
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                try:
                    video_info = ydl.extract_info(
                        f"https://www.youtube.com/watch?v={entry['id']}",
                        download=False
                    )
                except Exception as e:
                    self.log(f"[yellow]Pulando vídeo {entry.get('id')}: {e}[/]")
                    self.progress()
                    return None

            title    = video_info.get('title', 'Desconhecido')
            uploader = str(video_info.get('uploader', 'Desconhecido')).replace(" - Topic", "")

            upload_date = video_info.get('upload_date', '')
            if upload_date:
                upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"

            duration_ms = int((video_info.get('duration') or 0) * 1000)
            thumbnails  = video_info.get('thumbnails', [])
            image_url   = thumbnails[-1]['url'] if thumbnails else ""

            self.log(f"[dim]Lido (YouTube):[/] {title}")
            self.progress()

            return {
                "Track Name":            title,
                "Artist Name(s)":        uploader,
                "Album Name":            playlist_name,
                "Album Artist Name(s)":  uploader,
                "Album Release Date":    upload_date,
                "Album Image URL":       image_url,
                "Disc Number":           "1",
                "Track Number":          "1",
                "Track Duration (ms)":   duration_ms,
                "Popularity":            "50",
                "ISRC":                  ""
            }

        with ThreadPoolExecutor(max_workers) as executor:
            '''
            O executor.map lança as threads simultaneamente, mas devolve 
            os resultados rigorosamente na mesma ordem de raw_entries.
            '''
            results = list(executor.map(fetch_video, raw_entries))

        return [r for r in results if r is not None]

class SpotifyExporter(BasePlaylistExporter):
    """Implementação específica para baixar metadados ricos do Spotify."""
    def __init__(self, log_callback, progress_callback, client_id, client_secret):
        super().__init__(log_callback, progress_callback)
        self.client_id = client_id
        self.client_secret = client_secret

    def extrair_dados(self, playlist_url, max_workers=4):
        self.log("[cyan]Acessando o Spotify...[/]")
        try:
            auth_manager = SpotifyClientCredentials(client_id=self.client_id, client_secret=self.client_secret)
            sp = spotipy.Spotify(auth_manager=auth_manager)

            # Pega as músicas contornando o limite de 100 por página do Spotify
            results = sp.playlist_items(playlist_url)
            tracks = results['items']
            while results['next']:
                results = sp.next(results)
                tracks.extend(results['items'])

        except Exception as e:
            self.log(f"[bold red]Erro no Spotify: {e}[/]")
            return []

        self.progress(total=len(tracks)) # Define o tamanho da barra

        processed_entries = []
        for item in tracks:
            track = item.get('track')
            if not track:
                continue

            # Aqui obtemos os dados idênticos aos que o Exportify geraria nativamente!
            artists = ", ".join([a['name'] for a in track.get('artists', [])])
            album_artists = ", ".join([a['name'] for a in track.get('album', {}).get('artists', [])])
            images = track.get('album', {}).get('images', [])
            image_url = images[0]['url'] if images else ""

            processed_entries.append({
                "Track Name": track.get('name', ''),
                "Artist Name(s)": artists,
                "Album Name": track.get('album', {}).get('name', ''),
                "Album Artist Name(s)": album_artists,
                "Album Release Date": track.get('album', {}).get('release_date', ''),
                "Album Image URL": image_url,
                "Disc Number": track.get('disc_number', 1),
                "Track Number": track.get('track_number', 1),
                "Track Duration (ms)": track.get('duration_ms', 0),
                "Popularity": track.get('popularity', 0),
                "ISRC": track.get('external_ids', {}).get('isrc', '')
            })
            self.log(f"[dim]Lido (Spotify):[/] {track.get('name')}")

        return processed_entries
