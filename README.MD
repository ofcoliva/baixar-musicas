# Baixar Musicas

Baixe suas playlists do YouTube ou Spotify de forma descomplicada.

# Aviso Legal (Disclaimer)
Este projeto foi desenvolvido estritamente para fins educacionais e de estudo. O código aqui disponibilizado não deve, sob nenhuma circunstância, ser utilizado para fins comerciais, obtenção de lucro ou qualquer atividade que viole os Termos de Serviço das plataformas envolvidas.

Isenção de Responsabilidade: Eu me isento totalmente de qualquer responsabilidade sobre como este software será utilizado. O uso desta ferramenta é de sua inteira responsabilidade, bem como quaisquer consequências ou danos decorrentes do seu uso indevido.

Uso com Moderação: Utilize este programa com moderação e responsabilidade. O excesso de requisições ou o uso inadequado pode ser detectado pelos serviços (como YouTube e Spotify), resultando em bloqueios de IP, restrições ou banimento definitivo da sua conta.

# Ferramentas utilizadas
* [Python](https://pypi.org/project/yt-dlp/?utm_source=https://github.com/ofcoliva)
* [FFMPEG](https://ffmpeg.org/?utm_source=https://github.com/ofcoliva)
* [pip](https://python.land/virtual-environments/installing-packages-with-pip?utm_source=https://github.com/ofcoliva) ou [uv](https://docs.astral.sh/uv/?utm_source=https://github.com/ofcoliva)
* [yt-dlp](https://pypi.org/project/yt-dlp/?utm_source=https://github.com/ofcoliva)
* [textual](https://textual.textualize.io/?utm_source=https://github.com/ofcoliva)
* [spotipy](https://spotipy.readthedocs.io/en/2.26.0/?utm_source=https://github.com/ofcoliva)
* [tzdata](https://pypi.org/project/tzdata/?utm_source=https://github.com/ofcoliva)

# Siga os passos abaixo para execução do programa.

## Clone ou baixe o repositório

```powershell
git clone https://github.com/ofcoliva/baixar-musicas
```

## Entre no diretório
```poweshell
cd baixar-musicas
```

## Instale o FFMPEG

Windows
```powershell
winget install ffmpeg
```

Linux
```bash
sudo apt install ffmpeg
```


## Instale o UV ou o gerênciador de pacotes Python de sua preferência

Instruções para instalar o uv disponível no site [astral.sh](https://docs.astral.sh/uv/getting-started/installation)


## Sincronizar Dependências
```bash
uv sync
```

*caso o venv ainda esteja desativado, utilize o comando abaixo*
```powershell
.\.venv\Scripts\activate
```

## Exporte os cookies do YouTube (recomendado)

O YouTube pode bloquear ou limitar as requisições ao exportar ou baixar músicas, gerando erros como *"Sign in to confirm you're not a bot"*. Para reduzir esses bloqueios, exporte os cookies da sua conta do YouTube para um arquivo `cookies.txt` na raiz do projeto.

O programa detecta esse arquivo automaticamente na raiz (mesma pasta do `main.py`).

### Como exportar com a extensão "Get cookies.txt LOCALLY"

1. Instale a extensão no seu navegador:
   * [Chrome / Edge](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   * [Firefox](https://addons.mozilla.org/en-US/firefox/addon/get-cookies-txt-locally)

2. Faça login na sua conta do YouTube no navegador.

3. Acesse [https://www.youtube.com](https://www.youtube.com) com a conta logada.

4. Clique no ícone da extensão e selecione **Export** (formato Netscape / `cookies.txt`).

5. Salve o arquivo baixado como **`cookies.txt`** na **raiz deste projeto**.

`cookies.txt` contém as credenciais da sua sessão do YouTube. **Não compartilhe** esse arquivo e **não faça commit** dele — ele já está listado no `.gitignore`.

## Executar aplicacao
```bash
python main.py
```

Logo após a execução do comando uma tela como a de baixo será exibida com parâmetros configurados por padrão.

![img1](./imgs/img1.svg)

# Otimização com concorrencia explicada em uma imagem

![img](./imgs/img2.svg)
