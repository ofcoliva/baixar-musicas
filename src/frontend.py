import os
import re
import threading
import webbrowser
import dotenv

from datetime import datetime
from zoneinfo import ZoneInfo

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Header, Input, Button, Label, ProgressBar, RichLog, TabPane, TabbedContent, Select
from textual import work

from src.downloader import DownloaderBackend
from src.export_data_from import SpotifyExporter, YouTubeExporter

dotenv.load_dotenv()

class SpotifyCredentialsModal(ModalScreen[tuple[str, str]]):
    """Um pop-up para solicitar as credenciais do Spotify caso faltem no .env"""

    CSS_PATH = "styles.tcss"

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-dialog"):
            yield Label("[bold cyan]Configuração do Spotify Necessária![/]\n")
            yield Label("O seu navegador foi aberto na página de Desenvolvedor do Spotify.")
            yield Label("1. Faça login e clique em 'Create App'.")
            yield Label("2. Copie o Client ID e o Client Secret e cole abaixo:\n")
            
            yield Input(placeholder="Cole o Client ID aqui", id="client_id_input")
            yield Input(placeholder="Cole o Client Secret aqui", id="client_secret_input", password=True)
            
            with Horizontal():
                yield Button("Salvar", variant="success", id="btn_save_creds")
                yield Button("Cancelar", variant="error", id="btn_cancel_creds")

    def on_mount(self):
        webbrowser.open("https://developer.spotify.com/dashboard")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_save_creds":
            client_id = self.query_one("#client_id_input").value.strip()
            client_secret = self.query_one("#client_secret_input").value.strip()

            if client_id and client_secret:
                # Retorna os valores para a tela principal
                self.dismiss((client_id, client_secret))

        elif event.button.id == "btn_cancel_creds":
            self.dismiss((None, None))

