import os
import sys
import argparse
import shutil
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from random import randint
import yt_dlp

from rich.progress import (
    Progress, TextColumn, BarColumn, DownloadColumn,
    TransferSpeedColumn, TimeRemainingColumn, SpinnerColumn
)

FINISHED_DOWNLOAD = 0
# --- Configuração de Log Profissional ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Validações de Sistema ---
def check_dependencies():
    """Garante que as ferramentas necessárias estão no sistema."""
    if not shutil.which("ffmpeg"):
        logger.critical("FFMPEG não encontrado. É obrigatório para conversão de áudio para MP3.")
        logger.info("Instale via: 'winget install ffmpeg' (Windows) ou 'sudo apt install ffmpeg' (Linux)")
        sys.exit(1)

    if not (shutil.which("node") or shutil.which("deno")):
        logger.warning("Nenhum runtime JavaScript (Node.js ou Deno) encontrado no sistema.")
        logger.warning("O yt-dlp precisa disso para extrair formatos de alta qualidade do YouTube.")
        logger.info("Por favor, instale o Node.js (https://nodejs.org) e reinicie o terminal.")
        # Não damos sys.exit() aqui porque alguns vídeos ainda baixam sem ele,
        # mas o aviso visual fica claro para quem rodar.
class PlaylistDownloader:
    """Gerencia extração de URLs e downloads paralelos usando a API nativa do yt-dlp."""

    def __init__(self, output_dir: str, cookie_file: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cookie_file = cookie_file

    def _get_base_options(self) -> dict:
        """Retorna as configurações blindadas anti-bot e de qualidade máxima."""
        return {
            'format': 'bestaudio/best',
            'postprocessors': [
                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '0'},
                {'key': 'EmbedThumbnail'}, # Embutir capa DENTRO do MP3
            ],
            'outtmpl': str(self.output_dir / '%(title)s.%(ext)s'),

            # --- Anti-Bot Avançado ---
            'cookiefile': self.cookie_file if os.path.exists(self.cookie_file) else None,
            'sleep_interval': randint(7, 15),      # Delay humanizado inicial
            'max_sleep_interval': 30,              # Teto do delay
            'sleep_requests': randint(3, 8),       # Delay entre requisições de página
            'extractor_args': {
                'youtube': {'player_client': ['android', 'web']} # Usa a API de celular (menos bloqueios)
            },

            # --- Limpeza de Output ---
            'writemetadata': True,
            'writethumbnail': True,
            'quiet': True,
            'no_warnings': True,
        }

    def get_playlist_urls(self, playlist_url: str) -> list[str]:
        """Usa a API para extrair apenas as URLs, sem baixar os vídeos ainda."""
        logger.info(f"Lendo playlist: {playlist_url}")

        opts = {
            'extract_flat': True, # Modo "apenas leitura"
            'quiet': True,
            'cookiefile': self.cookie_file if os.path.exists(self.cookie_file) else None,
        }

        urls = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                if 'entries' in info:
                    urls = [entry['url'] for entry in info['entries'] if entry.get('url')]
                else:
                    urls = [playlist_url] # Fallback: se for só um vídeo, retorna ele mesmo
        except Exception as e:
            logger.error(f"Falha ao ler playlist: {e}")

        return urls

    # def download_video(self, video_url: str):
    #     global FINISHED_DOWNLOAD
    #     """Baixa um único vídeo. Será chamado em paralelo pelos workers."""
    #     opts = self._get_base_options()
    #     try:
    #         logger.info(f"Baixando: {video_url}")
    #         with yt_dlp.YoutubeDL(opts) as ydl:
    #             ydl.download([video_url])
    #         FINISHED_DOWNLOAD += 1
    #         logger.info(f"Concluído: {video_url}")
    #     except Exception as e:
    #         logger.error(f"Erro no download de {video_url}: {e}")

    def download_video(self, video_url: str, progress: Progress, task_id):
        opts = self._get_base_options()

        # O Gancho (Hook): Intercepta os dados que o yt-dlp enviaria pro terminal
        def yt_dlp_hook(d):
            if d['status'] == 'downloading':
                # Pega o título ou usa um nome genérico
                title = d.get('info_dict', {}).get('title', 'Processando...')[:35]
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)

                # Atualiza a barra do rich
                progress.update(
                    task_id,
                    description=f"[cyan]{title}...",
                    completed=downloaded,
                    total=total if total > 0 else None
                )

            elif d['status'] == 'finished':
                title = d.get('info_dict', {}).get('title', 'Concluído')[:35]
                # Barra cheia e verde ao terminar
                progress.update(task_id, description=f"[green]✓ {title}", completed=1, total=1)

        # Injetamos o gancho nas opções
        opts['progress_hooks'] = [yt_dlp_hook]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([video_url])
        except Exception as e:
            progress.update(task_id, description=f"[red]X Erro: {video_url[-11:]}")
            # Usamos o print do console do rich para não quebrar a barra
            progress.console.print(f"[red]Erro no download de {video_url}: {e}")

# --- Ponto de Entrada (Main) ---
def main():
    parser = argparse.ArgumentParser(description="YouTube Playlist Downloader Avançado")
    parser.add_argument("url", help="URL da playlist do YouTube")
    parser.add_argument("-p", "--processos", type=int, default=3, help="Número de downloads simultâneos (Cuidado com bloqueios se > 3)")
    parser.add_argument("-o", "--output", default="./yt_musics", help="Diretório de saída (Ex: ./minhas_musicas)")
    parser.add_argument("-c", "--cookies", default="www.youtube.com_cookies.txt", help="Caminho para o arquivo TXT de cookies")
    args = parser.parse_args()

    check_dependencies()

    if not os.path.exists(args.cookies):
        logger.warning(f"Arquivo de cookies '{args.cookies}' não encontrado. Iniciando modo anônimo (Risco alto de bloqueio).")

    downloader = PlaylistDownloader(output_dir=args.output, cookie_file=args.cookies)

    # 1. Busca todas as URLs
    urls = downloader.get_playlist_urls(args.url)
    total = len(urls)

    if total == 0:
        logger.warning("Nenhum vídeo encontrado. Verifique a URL ou seus cookies.")
        sys.exit(1)

    logger.info(f"Total de vídeos enfileirados: {total}")
    logger.info(f"Iniciando {args.processos} workers paralelos...")

    # 2. Executa em Paralelo com barra de progresso visual no terminal
    sucessos = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as progress:

        with ThreadPoolExecutor(max_workers=args.processos) as executor:
            futuros = {}
            for url in urls:
                # Criamos uma linha (tarefa) genérica inicial para cada URL
                task_id = progress.add_task("[yellow]Aguardando na fila...", total=None)
                # Disparamos a função passando a interface visual para ela
                futuro = executor.submit(downloader.download_video, url, progress, task_id)
                futuros[futuro] = url

            # Aguarda todos finalizarem
            for futuro in as_completed(futuros):
                pass

    logger.info(f"🎉 Processo finalizado! {total}/{sucessos}")

if __name__ == "__main__":
    main()