# YDownloader

[![GitHub Actions](https://github.com/your-repo/YDownloader/actions/workflows/build.yml/badge.svg)](https://github.com/your-repo/YDownloader/actions)

*_Elegant video downloading made simple_*  
*シンプルで洗練された動画ダウンロード体験*

---

## Overview / 概要

*_YDownloader is a sleek, GUI-based video downloader built with [Flet](https://flet.dev/). Seamlessly integrated with [yt-dlp](https://github.com/yt-dlp/yt-dlp), it lets you download videos by simply pasting a URL. Enjoy effortless updates and a modern interface._*

YDownloaderは、[Flet](https://flet.dev/) を使って構築された洗練されたGUI動画ダウンローダーです。URLを貼るだけで[yt-dlp](https://github.com/yt-dlp/yt-dlp)とのシームレスな連携により、簡単に動画をダウンロードできます。手間いらずのアップデートとモダンな操作性を提供します。

---

## Features / 特徴

- **Intuitive Interface / 直感的な操作性**  
  *_Paste a video URL and press `Enter` or click the search icon._*  
  動画URLを入力し、`Enter`キーまたは検索アイコンをクリックするだけで操作可能。

- **Multiline Input / 複数行入力**  
  *_Use `Shift + Enter` to add line breaks._*  
  `Shift + Enter`で改行ができます。

- **Seamless Updates / シームレスな更新**  
  *_Simply update yt-dlp by replacing the executable in the `external` folder._*  
  `external`フォルダ内の実行ファイルを置き換えるだけでyt-dlpを更新可能。

- **Automated Builds / 自動ビルド**  
  *_GitHub Actions automatically generate installers and patches._*  
  GitHub Actionsにより、インストーラーやパッチが自動生成されます。

---

## Installation / インストール方法

1. **Download / ダウンロード**  
   *_Get the installer from the [Releases](https://github.com/your-repo/YDownloader/releases) page._*  
   [Releases](https://github.com/your-repo/YDownloader/releases)からインストーラーを入手してください。

2. **Install / インストール**  
   *_Run the installer and follow the on-screen instructions._*  
   インストーラーを実行し、画面の指示に従ってインストールしてください。

3. **Launch / 起動**  
   *_Open YDownloader and paste a video URL to begin downloading._*  
   YDownloaderを起動し、動画URLを入力してダウンロードを開始してください。

4. **Update / 更新**  
   *_Replace the yt-dlp executable in the `external` folder as needed._*  
   `external`フォルダ内のyt-dlp実行ファイルを最新のものに置き換えてください。

---

## Usage / 使い方

- *_Paste the URL into the search bar and press `Enter` (or click the search icon) to load video details and start downloading._*  
  検索バーにURLを貼り付け、`Enter`キー（または検索アイコン）をクリックすると動画情報が表示され、ダウンロードが始まります。

- *_Updating is as simple as replacing the yt-dlp file in the `external` folder._*  
  更新は、`external`フォルダ内のyt-dlpファイルを置き換えるだけで完了します。

---

## Development / 開発

**Requirements / 必要条件**  
- Python 3.10+ (Python 3.10以上)  
- [Flet](https://flet.dev/)  
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

**Setup / セットアップ:**
```sh
git clone https://github.com/your-repo/YDownloader.git
cd YDownloader
pip install -r requirements.txt
python main.py
