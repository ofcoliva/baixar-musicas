# Dependências

Necessário yt-dlp e ffmpeg

comando para instalar yt-dlp
```powershell
pip freeze -r requirements.txt
```

comando para instalar ffmpeg
```powershell
winget install ffmpeg
```


Exemplo de uso para youtube
```powershell
python youtube_downloader.py "https://www.youtube.com/watch?v=NkMTKGM-efw&list=PLnmwNDHEorITxGoIhCdusczEXCNntYC5s" --processNumber 5 --musicPath "./yt_music"
```

Exemplo de uso para spotify

```powershell
python3 spotify_dl.py songs.csv --processNumber 6 --musicPath "./spotify_musics"
```