class BaixarMusicas(App):
    """Interface Gráfica do Spotify Downloader"""

    CSS_PATH = "styles.tcss"

    def __init__(self):
        super().__init__()
        self.backend = DownloaderBackend(log_callback=self.safe_log, progress_callback=self.safe_update_progress)
        self.historico_download = []
        self.historico_export = []

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="aba-download"):

            # 1 aba            
            with TabPane("Downloads", id="aba-download"):
                with Container(id="main_container"):
                    yield Label("[bold]Baixe suas musicas atraves do arquivo csv exportado", classes="titulo-aba")
                    with Horizontal(classes="input_row"):
                        yield Input(placeholder="Caminho para o arquivo .csv", value="./playlist.csv", id="csv_input")
                        yield Input(placeholder="Pasta de Saída", value="./musics", id="path_input")

                    with Horizontal(classes="input_row"):
                        yield Input(placeholder="Qtd. Processos", value="4", type="integer", id="workers_input")
                        yield Button("Iniciar Download", variant="success", id="start_btn")
                        # yield Button("Copiar Log", variant="primary", id="copy_btn") 

                    yield ProgressBar(id="progress_bar", show_eta=True)
                    yield RichLog(id="log", highlight=True, markup=True)

            # 2 aba
            with TabPane("Exports", id="aba-export_tube"):
                with Container(id="main_container"):
                    yield Label("[bold]Exporte suas músicas para um arquivo .csv[/]", classes="titulo-aba")

                    with Horizontal(classes="input_row"):
                        yield Select((("YouTube", "youtube"), ("Spotify", "spotify")), value="youtube", id="platform_select")
                        yield Input(placeholder="URL da playlist", id="url_input")

                    with Horizontal(classes="input_row"):
                        yield Input(placeholder="Diretório do arquivo [.csv]", value="./playlist.csv", id="output_file_path")
                        yield Button("Iniciar Exportação", variant="primary", id="start_exportation_btn")

                    yield ProgressBar(id="export_progress_bar", show_eta=True)
                    yield RichLog(id="export_log", highlight=True, markup=True)

            # 3 aba
            with TabPane("Sobre", id="aba-sobre"):
                yield Label("Spotify Downloader TUI v1.0\nCriado com Python e Textual.")

    def on_mount(self) -> ComposeResult:
        self.safe_log("[bold cyan]Verificando dependências...[/]")
        self.backend.check_dependencies()

    def safe_log(self, message: str):
        """Recebe as mensagens do backend e garante que sejam escritas na thread correta."""

        texto_limpo = re.sub(r'\[.*?\]', '', message)
        self.historico_download.append(texto_limpo)

        log_widget = self.query_one(RichLog)
        if self._thread_id == threading.get_ident():
            log_widget.write(message)
        else:
            self.call_from_thread(log_widget.write, message)

    def safe_export_log(self, message: str):
        """Escreve os logs na aba de Exportação."""
        texto_limpo = re.sub(r'\[.*?\]', '', message)
        self.historico_export.append(texto_limpo)

        log_widget = self.query_one("#export_log", RichLog)
        if self._thread_id == threading.get_ident():
            log_widget.write(message)
        else:
            self.call_from_thread(log_widget.write, message)

    def safe_update_progress(self):
        """Avança a barra de progresso."""
        progress = self.query_one(ProgressBar)
        self.call_from_thread(progress.advance, 1)

    def safe_update_export_progress(self, advance=1, total=None):
        """Avança a barra de progresso da exportação ou define o total."""
        def update():
            progress = self.query_one("#export_progress_bar", ProgressBar)
            if total is not None:
                progress.update(total=total, progress=0)
            else:
                progress.advance(advance)
        self.call_from_thread(update)
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:

        if event.button.id == "start_btn":
            csv_path = self.query_one("#csv_input").value
            music_path = self.query_one("#path_input").value
            workers = int(self.query_one("#workers_input").value or 4)

            if not csv_path:
                self.safe_log("[bold red]Erro: Informe o caminho do arquivo CSV![/]")
                return

            if not self.backend.downloader_cmd:
                self.safe_log("[bold red]Erro: Ferramentas ausentes.[/]")
                return

            event.button.disabled = True
            
            try:
                with open(csv_path, mode='r', encoding='utf-8-sig') as f:
                    total_songs = sum(1 for row in f) - 1 # -1 para descontar o cabeçalho
                self.query_one(ProgressBar).update(total=total_songs, progress=0)
            except Exception:
                pass

            self.run_downloads_in_background(csv_path, music_path, workers)


        # Iniciar exportação do .csv
        if event.button.id == "start_exportation_btn":
            url = self.query_one("#url_input").value
            output_file = self.query_one("#output_file_path").value
            plataforma = self.query_one("#platform_select", Select).value

            if not url:
                self.safe_export_log("[bold red]Erro: Informe a URL da playlist![/]")
                return

            # Função auxiliar que será chamada APÓS obtermos as chaves (seja do .env ou do Modal)
            def executar_exportacao(client_id, client_secret):
                event.button.disabled = True
                if plataforma == "youtube":
                    exporter = YouTubeExporter(self.safe_export_log, self.safe_update_export_progress)
                elif plataforma == "spotify":
                    exporter = SpotifyExporter(
                        self.safe_export_log, 
                        self.safe_update_export_progress,
                        client_id=client_id, 
                        client_secret=client_secret
                    )
                self.run_exportation_in_background(
                    exporter_instance=exporter, 
                    url=url, 
                    output_file_path=output_file
                )

            # Lógica de verificação do Spotify
            if plataforma == "spotify":
                # Tenta carregar do arquivo .env
                dotenv.load_dotenv()
                env_client_id = os.getenv("SPOTIFY_CLIENT_ID")
                env_client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

                if env_client_id and env_client_secret:
                    # Já tem as chaves, roda direto!
                    executar_exportacao(env_client_id, env_client_secret)
                else:
                    # Não tem as chaves. Chama o Pop-up (Modal)!
                    def salvar_e_continuar(credenciais):
                        cid, csec = credenciais
                        if cid and csec:
                            # Salva no arquivo .env
                            dotenv.set_key(".env", "SPOTIFY_CLIENT_ID", cid)
                            dotenv.set_key(".env", "SPOTIFY_CLIENT_SECRET", csec)
                            # Atualiza as variáveis na memória atual
                            os.environ["SPOTIFY_CLIENT_ID"] = cid
                            os.environ["SPOTIFY_CLIENT_SECRET"] = csec
                            
                            self.safe_export_log("[green]Credenciais do Spotify salvas com sucesso no arquivo .env![/]")
                            executar_exportacao(cid, csec)
                        else:
                            self.safe_export_log("[red]Exportação cancelada. Credenciais não informadas.[/]")

                    # Abre o Modal na tela e espera o usuário preencher
                    self.push_screen(SpotifyCredentialsModal(), salvar_e_continuar)

            else:
                # Se for YouTube, roda direto porque não precisa de chave
                executar_exportacao(None, None)

        # if event.button.id == "copy_btn":
        #     texto_completo = "\n".join(self.historico_download)
        #     self.copy_to_clipboard(texto_completo)
        #     self.notify("Log de downloads copiado!", title="Copiado")
        #     return

    def salvar_log_em_arquivo(self, prefixo: str, historico: list):
        """Salva a lista de histórico de logs em um arquivo txt."""
        if not historico:
            return

        texto_completo = "\n".join(historico)
        now_sp = datetime.now(tz=ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d_%H-%M-%S")

        if not os.path.isdir("./logs"): 
            os.mkdir("./logs")

        caminho_arquivo = f"./logs/{prefixo}-{now_sp}.txt"

        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            f.write(texto_completo)

        # Limpa o histórico após salvar para não duplicar no próximo clique
        historico.clear()

        self.call_from_thread(lambda: self.notify(f"Salvo: {caminho_arquivo}", title="Log Salvo"))

    @work(thread=True)
    def run_downloads_in_background(self, csv_path, music_path, workers):
        """Chama a rotina pesada do backend em uma thread separada."""
        self.backend.run(csv_path, music_path, workers)
        self.safe_log("[bold green]Processo finalizado![/]")

        self.salvar_log_em_arquivo("download", self.historico_download)

        # Reabilita o botão ao terminar
        btn1 = self.query_one("#start_btn")
        self.call_from_thread(lambda: setattr(btn1, "disabled", False))

    @work(thread=True)
    def run_exportation_in_background(self, exporter_instance, url, output_file_path):
        """Roda o extrator dinamicamente sem congelar a tela."""

        exporter_instance.gerar_csv(url, output_file_path)

        self.salvar_log_em_arquivo("exportacao", self.historico_export)

        btn = self.query_one("#start_exportation_btn")
        self.call_from_thread(lambda: setattr(btn, "disabled", False))
        self.call_from_thread(lambda: self.notify("Arquivo exportado com sucesso!", title="Sucesso"))
